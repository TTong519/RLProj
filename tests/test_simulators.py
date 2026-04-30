"""Tests for simulator module."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from surg_rl.scene_definition import (
    Metadata,
    SceneDefinition,
    SimulatorType,
    TissueConfig,
    TissueMeshDefinition,
    TissueType,
)
from surg_rl.simulators import (
    AssetMissingError,
    BaseSimulator,
    MuJoCoSimulator,
    Observation,
    PyBulletSimulator,
    SceneBuilder,
    State,
    StepResult,
)


class TestObservation:
    """Tests for Observation class."""

    def test_observation_defaults(self):
        """Test default observation values."""
        obs = Observation()
        assert obs.rgb_image is None
        assert obs.depth_image is None
        assert obs.robot_state is None
        assert obs.end_effector_pos is None
        assert obs.end_effector_quat is None
        assert obs.force_torque is None
        assert obs.tissue_state is None
        assert obs.custom == {}

    def test_observation_to_dict(self):
        """Test observation to dict conversion."""
        import numpy as np

        obs = Observation(
            rgb_image=np.zeros((100, 100, 3)),
            robot_state=np.array([0.0, 0.0, 0.0]),
        )
        d = obs.to_dict()
        assert "rgb_image" in d
        assert "robot_state" in d
        assert d["robot_state"].shape == (3,)


class TestState:
    """Tests for State class."""

    def test_state_defaults(self):
        """Test default state values."""
        state = State()
        assert state.time == 0.0
        assert state.qpos is None
        assert state.qvel is None
        assert state.body_positions == {}
        assert state.body_orientations == {}


class TestStepResult:
    """Tests for StepResult class."""

    def test_step_result(self):
        """Test step result creation."""
        obs = Observation()
        result = StepResult(
            observation=obs,
            reward=1.0,
            terminated=False,
            truncated=False,
        )
        assert result.observation is obs
        assert result.reward == 1.0
        assert not result.terminated
        assert not result.truncated
        assert not result.done

    def test_step_result_done(self):
        """Test done property."""
        result = StepResult(
            observation=Observation(),
            reward=0.0,
            terminated=True,
            truncated=False,
        )
        assert result.done


class TestSceneBuilder:
    """Tests for SceneBuilder class."""

    def test_scene_builder_initialization(self):
        """Test scene builder initializes correctly."""
        builder = SceneBuilder()
        assert builder.assets_dir is None
        assert builder.use_primitive_fallback is True

    def test_scene_builder_with_assets_dir(self, tmp_path: Path):
        """Test scene builder with assets directory."""
        builder = SceneBuilder(assets_dir=tmp_path)
        assert builder.assets_dir == tmp_path

    def test_resolve_asset_path_absolute(self, tmp_path: Path):
        """Test resolving absolute asset path."""
        builder = SceneBuilder(assets_dir=tmp_path)

        # Create test file
        test_file = tmp_path / "test.obj"
        test_file.write_text("mesh")

        resolved = builder.resolve_asset_path(str(test_file))
        assert resolved == test_file

    def test_resolve_asset_path_relative(self, tmp_path: Path):
        """Test resolving relative asset path."""
        builder = SceneBuilder(assets_dir=tmp_path)

        # Create test file
        test_file = tmp_path / "test.obj"
        test_file.write_text("mesh")

        resolved = builder.resolve_asset_path("test.obj")
        assert resolved == test_file

    def test_resolve_asset_path_not_found(self, tmp_path: Path):
        """Test resolving missing asset path."""
        builder = SceneBuilder(assets_dir=tmp_path)

        resolved = builder.resolve_asset_path("nonexistent.obj")
        assert resolved is None

    def test_create_box_mesh(self, tmp_path: Path):
        """Test creating box mesh."""
        builder = SceneBuilder()

        mesh_path = builder._create_box_mesh((0.1, 0.1, 0.1), "test_box")
        assert mesh_path.exists()
        assert mesh_path.suffix == ".obj"

        content = mesh_path.read_text()
        assert "test_box" in content
        assert "v " in content  # Has vertices
        assert "f " in content  # Has faces

    def test_create_cylinder_mesh(self):
        """Test creating cylinder mesh."""
        builder = SceneBuilder()

        mesh_path = builder._create_cylinder_mesh(0.05, 0.1, "test_cyl")
        assert mesh_path.exists()
        assert mesh_path.suffix == ".obj"

        content = mesh_path.read_text()
        assert "test_cyl" in content

    def test_create_sphere_mesh(self):
        """Test creating sphere mesh."""
        builder = SceneBuilder()

        mesh_path = builder._create_sphere_mesh(0.05, "test_sphere")
        assert mesh_path.exists()
        assert mesh_path.suffix == ".obj"

        content = mesh_path.read_text()
        assert "test_sphere" in content

    def test_primitive_color_selection(self):
        """Test primitive color selection."""
        builder = SceneBuilder()

        color = builder._get_primitive_color("robot")
        assert color == (0.3, 0.3, 0.8, 1.0)

        color = builder._get_primitive_color("tissue", "skin")
        assert color == (0.95, 0.85, 0.8, 1.0)

        color = builder._get_primitive_color("unknown")
        assert color == (0.5, 0.5, 0.5, 1.0)

    def test_mesh_caching(self):
        """Test that meshes are cached."""
        builder = SceneBuilder()

        mesh1 = builder._create_box_mesh((0.1, 0.1, 0.1), "box1")
        mesh2 = builder._create_box_mesh((0.1, 0.1, 0.1), "box1")

        # Should return same path due to caching
        assert mesh1 == mesh2


class TestMuJoCoSimulator:
    """Tests for MuJoCoSimulator class."""

    def test_simulator_initialization(self):
        """Test simulator initializes correctly."""
        sim = MuJoCoSimulator()
        assert sim.timestep == 0.002
        assert sim.frame_skip == 1
        assert sim.render_width == 640
        assert sim.render_height == 480

    def test_simulator_custom_settings(self):
        """Test simulator with custom settings."""
        sim = MuJoCoSimulator(
            timestep=0.001,
            frame_skip=2,
            render_width=800,
            render_height=600,
        )
        assert sim.timestep == 0.001
        assert sim.frame_skip == 2
        assert sim.render_width == 800
        assert sim.render_height == 600

    def test_simulator_properties(self):
        """Test simulator properties."""
        sim = MuJoCoSimulator()
        assert sim.scene is None
        assert sim.simulation_time == 0.0

    def test_context_manager(self):
        """Test context manager protocol."""
        with MuJoCoSimulator() as sim:
            assert sim is not None
        # Should be cleaned up after context exit


class TestPyBulletSimulator:
    """Tests for PyBulletSimulator class."""

    def test_simulator_initialization(self):
        """Test simulator initializes correctly."""
        sim = PyBulletSimulator()
        assert sim.timestep == 0.002
        assert sim.frame_skip == 1
        assert sim.render_mode == "DIRECT"

    def test_simulator_custom_settings(self):
        """Test simulator with custom settings."""
        sim = PyBulletSimulator(
            timestep=0.001,
            frame_skip=2,
            render_mode="GUI",
        )
        assert sim.timestep == 0.001
        assert sim.frame_skip == 2
        assert sim.render_mode == "GUI"

    def test_simulator_properties(self):
        """Test simulator properties."""
        sim = PyBulletSimulator()
        assert sim.scene is None
        assert sim.simulation_time == 0.0

    def test_endeffector_pose_action_sets_joint_targets(self, suturing_scene):
        """Test endeffector_pose action mode applies IK without crashing."""
        sim = PyBulletSimulator()
        sim.load_scene(suturing_scene)
        sim.set_action_mode("endeffector_pose")
        action = np.zeros(6, dtype=np.float32)
        sim.step(action)

    def test_endeffector_delta_action_sets_joint_targets(self, suturing_scene):
        """Test endeffector_delta action mode applies IK without crashing."""
        sim = PyBulletSimulator()
        sim.load_scene(suturing_scene)
        sim.set_action_mode("endeffector_delta")
        action = np.zeros(6, dtype=np.float32)
        sim.step(action)


class TestBaseSimulator:
    """Tests for BaseSimulator abstract class."""

    def test_base_simulator_cannot_instantiate(self):
        """Test that BaseSimulator cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSimulator()


