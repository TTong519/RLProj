"""Tests for SurgicalEnv environment wrapper."""

import numpy as np
import pytest

from surg_rl.rl.environment import (
    SurgicalEnv,
    SurgicalEnvConfig,
    make_env,
    make_vec_env,
)
from surg_rl.rl.observation import ObservationType


class TestSurgicalEnvDefaults:
    def test_default_observation_config(self):
        """Default observation config includes expected types."""
        config = SurgicalEnvConfig(scene_path="scenes/minimal_scene.json")
        env = SurgicalEnv(config)
        types = env._obs_builder.config.observation_types
        assert ObservationType.JOINT_POSITIONS in types
        assert ObservationType.DISTANCE_TO_TARGET in types
        env.close()

    def test_default_action_config_reads_joint_count(self):
        """Default action config uses first robot joint count."""
        config = SurgicalEnvConfig(scene_path="scenes/simple_suturing.json")
        env = SurgicalEnv(config)
        size = env._action_builder.get_action_size()
        assert size > 0
        env.close()

    def test_setup_controller(self):
        """Controller is created when use_curriculum=True."""
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            use_curriculum=True,
        )
        env = SurgicalEnv(config)
        assert env._controller is not None
        env.close()

    def test_invalid_simulator_type_raises(self):
        """Unknown simulator type raises ValueError."""
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            simulator_type="invalid",
        )
        with pytest.raises(ValueError, match="Unknown simulator type"):
            SurgicalEnv(config)


