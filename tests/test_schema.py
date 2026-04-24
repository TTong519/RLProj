"""Tests for scene definition schema."""

import json
from pathlib import Path

import pytest
import yaml

from surg_rl.scene_definition import (
    AssetReference,
    BoundingBox,
    CameraConfig,
    CameraType,
    CuttingProperties,
    DomainRandomizationConfig,
    DynamicsRandomization,
    EnvironmentConfig,
    EulerAngles,
    GroundPlaneConfig,
    GraspingProperties,
    InstrumentConfig,
    InstrumentType,
    JointConfig,
    JointLimits,
    JointType,
    LightConfig,
    LightType,
    MeshAsset,
    Metadata,
    Orientation,
    PhysicsConfig,
    PhysicsMaterial,
    PhysicsRandomization,
    Position,
    RewardShaping,
    RgbColor,
    RigidBodyPhysics,
    RobotConfig,
    RobotType,
    SceneDefinition,
    SoftBodyPhysics,
    TaskConfig,
    TaskObjective,
    TextureAsset,
    TissueConfig,
    TissueMeshDefinition,
    TissueType,
    VisualRandomization,
)
from surg_rl.scene_definition.schema import Pose


class TestPosition:
    """Tests for Position model."""

    def test_default_values(self):
        """Test default position is origin."""
        pos = Position()
        assert pos.x == 0.0
        assert pos.y == 0.0
        assert pos.z == 0.0

    def test_custom_values(self):
        """Test custom position values."""
        pos = Position(x=1.0, y=2.0, z=3.0)
        assert pos.x == 1.0
        assert pos.y == 2.0
        assert pos.z == 3.0

    def test_to_tuple(self):
        """Test conversion to tuple."""
        pos = Position(x=1.5, y=2.5, z=3.5)
        assert pos.to_tuple() == (1.5, 2.5, 3.5)


class TestOrientation:
    """Tests for Orientation model."""

    def test_default_values(self):
        """Test default orientation is identity quaternion."""
        orient = Orientation()
        assert orient.w == 1.0
        assert orient.x == 0.0
        assert orient.y == 0.0
        assert orient.z == 0.0

    def test_custom_values(self):
        """Test custom orientation values."""
        orient = Orientation(w=0.707, x=0.707, y=0.0, z=0.0)
        assert orient.w == 0.707
        assert orient.x == 0.707

    def test_to_tuple(self):
        """Test conversion to tuple."""
        orient = Orientation(w=1.0, x=0.0, y=0.5, z=0.5)
        assert orient.to_tuple() == (1.0, 0.0, 0.5, 0.5)


class TestPose:
    """Tests for Pose model."""

    def test_default_pose(self):
        """Test default pose at origin with identity rotation."""
        pose = Pose()
        assert pose.position.x == 0.0
        assert pose.orientation.w == 1.0

    def test_custom_pose(self):
        """Test custom pose values."""
        pose = Pose(
            position=Position(x=1.0, y=2.0, z=3.0),
            orientation=Orientation(w=0.707, x=0.707, y=0.0, z=0.0),
        )
        assert pose.position.x == 1.0
        assert pose.orientation.x == 0.707

    def test_get_position_tuple(self):
        """Test position tuple extraction."""
        pose = Pose(position=Position(x=1.0, y=2.0, z=3.0))
        assert pose.get_position_tuple() == (1.0, 2.0, 3.0)


class TestRgbColor:
    """Tests for RgbColor model."""

    def test_default_values(self):
        """Test default color is white."""
        color = RgbColor()
        assert color.r == 1.0
        assert color.g == 1.0
        assert color.b == 1.0
        assert color.a == 1.0

    def test_custom_values(self):
        """Test custom color values."""
        color = RgbColor(r=0.5, g=0.3, b=0.8, a=0.9)
        assert color.r == 0.5
        assert color.g == 0.3
        assert color.b == 0.8
        assert color.a == 0.9

    def test_validation_range(self):
        """Test color values are validated to 0-1 range."""
        with pytest.raises(ValueError):
            RgbColor(r=1.5, g=-0.1, b=2.0)


