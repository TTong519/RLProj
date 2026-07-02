"""Tests for RLlib training entrypoint (08-02) — unit level.

DIST-02, DIST-03.  Integration tests requiring real Ray are skipped when
``ray`` is not installed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def _rllib_available() -> bool:
    """True only when Ray + dm-tree are importable (Ray needs dm-tree at runtime)."""
    if __import__("importlib").util.find_spec("ray") is None:
        return False
    return __import__("importlib").util.find_spec("tree") is not None


# --------------------------------------------------------------------------- #
# GPU auto-configuration (already partially covered in test_rllib_env_registration)
# --------------------------------------------------------------------------- #


def test_multi_gpu_two_gpus():
    """Two GPUs → two remote learners, one GPU each."""
    import torch

    from surg_rl.rl.rllib.config import RllibConfig
    from surg_rl.rl.training import TrainingConfig

    with patch.object(torch.cuda, "device_count", return_value=2):
        rc = RllibConfig.from_training_config(TrainingConfig(), env_config={})
    assert rc.num_learners == 2
    assert rc.num_gpus_per_learner == 1.0


def test_single_gpu_local_learner():
    """One GPU → local learner for better throughput."""
    import torch

    from surg_rl.rl.rllib.config import RllibConfig
    from surg_rl.rl.training import TrainingConfig

    with patch.object(torch.cuda, "device_count", return_value=1):
        rc = RllibConfig.from_training_config(TrainingConfig(), env_config={})
    assert rc.num_learners == 0
    assert rc.num_gpus_per_learner == 1.0


def test_cpu_only_zero_gpus():
    """No GPU → CPU learners."""
    import torch

    from surg_rl.rl.rllib.config import RllibConfig
    from surg_rl.rl.training import TrainingConfig

    with patch.object(torch.cuda, "device_count", return_value=0):
        rc = RllibConfig.from_training_config(TrainingConfig(), env_config={})
    assert rc.num_learners == 0
    assert rc.num_gpus_per_learner == 0.0


# --------------------------------------------------------------------------- #
# Ray is installed checks — skip if ray not available
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _rllib_available(),
    reason="ray[rllib] / dm-tree not installed",
)
def test_train_rllib_rllib_config_builds():
    """``build_rllib_config`` returns an RLlib object when Ray is available."""
    from surg_rl.rl.rllib.config import RllibConfig

    rc = RllibConfig(algorithm="PPO")
    cfg = rc.build_rllib_config()
    assert cfg is not None
    # Is a PPOConfig instance
    assert "PPO" in type(cfg).__name__


@pytest.mark.skipif(
    not _rllib_available(),
    reason="ray[rllib] / dm-tree not installed",
)
def test_train_rllib_rllib_sac_builds():
    """``build_rllib_config`` works for SAC too."""
    from surg_rl.rl.rllib.config import RllibConfig

    rc = RllibConfig(algorithm="SAC")
    cfg = rc.build_rllib_config()
    assert cfg is not None
    assert "SAC" in type(cfg).__name__


@pytest.mark.skipif(
    not _rllib_available(),
    reason="ray[rllib] / dm-tree not installed",
)
class TestTrainRllibIntegration:
    """Integration tests for train_rllib() configuration pipeline."""

    def test_train_rllib_config_pipeline(self):
        """Full config pipeline: RllibConfig → build_rllib_config → training kwargs."""
        from surg_rl.rl.rllib.config import RllibConfig
        from surg_rl.rl.training import AlgorithmConfig, TrainingConfig

        tc = TrainingConfig(
            algorithm=AlgorithmConfig(name="PPO"),
            n_envs=2,
            total_timesteps=50000,
            scene_path="/tmp/test.json",
            seed=42,
        )

        rc = RllibConfig.from_training_config(tc, env_config={"foo": 1})
        assert rc.env_name == "surg-rl"
        assert rc.algorithm == "PPO"
        assert rc.env_config["foo"] == 1
        assert rc.env_config.get("scene_path") == "/tmp/test.json"
        assert rc.total_timesteps == 50000
        assert rc.seed == 42

    def test_rllib_config_stop_criteria(self):
        """build_stop_criteria() returns timestep-bounded dict."""
        from surg_rl.rl.rllib.config import RllibConfig

        rc = RllibConfig(total_timesteps=100000)
        stop = rc.build_stop_criteria()
        assert stop["num_env_steps_sampled_lifetime"] == 100000

    def test_rllib_unsupported_algorithm_raises(self):
        """_resolve_algo_class raises ValueError for unknown algorithm."""
        from surg_rl.rl.rllib.train import _resolve_algo_class

        with pytest.raises(ValueError, match="Unsupported algorithm"):
            _resolve_algo_class("A3C")