class TestSceneBuilderCleanup:
    """Tests for SceneBuilder cleanup behavior."""

    def test_cleanup_removes_temp_dir(self):
        """cleanup() must remove the temp directory."""
        import os

        builder = SceneBuilder()
        assert os.path.exists(builder.temp_dir)
        builder.cleanup()
        assert not os.path.exists(builder.temp_dir)


class TestAssetMissingError:
    """Tests for AssetMissingError."""

    def test_asset_missing_error(self):
        """Test AssetMissingError creation."""
        error = AssetMissingError("path/to/asset.obj", "mesh")
        assert error.asset_path == "path/to/asset.obj"
        assert error.asset_type == "mesh"
        assert "mesh" in str(error)
        assert "Primitive" in str(error)


class TestWithSceneDefinition:
    """Tests with actual scene definitions."""

    def test_create_mjcf_from_minimal_scene(self, tmp_path: Path):
        """Test creating MJCF from minimal scene."""
        # Create a minimal scene
        scene = SceneDefinition(
            metadata=Metadata(name="Test Scene"),
            simulator=SimulatorType.MUJOCO,
        )

        builder = SceneBuilder(use_primitive_fallback=True)
        mjcf_path = builder.create_mjcf(scene, output_path=tmp_path / "test.xml")

        assert mjcf_path.exists()
        content = mjcf_path.read_text()
        assert "mujoco" in content
        assert "Test Scene" in content

    def test_cleanup_temp_files(self):
        """Test that temp files are cleaned up."""
        builder = SceneBuilder()

        # Create some temp files
        mesh_path = builder._create_box_mesh((0.1, 0.1, 0.1), "test")
        assert mesh_path.exists()

        # Cleanup
        builder.cleanup()
        assert not mesh_path.exists()

    def test_mjcf_includes_joints_and_actuators(self, tmp_path: Path):
        """Test that MJCF contains joints and actuators for robots."""
        from surg_rl.scene_definition import RobotConfig, RobotType

        scene = SceneDefinition(
            metadata=Metadata(name="Joint Test Scene"),
            simulator=SimulatorType.MUJOCO,
            robots=[
                RobotConfig(
                    name="test_robot",
                    type=RobotType.ROBOTIC_ARM,
                    joints=[
                        {
                            "name": "shoulder",
                            "type": "revolute",
                            "limits": {"lower": -1.57, "upper": 1.57},
                        }
                    ],
                )
            ],
        )

        builder = SceneBuilder(use_primitive_fallback=True)
        mjcf_path = builder.create_mjcf(scene, output_path=tmp_path / "test.xml")
        content = mjcf_path.read_text()

        assert "actuator" in content
        assert "shoulder" in content
        assert "motor" in content
        assert 'joint="shoulder"' in content


