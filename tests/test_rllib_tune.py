"""Tests for Tune integration (08-03) — unit level.

DIST-04.  All tests require Ray Tune at import time.
"""

import pytest

pytest.importorskip("ray", reason="ray[rllib] not installed")

try:
    from ray import tune
except ImportError:
    tune = None  # type: ignore

from surg_rl.rl.rllib.config import RllibConfig
from surg_rl.rl.rllib.tune_integration import build_tune_search_space

# --------------------------------------------------------------------------- #
# build_tune_search_space unit tests (no Ray required)
# --------------------------------------------------------------------------- #


def test_build_tune_search_space_basic():

    base = RllibConfig(algorithm="PPO")
    space = build_tune_search_space(
        base,
        scene_paths=["a.json", "b.json"],
        simulator_types=["mujoco", "pybullet"],
        algorithms=["PPO", "SAC"],
    )
    assert "env_config" in space
    assert "scene_path" in space["env_config"]
    assert "simulator_type" in space["env_config"]
    assert "algorithm" in space
    assert "lr" in space
    assert "gamma" in space


def test_build_tune_search_space_ppo_only():

    base = RllibConfig(algorithm="PPO")
    space = build_tune_search_space(
        base,
        lr_range=(1e-5, 1e-3),
        gamma_range=(0.95, 0.999),
    )
    assert "clip_param" in space
    assert "entropy_coeff" in space
    assert "tau" not in space  # SAC-only


def test_build_tune_search_space_sac_only():

    base = RllibConfig(algorithm="SAC")
    space = build_tune_search_space(
        base,
        lr_range=(1e-5, 1e-3),
        gamma_range=(0.95, 0.999),
    )
    assert "tau" in space
    assert "clip_param" not in space
    assert "entropy_coeff" not in space


def test_build_tune_search_space_reward_weights():

    base = RllibConfig(algorithm="PPO")
    space = build_tune_search_space(
        base,
        reward_weight_ranges={"distance_weight": (0.1, 2.0)},
    )
    assert "env_config" in space
    assert "reward_config" in space["env_config"]
    assert "distance_weight" in space["env_config"]["reward_config"]


# --------------------------------------------------------------------------- #
# Ray is installed checks
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("ray") is None,
    reason="ray[rllib] not installed",
)
def test_build_tune_search_space_returns_tune_objects():
    from ray.tune.search.sample import Categorical

    base = RllibConfig(algorithm="PPO")
    space = build_tune_search_space(base, scene_paths=["a.json"])
    assert isinstance(space["env_config"]["scene_path"], Categorical)