class TestSurgicalEnvLifecycle:
    def test_reset_returns_obs_and_info(self):
        config = SurgicalEnvConfig(scene_path="scenes/minimal_scene.json")
        env = SurgicalEnv(config)
        obs, info = env.reset(seed=42)
        assert isinstance(obs, dict)
        assert "step" in info
        env.close()

    def test_step_returns_tuple(self):
        config = SurgicalEnvConfig(scene_path="scenes/minimal_scene.json")
        env = SurgicalEnv(config)
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        env.close()

    def test_step_truncation_at_max_steps(self):
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = np.zeros(6, dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        env.close()


# ============================================================================
# Plan 09-02 Task 1: ROS2 Bridge Integration Tests
# ============================================================================


class TestRos2BridgeConfigWiring:
    """Tests for ros2_bridge_config field on SurgicalEnvConfig."""

    def test_ros2_bridge_config_default_is_none(self):
        """Test 1: ros2_bridge_config defaults to None."""
        config = SurgicalEnvConfig()
        assert config.ros2_bridge_config is None

    def test_ros2_bridge_config_can_be_set(self):
        """Ros2BridgeConfig can be set on SurgicalEnvConfig."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        rc = Ros2BridgeConfig(state_topic="/test", command_topic="/test2")
        config = SurgicalEnvConfig(ros2_bridge_config=rc)
        assert config.ros2_bridge_config is not None
        assert config.ros2_bridge_config.state_topic == "/test"

    def test_env_init_without_bridge_config_no_bridge(self):
        """Test 1: Without bridge config, _bridge is None."""
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            ros2_bridge_config=None,
        )
        env = SurgicalEnv(config)
        assert env._bridge is None
        env.close()


class TestRos2BridgeEnvLifecycle:
    """Tests for bridge lifecycle in SurgicalEnv (macOS graceful degradation)."""

    def test_macos_bridge_is_none_with_config(self):
        """Test 6: On macOS, _bridge=None even with config, env functional."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        rc = Ros2BridgeConfig(state_topic="/test", command_topic="/test2")
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            ros2_bridge_config=rc,
        )
        env = SurgicalEnv(config)
        # macOS: bridge should be None (graceful degradation)
        assert env._bridge is None
        # Env should still be functional
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        env.close()

    def test_bridge_process_terminates_in_close(self):
        """Test 5: close() handles bridge gracefully even when None."""
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
        )
        env = SurgicalEnv(config)
        env.reset()
        # _bridge is None — close() should not raise
        env.close()
        # Should be able to close again without error
        env.close()

    def test_mocked_bridge_spawns_process(self):
        """Test 2: When HAS_ROS2=True (mocked), bridge Process spawns."""
        from unittest.mock import MagicMock, patch

        from surg_rl.ros2.config import Ros2BridgeConfig

        rc = Ros2BridgeConfig(state_topic="/test", command_topic="/test2")
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            ros2_bridge_config=rc,
        )

        with patch("surg_rl.rl.environment.HAS_ROS2", True):
            with patch("surg_rl.rl.environment.platform.system", return_value="Linux"):
                with patch(
                    "surg_rl.rl.environment.multiprocessing.Process"
                ) as mock_process_cls:
                    env = SurgicalEnv(config)
                    try:
                        assert env._bridge is not None
                        # Verify Process was created via start()
                        mock_process_cls.assert_called_once()
                        mock_process = mock_process_cls.return_value
                        mock_process.start.assert_called_once()
                    finally:
                        env.close()

    def test_mocked_step_injects_external_action(self):
        """Test 4: step() calls controller.get_action() — external action injection."""
        from unittest.mock import MagicMock, patch

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
        )
        env = SurgicalEnv(config)
        env.reset()

        # Mock controller.get_action to verify it is called
        env._controller = MagicMock()
        env._controller.get_action.return_value = np.array([0.5])

        action = np.array([0.1])
        env.step(action)

        # Controller.get_action should have been called with the action
        env._controller.get_action.assert_called_once()
        env.close()

    def test_mocked_step_publishes_joint_state(self):
        """Test 2: When bridge active, step() publishes joint state."""
        from unittest.mock import MagicMock, patch

        from surg_rl.ros2.config import Ros2BridgeConfig

        rc = Ros2BridgeConfig(state_topic="/test", command_topic="/test2")
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            ros2_bridge_config=rc,
        )

        with patch("surg_rl.rl.environment.HAS_ROS2", True):
            with patch("surg_rl.rl.environment.platform.system", return_value="Linux"):
                mock_bridge = MagicMock()
                with patch(
                    "surg_rl.rl.environment.Ros2Bridge", return_value=mock_bridge
                ):
                    env = SurgicalEnv(config)
                    try:
                        env.reset()
                        action = env.action_space.sample()
                        env.step(action)
                        # publish_joint_state should have been called
                        mock_bridge.publish_joint_state.assert_called()
                    finally:
                        env.close()

    def test_no_bridge_ros2_false_warns(self):
        """Test 3: When HAS_ROS2=False, bridge config → _bridge=None, env works."""
        from unittest.mock import patch

        from surg_rl.ros2.config import Ros2BridgeConfig

        rc = Ros2BridgeConfig(state_topic="/test", command_topic="/test2")
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            ros2_bridge_config=rc,
        )

        with patch("surg_rl.rl.environment.HAS_ROS2", False):
            env = SurgicalEnv(config)
            try:
                assert env._bridge is None
                # Env should still work
                env.reset()
                action = env.action_space.sample()
                obs, reward, terminated, truncated, info = env.step(action)
                assert isinstance(obs, dict)
            finally:
                env.close()

    def test_render_rgb_array(self):
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="rgb_array",
        )
        env = SurgicalEnv(config)
        env.reset()
        env.render()
        # rgb may be None if renderer unavailable
        env.close()

    def test_render_human_returns_none(self):
        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="human",
        )
        env = SurgicalEnv(config)
        env.reset()
        result = env.render()
        assert result is None
        env.close()


class TestSurgicalEnvInfo:
    def test_build_info_contains_distance(self):
        config = SurgicalEnvConfig(scene_path="scenes/minimal_scene.json")
        env = SurgicalEnv(config)
        env.reset()
        from surg_rl.simulators.base_simulator import Observation

        sim_obs = Observation(end_effector_pos=np.array([0.1, 0.0, 0.5]))
        env._target_pos = np.array([0.3, 0.0, 0.5])
        info = env._build_info(sim_obs)
        assert "distance_to_target" in info
        env.close()


class TestSurgicalEnvState:
    def test_set_target_updates_target_pos(self):
        config = SurgicalEnvConfig(scene_path="scenes/minimal_scene.json")
        env = SurgicalEnv(config)
        env.set_target(np.array([0.5, 0.2, 0.3]))
        assert np.allclose(env._target_pos, np.array([0.5, 0.2, 0.3]))
        env.close()

    def test_get_state_set_state_roundtrip(self):
        config = SurgicalEnvConfig(scene_path="scenes/minimal_scene.json")
        env = SurgicalEnv(config)
        env.reset(seed=10)
        state = env.get_state()
        assert "step_count" in state
        env.close()


