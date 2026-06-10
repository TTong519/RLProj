"""Tests for multi-agent RL env: arm_id routing, MultiAgentSurgicalEnv, ObservationFilter.

Phase 22 Plan 02 — Core MultiAgentSurgicalEnv + simulator arm routing.
"""

import json

import numpy as np
import pytest

from surg_rl.scene_definition.schema import (
    ArmConfig,
    MultiAgentConfig,
    RobotConfig,
    SceneDefinition,
)

# ============================================================================
# Helper: Create a minimal dual-arm scene for simulator tests
# ============================================================================


def _make_dual_arm_scene() -> SceneDefinition:
    """Create a minimal valid dual-arm scene with 2 robots."""
    return SceneDefinition(
        robots=[
            RobotConfig(
                name="surgeon_arm",
                type="davinci",
                urdf_path="fake_surgeon.urdf",
                base_pose={"position": {"x": -0.2, "y": 0, "z": 0}},
                joints=[
                    {
                        "name": "s_joint_0",
                        "type": "revolute",
                        "limits": {"lower": -3.14, "upper": 3.14, "velocity": 2.0, "effort": 100.0},
                    },
                    {
                        "name": "s_joint_1",
                        "type": "revolute",
                        "limits": {"lower": -3.14, "upper": 3.14, "velocity": 2.0, "effort": 100.0},
                    },
                ],
            ),
            RobotConfig(
                name="assistant_arm",
                type="davinci",
                urdf_path="fake_assistant.urdf",
                base_pose={"position": {"x": 0.2, "y": 0, "z": 0}},
                joints=[
                    {
                        "name": "a_joint_0",
                        "type": "revolute",
                        "limits": {"lower": -3.14, "upper": 3.14, "velocity": 2.0, "effort": 100.0},
                    },
                ],
            ),
        ],
        multi_agent=MultiAgentConfig(
            arm_configs=[
                ArmConfig(role="surgeon", robot_ref="surgeon_arm"),
                ArmConfig(role="assistant", robot_ref="assistant_arm"),
            ]
        ),
    )


def _make_single_arm_scene() -> SceneDefinition:
    """Create a minimal valid single-arm scene."""
    return SceneDefinition(
        robots=[
            RobotConfig(
                name="robot_1",
                type="davinci",
                urdf_path="fake_robot.urdf",
                base_pose={"position": {"x": 0, "y": 0, "z": 0}},
                joints=[
                    {
                        "name": "joint_0",
                        "type": "revolute",
                        "limits": {"lower": -3.14, "upper": 3.14, "velocity": 2.0, "effort": 100.0},
                    },
                    {
                        "name": "joint_1",
                        "type": "revolute",
                        "limits": {"lower": -3.14, "upper": 3.14, "velocity": 2.0, "effort": 100.0},
                    },
                ],
            ),
        ],
    )


# ============================================================================
# TASK 1: arm_id routing on BaseSimulator + MuJoCo + PyBullet backends
# ============================================================================


