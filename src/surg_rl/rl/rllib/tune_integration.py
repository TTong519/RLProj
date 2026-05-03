"""Ray Tune integration for hyperparameter search (placeholder — completed in 08-03)."""

from typing import Any

from surg_rl.rl.rllib import _check_rllib


def build_tune_search_space(
    scene_definitions: list[str] | None = None,
    reward_weights: dict[str, tuple[float, float, int]] | None = None,
) -> dict[str, Any]:
    """Build a Tune ``param_space`` dict from project configs.

    Args:
        scene_definitions: List of scene JSON paths to sweep over.
        reward_weights: Mapping ``reward_name → (min, max, n_samples)``.

    Returns:
        A dict suitable for ``tune.Tuner(param_space=...)``.
    """
    _check_rllib()
    raise NotImplementedError("Implemented in 08-03")


def run_tune_experiment(
    rllib_config: "RllibConfig",
    search_space: dict[str, Any] | None = None,
    scheduler: Any | None = None,
    num_samples: int = 3,
) -> Any:
    """Run a Ray Tune experiment with RLlib.

    Returns:
        A :class:`ray.tune.ResultGrid`.
    """
    _check_rllib()
    raise NotImplementedError("Implemented in 08-03")
