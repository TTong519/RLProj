"""SuperSuit wrappers for PettingZoo -> SB3 conversion (D-06)."""

from stable_baselines3.common.vec_env import VecEnv

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

_SUPERSUT_AVAILABLE = False
try:
    from supersuit import (  # type: ignore[import-untyped]
        concat_vec_envs_v1,
        pettingzoo_env_to_vec_env_v1,
    )

    _SUPERSUT_AVAILABLE = True
except ImportError:
    pass


def wrap_for_sb3(env, num_envs: int = 1) -> VecEnv:
    """Convert PettingZoo ParallelEnv to SB3-compatible VecEnv.

    D-06: Canonical pipeline: pettingzoo_env_to_vec_env_v1 -> concat_vec_envs_v1.

    Args:
        env: PettingZoo ParallelEnv instance.
        num_envs: Number of parallel environments (>=1).

    Returns:
        SB3-compatible VecEnv.

    Raises:
        ImportError: If supersuit is not installed.
    """
    if not _SUPERSUT_AVAILABLE:
        raise ImportError(
            "supersuit is required for SB3-compatible MARL training. "
            "Install: pip install surg-rl[marl]"
        )

    vec_env = pettingzoo_env_to_vec_env_v1(env)
    if num_envs > 1:
        vec_env = concat_vec_envs_v1(vec_env, num_vec_envs=num_envs, num_cpus=1)
    return vec_env