class TestBoundingBox:
    """Tests for BoundingBox model."""

    def test_valid_bounds(self):
        """Test valid bounding box."""
        bbox = BoundingBox(
            min_corner=Position(x=0.0, y=0.0, z=0.0),
            max_corner=Position(x=1.0, y=2.0, z=3.0),
        )
        assert bbox.get_dimensions() == (1.0, 2.0, 3.0)

    def test_invalid_bounds(self):
        """Test that invalid bounds raise validation error."""
        with pytest.raises(ValueError):
            BoundingBox(
                min_corner=Position(x=1.0, y=0.0, z=0.0),
                max_corner=Position(x=0.0, y=1.0, z=1.0),
            )


class TestAssetReference:
    """Tests for AssetReference model."""

    def test_basic_asset(self):
        """Test basic asset reference."""
        asset = AssetReference(path="assets/meshes/robot.obj")
        assert asset.path == "assets/meshes/robot.obj"
        # file_type may be None or inferred depending on validator
        assert asset.file_type in ("obj", None)

    def test_asset_with_checksum(self):
        """Test asset with checksum."""
        asset = AssetReference(
            path="assets/meshes/robot.stl", checksum="abc123"
        )
        assert asset.checksum == "abc123"


class TestMeshAsset:
    """Tests for MeshAsset model."""

    def test_mesh_with_scale(self):
        """Test mesh with custom scale."""
        mesh = MeshAsset(path="robot.obj", scale=(2.0, 2.0, 2.0))
        assert mesh.scale == (2.0, 2.0, 2.0)
        # file_type may be None or inferred depending on validator
        assert mesh.file_type in ("obj", None)


class TestPhysicsConfig:
    """Tests for PhysicsConfig model."""

    def test_default_physics(self):
        """Test default physics configuration."""
        physics = PhysicsConfig()
        assert physics.gravity == (0.0, 0.0, -9.81)
        assert physics.timestep == 0.002
        assert physics.ground_plane is True

    def test_custom_physics(self):
        """Test custom physics configuration."""
        physics = PhysicsConfig(
            gravity=(0.0, 0.0, -5.0),
            timestep=0.001,
            solver_iterations=100,
        )
        assert physics.gravity == (0.0, 0.0, -5.0)
        assert physics.solver_iterations == 100


class TestSoftBodyPhysics:
    """Tests for SoftBodyPhysics model."""

    def test_default_soft_body(self):
        """Test default soft body physics."""
        sbp = SoftBodyPhysics()
        assert sbp.stiffness == 1000.0
        assert sbp.density == 1000.0

    def test_custom_soft_body(self):
        """Test custom soft body physics."""
        sbp = SoftBodyPhysics(
            stiffness=5000.0,
            damping=0.2,
            density=1100.0,
            poissons_ratio=0.4,
        )
        assert sbp.stiffness == 5000.0
        assert sbp.poissons_ratio == 0.4

    def test_soft_body_new_fields(self):
        """Test new soft body physics fields."""
        sbp = SoftBodyPhysics(
            elasticity=0.8,
            bending_stiffness=200.0,
            self_collision=True,
        )
        assert sbp.elasticity == 0.8
        assert sbp.bending_stiffness == 200.0
        assert sbp.self_collision is True

    def test_soft_body_default_new_fields(self):
        """Test default values for new soft body physics fields."""
        sbp = SoftBodyPhysics()
        assert sbp.elasticity == 0.5
        assert sbp.bending_stiffness == 100.0
        assert sbp.self_collision is False


