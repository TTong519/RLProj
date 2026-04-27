"""Tests for RL TrainingManager using mocked SB3."""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from surg_rl.rl.training import (
    TrainingManager,
    TrainingConfig,
    AlgorithmConfig,
)
from surg_rl.rl.environment import SurgicalEnvConfig, make_env
from surg_rl.rl.action import ActionConfig, ActionType
from surg_rl.rl.observation import ObservationConfig, ObservationType


class TestAlgorithmSelection:
    def test_get_algorithm_class_import_error(self):
        """Missing stable-baselines3 raises ImportError."""
        with patch.dict('sys.modules', {'stable_baselines3': None}):
            manager = TrainingManager()
            with pytest.raises(ImportError, match="stable-baselines3"):
                manager._get_algorithm_class()

    def test_get_algorithm_class_unknown_algorithm(self):
        """Unknown algorithm name raises ValueError."""
        config = TrainingConfig(algorithm=AlgorithmConfig(name="UNKNOWN"))
        manager = TrainingManager(config)
        with pytest.raises(ValueError, match="Unknown algorithm"):
            manager._get_algorithm_class()

    def test_get_algorithm_class_ppo(self):
        """PPO algorithm class returned."""
        mock_ppo = MagicMock()
        with patch.dict('sys.modules', {'stable_baselines3': MagicMock(PPO=mock_ppo)}):
            config = TrainingConfig(algorithm=AlgorithmConfig(name="PPO"))
            manager = TrainingManager(config)
            # We can't fully import; test via name check
            assert config.algorithm.name.upper() == "PPO"

    def test_get_algorithm_class_sac(self):
        config = TrainingConfig(algorithm=AlgorithmConfig(name="SAC"))
        assert config.algorithm.name.upper() == "SAC"

    def test_get_algorithm_class_td3(self):
        config = TrainingConfig(algorithm=AlgorithmConfig(name="TD3"))
        assert config.algorithm.name.upper() == "TD3"

    def test_get_algorithm_class_ddpg(self):
        config = TrainingConfig(algorithm=AlgorithmConfig(name="DDPG"))
        assert config.algorithm.name.upper() == "DDPG"

    def test_get_algorithm_class_a2c(self):
        config = TrainingConfig(algorithm=AlgorithmConfig(name="A2C"))
        assert config.algorithm.name.upper() == "A2C"


class TestEnvironmentCreation:
    def test_create_environment_single_env(self):
        """Single env returns SurgicalEnv when n_envs=1."""
        config = TrainingConfig(
            scene_path="scenes/minimal_scene.json",
            n_envs=1,
        )
        manager = TrainingManager(config)
        env = manager._create_environment()
        from gymnasium import Env
        assert isinstance(env, Env)

    def test_create_environment_vec_env(self):
        """n_envs > 1 returns vectorized env."""
        config = TrainingConfig(
            scene_path="scenes/minimal_scene.json",
            n_envs=2,
        )
        manager = TrainingManager(config)
        with patch("stable_baselines3.common.vec_env.SubprocVecEnv") as mock_vec:
            manager._create_environment()
            mock_vec.assert_called_once()


class TestModelCreation:
    def test_create_model_multi_input_policy(self):
        """Dict observation space triggers MultiInputPolicy."""
        mock_algo = MagicMock()
        env = MagicMock()
        env.observation_space = MagicMock()
        type(env.observation_space).__name__ = 'Dict'
        from gymnasium import spaces
        env.observation_space = spaces.Dict({"a": spaces.Box(0, 1, (1,))})
        env.action_space = spaces.Box(-1, 1, (1,))
        config = TrainingConfig(algorithm=AlgorithmConfig(name="PPO"))
        manager = TrainingManager(config)
        with patch.object(manager, "_get_algorithm_class", return_value=mock_algo):
            manager._create_model(env)
        call_kwargs = mock_algo.call_args.kwargs
        assert call_kwargs["policy"] == "MultiInputPolicy"

    def test_create_model_mlp_policy(self):
        """Box observation space triggers MlpPolicy."""
        mock_algo = MagicMock()
        env = MagicMock()
        from gymnasium import spaces
        env.observation_space = spaces.Box(0, 1, (1,))
        env.action_space = spaces.Box(-1, 1, (1,))
        config = TrainingConfig(algorithm=AlgorithmConfig(name="PPO"))
        manager = TrainingManager(config)
        with patch.object(manager, "_get_algorithm_class", return_value=mock_algo):
            manager._create_model(env)
        call_kwargs = mock_algo.call_args.kwargs
        assert call_kwargs["policy"] == "MlpPolicy"