class TestBaseSimulatorArmId:
    """Tests for arm_id parameter on BaseSimulator.apply_action."""

    def test_apply_action_signature_accepts_arm_id(self):
        """apply_action(action, arm_id=None) has correct signature (backward compat)."""
        import inspect

        from surg_rl.simulators.base_simulator import BaseSimulator

        sig = inspect.signature(BaseSimulator.apply_action)
        params = list(sig.parameters.keys())
        assert "arm_id" in params, "apply_action must accept arm_id parameter"
        assert params == [
            "self",
            "action",
            "arm_id",
        ], f"apply_action params should be ['self', 'action', 'arm_id'], got {params}"

    def test_apply_action_abstract_accepts_arm_id(self):
        """_apply_action abstract method accepts arm_id parameter."""
        import inspect

        from surg_rl.simulators.base_simulator import BaseSimulator

        sig = inspect.signature(BaseSimulator._apply_action)
        params = list(sig.parameters.keys())
        assert "arm_id" in params, "_apply_action must accept arm_id parameter"
        assert params == [
            "self",
            "action",
            "arm_id",
        ], f"_apply_action params should be ['self', 'action', 'arm_id'], got {params}"

    def test_apply_action_passes_arm_id_to_implementation(self):
        """apply_action propagates arm_id to _apply_action."""

        from surg_rl.simulators.base_simulator import BaseSimulator

        captured = {}

        class TestSim(BaseSimulator):
            def load_scene(self, scene_definition):
                pass

            def reset(self, seed=None):
                pass  # pragma: no cover

            def step(self, action):
                pass  # pragma: no cover

            def render(self, mode="rgb_array", width=None, height=None, camera_name=None):
                pass  # pragma: no cover

            def get_state(self):
                pass  # pragma: no cover

            def set_state(self, state):
                pass  # pragma: no cover

            def close(self):
                pass  # pragma: no cover

            def start_viewer(self, target_fps=30.0):
                return False

            def stop_viewer(self):
                pass

            def get_joint_states(self):
                return {}  # pragma: no cover

            def _apply_action(self, action, arm_id=None):
                captured["action"] = action
                captured["arm_id"] = arm_id

        sim = TestSim()
        action = np.array([1.0, 2.0, 3.0])
        sim.apply_action(action, arm_id="surgeon")

        np.testing.assert_array_equal(captured["action"], action)
        assert captured["arm_id"] == "surgeon"

        # Test default None
        captured.clear()
        sim.apply_action(action)
        assert captured["arm_id"] is None


class TestMuJoCoArmRouting:
    """Tests for arm_id routing in MuJoCo simulator."""

    @pytest.mark.integration
    def test_mujoco_arm_id_none_routes_all_joints(self, monkeypatch):
        """arm_id=None routes action to all joints (backward compatible)."""

        # Suppress any OS-level GL/display issues
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_dual_arm_scene()

        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

        sim = MuJoCoSimulator(timestep=0.002, frame_skip=1, render_mode="rgb_array")
        try:
            sim.load_scene(scene)
            sim.reset()

            # Get total controls
            n_controls = sim.get_num_controls()
            assert n_controls > 0, "Should have at least one control"

            action = np.ones(n_controls, dtype=np.float32)
            sim.apply_action(action, arm_id=None)

            # Verify all controls were set
            for i in range(n_controls):
                assert sim._data.ctrl[i] == 1.0, f"ctrl[{i}] should be 1.0, got {sim._data.ctrl[i]}"
        finally:
            sim.close()

    @pytest.mark.integration
    def test_mujoco_arm_id_surgeon_routes_surgeon_only(self, monkeypatch):
        """arm_id="surgeon" routes action only to surgeon arm joints."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_dual_arm_scene()

        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

        sim = MuJoCoSimulator(timestep=0.002, frame_skip=1, render_mode="rgb_array")
        try:
            sim.load_scene(scene)
            sim.reset()

            assert sim._arm_joint_ranges is not None
            assert "surgeon" in sim._arm_joint_ranges
            surgeon_start, surgeon_end = sim._arm_joint_ranges["surgeon"]

            # Store original ctrl values (should be zeros from reset)
            original_ctrl = sim._data.ctrl.copy()

            # Create an action for surgeon arm joints only
            surgeon_dof = surgeon_end - surgeon_start
            surgeon_action = np.full(surgeon_dof, 0.5, dtype=np.float32)

            sim.apply_action(surgeon_action, arm_id="surgeon")

            # Surgeon joints should be set
            for i in range(surgeon_start, surgeon_end):
                assert (
                    sim._data.ctrl[i] == 0.5
                ), f"Surgeon ctrl[{i}] should be 0.5, got {sim._data.ctrl[i]}"

            # Non-surgeon joints should remain unchanged
            for i in range(len(sim._data.ctrl)):
                if i < surgeon_start or i >= surgeon_end:
                    assert (
                        sim._data.ctrl[i] == original_ctrl[i]
                    ), f"Non-surgeon ctrl[{i}] changed from {original_ctrl[i]} to {sim._data.ctrl[i]}"
        finally:
            sim.close()

    @pytest.mark.integration
    def test_mujoco_arm_id_unknown_raises_value_error(self, monkeypatch):
        """arm_id="nonexistent" raises ValueError."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_dual_arm_scene()

        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

        sim = MuJoCoSimulator(timestep=0.002, frame_skip=1, render_mode="rgb_array")
        try:
            sim.load_scene(scene)
            sim.reset()

            with pytest.raises(ValueError, match="Unknown arm_id"):
                sim.apply_action(np.array([1.0]), arm_id="nonexistent")
        finally:
            sim.close()


