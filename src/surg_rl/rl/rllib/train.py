"""RLlib training entrypoint.

Provides :func:`train_rllib` which initialises Ray, registers the environment,
builds the RLlib algorithm, runs the training loop, and shuts down cleanly.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from surg_rl.rl.rllib import _check_rllib
from surg_rl.rl.rllib.config import RllibConfig
from surg_rl.rl.rllib.env_wrapper import register_surgical_env
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


def train_rllib(
    config: RllibConfig,
    stop_criteria: dict[str, Any] | None = None,
    *,
    local_mode: bool = False,
    log_dir: str | None = None,
    checkpoint_dir: str | None = None,
    callbacks: list | None = None,
) -> str:
    """Train a policy with Ray RLlib.

    The workflow is intentionally sequential — Ray handles the
    distributed parts internally through its :class:`EnvRunner`
    abstractions.  This function stays lightweight: init → build → loop →
    cleanup.

    Args:
        config: Populated :class:`RllibConfig`.
        stop_criteria: Optional ``tune.run`` stop dict.  Ignored when
            ``total_timesteps`` on *config* is non-zero (the default).
        local_mode: If *True*, Ray runs in single-process local mode.  Useful
            for debugging but slower for actual training.
        log_dir: Directory for RLlib logs.  Defaults to
            :data:`~RllibConfig.save_dir`.
        checkpoint_dir: Directory for checkpoints.  Defaults to *log_dir*.
        callbacks: Additional RLlib callbacks (e.g. for curriculum integration).

    Returns:
        Path to the final checkpoint directory (or *checkpoint_dir* itself).
    """
    _check_rllib()
    import ray

    register_surgical_env()

    save_dir = Path(checkpoint_dir or log_dir or config.save_dir or "rllib_results")
    save_dir.mkdir(parents=True, exist_ok=True)

    if not ray.is_initialized():
        ray_address = os.environ.get("RAY_ADDRESS", "auto")
        ray.init(
            address=ray_address,
            local_mode=local_mode,
            ignore_reinit_error=True,
        )
        logger.info("Ray connected: address=%s", ray_address)
        resources = ray.available_resources()
        logger.info(
            "Ray initialised — CPUs=%s GPUs=%s",
            resources.get("CPU"),
            resources.get("GPU"),
        )

    rllib_cfg = config.build_rllib_config()

    algo_cls = _resolve_algo_class(config.algorithm)
    algo = (
        rllib_cfg.build_algo() if hasattr(rllib_cfg, "build_algo") else algo_cls(config=rllib_cfg)
    )

    if callbacks:
        for cb in callbacks:
            algo.add_callback(cb)

    stop = stop_criteria or config.build_stop_criteria()
    lifetime_key = "num_env_steps_sampled_lifetime"
    target = stop.get(lifetime_key, config.total_timesteps)

    timesteps_done = 0
    checkpoint_path: str | None = None
    start_time = time.time()

    try:
        while timesteps_done < target:
            result = algo.train()
            timesteps_done = int(result.get(lifetime_key, 0))
            reward = result.get("env_runners", {}).get("episode_return_mean", float("nan"))
            logger.info(
                "Iter %s | steps %d/%d | reward=%.2f",
                result.get("training_iteration", "?"),
                timesteps_done,
                target,
                reward,
            )

            if config.checkpoint_freq > 0 and timesteps_done >= (
                (timesteps_done // config.checkpoint_freq) * config.checkpoint_freq
            ):
                ckpt = algo.save_to_path(str(save_dir / f"checkpoint_{timesteps_done}"))
                logger.info("Checkpoint: %s", ckpt.path if hasattr(ckpt, "path") else ckpt)

        # Final checkpoint
        final_ckpt = algo.save_to_path(str(save_dir / "final"))
        checkpoint_path = str(final_ckpt.path if hasattr(final_ckpt, "path") else final_ckpt)
        logger.info("Final checkpoint saved to %s", checkpoint_path)

    except KeyboardInterrupt:
        logger.warning("Training interrupted by user")
        interrupted_ckpt = algo.save_to_path(str(save_dir / "interrupted"))
        checkpoint_path = str(
            interrupted_ckpt.path if hasattr(interrupted_ckpt, "path") else interrupted_ckpt
        )
        raise
    finally:
        if hasattr(algo, "stop"):
            algo.stop()
        if ray.is_initialized():
            ray.shutdown()
        elapsed = time.time() - start_time
        logger.info("Ray shut down after %.1f s", elapsed)

    return str(checkpoint_path or save_dir)


def _resolve_algo_class(algorithm: str):
    """Return the RLlib algorithm class for *algorithm* name."""
    algorithm = algorithm.upper()
    if algorithm == "PPO":
        from ray.rllib.algorithms.ppo import PPO

        return PPO
    if algorithm == "SAC":
        from ray.rllib.algorithms.sac import SAC

        return SAC
    raise ValueError(f"Unsupported algorithm: {algorithm!r}")