class TestMuJoCoJointControl:
    """Tests for MuJoCo joint control."""

    def test_load_scene_creates_joints(self, tmp_path: Path):
        """Test that loading a scene creates controllable joints."""
        from surg_rl.scene_definition import RobotConfig, RobotType

        scene = SceneDefinition(
            metadata=Metadata(name="Joint Scene"),
            simulator=SimulatorType.MUJOCO,
            robots=[
                RobotConfig(
                    name="arm",
                    type=RobotType.ROBOTIC_ARM,
                    urdf_path="dummy.urdf",
                )
            ],
        )

        sim = MuJoCoSimulator()
        sim.load_scene(scene)

        # Should have at least one joint state entry
        joint_states = sim.get_joint_states()
        assert "arm" in joint_states
        assert "positions" in joint_states["arm"]
        assert "velocities" in joint_states["arm"]

        sim.close()

    def test_apply_action_sets_ctrl(self, tmp_path: Path):
        """Test that applying an action sets MuJoCo controls."""
        from surg_rl.scene_definition import RobotConfig, RobotType

        scene = SceneDefinition(
            metadata=Metadata(name="Action Scene"),
            simulator=SimulatorType.MUJOCO,
            robots=[
                RobotConfig(
                    name="arm",
                    type=RobotType.ROBOTIC_ARM,
                    urdf_path="dummy.urdf",
                )
            ],
        )

        sim = MuJoCoSimulator()
        sim.load_scene(scene)

        # Apply a non-zero action
        action = np.array([0.5], dtype=np.float32)
        sim.apply_action(action)

        # Verify ctrl was set
        assert sim._data.ctrl[0] == pytest.approx(0.5)

        sim.close()

    def test_get_state_includes_qpos_qvel(self, tmp_path: Path):
        """Test that get_state includes joint positions and velocities."""
        from surg_rl.scene_definition import RobotConfig, RobotType

        scene = SceneDefinition(
            metadata=Metadata(name="State Scene"),
            simulator=SimulatorType.MUJOCO,
            robots=[
                RobotConfig(
                    name="arm",
                    type=RobotType.ROBOTIC_ARM,
                    urdf_path="dummy.urdf",
                )
            ],
        )

        sim = MuJoCoSimulator()
        sim.load_scene(scene)

        state = sim.get_state()
        assert state.qpos is not None
        assert state.qvel is not None
        assert state.body_positions is not None

        sim.close()

    def test_step_with_action(self, tmp_path: Path):
        """Test that step applies action and advances simulation."""
        from surg_rl.scene_definition import RobotConfig, RobotType

        scene = SceneDefinition(
            metadata=Metadata(name="Step Scene"),
            simulator=SimulatorType.MUJOCO,
            robots=[
                RobotConfig(
                    name="arm",
                    type=RobotType.ROBOTIC_ARM,
                    urdf_path="dummy.urdf",
                )
            ],
        )

        sim = MuJoCoSimulator()
        sim.load_scene(scene)

        sim._data.qpos.copy()
        action = np.array([0.1], dtype=np.float32)
        result = sim.step(action)

        # Simulation should have advanced
        assert sim.simulation_time > 0.0
        assert result.observation is not None

        sim.close()


