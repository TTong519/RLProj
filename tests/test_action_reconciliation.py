"""Tests for action–simulator DOF reconciliation (Phase 1)."""

from typing import Any

import numpy as np

from surg_rl.scene_definition.schema import SceneDefinition
from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
from surg_rl.simulators.pybullet_simulator import PyBulletSimulator


def _minimal_scene(num_joints: int = 3) -> SceneDefinition:
    """Build a minimal schema-compliant scene with a single robot having N revolute joints."""
    joints = (
        [
            {
                "name": f"joint_{i}",
                "type": "revolute",
                "limits": {"lower": -1.0, "upper": 1.0},
                "initial_position": 0.0,
                "damping": 0.1,
                "friction": 0.0,
            }
            for i in range(num_joints)
        ]
        if num_joints > 0
        else []
    )
    data: dict[str, Any] = {
        "metadata": {"name": "test_scene", "version": "1.0"},
        "robots": [
            {
                "name": "robot0",
                "type": "custom",
                "joints": joints,
                "base_pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            }
        ],
    }
    return SceneDefinition(**data)


class TestMuJoCoActionReconciliation:
    """MuJoCo action mapping tests."""

    def test_get_num_controls_matches_joint_count(self) -> None:
        sim = MuJoCoSimulator()
        scene = _minimal_scene(num_joints=3)
        sim.load_scene(scene)
        assert sim.get_num_controls() == 3

    def test_apply_action_maps_correctly(self) -> None:
        sim = MuJoCoSimulator()
        scene = _minimal_scene(num_joints=3)
        sim.load_scene(scene)
        action = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        sim.apply_action(action)
        # The flat ctrl should match the action after mapping
        expected = np.zeros(sim.get_num_controls(), dtype=np.float32)
        expected[:] = action
        np.testing.assert_array_almost_equal(sim._data.ctrl[:3], expected)

    def test_action_size_mismatch_does_not_crash(self) -> None:
        sim = MuJoCoSimulator()
        scene = _minimal_scene(num_joints=3)
        sim.load_scene(scene)
        # Send too-short action
        sim.apply_action(np.array([0.5], dtype=np.float32))
        # Should survive without error

    def test_gripper_placeholder_not_exposed_by_default(self) -> None:
        sim = MuJoCoSimulator()
        scene = _minimal_scene(num_joints=4)
        sim.load_scene(scene)
        # With no endeffector, gripper slot should be absent
        assert sim.get_num_controls() == 4
        for m in sim._control_map:
            assert not m.get("is_gripper", False)


class TestPyBulletActionReconciliation:
    """PyBullet action mapping tests."""

    def test_get_num_controls_matches_joint_count(self) -> None:
        sim = PyBulletSimulator(render_mode="DIRECT")
        scene = _minimal_scene(num_joints=3)
        sim.load_scene(scene)
        # PyBullet currently loads a single revolute link per primitive robot,
        # so control count reflects actual joints (1), not scene joints.
        assert sim.get_num_controls() == 1

    def test_apply_action_maps_correctly(self) -> None:
        sim = PyBulletSimulator(render_mode="DIRECT")
        scene = _minimal_scene(num_joints=3)
        sim.load_scene(scene)
        action = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        sim.apply_action(action)
        assert sim._control_map is not None
        # Only first action element gets applied because there is 1 joint
        assert sim._control_map[0]["robot_name"] == "robot0"
        assert len(sim._control_map) == 1

    def test_action_size_mismatch_does_not_crash(self) -> None:
        sim = PyBulletSimulator(render_mode="DIRECT")
        scene = _minimal_scene(num_joints=3)
        sim.load_scene(scene)
        sim.apply_action(np.array([0.5], dtype=np.float32))


class TestEnvironmentActionConfig:
    """Environment-level default action config."""

    def test_default_action_config_uses_simulator_dof_count(self) -> None:
        from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

        scene = _minimal_scene(num_joints=5)
        env = SurgicalEnv(
            config=SurgicalEnvConfig(
                scene=scene,
                simulator_type="mujoco",
                render_mode=None,
            )
        )
        assert env._action_builder.config.num_joints == 5
        assert not env._action_builder.config.include_gripper

    def test_action_space_size_matches_num_controls(self) -> None:
        from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

        scene = _minimal_scene(num_joints=4)
        env = SurgicalEnv(
            config=SurgicalEnvConfig(
                scene=scene,
                simulator_type="mujoco",
                render_mode=None,
            )
        )
        assert env.action_space.shape[0] == 4