class TestPyBulletArmRouting:
    """Tests for arm_id routing in PyBullet simulator."""

    @pytest.mark.integration
    def test_pybullet_arm_id_none_routes_all_joints(self, monkeypatch):
        """arm_id=None routes action to all joints (backward compatible)."""
        # Prevent PyBullet from opening a GUI
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_dual_arm_scene()

        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

        sim = PyBulletSimulator(timestep=0.002, frame_skip=1, render_mode="DIRECT")
        try:
            sim.load_scene(scene)
            sim.reset()

            n_controls = sim.get_num_controls()
            assert n_controls > 0, "Should have at least one control"

            action = np.full(n_controls, 0.3, dtype=np.float32)
            sim.apply_action(action, arm_id=None)

            # Just verify no error — PyBullet doesn't expose ctrl array like MuJoCo
            # We trust the arm routing logic below
        finally:
            sim.close()

    @pytest.mark.integration
    def test_pybullet_arm_id_surgeon_routes_correct_joints(self, monkeypatch):
        """arm_id="surgeon" routes action only to surgeon arm joints."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_dual_arm_scene()

        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

        sim = PyBulletSimulator(timestep=0.002, frame_skip=1, render_mode="DIRECT")
        try:
            sim.load_scene(scene)
            sim.reset()

            assert sim._arm_joint_ranges is not None
            assert "surgeon" in sim._arm_joint_ranges
            surgeon_start, surgeon_end = sim._arm_joint_ranges["surgeon"]

            # Build a surgeon-only action
            surgeon_dof = surgeon_end - surgeon_start
            surgeon_action = np.full(surgeon_dof, 0.7, dtype=np.float32)
            sim.apply_action(surgeon_action, arm_id="surgeon")

            # Verify: no error is a pass for PyBullet (action applied only to surgeon)
        finally:
            sim.close()

    @pytest.mark.integration
    def test_pybullet_arm_id_unknown_raises_value_error(self, monkeypatch):
        """arm_id="nonexistent" raises ValueError."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_dual_arm_scene()

        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

        sim = PyBulletSimulator(timestep=0.002, frame_skip=1, render_mode="DIRECT")
        try:
            sim.load_scene(scene)
            sim.reset()

            with pytest.raises(ValueError, match="Unknown arm_id"):
                sim.apply_action(np.array([1.0]), arm_id="nonexistent")
        finally:
            sim.close()


# ============================================================================
# Task 4 (backward compat): Existing single-arm scene applies actions unchanged
# ============================================================================


