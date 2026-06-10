"""Tests for RLlib environment registration (08-01).

DIST-01, DIST-06
"""

import pytest


# Ensure we can import without Ray installed
@pytest.fixture(autouse=True)
def _skip_if_ray_required():
    """These tests mock Ray or test import paths."""
    pass


def test_make_surgical_env_basic(monkeypatch):
    """Create a SurgicalEnv via the RLlib factory (no actual scene load)."""
    from surg_rl.rl.rllib.env_wrapper import make_surgical_env

    cfg = {"simulator_type": "pybullet", "max_episode_steps": 100}
    env = make_surgical_env(cfg)

    assert env.render_mode is None  # forced headless
    assert env.config.simulator_type == "pybullet"
    assert env.config.max_episode_steps == 100


def test_make_surgical_env_empty_config():
    """Factory tolerates None/empty config."""
    from surg_rl.rl.rllib.env_wrapper import make_surgical_env

    env = make_surgical_env(None)
    assert env.render_mode is None
    assert env.config.simulator_type == "mujoco"  # default


def test_make_surgical_env_render_mode_forced():
    """Even if user passes render_mode='human', it is forced to None."""
    from surg_rl.rl.rllib.env_wrapper import make_surgical_env

    env = make_surgical_env({"render_mode": "human"})
    assert env.render_mode is None


def test_rllib_config_defaults():
    """RllibConfig has sensible defaults."""
    from surg_rl.rl.rllib.config import RllibConfig

    rc = RllibConfig()
    assert rc.env_name == "surg-rl"
    assert rc.algorithm == "PPO"
    assert rc.framework == "torch"
    assert rc.num_learners == 0
    assert rc.num_gpus_per_learner == 0.0


def test_rllib_config_from_training_config():
    """Factory conversion from TrainingConfig preserves algorithm fields."""
    from surg_rl.rl.rllib.config import RllibConfig
    from surg_rl.rl.training import AlgorithmConfig, TrainingConfig

    algo = AlgorithmConfig(
        name="SAC",
        learning_rate=1e-3,
        gamma=0.98,
        n_steps=512,
    )
    tc = TrainingConfig(
        scene_path="scenes/test.json",
        algorithm=algo,
        n_envs=4,
        seed=42,
        log_dir="logs/test",
        save_freq=10_000,
    )

    rc = RllibConfig.from_training_config(tc)

    assert rc.algorithm == "SAC"
    assert rc.lr == 1e-3
    assert rc.gamma == 0.98
    assert rc.env_config["scene_path"] == "scenes/test.json"
    assert rc.env_config["seed"] == 42
    assert rc.total_timesteps == tc.total_timesteps
    assert rc.num_env_runners == 3  # n_envs - 1


def test_rllib_config_from_training_config_gpu_count():
    """GPU count auto-detected (we mock it to 1 here)."""
    from unittest.mock import patch

    from surg_rl.rl.rllib.config import RllibConfig
    from surg_rl.rl.training import TrainingConfig

    with patch("torch.cuda.device_count", return_value=1):
        rc = RllibConfig.from_training_config(TrainingConfig())
        assert rc.num_learners == 0
        assert rc.num_gpus_per_learner == 1.0

    with patch("torch.cuda.device_count", return_value=0):
        rc = RllibConfig.from_training_config(TrainingConfig())
        assert rc.num_learners == 0
        assert rc.num_gpus_per_learner == 0.0


def test_rllib_config_build_stop_criteria():
    """Stop criteria maps total_timesteps correctly."""
    from surg_rl.rl.rllib.config import RllibConfig

    rc = RllibConfig(total_timesteps=500_000)
    assert rc.build_stop_criteria()["num_env_steps_sampled_lifetime"] == 500_000


def test_rllib_package_import_no_ray():
    """Importing the package does not require Ray installed."""
    # RllibConfig import was already tested above
    from surg_rl.rl.rllib import RllibConfig

    assert RllibConfig is not None


def test_rllib_lazy_fail_without_ray():
    """Calling ray-dependent functions gives a helpful ImportError."""
    import surg_rl.rl.rllib as rllib_mod

    original_ray = rllib_mod.ray
    try:
        rllib_mod.ray = None
        with pytest.raises(ImportError, match="Ray/RLlib is not installed"):
            rllib_mod._check_rllib()
    finally:
        rllib_mod.ray = original_ray