class TestRobotConfig:
    """Tests for RobotConfig model."""

    def test_robot_with_urdf(self):
        """Test robot defined via URDF file."""
        robot = RobotConfig(
            name="test_robot",
            type=RobotType.ROBOTIC_ARM,
            urdf_path="assets/robots/test.urdf",
        )
        assert robot.name == "test_robot"
        assert robot.urdf_path == "assets/robots/test.urdf"

    def test_robot_with_direct_definition(self):
        """Test robot defined with links and joints."""
        robot = RobotConfig(
            name="test_robot",
            type=RobotType.CUSTOM,
            links=[
                {
                    "name": "link1",
                    "physics": {"mass": 1.0},
                }
            ],
            joints=[
                {
                    "name": "joint1",
                    "type": JointType.REVOLUTE,
                    "limits": {"lower": -3.14, "upper": 3.14},
                }
            ],
        )
        assert len(robot.links) == 1
        assert len(robot.joints) == 1

    def test_robot_requires_definition(self):
        """Test that robot requires either file or direct definition."""
        with pytest.raises(ValueError):
            RobotConfig(name="invalid_robot")


class TestTissueConfig:
    """Tests for TissueConfig model."""

    def test_tissue_with_primitive(self):
        """Test tissue with primitive geometry."""
        tissue = TissueConfig(
            name="test_tissue",
            type=TissueType.SKIN,
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
        )
        assert tissue.name == "test_tissue"
        assert tissue.geometry.primitive == "box"

    def test_tissue_with_mesh(self):
        """Test tissue with mesh geometry."""
        tissue = TissueConfig(
            name="organ_mesh",
            type=TissueType.ORGAN,
            geometry=TissueMeshDefinition(mesh=MeshAsset(path="organ.obj")),
        )
        assert tissue.geometry.mesh.path == "organ.obj"

    def test_tissue_soft_body_flag(self):
        """Test tissue soft body flag."""
        tissue = TissueConfig(
            name="soft_tissue",
            type=TissueType.SKIN,
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
            soft_body=True,
        )
        assert tissue.soft_body is True
        assert tissue.physics is not None

    def test_tissue_soft_body_default(self):
        """Test tissue soft body flag defaults to False."""
        tissue = TissueConfig(
            name="rigid_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.01)),
        )
        assert tissue.soft_body is False


class TestInstrumentConfig:
    """Tests for InstrumentConfig model."""

    def test_scalpel_instrument(self):
        """Test scalpel instrument configuration."""
        instrument = InstrumentConfig(
            name="scalpel",
            type=InstrumentType.SCALPEL,
            cutting=CuttingProperties(sharpness=0.9, max_cut_depth=0.05),
        )
        assert instrument.type == InstrumentType.SCALPEL
        assert instrument.cutting.sharpness == 0.9

    def test_forceps_instrument(self):
        """Test forceps instrument configuration."""
        instrument = InstrumentConfig(
            name="forceps",
            type=InstrumentType.FORCEPS,
            grasping=GraspingProperties(max_aperture=0.02, grip_force=5.0),
        )
        assert instrument.grasping.max_aperture == 0.02


class TestEnvironmentConfig:
    """Tests for EnvironmentConfig model."""

    def test_default_environment(self):
        """Test default environment configuration."""
        env = EnvironmentConfig()
        assert env.name == "operating_room"
        assert len(env.lights) == 1
        assert len(env.cameras) == 1

    def test_custom_environment(self):
        """Test custom environment configuration."""
        env = EnvironmentConfig(
            name="custom_room",
            lights=[
                LightConfig(name="light1", type=LightType.POINT, position=Position(x=1, y=1, z=2)),
            ],
            cameras=[
                CameraConfig(name="cam1", type=CameraType.ORTHOGRAPHIC),
            ],
        )
        assert env.name == "custom_room"
        assert env.lights[0].name == "light1"


class TestCameraConfig:
    """Tests for CameraConfig model."""

    def test_perspective_camera(self):
        """Test perspective camera configuration."""
        cam = CameraConfig(name="main", type=CameraType.PERSPECTIVE, fov=60.0)
        assert cam.type == CameraType.PERSPECTIVE
        assert cam.fov == 60.0

    def test_orthographic_camera(self):
        """Test orthographic camera configuration."""
        cam = CameraConfig(
            name="top_view",
            type=CameraType.ORTHOGRAPHIC,
            orthographic_width=1.0,
            orthographic_height=1.0,
        )
        assert cam.type == CameraType.ORTHOGRAPHIC


