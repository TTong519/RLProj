"""Multi-agent RL — PettingZoo ParallelEnv + SuperSuit SB3 wrappers.

Optional dependencies: pettingzoo >= 1.24.0, supersuit >= 3.9.0
Install: pip install surg-rl[marl]
"""

from surg_rl.utils.lazy_imports import LazyImport

PETTINGZOO = LazyImport("pettingzoo", "marl")

from .multi_agent_env import MultiAgentSurgicalEnv  # noqa: E402
from .training import MultiAgentTrainingManager  # noqa: E402
from .wrappers import wrap_for_sb3  # noqa: E402

__all__ = [
    "PETTINGZOO",
    "MultiAgentSurgicalEnv",
    "wrap_for_sb3",
    "MultiAgentTrainingManager",
]