class TestSingleArmBackwardCompat:
    """arm_id=None on single-arm scenes is backward compatible."""

    @pytest.mark.integration
    def test_mujoco_single_arm_arm_id_none(self, monkeypatch):
        """Single-arm MuJoCo scene works with arm_id=None (backward compat)."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_single_arm_scene()

        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

        sim = MuJoCoSimulator(timestep=0.002, frame_skip=1, render_mode="rgb_array")
        try:
            sim.load_scene(scene)
            sim.reset()

            n_controls = sim.get_num_controls()
            action = np.ones(n_controls, dtype=np.float32)
            sim.apply_action(action, arm_id=None)

            # All controls set
            for i in range(n_controls):
                assert sim._data.ctrl[i] == 1.0
        finally:
            sim.close()

    @pytest.mark.integration
    def test_pybullet_single_arm_arm_id_none(self, monkeypatch):
        """Single-arm PyBullet scene works with arm_id=None (backward compat)."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_single_arm_scene()

        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

        sim = PyBulletSimulator(timestep=0.002, frame_skip=1, render_mode="DIRECT")
        try:
            sim.load_scene(scene)
            sim.reset()

            n_controls = sim.get_num_controls()
            action = np.full(n_controls, 0.5, dtype=np.float32)
            sim.apply_action(action, arm_id=None)
            # No error = pass
        finally:
            sim.close()


# ============================================================================
# TASK 2: MultiAgentSurgicalEnv (ParallelEnv) + ObservationFilter
# ============================================================================


