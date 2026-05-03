"""Ray Tune integration for hyperparameter search.

Provides :func:`build_tune_search_space` and :func:`run_tune_experiment`.

Example::

    base = RllibConfig(total_timesteps=50_000)
    space = build_tune_search_space(base, scene_paths=["a.json", "b.json"])
    results = run_tune_experiment(base, space, num_samples=3)
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from surg_rl.rl.rllib import _check_rllib
from surg_rl.rl.rllib.config import RllibConfig
from surg_rl.rl.rllib.train import train_rllib
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


# Lazily import tune objects so tests without Ray can still import this module.
def _tune():
    from ray import tune as t
    return t


def build_tune_search_space(
    base_config: RllibConfig | None = None,
    *,
    scene_paths: list[str] | None = None,
    simulator_types: list[str] | None = None,
    algorithms: list[str] | None = None,
    lr_range: tuple[float, float] = (1e-5, 1e-3),
    gamma_range: tuple[float, float] = (0.95, 0.999),
    reward_weight_ranges: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Return a flat ``param_space`` dict suitable for ``tune.Tuner``.

    Keys map directly to :class:`RllibConfig` fields (or ``env_config``
    sub-keys).  The search space is intentionally flat so that Tune's
    schedulers can mutate individual hyperparameters without replacing nested
    structs wholesale.
    """
    t = _tune()
    space: dict[str, Any] = {}

    if scene_paths:
        space["env_config"] = {"scene_path": t.choice(scene_paths)}
    if simulator_types:
        space.setdefault("env_config", {}).update(
            {"simulator_type": t.choice(simulator_types)}
        )
    if algorithms:
        space["algorithm"] = t.choice(algorithms)

    space["lr"] = t.loguniform(*lr_range)
    space["gamma"] = t.uniform(*gamma_range)

    algo = base_config.algorithm.upper() if base_config and base_config.algorithm else "PPO"
    if algo == "PPO":
        space["clip_param"] = t.uniform(0.05, 0.3)
        space["entropy_coeff"] = t.loguniform(1e-4, 0.1)
    elif algo == "SAC":
        space["tau"] = t.uniform(0.001, 0.02)

    if reward_weight_ranges:
        space.setdefault("env_config", {}).update(
            {
                "reward_config": {
                    name: t.uniform(low, high)
                    for name, (low, high) in reward_weight_ranges.items()
                }
            }
        )

    return space


def run_tune_experiment(
    base_config: RllibConfig,
    param_space: dict[str, Any] | None = None,
    *,
    num_samples: int = 3,
    max_training_iterations: int = 10,
    metric: str = "env_runners/episode_return_mean",
    mode: str = "max",
    scheduler: str = "asha",
    name: str = "surg_rl_tune",
    local_mode: bool = True,
) -> Any:
    """Run a Ray Tune experiment with RLlib.

    Parameters
    ----------
    base_config : RllibConfig
        Starting config — non-sampled fields come from here.
    param_space : dict | None
        Search space returned by :func:`build_tune_search_space`.
    num_samples : int
        Number of trials (must be ≥ 3 for DIST-04).
    max_training_iterations : int
        Upper bound on iterations per trial.
    metric : str
        Metric reported by RLlib to optimise.
    mode : str
        ``"min"`` or ``"max"``.
    scheduler : str
        ``"asha"`` or ``"pbt"``.
    name : str
        Experiment name for Tune logs.
    local_mode : bool
        Whether to run Ray in local mode (single-process).

    Returns:
        A :class:`ray.tune.ResultGrid`.
    """
    _check_rllib()
    t = _tune()

    param_space = param_space or {}

    def _trainable(tune_cfg: dict[str, Any]) -> None:
        """Inner trainable — sampled flat config applied to *base_config*."""
        import copy

        flat_overrides: dict[str, Any] = {}
        env_overrides: dict[str, Any] = {}
        for key, value in tune_cfg.items():
            if key == "env_config":
                env_overrides = value
            else:
                flat_overrides[key] = value

        merged_env = copy.deepcopy(base_config.env_config)
        merged_env.update(env_overrides)

        new_cfg = dataclasses.replace(
            base_config,
            env_config=merged_env,
            **flat_overrides,
        )
        train_rllib(new_cfg, local_mode=local_mode)

    # Scheduler
    if scheduler == "asha":
        from ray.tune.schedulers import ASHAScheduler

        sched = ASHAScheduler(
            metric=metric,
            mode=mode,
            max_t=max_training_iterations,
            grace_period=1,
            reduction_factor=2,
        )
    elif scheduler == "pbt":
        from ray.tune.schedulers import PopulationBasedTraining

        sched = PopulationBasedTraining(
            metric=metric,
            mode=mode,
            perturbation_interval=5,
            hyperparam_mutations={"lr": t.loguniform(1e-5, 1e-3)},
        )
    else:
        sched = None

    tuner = t.Tuner(
        _trainable,
        param_space=param_space,
        tune_config=t.TuneConfig(
            metric=metric,
            mode=mode,
            num_samples=num_samples,
            scheduler=sched,
        ),
        run_config=t.RunConfig(
            name=name,
            stop={"training_iteration": max_training_iterations},
        ),
    )

    results = tuner.fit()

    best = results.get_best_result()
    if best and hasattr(best, "metrics"):
        best_reward = best.metrics.get(metric, float("nan"))
        logger.info(
            "Best trial: %s | %s=%.2f",
            best.path if hasattr(best, "path") else "?",
            metric,
            best_reward,
        )
        best_cfg_path = Path(base_config.save_dir or "rllib_results") / "best_config.json"
        best_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        best_cfg_path.write_text(
            json.dumps(best.config, indent=2, default=str)
        )
    else:
        logger.warning("No best result returned from Tune")

    return results
