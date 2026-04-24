"""Tests for the RL training module.

Tests cover observation spaces, action spaces, reward functions,
the Gymnasium environment wrapper, training configuration, and callbacks.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from surg_rl.rl.observation import (
    ObservationBuilder,
    ObservationConfig,
    ObservationSpec,
    ObservationType,
    JOINT_POSITIONS_SPEC,
    JOINT_VELOCITIES_SPEC,
    ENDEFFECTOR_POS_SPEC,
    FORCE_TORQUE_SPEC,
    TARGET_POS_SPEC,
    DISTANCE_TO_TARGET_SPEC,
)
from surg_rl.rl.action import (
    ActionBuilder,
    ActionConfig,
    ActionScaling,
    ActionSpec,
    ActionType,
    GRIPPER_SPEC,
)
from surg_rl.rl.rewards import (
    BaseRewardFunction,
    CollisionPenalty,
    CompositeReward,
    DistanceReward,
    OrientationReward,
    ActionPenalty,
    TimePenalty,
    RewardConfig,
    RewardResult,
    RewardType,
    SuccessReward,
    create_default_reward,
)
from surg_rl.rl.environment import (
    SurgicalEnv,
    SurgicalEnvConfig,
    make_env,
    make_vec_env,
)
from surg_rl.rl.training import (
    AlgorithmConfig,
    TrainingConfig,
    TrainingManager,
)
from surg_rl.rl.callbacks import (
    CheckpointCallback,
    TrainingProgressCallback,
    EvaluationCallback,
    TensorBoardCallback,
)


# ============================================================================
# Observation Tests
# ============================================================================


class TestObservationType:
    """Tests for ObservationType enum."""

    def test_observation_types_exist(self):
        """Test that all observation types are defined."""
        assert ObservationType.JOINT_POSITIONS == "joint_positions"
        assert ObservationType.JOINT_VELOCITIES == "joint_velocities"
        assert ObservationType.ENDEFFECTOR_POS == "endeffector_pos"
        assert ObservationType.FORCE_TORQUE == "force_torque"
        assert ObservationType.RGB_IMAGE == "rgb_image"
        assert ObservationType.DISTANCE_TO_TARGET == "distance_to_target"

    def test_all_spec_types_are_valid(self):
        """Test that all default specs reference valid observation types."""
        specs = [
            JOINT_POSITIONS_SPEC,
            JOINT_VELOCITIES_SPEC,
            ENDEFFECTOR_POS_SPEC,
            FORCE_TORQUE_SPEC,
            TARGET_POS_SPEC,
            DISTANCE_TO_TARGET_SPEC,
        ]
        for spec in specs:
            assert isinstance(spec.obs_type, ObservationType)


class TestObservationSpec:
    """Tests for ObservationSpec."""

    def test_spec_creation(self):
        """Test creating an observation spec."""
        spec = ObservationSpec(
            name="test_obs",
            obs_type=ObservationType.JOINT_POSITIONS,
            shape=(7,),
            low=-np.pi * np.ones(7),
            high=np.pi * np.ones(7),
        )
        assert spec.name == "test_obs"
        assert spec.shape == (7,)
        assert spec.normalize is False

    def test_get_space(self):
        """Test getting a Gymnasium space from a spec."""
        spec = ObservationSpec(
            name="test",
            obs_type=ObservationType.JOINT_POSITIONS,
            shape=(3,),
            low=-np.ones(3),
            high=np.ones(3),
        )
        space = spec.get_space()
        assert space.shape == (3,)
        assert space.low[0] == -1.0
        assert space.high[0] == 1.0

    def test_get_space_unbounded(self):
        """Test getting an unbounded space from a spec without bounds."""
        spec = ObservationSpec(
            name="test",
            obs_type=ObservationType.CUSTOM,
            shape=(5,),
        )
        space = spec.get_space()
        assert space.shape == (5,)
        assert np.isinf(space.low[0])
        assert np.isinf(space.high[0])


class TestObservationBuilder:
    """Tests for ObservationBuilder."""

    def test_default_config(self):
        """Test creating an observation builder with defaults."""
        builder = ObservationBuilder()
        space = builder.get_observation_space()
        from gymnasium import spaces; assert isinstance(space, spaces.Dict)
        assert "joint_positions" in space.spaces
        assert "joint_velocities" in space.spaces
        assert "endeffector_pos" in space.spaces
        assert "target_pos" in space.spaces
        assert "distance_to_target" in space.spaces

    def test_custom_config(self):
        """Test creating an observation builder with custom config."""
        config = ObservationConfig(
            observation_types=[
                ObservationType.JOINT_POSITIONS,
                ObservationType.ENDEFFECTOR_POS,
            ],
            include_force=True,
        )
        builder = ObservationBuilder(config=config)
        space = builder.get_observation_space()
        assert "joint_positions" in space.spaces
        assert "endeffector_pos" in space.spaces
        assert "force_torque" in space.spaces

    def test_get_observation_size(self):
        """Test getting observation vector size."""
        config = ObservationConfig(
            observation_types=[
                ObservationType.JOINT_POSITIONS,
                ObservationType.ENDEFFECTOR_POS,
            ],
        )
        builder = ObservationBuilder(config=config, num_joints=7)
        size = builder.get_observation_size()
        assert size == 7 + 3  # 7 joints + 3 position

    def test_extract_observation(self):
        """Test extracting observation from simulator data."""
        from surg_rl.simulators.base_simulator import Observation

        config = ObservationConfig(
            observation_types=[
                ObservationType.JOINT_POSITIONS,
                ObservationType.ENDEFFECTOR_POS,
            ],
        )
        builder = ObservationBuilder(config=config, num_joints=7)

        sim_obs = Observation(
            robot_state=np.random.randn(14),
            end_effector_pos=np.array([0.3, 0.0, 0.5]),
        )

        obs = builder.extract_observation(sim_obs, target_pos=np.array([0.5, 0.0, 0.5]))
        assert "joint_positions" in obs
        assert "endeffector_pos" in obs
        assert obs["joint_positions"].shape == (7,)
        assert obs["endeffector_pos"].shape == (3,)

    def test_flatten_observation(self):
        """Test flattening observation dict to vector."""
        config = ObservationConfig(
            observation_types=[
                ObservationType.JOINT_POSITIONS,
                ObservationType.ENDEFFECTOR_POS,
            ],
        )
        builder = ObservationBuilder(config=config, num_joints=7)

        from surg_rl.simulators.base_simulator import Observation
        sim_obs = Observation(
            robot_state=np.random.randn(14),
            end_effector_pos=np.array([0.3, 0.0, 0.5]),
        )

        obs = builder.extract_observation(sim_obs)
        flat = builder.flatten_observation(obs)
        assert flat.shape == (10,)  # 7 + 3

    def test_num_joints_override(self):
        """Test that number of joints can be overridden."""
        config = ObservationConfig(
            observation_types=[ObservationType.JOINT_POSITIONS],
        )
        builder = ObservationBuilder(config=config, num_joints=6)
        space = builder.get_observation_space()
        assert space["joint_positions"].shape == (6,)


# ============================================================================
# Action Tests
# ============================================================================


class TestActionType:
    """Tests for ActionType enum."""

    def test_action_types_exist(self):
        """Test that all action types are defined."""
        assert ActionType.JOINT_POSITIONS == "joint_positions"
        assert ActionType.JOINT_VELOCITIES == "joint_velocities"
        assert ActionType.ENDEFFECTOR_POSE == "endeffector_pose"
        assert ActionType.GRIPPER == "gripper"

    def test_action_scaling_types(self):
        """Test that all action scaling types are defined."""
        assert ActionScaling.NORMALIZE == "normalize"
        assert ActionScaling.TANH == "tanh"
        assert ActionScaling.NONE == "none"


class TestActionConfig:
    """Tests for ActionConfig."""

    def test_default_config(self):
        """Test default action configuration."""
        config = ActionConfig()
        assert config.action_type == ActionType.JOINT_POSITIONS
        assert config.num_joints == 7
        assert config.include_gripper is True

    def test_custom_config(self):
        """Test custom action configuration."""
        config = ActionConfig(
            action_type=ActionType.ENDEFFECTOR_DELTA,
            include_gripper=False,
        )
        assert config.action_type == ActionType.ENDEFFECTOR_DELTA
        assert config.include_gripper is False


class TestActionBuilder:
    """Tests for ActionBuilder."""

    def test_default_builder(self):
        """Test creating an action builder with defaults."""
        builder = ActionBuilder()
        space = builder.get_action_space()
        assert space.shape == (8,)  # 7 joints + 1 gripper

    def test_no_gripper(self):
        """Test action builder without gripper."""
        config = ActionConfig(include_gripper=False)
        builder = ActionBuilder(config=config)
        space = builder.get_action_space()
        assert space.shape == (7,)  # Just joints

    def test_process_action(self):
        """Test action processing."""
        builder = ActionBuilder()
        action = np.zeros(8, dtype=np.float32)
        processed = builder.process_action(action)
        assert processed is not None
        assert processed.shape == (8,)

    def test_split_action(self):
        """Test splitting action into components."""
        builder = ActionBuilder()
        action = np.zeros(8, dtype=np.float32)
        split = builder.split_action(action)
        assert "joint_positions" in split
        assert "gripper" in split
        assert split["joint_positions"].shape == (7,)
        assert split["gripper"].shape == (1,)

    def test_get_action_size(self):
        """Test getting action size."""
        builder = ActionBuilder()
        assert builder.get_action_size() == 8  # 7 + 1

    def test_reset(self):
        """Test resetting action builder."""
        builder = ActionBuilder()
        action = np.ones(8, dtype=np.float32) * 0.5
        builder.process_action(action)
        builder.reset()
        assert builder._last_action is None


# ============================================================================
# Reward Tests
# ============================================================================


class TestRewardResult:
    """Tests for RewardResult."""

    def test_creation(self):
        """Test creating a reward result."""
        result = RewardResult(total=1.0, components={"distance": 0.5, "shaping": 0.5})
        assert result.total == 1.0
        assert any("distance" in k for k in result.components)

    def test_addition(self):
        """Test adding two reward results."""
        r1 = RewardResult(total=1.0, components={"a": 1.0})
        r2 = RewardResult(total=2.0, components={"b": 2.0})
        combined = r1 + r2
        assert combined.total == 3.0
        assert "a" in combined.components
        assert "b" in combined.components

    def test_scaling(self):
        """Test scaling a reward result."""
        result = RewardResult(total=2.0, components={"a": 1.0, "b": 1.0})
        scaled = result * 0.5
        assert scaled.total == 1.0
        assert scaled.components["a"] == 0.5


class TestDistanceReward:
    """Tests for DistanceReward."""

    def test_exponential_reward(self):
        """Test exponential distance reward."""
        reward_fn = DistanceReward(weight=1.0, shape="exponential")
        obs = {"distance_to_target": np.array([0.1])}
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total > 0  # Should be positive for exponential
        reward_fn.reset()

    def test_linear_reward(self):
        """Test linear distance reward."""
        reward_fn = DistanceReward(weight=1.0, shape="linear")
        obs = {"distance_to_target": np.array([0.5])}
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total < 0  # Should be negative for linear
        reward_fn.reset()

    def test_gaussian_reward(self):
        """Test Gaussian distance reward."""
        reward_fn = DistanceReward(weight=1.0, shape="gaussian", sigma=0.1)
        # At distance 0 (target), reward should be ~1
        obs = {"distance_to_target": np.array([0.0])}
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total > 0.9  # Gaussian at 0 should be close to 1
        reward_fn.reset()

    def test_shaping_reward(self):
        """Test that shaping reward is positive when approaching."""
        reward_fn = DistanceReward(weight=1.0, shape="exponential")

        # First step - far from target
        obs1 = {"distance_to_target": np.array([0.5])}
        reward_fn.compute(obs1, np.zeros(7), {})

        # Second step - closer to target
        obs2 = {"distance_to_target": np.array([0.3])}
        result = reward_fn.compute(obs2, np.zeros(7), {})
        assert result.info.get("approaching", False)
        reward_fn.reset()


class TestActionPenalty:
    """Tests for ActionPenalty."""

    def test_l2_penalty(self):
        """Test L2 action penalty."""
        reward_fn = ActionPenalty(weight=0.01, penalty_type="l2")
        action = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        result = reward_fn.compute({}, action, {})
        assert result.total < 0  # Penalty should be negative

    def test_l1_penalty(self):
        """Test L1 action penalty."""
        reward_fn = ActionPenalty(weight=0.01, penalty_type="l1")
        action = np.array([1.0, 0.0, 0.0])
        result = reward_fn.compute({}, action, {})
        assert result.total < 0

    def test_zero_action(self):
        """Test penalty with zero action."""
        reward_fn = ActionPenalty(weight=0.01)
        action = np.zeros(7)
        result = reward_fn.compute({}, action, {})
        assert result.total == 0.0  # No penalty for zero action


class TestTimePenalty:
    """Tests for TimePenalty."""

    def test_time_penalty(self):
        """Test that time penalty is applied each step."""
        reward_fn = TimePenalty(weight=0.001)
        result = reward_fn.compute({}, np.zeros(7), {})
        assert result.total == -0.001

    def test_time_penalty_accumulates(self):
        """Test that step counter increments."""
        reward_fn = TimePenalty(weight=0.001)
        reward_fn.compute({}, np.zeros(7), {})
        reward_fn.compute({}, np.zeros(7), {})
        assert reward_fn._step == 2

    def test_reset(self):
        """Test resetting time penalty."""
        reward_fn = TimePenalty(weight=0.001)
        reward_fn.compute({}, np.zeros(7), {})
        reward_fn.reset()
        assert reward_fn._step == 0


class TestSuccessReward:
    """Tests for SuccessReward."""

    def test_success(self):
        """Test reward on task success."""
        reward_fn = SuccessReward(success_reward=100.0)
        obs = {"distance_to_target": np.array([0.005])}
        result = reward_fn.compute(obs, np.zeros(7), {"terminated": True, "success": True})
        assert result.total == 100.0

    def test_failure(self):
        """Test penalty on task failure."""
        reward_fn = SuccessReward(failure_penalty=-50.0)
        obs = {"distance_to_target": np.array([0.5])}
        result = reward_fn.compute(obs, np.zeros(7), {"terminated": True, "success": False})
        assert result.total == -50.0

    def test_no_terminal(self):
        """Test no reward when not terminal."""
        reward_fn = SuccessReward(success_reward=100.0)
        obs = {}
        result = reward_fn.compute(obs, np.zeros(7), {"terminated": False})
        assert result.total == 0.0


class TestCollisionPenalty:
    """Tests for CollisionPenalty."""

    def test_collision(self):
        """Test penalty on collision."""
        reward_fn = CollisionPenalty(weight=10.0)
        result = reward_fn.compute({}, np.zeros(7), {"collision": True})
        assert result.total < 0

    def test_no_collision(self):
        """Test no penalty without collision."""
        reward_fn = CollisionPenalty(weight=10.0)
        result = reward_fn.compute({}, np.zeros(7), {"collision": False})
        assert result.total == 0.0

    def test_tissue_damage(self):
        """Test penalty with tissue damage."""
        reward_fn = CollisionPenalty(weight=10.0, tissue_weight=5.0)
        result = reward_fn.compute({}, np.zeros(7), {"collision": True, "tissue_damage": 2.0})
        assert result.total < -10.0  # Collision + tissue damage


class TestCompositeReward:
    """Tests for CompositeReward."""

    def test_composite_reward(self):
        """Test combining multiple reward functions."""
        reward_fn = CompositeReward([
            (DistanceReward(weight=1.0, shape="exponential"), 1.0),
            (ActionPenalty(weight=0.01), 1.0),
            (TimePenalty(weight=0.001), 1.0),
        ])

        obs = {"distance_to_target": np.array([0.1])}
        action = np.ones(7) * 0.1
        result = reward_fn.compute(obs, action, {})

        assert result.total != 0  # Should be non-zero
        assert any("distance" in k for k in result.components)
        assert any("action_penalty" in k for k in result.components)

    def test_create_default_reward(self):
        """Test creating default reward function."""
        reward_fn = create_default_reward()
        assert isinstance(reward_fn, CompositeReward)

    def test_composite_reset(self):
        """Test resetting composite reward."""
        reward_fn = CompositeReward([
            (TimePenalty(), 1.0),
        ])
        reward_fn.compute({}, np.zeros(7), {})
        reward_fn.reset()
        # TimePenalty should reset to 0 steps
        result = reward_fn.compute({}, np.zeros(7), {})
        assert any("time_penalty" in k for k in result.components)


# ============================================================================
# Training Configuration Tests
# ============================================================================


class TestAlgorithmConfig:
    """Tests for AlgorithmConfig."""

    def test_default_config(self):
        """Test default algorithm configuration."""
        config = AlgorithmConfig()
        assert config.name == "PPO"
        assert config.learning_rate == 3e-4
        assert config.gamma == 0.99

    def test_custom_config(self):
        """Test custom algorithm configuration."""
        config = AlgorithmConfig(
            name="SAC",
            learning_rate=1e-4,
            buffer_size=500_000,
        )
        assert config.name == "SAC"
        assert config.learning_rate == 1e-4
        assert config.buffer_size == 500_000

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = AlgorithmConfig()
        d = config.to_dict()
        assert "name" in d
        assert "learning_rate" in d
        assert d["name"] == "PPO"


class TestTrainingConfig:
    """Tests for TrainingConfig."""

    def test_default_config(self):
        """Test default training configuration."""
        config = TrainingConfig()
        assert config.total_timesteps == 1_000_000
        assert config.algorithm.name == "PPO"
        assert config.seed == 42

    def test_save_load(self):
        """Test saving and loading configuration."""
        config = TrainingConfig(
            scene_path="scenes/test.json",
            total_timesteps=50000,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            config.save(f.name)
            loaded = TrainingConfig.load(f.name)
            assert loaded.scene_path == "scenes/test.json"
            assert loaded.total_timesteps == 50000
            os.unlink(f.name)

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = TrainingConfig()
        d = config.to_dict()
        assert "algorithm" in d
        assert "scene_path" in d
        assert "total_timesteps" in d


# ============================================================================
# Callback Tests
# ============================================================================


class TestTrainingProgressCallback:
    """Tests for TrainingProgressCallback."""

    def test_creation(self):
        """Test creating a progress callback."""
        callback = TrainingProgressCallback(verbose=0)
        assert callback.verbose == 0
        assert callback._step == 0

    def test_get_stats_initial(self):
        """Test getting initial stats."""
        callback = TrainingProgressCallback()
        stats = callback.get_stats()
        assert stats["step"] == 0
        assert stats["episodes"] == 0


class TestCheckpointCallback:
    """Tests for CheckpointCallback."""

    def test_creation(self):
        """Test creating a checkpoint callback."""
        callback = CheckpointCallback(
            save_freq=10000,
            save_path="/tmp/checkpoints",
            name_prefix="test",
        )
        assert callback.save_freq == 10000
        assert callback.name_prefix == "test"


class TestTensorBoardCallback:
    """Tests for TensorBoardCallback."""

    def test_creation(self):
        """Test creating a TensorBoard callback."""
        callback = TensorBoardCallback(verbose=0)
        assert callback.log_interval == 100
        assert callback.controller is None

    def test_creation_with_controller(self):
        """Test creating a TensorBoard callback with a controller."""
        from unittest.mock import MagicMock

        controller = MagicMock()
        controller.get_curriculum_stage.return_value = None
        controller.get_difficulty.return_value = None
        controller.current_params = MagicMock()
        controller.current_params.physics = {}
        controller.current_params.visual = {}
        controller.current_params.dynamics = {}

        callback = TensorBoardCallback(controller=controller, log_interval=50)
        assert callback.controller is controller
        assert callback.log_interval == 50

    def test_on_step_logs_episode_metrics(self):
        """Test that _on_step logs episode metrics."""
        from unittest.mock import MagicMock

        callback = TensorBoardCallback(verbose=0)
        model = MagicMock()
        model.num_timesteps = 10
        logger = MagicMock()
        model.logger = logger
        callback.init_callback(model)

        callback.locals = {
            "infos": [
                {"episode": {"r": 100.0, "l": 50}},
            ],
        }
        callback.on_step()

        logger.record.assert_any_call("rollout/episode_reward", 100.0)
        logger.record.assert_any_call("rollout/episode_length", 50)

    def test_on_step_logs_curriculum_and_difficulty(self):
        """Test that _on_step logs curriculum stage and difficulty."""
        from unittest.mock import MagicMock

        from surg_rl.dynamics.curriculum import CurriculumStage

        controller = MagicMock()
        controller.get_curriculum_stage.return_value = CurriculumStage.EASY
        controller.get_difficulty.return_value = 0.5
        controller.current_params = MagicMock()
        controller.current_params.physics = {"friction": 0.8}
        controller.current_params.visual = {}
        controller.current_params.dynamics = {}

        callback = TensorBoardCallback(controller=controller, verbose=0)
        model = MagicMock()
        model.num_timesteps = 10
        logger = MagicMock()
        model.logger = logger
        callback.init_callback(model)

        callback.locals = {"infos": []}
        callback.on_step()

        logger.record.assert_any_call("curriculum/stage", CurriculumStage.EASY.value)
        logger.record.assert_any_call("curriculum/difficulty", 0.5)
        logger.record.assert_any_call("randomization/physics/friction", 0.8)

    def test_on_step_logs_fps(self):
        """Test that _on_step logs training FPS."""
        from unittest.mock import MagicMock

        callback = TensorBoardCallback(verbose=0)
        model = MagicMock()
        model.num_timesteps = 100
        logger = MagicMock()
        model.logger = logger
        callback.init_callback(model)

        callback.locals = {"infos": []}
        callback._on_training_start()
        callback.on_step()

        assert logger.record.called
        fps_calls = [
            call for call in logger.record.call_args_list
            if call[0][0] == "time/fps"
        ]
        assert len(fps_calls) == 1
        assert fps_calls[0][0][1] > 0


class TestTrainingConfigTensorBoard:
    """Tests for TrainingConfig TensorBoard options."""

    def test_tensorboard_disabled_by_default(self):
        """Test that TensorBoard is disabled by default."""
        config = TrainingConfig()
        assert config.enable_tensorboard is False

    def test_tensorboard_enabled(self):
        """Test enabling TensorBoard."""
        config = TrainingConfig(enable_tensorboard=True)
        assert config.enable_tensorboard is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestObservationActionIntegration:
    """Integration tests for observation and action spaces."""

    def test_obs_action_sizes_match(self):
        """Test that observation and action builder produce consistent sizes."""
        obs_config = ObservationConfig(
            observation_types=[
                ObservationType.JOINT_POSITIONS,
                ObservationType.JOINT_VELOCITIES,
                ObservationType.ENDEFFECTOR_POS,
                ObservationType.DISTANCE_TO_TARGET,
            ],
        )
        act_config = ActionConfig(
            action_type=ActionType.JOINT_POSITIONS,
            num_joints=7,
            include_gripper=True,
        )

        obs_builder = ObservationBuilder(config=obs_config, num_joints=7)
        act_builder = ActionBuilder(config=act_config)

        obs_space = obs_builder.get_observation_space()
        act_space = act_builder.get_action_space()

        assert obs_space is not None
        assert act_space.shape == (8,)  # 7 joints + 1 gripper
        assert obs_builder.get_observation_size() == 7 + 7 + 3 + 1  # joints + vel + pos + dist

    def test_reward_with_observation(self):
        """Test reward computation with observation data."""
        reward_fn = create_default_reward(RewardConfig(
            distance_weight=1.0,
            action_penalty_weight=0.01,
            time_penalty_weight=0.001,
        ))

        obs = {
            "distance_to_target": np.array([0.1]),
            "joint_positions": np.random.randn(7),
        }
        action = np.random.randn(8)

        result = reward_fn.compute(obs, action, {"terminated": False})
        assert result.total != 0
        reward_fn.reset()


# ============================================================================
# Vectorized Environment Tests
# ============================================================================


class TestVectorizedEnv:
    """Tests for vectorized environment creation and stepping."""

    def test_make_vec_env_dummy(self):
        """Test that make_vec_env returns DummyVecEnv for n_envs=1."""
        from stable_baselines3.common.vec_env import DummyVecEnv

        vec_env = make_vec_env("scenes/minimal_scene.json", n_envs=1)
        assert isinstance(vec_env, DummyVecEnv)
        vec_env.close()

    def test_make_vec_env_subproc(self):
        """Test that make_vec_env returns SubprocVecEnv for n_envs>1."""
        from stable_baselines3.common.vec_env import SubprocVecEnv

        vec_env = make_vec_env("scenes/minimal_scene.json", n_envs=2)
        assert isinstance(vec_env, SubprocVecEnv)
        vec_env.close()

    def test_make_vec_env_explicit_cls(self):
        """Test that vec_env_cls overrides the default."""
        from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

        vec_env = make_vec_env(
            "scenes/minimal_scene.json",
            n_envs=2,
            vec_env_cls=DummyVecEnv,
        )
        assert isinstance(vec_env, DummyVecEnv)
        vec_env.close()

    def test_vec_env_reset_step(self):
        """Test reset and step on a vectorized environment."""
        vec_env = make_vec_env("scenes/minimal_scene.json", n_envs=2)
        obs = vec_env.reset()
        assert obs is not None
        # Dict observation space: each key should have shape (n_envs, ...)
        for key, arr in obs.items():
            assert arr.shape[0] == 2, f"Expected batch dim 2 for {key}, got {arr.shape}"

        action = np.stack([vec_env.action_space.sample() for _ in range(2)])
        obs, rewards, dones, infos = vec_env.step(action)
        assert len(rewards) == 2
        assert len(dones) == 2
        vec_env.close()

    def test_vec_env_seeding(self):
        """Test that each sub-environment receives a different seed."""
        from stable_baselines3.common.vec_env import DummyVecEnv

        vec_env = make_vec_env(
            "scenes/minimal_scene.json",
            n_envs=3,
            seed=42,
            vec_env_cls=DummyVecEnv,
        )
        obs = vec_env.reset()
        assert obs is not None
        vec_env.close()


def test_evaluate_with_vec_env():
    """evaluate() must work when _create_environment returns a VecEnv."""
    from unittest.mock import MagicMock
    from surg_rl.rl.training import TrainingManager, TrainingConfig, AlgorithmConfig

    config = TrainingConfig(
        scene_path="scenes/minimal_scene.json",
        algorithm=AlgorithmConfig(name="PPO"),
        n_envs=2,
        total_timesteps=100,
    )
    manager = TrainingManager(config)

    model = MagicMock()
    model.predict.return_value = (np.zeros(7), None)
    manager._model = model

    vec_env = MagicMock()
    vec_env.reset.return_value = np.zeros((2, 10))
    vec_env.step.return_value = (
        np.zeros((2, 10)),
        np.array([1.0, 1.0]),
        np.array([True, True]),
        [{}, {}],
    )
    manager._create_environment = MagicMock(return_value=vec_env)

    results = manager.evaluate(n_episodes=2)
    assert "mean_reward" in results


def test_env_seeding_is_reproducible():
    """Seeded envs must produce identical target positions and not poison global RNG."""
    from unittest.mock import MagicMock, patch
    from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

    config = SurgicalEnvConfig(
        scene_path="scenes/minimal_scene.json",
        seed=42,
    )
    # Mock simulator to avoid loading scene
    with patch("surg_rl.rl.environment.MuJoCoSimulator") as MockSim:
        sim = MagicMock()
        sim.get_observation.return_value = MagicMock(
            robot_state=np.zeros(7),
            end_effector_pos=np.array([0.0, 0.0, 0.0]),
            end_effector_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        MockSim.return_value = sim

        env1 = SurgicalEnv(config)
        env2 = SurgicalEnv(config)

        # Seed global RNG to known state; reset must not alter it.
        np.random.seed(123)
        expected_next = np.random.uniform()

        np.random.seed(123)
        obs1, info1 = env1.reset(seed=42)
        obs2, info2 = env2.reset(seed=42)
        actual_next = np.random.uniform()

        assert np.allclose(obs1["target_pos"], obs2["target_pos"])
        assert np.isclose(actual_next, expected_next), "reset() poisoned global np.random"


def test_observation_noise_is_reproducible():
    """Observation noise must be reproducible with the same seed."""
    from surg_rl.rl.observation import ObservationBuilder, ObservationConfig
    from unittest.mock import MagicMock

    config = ObservationConfig()
    builder = ObservationBuilder(config=config)
    builder.seed(42)

    obs = MagicMock()
    obs.robot_state = np.array([1.0, 2.0, 3.0])
    obs.end_effector_pos = np.array([0.1, 0.2, 0.3])
    obs.end_effector_quat = np.array([1.0, 0.0, 0.0, 0.0])
    obs.force_torque = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    obs.tissue_state = {}

    spec = builder._specs["joint_positions"]
    result1 = builder._apply_noise(np.array([1.0, 2.0, 3.0]), spec.noise_scale)

    builder.seed(42)
    result2 = builder._apply_noise(np.array([1.0, 2.0, 3.0]), spec.noise_scale)

    assert np.allclose(result1, result2)


def test_tanh_scaling_maps_to_action_bounds():
    """TANH scaling must map (-inf, inf) input to actual action-space bounds."""
    from surg_rl.rl.action import ActionBuilder, ActionConfig, ActionScaling

    config = ActionConfig(scaling=ActionScaling.TANH, include_gripper=False, clip_actions=False)
    builder = ActionBuilder(config=config)
    space = builder.get_action_space()

    # Large input values should be squashed to actual bounds
    action = np.ones(space.shape) * 10.0
    scaled = builder.process_action(action)

    # After TANH scaling, output should be mapped to actual bounds, not left in (-1, 1)
    assert np.allclose(scaled, space.high, atol=1e-2), f"Expected near {space.high}, got {scaled}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