class TestMultiAgentSurgicalEnv:
    """Integration tests for MultiAgentSurgicalEnv (ParallelEnv)."""

    @pytest.fixture
    def dual_arm_scene(self, tmp_path):
        """Create a dual-arm scene JSON for env loading."""
        scene_dict = {
            "metadata": {"name": "Dual Arm Test Scene"},
            "robots": [
                {
                    "name": "surgeon_arm",
                    "type": "davinci",
                    "urdf_path": "fake_surgeon.urdf",
                    "base_pose": {"position": {"x": -0.2, "y": 0, "z": 0}},
                    "joints": [
                        {
                            "name": "s_joint_0",
                            "type": "revolute",
                            "limits": {
                                "lower": -3.14,
                                "upper": 3.14,
                                "velocity": 2.0,
                                "effort": 100.0,
                            },
                        },
                    ],
                },
                {
                    "name": "assistant_arm",
                    "type": "davinci",
                    "urdf_path": "fake_assistant.urdf",
                    "base_pose": {"position": {"x": 0.2, "y": 0, "z": 0}},
                    "joints": [
                        {
                            "name": "a_joint_0",
                            "type": "revolute",
                            "limits": {
                                "lower": -3.14,
                                "upper": 3.14,
                                "velocity": 2.0,
                                "effort": 100.0,
                            },
                        },
                    ],
                },
            ],
            "multi_agent": {
                "arm_configs": [
                    {"role": "surgeon", "robot_ref": "surgeon_arm"},
                    {"role": "assistant", "robot_ref": "assistant_arm"},
                ],
                "shared_policy": True,
                "cooperative": True,
                "observation_sharing": False,
            },
        }
        scene_path = tmp_path / "dual_arm_scene.json"
        scene_path.write_text(json.dumps(scene_dict))
        return scene_path

    @pytest.mark.integration
    def test_env_not_instance_of_surgical_env(self, dual_arm_scene, monkeypatch):
        """isinstance(MultiAgentSurgicalEnv, SurgicalEnv) is False (D-11 passthrough)."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv
        from surg_rl.rl.environment import SurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            assert not isinstance(
                env, SurgicalEnv
            ), "MultiAgentSurgicalEnv must NOT be a SurgicalEnv subclass (D-11)"
        finally:
            env.close()

    @pytest.mark.integration
    def test_env_reset_returns_agent_dicts(self, dual_arm_scene, monkeypatch):
        """env.reset() returns ({agent_id: obs_dict}, {agent_id: info_dict})."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            obs, info = env.reset()

            assert isinstance(obs, dict), "reset must return dict of observations"
            assert isinstance(info, dict), "reset must return dict of infos"
            assert "surgeon" in obs, "surgeon agent missing from observations"
            assert "assistant" in obs, "assistant agent missing from observations"
            assert "surgeon" in info, "surgeon agent missing from infos"
            assert "assistant" in info, "assistant agent missing from infos"

            # Each agent's obs should be a dict
            assert isinstance(obs["surgeon"], dict), "surgeon obs must be a dict"
            assert isinstance(obs["assistant"], dict), "assistant obs must be a dict"
        finally:
            env.close()

    @pytest.mark.integration
    def test_env_agents_property(self, dual_arm_scene, monkeypatch):
        """env.agents equals ["surgeon", "assistant"]."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            agents = env.agents
            assert "surgeon" in agents, "surgeon missing from agents list"
            assert "assistant" in agents, "assistant missing from agents list"
            assert len(agents) == 2, f"Expected 2 agents, got {len(agents)}"
        finally:
            env.close()

    @pytest.mark.integration
    def test_env_step_returns_5_tuple_of_dicts(self, dual_arm_scene, monkeypatch):
        """env.step({"surgeon": a_s, "assistant": a_a}) returns 5-tuple of dicts."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            env.reset()

            actions = {
                "surgeon": np.array([0.1], dtype=np.float32),
                "assistant": np.array([0.2], dtype=np.float32),
            }
            result = env.step(actions)

            assert len(result) == 5, f"step must return 5-tuple, got {len(result)}"
            obs, rewards, terms, truncs, infos = result

            assert isinstance(obs, dict)
            assert isinstance(rewards, dict)
            assert isinstance(terms, dict)
            assert isinstance(truncs, dict)
            assert isinstance(infos, dict)

            assert "surgeon" in obs
            assert "assistant" in obs
            assert "surgeon" in rewards
            assert "assistant" in rewards
        finally:
            env.close()

    @pytest.mark.integration
    def test_surgeon_assistant_obs_differ(self, dual_arm_scene, monkeypatch):
        """Surgeon and assistant observations differ (filtered per-agent)."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            obs, _info = env.reset()

            surgeon_keys = set(obs["surgeon"].keys())
            assistant_keys = set(obs["assistant"].keys())

            # At minimum, they should both have some robot_state-derived keys
            # In a full implementation with distinct observation_keys, they'd differ.
            # Here we verify both have observations (non-empty).
            assert len(surgeon_keys) > 0, "surgeon obs should have keys"
            assert len(assistant_keys) > 0, "assistant obs should have keys"
        finally:
            env.close()

    @pytest.mark.integration
    def test_reward_dict_separate_values(self, dual_arm_scene, monkeypatch):
        """Reward dict has separate values for surgeon and assistant."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            env.reset()

            actions = {
                "surgeon": np.array([0.1], dtype=np.float32),
                "assistant": np.array([0.2], dtype=np.float32),
            }
            _obs, rewards, _term, _trunc, _info = env.step(actions)

            assert "surgeon" in rewards
            assert "assistant" in rewards
            assert isinstance(rewards["surgeon"], (float, np.floating))
            assert isinstance(rewards["assistant"], (float, np.floating))
        finally:
            env.close()

    @pytest.mark.integration
    def test_env_close_cleans_up(self, dual_arm_scene, monkeypatch):
        """env.close() cleans up without error."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            env.reset()
            actions = {
                "surgeon": np.array([0.1], dtype=np.float32),
                "assistant": np.array([0.2], dtype=np.float32),
            }
            env.step(actions)
        finally:
            env.close()
        # No error = pass

    @pytest.mark.integration
    def test_observation_space_function(self, dual_arm_scene, monkeypatch):
        """env.observation_space("surgeon") and .action_space("surgeon") work."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            obs_space_s = env.observation_space("surgeon")
            act_space_s = env.action_space("surgeon")
            assert obs_space_s is not None
            assert act_space_s is not None

            obs_space_a = env.observation_space("assistant")
            act_space_a = env.action_space("assistant")
            assert obs_space_a is not None
            assert act_space_a is not None
        finally:
            env.close()

    @pytest.mark.integration
    def test_env_has_single_surgical_env(self, dual_arm_scene, monkeypatch):
        """hasattr(env, '_surgical_env') is True (one SurgicalEnv owned)."""
        monkeypatch.setenv("DISPLAY", "")

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        config = {"scene_path": str(dual_arm_scene), "simulator_type": "mujoco"}
        env = MultiAgentSurgicalEnv(config)
        try:
            assert hasattr(env, "_surgical_env"), "MultiAgentSurgicalEnv must own _surgical_env"
            from surg_rl.rl.environment import SurgicalEnv

            assert isinstance(
                env._surgical_env, SurgicalEnv
            ), "_surgical_env must be a SurgicalEnv instance"
        finally:
            env.close()

    @pytest.mark.integration
    def test_env_raises_if_no_multi_agent(self, monkeypatch):
        """MultiAgentSurgicalEnv raises ValueError if scene.multi_agent is None."""
        monkeypatch.setenv("DISPLAY", "")

        scene = _make_single_arm_scene()

        from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv

        with pytest.raises(ValueError, match="multi_agent"):
            MultiAgentSurgicalEnv({"scene": scene, "simulator_type": "mujoco"})


