"""Tests for simulator module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from surg_rl.simulators import (
    BaseSimulator,
    Observation,
    State,
    StepResult,
    SimulationStatus,
    MuJoCoSimulator,
    PyBulletSimulator,
    SceneBuilder,
    AssetMissingError,
)
from surg_rl.scene_definition import (
    SceneDefinition,
    Metadata,
    SimulatorType,
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

        resolved = builder._resolve_asset_path(str(test_file))
        assert resolved == test_file

    def test_resolve_asset_path_relative(self, tmp_path: Path):
        """Test resolving relative asset path."""
        builder = SceneBuilder(assets_dir=tmp_path)

        # Create test file
        test_file = tmp_path / "test.obj"
        test_file.write_text("mesh")

        resolved = builder._resolve_asset_path("test.obj")
        assert resolved == test_file

    def test_resolve_asset_path_not_found(self, tmp_path: Path):
        """Test resolving missing asset path."""
        builder = SceneBuilder(assets_dir=tmp_path)

        resolved = builder._resolve_asset_path("nonexistent.obj")
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


class TestBaseSimulator:
    """Tests for BaseSimulator abstract class."""

    def test_base_simulator_cannot_instantiate(self):
        """Test that BaseSimulator cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSimulator()


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