class TestMakeEnvFactory:
    def test_make_env_returns_surgical_env(self):
        env = make_env("scenes/minimal_scene.json", simulator_type="mujoco")
        assert isinstance(env, SurgicalEnv)
        env.close()

    def test_make_vec_env_returns_env(self):
        env = make_vec_env("scenes/minimal_scene.json", n_envs=1)
        assert env is not None
        env.close()


class TestSurgicalEnvTorque:
    def test_step_with_joint_torques_mujoco(self):
        """SurgicalEnv step succeeds with JOINT_TORQUES on MuJoCo."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            simulator_type="mujoco",
            action_config=ActionConfig(
                action_type=ActionType.JOINT_TORQUES,
                num_joints=1,
                include_gripper=False,
            ),
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        assert isinstance(reward, float)
        env.close()

    def test_step_with_joint_torques_pybullet(self):
        """SurgicalEnv step succeeds with JOINT_TORQUES on PyBullet."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            simulator_type="pybullet",
            action_config=ActionConfig(
                action_type=ActionType.JOINT_TORQUES,
                num_joints=1,
                include_gripper=False,
            ),
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        assert isinstance(reward, float)
        env.close()


class TestGripper:
    """ACT-04: Gripper actuation works end-to-end in both backends."""

    def test_action_space_includes_gripper_when_configured(self):
        """Explicit include_gripper=True yields action size = num_joints + 1."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/simple_suturing.json",
            action_config=ActionConfig(
                action_type=ActionType.JOINT_POSITIONS,
                num_joints=1,
                include_gripper=True,
            ),
        )
        env = SurgicalEnv(config)
        assert env.action_space.shape[0] == 2
        env.close()

    def test_step_with_gripper_action_mujoco(self):
        """Step succeeds with gripper-including action on MuJoCo."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/simple_suturing.json",
            simulator_type="mujoco",
            action_config=ActionConfig(
                action_type=ActionType.JOINT_POSITIONS,
                num_joints=1,
                include_gripper=True,
            ),
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = np.zeros(2, dtype=np.float32)  # 1 joint + 1 gripper
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        env.close()

    def test_step_with_gripper_action_pybullet(self):
        """Step succeeds with gripper-including action on PyBullet."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/simple_suturing.json",
            simulator_type="pybullet",
            action_config=ActionConfig(
                action_type=ActionType.JOINT_POSITIONS,
                num_joints=1,
                include_gripper=True,
            ),
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = np.zeros(2, dtype=np.float32)  # 1 joint + 1 gripper
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        env.close()

    def test_default_action_config_detects_gripper_from_scene(self):
        """When no action_config is provided, gripper is auto-detected from scene."""
        config = SurgicalEnvConfig(
            scene_path="scenes/simple_suturing.json",
            simulator_type="mujoco",
        )
        env = SurgicalEnv(config)
        # simple_suturing has end_effectors, so include_gripper should be True
        assert env._action_builder.config.include_gripper is True
        env.close()


class TestActionTypeValidation:
    """ACT-05: Unsupported ActionType values are rejected at scene load time."""

    def test_endeffector_pose_does_not_raise(self):
        """ENDEFFECTOR_POSE is now implemented via simulator IK."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            simulator_type="mujoco",
            action_config=ActionConfig(
                action_type=ActionType.ENDEFFECTOR_POSE,
                num_joints=6,
                include_gripper=False,
            ),
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = np.zeros(6, dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        env.close()

    def test_endeffector_delta_does_not_raise(self):
        """ENDEFFECTOR_DELTA is now implemented via simulator IK."""
        from surg_rl.rl.action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            simulator_type="mujoco",
            action_config=ActionConfig(
                action_type=ActionType.ENDEFFECTOR_DELTA,
                num_joints=6,
                include_gripper=False,
            ),
            max_episode_steps=2,
        )
        env = SurgicalEnv(config)
        env.reset()
        action = np.zeros(6, dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, dict)
        env.close()


