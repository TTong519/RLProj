"""Multi-agent RL — PettingZoo ParallelEnv + SuperSuit SB3 wrappers.

Optional dependencies: pettingzoo >= 1.24.0, supersuit >= 3.9.0
Install: pip install surg-rl[marl]
"""

from surg_rl.utils.lazy_imports import LazyImport

PETTINGZOO = LazyImport("pettingzoo", "marl")

__all__ = ["PETTINGZOO"]