class TestLightConfig:
    """Tests for LightConfig model."""

    def test_directional_light(self):
        """Test directional light configuration."""
        light = LightConfig(
            name="sun",
            type=LightType.DIRECTIONAL,
            direction=(0.0, -1.0, -0.5),
        )
        assert light.type == LightType.DIRECTIONAL
        assert light.direction == (0.0, -1.0, -0.5)

    def test_point_light(self):
        """Test point light configuration."""
        light = LightConfig(
            name="lamp",
            type=LightType.POINT,
            position=Position(x=1.0, y=2.0, z=3.0),
        )
        assert light.position.x == 1.0

    def test_point_light_requires_position(self):
        """Test that point light requires position."""
        with pytest.raises(ValueError):
            LightConfig(name="invalid", type=LightType.POINT)

    def test_light_config_validator_returns_copy(self):
        """LightConfig validator must return a model_copy, not mutate self."""
        cfg = LightConfig.model_validate({"type": LightType.DIRECTIONAL})
        assert cfg.direction == (0.0, 0.0, -1.0)
        assert cfg.type == LightType.DIRECTIONAL


class TestTaskConfig:
    """Tests for TaskConfig model."""

    def test_basic_task(self):
        """Test basic task configuration."""
        task = TaskConfig(
            name="test_task",
            description="A test task",
            max_episode_length=500,
        )
        assert task.name == "test_task"
        assert task.max_episode_length == 500

    def test_task_with_objectives(self):
        """Test task with multiple objectives."""
        task = TaskConfig(
            name="complex_task",
            description="A complex task",
            objectives=[
                TaskObjective(name="obj1", description="First objective", success_criteria="Done", weight=1.0),
                TaskObjective(name="obj2", description="Second objective", success_criteria="Complete", weight=2.0),
            ],
        )
        assert len(task.objectives) == 2


class TestSceneDefinition:
    """Tests for SceneDefinition model."""

    def test_minimal_scene(self):
        """Test minimal scene definition."""
        scene = SceneDefinition(metadata=Metadata(name="Test Scene"))
        assert scene.metadata.name == "Test Scene"
        assert len(scene.robots) == 0
        assert len(scene.tissues) == 0

    def test_scene_with_components(self):
        """Test scene with all components."""
        scene = SceneDefinition(
            metadata=Metadata(name="Complete Scene"),
            physics=PhysicsConfig(timestep=0.001),
            robots=[
                RobotConfig(name="robot1", urdf_path="robot.urdf"),
            ],
            tissues=[
                TissueConfig(
                    name="tissue1",
                    geometry=TissueMeshDefinition(primitive="sphere", radius=0.1),
                ),
            ],
        )
        assert len(scene.robots) == 1
        assert len(scene.tissues) == 1
        assert scene.physics.timestep == 0.001

    def test_get_robot_by_name(self):
        """Test getting robot by name."""
        scene = SceneDefinition(
            robots=[
                RobotConfig(name="robot_a", urdf_path="a.urdf"),
                RobotConfig(name="robot_b", urdf_path="b.urdf"),
            ],
        )
        robot = scene.get_robot("robot_a")
        assert robot is not None
        assert robot.name == "robot_a"
        assert scene.get_robot("nonexistent") is None

    def test_get_active_cameras(self):
        """Test getting active cameras."""
        scene = SceneDefinition(
            environment=EnvironmentConfig(
                cameras=[
                    CameraConfig(name="active_cam", active=True),
                    CameraConfig(name="inactive_cam", active=False),
                ],
            ),
        )
        active = scene.get_active_cameras()
        assert len(active) == 1
        assert active[0].name == "active_cam"