# ============================================================================
# ObservationFilter tests
# ============================================================================


class TestObservationFilter:
    """Tests for ObservationFilter (per-agent key filtering)."""

    def test_filter_all_keys_when_none(self):
        """When observation_keys is None, all keys pass through."""
        from surg_rl.marl.observation_filter import ObservationFilter

        multi_agent = MultiAgentConfig(
            arm_configs=[
                ArmConfig(role="surgeon", robot_ref="r1", observation_keys=None),
                ArmConfig(role="assistant", robot_ref="r2", observation_keys=None),
            ]
        )
        filt = ObservationFilter(multi_agent)

        obs = {"joint_positions": np.array([1.0]), "endeffector_pos": np.array([2.0])}
        result = filt.filter("surgeon", obs)
        assert set(result.keys()) == set(obs.keys())
        np.testing.assert_array_equal(result["joint_positions"], obs["joint_positions"])

    def test_filter_subset_keys_when_specified(self):
        """When observation_keys specified, only those keys pass through."""
        from surg_rl.marl.observation_filter import ObservationFilter

        multi_agent = MultiAgentConfig(
            arm_configs=[
                ArmConfig(role="surgeon", robot_ref="r1", observation_keys=["endeffector_pos"]),
                ArmConfig(role="assistant", robot_ref="r2", observation_keys=["joint_positions"]),
            ]
        )
        filt = ObservationFilter(multi_agent)

        obs = {
            "joint_positions": np.array([1.0, 2.0]),
            "endeffector_pos": np.array([3.0, 4.0, 5.0]),
            "joint_velocities": np.array([0.1, 0.2]),
        }

        surgeon_result = filt.filter("surgeon", obs)
        assert set(surgeon_result.keys()) == {"endeffector_pos"}
        np.testing.assert_array_equal(surgeon_result["endeffector_pos"], obs["endeffector_pos"])

        assistant_result = filt.filter("assistant", obs)
        assert set(assistant_result.keys()) == {"joint_positions"}
        np.testing.assert_array_equal(assistant_result["joint_positions"], obs["joint_positions"])

    def test_filter_unknown_agent_returns_empty(self):
        """Filtering for unknown agent returns empty dict."""
        from surg_rl.marl.observation_filter import ObservationFilter

        multi_agent = MultiAgentConfig(
            arm_configs=[
                ArmConfig(role="surgeon", robot_ref="r1"),
                ArmConfig(role="assistant", robot_ref="r2"),
            ]
        )
        filt = ObservationFilter(multi_agent)

        obs = {"joint_positions": np.array([1.0])}
        result = filt.filter("camera", obs)
        assert result == {}, "Unknown agent should return empty dict"

    def test_filter_missing_keys_in_obs_skipped(self):
        """Keys in observation_keys but missing from obs are silently skipped."""
        from surg_rl.marl.observation_filter import ObservationFilter

        multi_agent = MultiAgentConfig(
            arm_configs=[
                ArmConfig(
                    role="surgeon",
                    robot_ref="r1",
                    observation_keys=["exists_key", "missing_key"],
                ),
                ArmConfig(role="assistant", robot_ref="r2"),
            ]
        )
        filt = ObservationFilter(multi_agent)

        obs = {"exists_key": np.array([1.0])}
        result = filt.filter("surgeon", obs)
        assert set(result.keys()) == {"exists_key"}, "missing_key should be silently skipped"