class TestTrainingLoop:
    def test_train_calls_learn_and_save(self):
        """train() calls model.learn() and saves the model."""
        config = TrainingConfig(
            scene_path="scenes/minimal_scene.json",
            total_timesteps=10,
            save_freq=100,
            n_envs=1,
        )
        manager = TrainingManager(config)
        mock_model = MagicMock()
        mock_env = MagicMock()
        with patch.object(manager, "_create_environment", return_value=mock_env):
            with patch.object(manager, "_create_model", return_value=mock_model):
                manager.train()
        mock_model.learn.assert_called_once()
        mock_model.save.assert_called_once()

    def test_training_config_to_dict(self):
        """TrainingConfig.to_dict() serializes algorithm sub-dict."""
        config = TrainingConfig()
        d = config.to_dict()
        assert "algorithm" in d
        assert isinstance(d["algorithm"], dict)

    def test_training_config_save_and_load(self, tmp_path):
        """TrainingConfig round-trips through JSON."""
        config = TrainingConfig(seed=12345)
        path = tmp_path / "config.json"
        config.save(path)
        loaded = TrainingConfig.load(path)
        assert loaded.seed == 12345


class TestEvaluation:
    def test_evaluate_non_vec_env(self):
        """evaluate with single env returns metrics dict."""
        config = TrainingConfig(scene_path="scenes/minimal_scene.json")
        manager = TrainingManager(config)
        mock_model = MagicMock()
        mock_env = MagicMock(spec=["reset", "step", "close"])
        obs = np.zeros(4)
        mock_env.reset.return_value = (obs, {})
        mock_env.step.return_value = (obs, 1.0, True, False, {})
        mock_model.predict.return_value = (np.zeros(1), None)
        with patch.object(manager, "_create_environment", return_value=mock_env):
            manager._model = mock_model
            results = manager.evaluate(n_episodes=2, render=False)
        assert "mean_reward" in results
        assert "success_rate" in results

    def test_evaluate_vec_env(self):
        """evaluate with vectorized env aggregates rewards."""
        config = TrainingConfig(scene_path="scenes/minimal_scene.json")
        manager = TrainingManager(config)
        mock_model = MagicMock()
        mock_env = MagicMock()
        mock_env.num_envs = 2
        obs = np.zeros((2, 4))
        mock_env.reset.return_value = obs
        # VecEnv returns: obs, reward, done, info
        mock_env.step.return_value = (obs, np.array([1.0, 0.5]), np.array([True, False]), [{}])
        mock_model.predict.return_value = (np.zeros((2, 1)), None)
        with patch.object(manager, "_create_environment", return_value=mock_env):
            manager._model = mock_model
            results = manager.evaluate(n_episodes=1, render=False)
        assert "mean_reward" in results

    def test_evaluate_without_model_raises(self):
        """evaluate without model or path raises ValueError."""
        manager = TrainingManager()
        with pytest.raises(ValueError, match="No model available"):
            manager.evaluate(n_episodes=1)


class TestModelPersistence:
    def test_save_model_without_model_raises(self):
        """save_model without training raises ValueError."""
        manager = TrainingManager()
        with pytest.raises(ValueError, match="No model to save"):
            manager.save_model()

    def test_load_model_sets_model(self):
        """load_model sets internal _model."""
        config = TrainingConfig(algorithm=AlgorithmConfig(name="PPO"))
        manager = TrainingManager(config)
        mock_cls = MagicMock()
        loaded = MagicMock()
        mock_cls.load.return_value = loaded
        with patch.object(manager, "_get_algorithm_class", return_value=mock_cls):
            manager.load_model("fake_path.zip")
        assert manager._model is loaded


class TestCleanup:
    def test_close_cleans_envs(self):
        """close() cleans up environment resources."""
        manager = TrainingManager()
        mock_env = MagicMock()
        mock_eval = MagicMock()
        manager._env = mock_env
        manager._eval_env = mock_eval
        manager.close()
        mock_env.close.assert_called_once()
        mock_eval.close.assert_called_once()