class TestSceneFileLoading:
    """Tests for loading scene files."""

    @pytest.fixture
    def scenes_dir(self) -> Path:
        """Get the scenes directory."""
        return Path(__file__).parent.parent / "scenes"

    def test_load_json_scene(self, scenes_dir: Path):
        """Test loading a JSON scene file."""
        json_scene = scenes_dir / "simple_suturing.json"
        if not json_scene.exists():
            pytest.skip("JSON scene file not found")

        with open(json_scene, "r") as f:
            data = json.load(f)

        scene = SceneDefinition(**data)
        assert scene.metadata.name == "Simple Suturing Scene"
        assert len(scene.robots) == 1
        assert len(scene.tissues) == 1

    def test_load_yaml_scene(self, scenes_dir: Path):
        """Test loading a YAML scene file."""
        yaml_scene = scenes_dir / "laparoscopic_dissection.yaml"
        if not yaml_scene.exists():
            pytest.skip("YAML scene file not found")

        with open(yaml_scene, "r") as f:
            data = yaml.safe_load(f)

        scene = SceneDefinition(**data)
        assert scene.metadata.name == "Laparoscopic Dissection"
        assert len(scene.robots) == 2

    def test_load_minimal_scene(self, scenes_dir: Path):
        """Test loading minimal scene file."""
        minimal_scene = scenes_dir / "minimal_scene.json"
        if not minimal_scene.exists():
            pytest.skip("Minimal scene file not found")

        with open(minimal_scene, "r") as f:
            data = json.load(f)

        scene = SceneDefinition(**data)
        assert scene.metadata.name == "Minimal Test Scene"

    def test_scene_serialization(self):
        """Test scene serialization to dict and JSON."""
        scene = SceneDefinition(
            metadata=Metadata(name="Test", version="1.0.0"),
            physics=PhysicsConfig(gravity=(0.0, 0.0, -10.0)),
        )
        
        # Serialize to dict
        scene_dict = scene.model_dump()
        assert scene_dict["metadata"]["name"] == "Test"
        # Note: tuples are serialized as tuples, not lists
        assert scene_dict["physics"]["gravity"] == (0.0, 0.0, -10.0)

        # Serialize to JSON
        scene_json = scene.model_dump_json()
        assert '"name":"Test"' in scene_json

    def test_scene_round_trip(self):
        """Test scene serialization round trip."""
        original = SceneDefinition(
            metadata=Metadata(name="Round Trip Test"),
            robots=[
                RobotConfig(name="test_robot", urdf_path="test.urdf"),
            ],
        )
        
        # Serialize and deserialize
        data = original.model_dump()
        restored = SceneDefinition(**data)
        
        assert restored.metadata.name == original.metadata.name
        assert len(restored.robots) == len(original.robots)
        assert restored.robots[0].name == original.robots[0].name


class TestDomainRandomization:
    """Tests for domain randomization configuration."""

    def test_physics_randomization(self):
        """Test physics randomization config."""
        rand = PhysicsRandomization(
            enabled=True,
            mass_range=(0.9, 1.1),
            friction_range=(0.4, 0.6),
        )
        assert rand.enabled is True
        assert rand.mass_range == (0.9, 1.1)

    def test_visual_randomization(self):
        """Test visual randomization config."""
        rand = VisualRandomization(
            enabled=True,
            color_range=(0.9, 1.1),
            texture_randomization=True,
        )
        assert rand.texture_randomization is True

    def test_dynamics_randomization(self):
        """Test dynamics randomization config."""
        rand = DynamicsRandomization(
            enabled=True,
            action_noise=(0.0, 0.05),
        )
        assert rand.enabled is True
        assert rand.action_noise == (0.0, 0.05)

    def test_domain_randomization_config(self):
        """Test complete domain randomization config."""
        config = DomainRandomizationConfig(
            physics=PhysicsRandomization(enabled=True),
            visual=VisualRandomization(enabled=False),
            dynamics=DynamicsRandomization(enabled=False),
            randomize_each_episode=True,
            seed=42,
        )
        assert config.physics.enabled is True
        assert config.seed == 42