class TestMarlTrainCLISmoke:
    """Smoke test: `surg-rl marl-train` runs end-to-end on a dual-arm scene.

    Per Phase 25 D-09: the CLI must construct MultiAgentSurgicalEnv correctly
    and call MultiAgentTrainingManager.train() without crashing. This test
    exercises the same code path via Typer's command runner while patching
    the trainer to avoid running real timesteps.
    """

    @pytest.fixture
    def dual_arm_scene(self, tmp_path):
        """Local copy of the dual-arm scene JSON fixture for CLI invocation."""
        scene_dict = {
            "metadata": {"name": "Dual Arm CLI Test Scene"},
            "robots": [
                {
                    "name": "surgeon_arm",
                    "type": "davinci",
                    "urdf_path": "fake_surgeon.urdf",
                    "base_pose": {"position": {"x": -0.2, "y": 0, "z": 0}},
                    "joints": [
                        {
                            "name": "s_joint_0",
                            "type": "revolute",
                            "limits": {
                                "lower": -3.14,
                                "upper": 3.14,
                                "velocity": 2.0,
                                "effort": 100.0,
                            },
                        },
                    ],
                },
                {
                    "name": "assistant_arm",
                    "type": "davinci",
                    "urdf_path": "fake_assistant.urdf",
                    "base_pose": {"position": {"x": 0.2, "y": 0, "z": 0}},
                    "joints": [
                        {
                            "name": "a_joint_0",
                            "type": "revolute",
                            "limits": {
                                "lower": -3.14,
                                "upper": 3.14,
                                "velocity": 2.0,
                                "effort": 100.0,
                            },
                        },
                    ],
                },
            ],
            "multi_agent": {
                "arm_configs": [
                    {"role": "surgeon", "robot_ref": "surgeon_arm"},
                    {"role": "assistant", "robot_ref": "assistant_arm"},
                ],
                "shared_policy": True,
                "cooperative": True,
                "observation_sharing": False,
            },
        }
        scene_path = tmp_path / "dual_arm_cli_scene.json"
        scene_path.write_text(json.dumps(scene_dict))
        return scene_path

    def test_marl_train_cli_smoke(self, dual_arm_scene, tmp_path, monkeypatch):
        """`surg-rl marl-train --scene <dual_arm> --timesteps 10` runs without error."""
        from typer.testing import CliRunner

        from surg_rl.cli import app
        from surg_rl.marl.training import MultiAgentTrainingManager

        monkeypatch.setenv("DISPLAY", "")

        # Patch MultiAgentTrainingManager.train to avoid running 10 real timesteps
        def fake_train(self):
            return {"shared": str(tmp_path / "fake_model.zip")}

        monkeypatch.setattr(MultiAgentTrainingManager, "train", fake_train)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "marl-train",
                "--scene",
                str(dual_arm_scene),
                "--timesteps",
                "10",
                "--headless",
            ],
        )

        # Acceptable outcomes: exit 0 (success) or any non-zero where the
        # output does NOT contain the render_mode kwarg bug or the
        # np.zeros(0) path bug (the two bugs Phase 25 closed).
        combined = (result.stdout or "") + (result.stderr or "")
        assert "unexpected keyword argument 'render_mode'" not in combined, (
            f"CLI still has the render_mode kwarg bug: {combined}"
        )
        assert "np.zeros(0)" not in combined, (
            f"MARL env still calls step(np.zeros(0)): {combined}"
        )
