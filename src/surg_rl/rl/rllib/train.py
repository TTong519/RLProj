"""RLlib training entrypoint (placeholder — completed in 08-02)."""

from __future__ import annotations

from typing import Any

from surg_rl.rl.rllib import _check_rllib
from surg_rl.rl.rllib.config import RllibConfig


def train_rllib(
    config: RllibConfig,
    stop_criteria: dict[str, Any] | None = None,
    *,
    local_mode: bool = False,
    log_dir: str | None = None,
    checkpoint_dir: str | None = None,
    callbacks: list | None = None,
) -> "ray.rllib.algorithms.algorithm.Algorithm":
    """Train a policy with Ray RLlib.

    Args:
        config: Populated :class:`RllibConfig`.
        stop_criteria: ``tune.run`` stop dict (e.g. ``{"training_iteration": 100}``).
        local_mode: Run Ray in local mode (debugging only).
        log_dir: Directory for RLlib results.
        checkpoint_dir: Directory to write checkpoints.
        callbacks: Additional Tune/Train callbacks.

    Returns:
        Trained RLlib :class:`~ray.rllib.algorithms.algorithm.Algorithm`.
    """
    _check_rllib()
    import ray
    from ray.rllib.algorithms.ppo import PPOConfig
    from ray.rllib.algorithms.sac import SACConfig  # noqa: F401
    raise NotImplementedError("train_rllib is implemented in 08-02")
