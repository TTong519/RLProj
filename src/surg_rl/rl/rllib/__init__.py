"""Ray RLlib support for surgical robotics RL training.

This subpackage provides Ray RLlib integration for distributed
reinforcement learning training. It is an optional extra — install
with ``pip install \"surg-rl[distributed]\"``.

Example::

   >>> from surg_rl.rl.rllib import RllibConfig, train_rllib
   >>> cfg = RllibConfig.from_training_config(TrainingConfig())
   >>> train_rllib(cfg)
"""

try:
    import ray
    from ray.tune.registry import register_env
except ImportError:  # pragma: no cover
    ray = None  # type: ignore[assignment]
    register_env = None  # type: ignore[assignment]


def _check_rllib():
    if ray is None:
        raise ImportError(
            "Ray/RLlib is not installed. "
            'Install with: pip install "surg-rl[distributed]"'
        )


from .config import RllibConfig
from .env_wrapper import make_surgical_env, register_surgical_env
from .train import train_rllib
from .tune_integration import build_tune_search_space, run_tune_experiment
from .checkpoint_utils import (
    inspect_rllib_checkpoint,
    inspect_sb3_checkpoint,
    compare_checkpoints,
)

__all__ = [
    "RllibConfig",
    "make_surgical_env",
    "register_surgical_env",
    "train_rllib",
    "build_tune_search_space",
    "run_tune_experiment",
    "inspect_rllib_checkpoint",
    "inspect_sb3_checkpoint",
    "compare_checkpoints",
];