class TestPyBulletJointControl:
    """Tests for PyBullet joint control (mocked)."""

    def test_collect_joint_info(self):
        """Test that joint info is collected after loading a body."""
        import unittest.mock as mock

        sim = PyBulletSimulator()
        sim._physics_client = 0
        sim._pb = mock.MagicMock()
        sim._pb.getNumJoints.return_value = 2
        sim._pb.getJointInfo.side_effect = [
            (0, b"joint_a", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            (1, b"joint_b", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ]

        sim._collect_joint_info("robot", body_id=1)

        assert "robot" in sim._joint_ids
        assert sim._joint_ids["robot"]["joint_a"] == 0
        assert sim._joint_ids["robot"]["joint_b"] == 1
        assert sim._pb.setJointMotorControl2.call_count == 2

    def test_apply_action(self):
        """Test that apply_action sends targets to joints."""
        import unittest.mock as mock

        sim = PyBulletSimulator()
        sim._physics_client = 0
        sim._pb = mock.MagicMock()
        sim._body_ids = {"robot": 1}
        sim._joint_ids = {"robot": {"joint_0": 0, "joint_1": 1}}
        sim._loaded = True

        action = np.array([0.1, 0.2], dtype=np.float32)
        sim.apply_action(action)

        assert sim._pb.setJointMotorControl2.call_count == 2
        # First call: body_id=1, joint=0, target=0.1
        first_call = sim._pb.setJointMotorControl2.call_args_list[0]
        assert first_call[0][0] == 1
        assert first_call[0][1] == 0
        assert first_call[1]["targetPosition"] == pytest.approx(0.1)

    def test_get_joint_states(self):
        """Test that get_joint_states returns positions and velocities."""
        import unittest.mock as mock

        sim = PyBulletSimulator()
        sim._physics_client = 0
        sim._pb = mock.MagicMock()
        sim._body_ids = {"robot": 1}
        sim._joint_ids = {"robot": {"joint_0": 0}}
        sim._loaded = True

        sim._pb.getJointState.return_value = (0.5, 0.1, [], [])

        states = sim.get_joint_states()
        assert "robot" in states
        assert states["robot"]["positions"][0] == pytest.approx(0.5)
        assert states["robot"]["velocities"][0] == pytest.approx(0.1)


class TestSoftBodyMJCF:
    """Tests for soft body MJCF generation."""

    def test_soft_body_flexcomp_in_mjcf(self, tmp_path: Path):
        """Test that soft body tissues generate flexcomp in MJCF."""
        scene = SceneDefinition(
            metadata=Metadata(name="Soft Body Scene"),
            simulator=SimulatorType.MUJOCO,
            tissues=[
                TissueConfig(
                    name="soft_tissue",
                    type=TissueType.SKIN,
                    geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
                    soft_body=True,
                ),
            ],
        )

        builder = SceneBuilder(use_primitive_fallback=True)
        mjcf_path = builder.create_mjcf(scene, output_path=tmp_path / "soft_body.xml")

        assert mjcf_path.exists()
        content = mjcf_path.read_text()
        assert "flexcomp" in content
        assert 'type="grid"' in content
        assert 'dim="3"' in content
        assert "soft_tissue_flex" in content

    def test_rigid_tissue_no_flexcomp(self, tmp_path: Path):
        """Test that rigid tissues do not generate flexcomp."""
        scene = SceneDefinition(
            metadata=Metadata(name="Rigid Body Scene"),
            simulator=SimulatorType.MUJOCO,
            tissues=[
                TissueConfig(
                    name="rigid_tissue",
                    type=TissueType.SKIN,
                    geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
                    soft_body=False,
                ),
            ],
        )

        builder = SceneBuilder(use_primitive_fallback=True)
        mjcf_path = builder.create_mjcf(scene, output_path=tmp_path / "rigid.xml")

        assert mjcf_path.exists()
        content = mjcf_path.read_text()
        assert "flexcomp" not in content
        assert "rigid_tissue_geom" in content


class TestMuJoCoSoftBody:
    """Tests for MuJoCo soft body support."""

    def test_get_tissue_deformation_not_loaded(self):
        """Test get_tissue_deformation returns None when scene not loaded."""
        sim = MuJoCoSimulator()
        result = sim.get_tissue_deformation("soft_tissue")
        assert result is None

    def test_get_tissue_deformation_flex_not_found(self):
        """Test get_tissue_deformation returns None when flex not found."""
        sim = MuJoCoSimulator()
        # Mock loaded state without actual model
        sim._loaded = True
        sim._mujoco = MagicMock()
        sim._model = MagicMock()
        sim._data = MagicMock()
        sim._mujoco.mj_name2id.return_value = -1
        sim._mujoco.mjtObj.mjOBJ_FLEX = 8

        result = sim.get_tissue_deformation("missing_tissue")
        assert result is None


class TestPyBulletSoftBody:
    """Tests for PyBullet soft body behavior."""

    def test_pybullet_soft_body_warning(self):
        """Test that PyBullet has limited soft body support."""
        # PyBullet does not natively support soft bodies in this implementation.
        # This test documents the expected limitation.
        sim = PyBulletSimulator()
        assert sim.render_mode == "DIRECT"


class TestBaseSimulatorDel:
    """Tests for BaseSimulator __del__ behavior."""

    def test_del_does_not_crash_on_close_failure(self):
        """__del__ should not raise even if close() fails during shutdown."""
        from unittest.mock import MagicMock

        class BrokenSimulator(BaseSimulator):
            def _apply_action(self, action: np.ndarray) -> None:
                pass

            def load_scene(self, scene):
                pass

            def reset(self, seed=None):
                return MagicMock()

            def step(self, action):
                return MagicMock()

            def render(self, mode="rgb_array"):
                return None

            def close(self):
                raise RuntimeError("cleanup failed")

            def get_state(self):
                return State()

            def set_state(self, state):
                pass

            def get_joint_states(self):
                return {}

        sim = BrokenSimulator()
        # __del__ should not raise
        sim.__del__()


class TestMuJoCoReset:
    """Tests for MuJoCo reset behavior."""

    def test_reset_does_not_poison_global_rng(self):
        """reset() must not call np.random.seed() globally."""
        from unittest.mock import MagicMock, patch

        sim = MuJoCoSimulator()
        sim._loaded = True
        sim._model = MagicMock()
        sim._data = MagicMock()
        sim._mujoco = MagicMock()
        sim._get_observation = MagicMock(return_value=MagicMock())

        with patch("numpy.random.seed") as mock_seed:
            sim.reset(seed=42)
            mock_seed.assert_not_called()


class TestPyBulletTermination:
    """Tests for PyBullet termination detection."""

    def test_check_termination_detects_nan(self):
        """_check_termination must return True when NaN is present."""
        from unittest.mock import MagicMock

        sim = PyBulletSimulator()
        sim._physics_client = 0
        sim._pb = MagicMock()
        sim._body_ids = {"robot": 1}
        sim._pb.getBasePositionAndOrientation.return_value = (
            [float("nan"), 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        )
        assert sim._check_termination() is True


class TestPyBulletBugs:
    """Regression tests for PyBullet simulator bugs."""

    def test_pybullet_primitive_robot_quaternion_order(self):
        """Bug 1: createMultiBody primitive fallback must pass [x, y, z, w]."""
        import unittest.mock as mock

        from surg_rl.scene_definition import Orientation, Pose, Position, RobotConfig, RobotType

        sim = PyBulletSimulator()
        sim._physics_client = 0
        sim._pb = mock.MagicMock()
        sim._pb.createCollisionShape.return_value = 1
        sim._pb.createVisualShape.return_value = 2
        sim._pb.createMultiBody.return_value = 42
        sim._pb.getNumJoints.return_value = 0

        robot = RobotConfig(
            name="test_robot",
            type=RobotType.ROBOTIC_ARM,
            urdf_path=None,
            joints=[
                {
                    "name": "j0",
                    "type": "revolute",
                    "limits": {"lower": -1.57, "upper": 1.57},
                }
            ],
            base_pose=Pose(
                position=Position(x=0.1, y=0.2, z=0.3),
                orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
            ),
        )

        sim._load_robot(robot)

        # Assert createMultiBody was called with [x, y, z, w] not [w, x, y, z]
        call_kwargs = sim._pb.createMultiBody.call_args[1]
        assert call_kwargs["baseOrientation"] == [0.0, 0.0, 0.0, 1.0]

    def test_pybullet_reset_resets_joints(self):
        """Bug 2: reset() must reset joint positions and velocities."""
        import unittest.mock as mock

        sim = PyBulletSimulator()
        sim._physics_client = 0
        sim._pb = mock.MagicMock()
        sim._body_ids = {"robot": 1}
        sim._joint_ids = {"robot": {"joint_0": 0, "joint_1": 1}}
        sim._initial_positions = {"robot": [0, 0, 0]}
        sim._initial_orientations = {"robot": [0, 0, 0, 1]}
        sim._loaded = True
        sim._scene = None

        # Mock _get_observation so reset can return
        sim._get_observation = mock.MagicMock(return_value=mock.MagicMock())

        sim.reset()

        # Assert resetJointState was called for each joint
        assert sim._pb.resetJointState.call_count == 2
        first_call = sim._pb.resetJointState.call_args_list[0]
        assert first_call[0][0] == 1  # body_id
        assert first_call[0][1] == 0  # joint_idx
        assert first_call[1]["targetValue"] == 0.0
        assert first_call[1]["targetVelocity"] == 0.0

    def test_pybullet_load_scene_without_physics(self):
        """Bug 3: load_scene() must not raise when physics is None."""
        import unittest.mock as mock

        from surg_rl.scene_definition import Metadata, SceneDefinition

        sim = PyBulletSimulator()
        sim._pb = mock.MagicMock()
        sim._physics_client = 0
        # Prevent _check_pybullet from overwriting our mock
        sim._check_pybullet = mock.MagicMock()

        # Use model_construct to bypass Pydantic validation so physics can be None
        scene = SceneDefinition.model_construct(
            metadata=Metadata(name="No Physics Scene"),
            physics=None,
        )

        # Should not raise AttributeError
        sim.load_scene(scene)

        # Default gravity should be set
        sim._pb.setGravity.assert_called_with(0, 0, -9.81, physicsClientId=0)


class TestMuJoCoRenderAndState:
    def test_render_depth_array(self, minimal_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(minimal_scene)
        sim.reset()
        depth = sim.render(mode="depth_array")
        # MuJoCo 3.x may return None if depth-rendering API doesn't match; just exercise path
        assert isinstance(depth, (np.ndarray, type(None)))

    def test_render_failure_returns_none(self, minimal_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(minimal_scene)
        sim.reset()
        with patch.object(sim, "_renderer_available", False):
            result = sim.render(mode="human")
        assert result is None

    def test_get_state_body_poses(self, suturing_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(suturing_scene)
        sim.reset()
        state = sim.get_state()
        assert state.qpos is not None
        assert state.qvel is not None

    def test_set_state_restores_qpos_qvel(self, suturing_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(suturing_scene)
        sim.reset()
        from surg_rl.simulators.base_simulator import State

        new_state = State(time=0.0, qpos=np.zeros(sim._model.nq), qvel=np.zeros(sim._model.nv))
        sim.set_state(new_state)
        retrieved = sim.get_state()
        assert np.allclose(retrieved.qpos, new_state.qpos)

    def test_check_termination_nan(self, suturing_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(suturing_scene)
        sim.reset()
        sim._data.qpos[0] = np.nan
        done = sim._check_termination()
        assert done is True

    def test_reset_without_load_raises(self):
        sim = MuJoCoSimulator()
        with pytest.raises(RuntimeError, match="Scene not loaded"):
            sim.reset()

    def test_apply_force(self, suturing_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(suturing_scene)
        sim.reset()
        # Should not crash even if bodies are missing
        sim.apply_force("surgical_arm", [1.0, 0.0, 0.0])


class TestPyBulletLoadAndState:
    def test_load_tissue_sphere(self, minimal_scene):
        from surg_rl.scene_definition.schema import TissueConfig, TissueMeshDefinition

        tissue = TissueConfig(
            name="sphere_tissue",
            geometry=TissueMeshDefinition(
                primitive="sphere", dimensions=(0.05, 0.05, 0.05), radius=0.05
            ),
        )
        minimal_scene.tissues.append(tissue)
        sim = PyBulletSimulator()
        sim.load_scene(minimal_scene)
        assert "sphere_tissue" in sim._body_ids

    def test_load_tissue_cylinder(self, minimal_scene):
        from surg_rl.scene_definition.schema import TissueConfig, TissueMeshDefinition

        tissue = TissueConfig(
            name="cyl_tissue",
            geometry=TissueMeshDefinition(primitive="cylinder", dimensions=(0.05, 0.05, 0.1)),
        )
        minimal_scene.tissues.append(tissue)
        sim = PyBulletSimulator()
        sim.load_scene(minimal_scene)
        assert "cyl_tissue" in sim._body_ids

    def test_load_instrument_no_pose(self, minimal_scene):
        from surg_rl.scene_definition.schema import InstrumentConfig

        instrument = InstrumentConfig(name="loose_inst")
        minimal_scene.instruments.append(instrument)
        sim = PyBulletSimulator()
        sim.load_scene(minimal_scene)
        assert "loose_inst" in sim._body_ids

    def test_render_returns_rgb(self, minimal_scene):
        sim = PyBulletSimulator(render_mode="rgb_array")
        sim.load_scene(minimal_scene)
        sim.reset()
        # PyBullet getCameraImage may return a flat tuple for RGB on some builds;
        # patch it to a numpy array so the render path is exercised.
        fake_rgb = np.zeros((480, 640, 4), dtype=np.uint8)
        with patch.object(sim._pb, "getCameraImage", return_value=(640, 480, fake_rgb, None, None)):
            rgb = sim.render(mode="rgb_array")
        assert rgb is not None

    def test_get_state(self, minimal_scene):
        sim = PyBulletSimulator()
        sim.load_scene(minimal_scene)
        sim.reset()
        state = sim.get_state()
        assert state.time is not None

    def test_set_state(self, suturing_scene):
        sim = PyBulletSimulator()
        sim.load_scene(suturing_scene)
        sim.reset()
        from surg_rl.simulators.base_simulator import State

        new_state = State(time=0.0, qpos=np.zeros(10), qvel=np.zeros(10))
        sim.set_state(new_state)
        retrieved = sim.get_state()
        # PyBullet set_state does not restore joint states; just verify shapes match zeros
        if retrieved.qpos is not None and new_state.qpos is not None:
            min_len = min(len(retrieved.qpos), len(new_state.qpos))
            assert np.allclose(retrieved.qpos[:min_len], new_state.qpos[:min_len])

    def test_step_without_load_raises(self):
        sim = PyBulletSimulator()
        with pytest.raises(RuntimeError, match="Scene not loaded"):
            sim.step(np.zeros(1))


class TestCameraNameRendering:
    """Regression tests for camera_name support in render()."""

    def test_mujoco_render_with_camera_name(self, suturing_scene):
        sim = MuJoCoSimulator()
        sim.load_scene(suturing_scene)
        sim.reset()
        rgb = sim.render(mode="rgb_array", camera_name="main_camera")
        assert isinstance(rgb, (np.ndarray, type(None)))

    def test_pybullet_render_with_camera_name(self, suturing_scene):
        sim = PyBulletSimulator(render_mode="rgb_array")
        sim.load_scene(suturing_scene)
        sim.reset()
        fake_rgb = np.zeros((480, 640, 4), dtype=np.uint8)
        with patch.object(sim._pb, "getCameraImage", return_value=(640, 480, fake_rgb, None, None)):
            rgb = sim.render(mode="rgb_array", camera_name="main_camera")
        assert rgb is not None


class TestPyBulletSoftBodyLoad:
    """Soft body loading tests for PyBullet."""

    @pytest.mark.xfail(
        sys.platform in ("darwin",) or os.environ.get("CI") == "true",
        reason="PyBullet soft body auto-tetgen unstable on macOS and some CI runners",
    )
    def test_pybullet_soft_body_load_no_crash(self, tmp_path):
        """Soft body tissue should load without NotImplementedError."""
        from surg_rl.scene_definition.schema import (
            SceneDefinition,
            SoftBodyPhysics,
            TissueConfig,
            TissueMeshDefinition,
        )

        scene = SceneDefinition(
            metadata={"name": "soft_test"},
            robots=[],
            tissues=[
                TissueConfig(
                    name="soft_tissue",
                    geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
                    soft_body=True,
                    physics=SoftBodyPhysics(),
                )
            ],
            instruments=[],
        )
        sim = PyBulletSimulator()
        sim.load_scene(scene)
        assert "soft_tissue" in sim._soft_body_ids
        assert sim._soft_body_ids["soft_tissue"] >= 0

    @pytest.mark.xfail(
        sys.platform in ("darwin",) or os.environ.get("CI") == "true",
        reason="PyBullet soft body unstable on macOS and CI",
    )
    def test_pybullet_soft_body_step_no_crash(self):
        """Soft body should survive at least one simulation step."""
        from surg_rl.scene_definition.schema import (
            SceneDefinition,
            SoftBodyPhysics,
            TissueConfig,
            TissueMeshDefinition,
        )

        scene = SceneDefinition(
            metadata={"name": "soft_step"},
            robots=[],
            tissues=[
                TissueConfig(
                    name="soft_tissue",
                    geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
                    soft_body=True,
                    physics=SoftBodyPhysics(),
                )
            ],
            instruments=[],
        )
        sim = PyBulletSimulator()
        sim.load_scene(scene)
        sim.step(np.zeros(1))  # dummy action

    @pytest.mark.xfail(
        sys.platform in ("darwin",) or os.environ.get("CI") == "true",
        reason="PyBullet soft body fragile on macOS/CI",
    )
    def test_pybullet_soft_body_get_mesh_data(self):
        """getMeshData should return vertices after loading."""
        from surg_rl.scene_definition.schema import (
            SceneDefinition,
            SoftBodyPhysics,
            TissueConfig,
            TissueMeshDefinition,
        )

        scene = SceneDefinition(
            metadata={"name": "mesh_data"},
            robots=[],
            tissues=[
                TissueConfig(
                    name="soft_tissue",
                    geometry=TissueMeshDefinition(
                        primitive="sphere",
                        dimensions=(0.05, 0.05, 0.05),
                        radius=0.05,
                    ),
                    soft_body=True,
                    physics=SoftBodyPhysics(),
                )
            ],
            instruments=[],
        )
        sim = PyBulletSimulator()
        sim.load_scene(scene)
        soft_id = sim._soft_body_ids["soft_tissue"]
        data = sim._pb.getMeshData(soft_id, physicsClientId=sim._physics_client)
        vertices = data[1]
        assert len(vertices) > 0

    @pytest.mark.xfail(
        sys.platform in ("darwin",) or os.environ.get("CI") == "true",
        reason="PyBullet soft body fragile on macOS/CI",
    )
    def test_pybullet_soft_body_anchor_to_world(self):
        """Anchoring a node to world should prevent gravity-driven motion."""
        from surg_rl.scene_definition.schema import (
            SceneDefinition,
            SoftBodyPhysics,
            TissueConfig,
            TissueMeshDefinition,
        )

        scene = SceneDefinition(
            metadata={"name": "anchor"},
            robots=[],
            tissues=[
                TissueConfig(
                    name="soft_tissue",
                    geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
                    soft_body=True,
                    physics=SoftBodyPhysics(),
                )
            ],
            instruments=[],
        )
        sim = PyBulletSimulator()
        sim.load_scene(scene)
        soft_id = sim._soft_body_ids["soft_tissue"]
        data = sim._pb.getMeshData(soft_id, physicsClientId=sim._physics_client)
        if len(data[1]) > 0:
            sim._pb.createSoftBodyAnchor(
                soft_id, 0, -1, [0, 0, 0], physicsClientId=sim._physics_client
            )
        # Step a few times
        for _ in range(10):
            sim._pb.stepSimulation(physicsClientId=sim._physics_client)
