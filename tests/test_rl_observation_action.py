"""Tests for RL observation and action deep coverage."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from surg_rl.rl.observation import (
    ObservationBuilder,
    ObservationConfig,
    ObservationSpec,
    ObservationType,
    DEFAULT_SPECS,
)
from surg_rl.rl.action import (
    ActionBuilder,
    ActionConfig,
    ActionSpec,
    ActionType,
    ActionScaling,
    DEFAULT_ACTION_SPECS,
)


class TestObservationBuilderDeep:
    def test_get_flat_observation_space_exists(self):
        config = ObservationConfig(observation_types=[ObservationType.JOINT_POSITIONS])
        builder = ObservationBuilder(config, num_joints=3)
        flat_space = builder.get_flat_observation_space()
        assert flat_space.shape[0] == 3

    def test_normalize_shape_mismatch_returns_zeros(self):
        config = ObservationConfig(observation_types=[ObservationType.JOINT_POSITIONS])
        builder = ObservationBuilder(config, num_joints=3)
        # Provide mismatched shape input
        result = builder._normalize(np.array([1.0]), "joint_positions")
        assert np.allclose(result, 0.0)

    def test_quaternion_angle_identical(self):
        q = np.array([1.0, 0.0, 0.0, 0.0])
        angle = ObservationBuilder._quaternion_angle(q, q)
        assert np.isclose(angle, 0.0)

    def test_quaternion_angle_180(self):
        q1 = np.array([1.0, 0.0, 0.0, 0.0])
        q2 = np.array([0.0, 1.0, 0.0, 0.0])
        angle = ObservationBuilder._quaternion_angle(q1, q2)
        assert angle > np.pi / 2

    def test_unflatten_observation_roundtrip(self):
        config = ObservationConfig(observation_types=[ObservationType.JOINT_POSITIONS])
        builder = ObservationBuilder(config, num_joints=3)
        obs = {"joint_positions": np.array([0.1, 0.2, 0.3])}
        flat = builder.flatten_observation(obs)
        rebuilt = builder.unflatten_observation(flat, obs)
        assert np.allclose(rebuilt["joint_positions"], obs["joint_positions"])

    def test_extract_observation_force_torque_fallback(self):
        config = ObservationConfig(observation_types=[ObservationType.FORCE_TORQUE])
        builder = ObservationBuilder(config)
        from surg_rl.simulators.base_simulator import Observation
        sim_obs = Observation()
        result = builder.extract_observation(sim_obs)
        assert "force_torque" in result
        assert result["force_torque"].shape == (6,)

    def test_extract_observation_tissue_deformation_padding(self):
        config = ObservationConfig(observation_types=[ObservationType.TISSUE_DEFORMATION])
        builder = ObservationBuilder(config)
        from surg_rl.simulators.base_simulator import Observation
        sim_obs = Observation(custom={"tissue_deformation": [0.1, 0.2]})
        result = builder.extract_observation(sim_obs)
        assert "tissue_deformation" in result
        assert result["tissue_deformation"].shape == (50, 3)

    def test_extract_observation_tool_positions(self):
        # TOOL_POSITIONS is not in DEFAULT_SPECS, so use CUSTOM + custom_specs
        custom_spec = ObservationSpec(
            name="tool_positions",
            obs_type=ObservationType.TOOL_POSITIONS,
            shape=(3,),
            low=-np.ones(3),
            high=np.ones(3),
        )
        config = ObservationConfig(observation_types=[ObservationType.CUSTOM])
        builder = ObservationBuilder(config, custom_specs={"tool_positions": custom_spec})
        from surg_rl.simulators.base_simulator import Observation
        sim_obs = Observation(custom={"tool_positions": [0.1, 0.2, 0.3]})
        result = builder.extract_observation(sim_obs)
        assert "tool_positions" in result

    def test_extract_observation_tool_positions_native_field(self):
        """M9: TOOL_POSITIONS must read observation.tool_positions, not custom."""
        config = ObservationConfig(observation_types=[ObservationType.TOOL_POSITIONS])
        builder = ObservationBuilder(config)
        from surg_rl.simulators.base_simulator import Observation
        sim_obs = Observation(tool_positions=np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]))
        result = builder.extract_observation(sim_obs)
        assert "tool_positions" in result
        assert not np.allclose(result["tool_positions"], 0.0)


class TestActionBuilderDeep:
    def test_discrete_action_space(self):
        spec = ActionSpec(name="discrete", action_type=ActionType.DISCRETE, shape=(), num_actions=5)
        space = spec.get_space()
        assert space.n == 5

    def test_process_action_tanh_scaling(self):
        config = ActionConfig(
            action_type=ActionType.JOINT_POSITIONS,
            num_joints=2,
            scaling=ActionScaling.TANH,
            include_gripper=False,
        )
        builder = ActionBuilder(config)
        raw = np.zeros(2, dtype=np.float32)
        processed = builder.process_action(raw)
        assert processed.shape == (2,)

    def test_process_action_relative_actions(self):
        config = ActionConfig(
            action_type=ActionType.JOINT_POSITIONS,
            num_joints=2,
            relative_actions=True,
            action_scale=0.5,
            include_gripper=False,
        )
        builder = ActionBuilder(config)
        builder.reset()
        a1 = np.array([0.1, 0.1], dtype=np.float32)
        out1 = builder.process_action(a1)
        a2 = np.array([0.1, 0.1], dtype=np.float32)
        out2 = builder.process_action(a2)
        # Second action should be relative to first
        assert not np.allclose(out1, out2)

    def test_normalize_action_maps_range(self):
        config = ActionConfig(
            action_type=ActionType.JOINT_POSITIONS,
            num_joints=1,
            include_gripper=False,
        )
        builder = ActionBuilder(config)
        action = np.array([-1.0])
        normalized = builder._normalize_action(action)
        assert np.allclose(normalized, builder.get_action_space().low)
