"""Scene schema definitions using Pydantic models.

This module defines the data structures for surgical robotics scene definitions,
including robots, tissues, instruments, environment settings, and physics parameters.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Enums
# ============================================================================


class SimulatorType(str, Enum):
    """Supported simulator backends."""

    MUJOCO = "mujoco"
    PYBULLET = "pybullet"


class RobotType(str, Enum):
    """Types of surgical robots."""

    DAVINCI = "davinci"
    LAPAROSCOPIC = "laparoscopic"
    ROBOTIC_ARM = "robotic_arm"
    CUSTOM = "custom"


class TissueType(str, Enum):
    """Types of tissue/organ models."""

    SKIN = "skin"
    MUSCLE = "muscle"
    ORGAN = "organ"
    VESSEL = "vessel"
    FAT = "fat"
    CARTILAGE = "cartilage"
    BONE = "bone"
    CUSTOM = "custom"


class InstrumentType(str, Enum):
    """Types of surgical instruments."""

    SCALPEL = "scalpel"
    FORCEPS = "forceps"
    NEEDLE_DRIVER = "needle_driver"
    SCISSORS = "scissors"
    CLAMP = "clamp"
    SUCTION = "suction"
    CAUTERY = "cautery"
    CAMERA = "camera"
    RETRACTOR = "retractor"
    CUSTOM = "custom"


class JointType(str, Enum):
    """Types of robot joints."""

    REVOLUTE = "revolute"
    PRISMATIC = "prismatic"
    CONTINUOUS = "continuous"
    FIXED = "fixed"
    PLANAR = "planar"
    SPHERICAL = "spherical"


class CameraType(str, Enum):
    """Types of camera configurations."""

    PERSPECTIVE = "perspective"
    ORTHOGRAPHIC = "orthographic"


class LightType(str, Enum):
    """Types of light sources."""

    POINT = "point"
    DIRECTIONAL = "directional"
    SPOTLIGHT = "spotlight"
    AMBIENT = "ambient"


# ============================================================================
# Base Models
# ============================================================================


class Position(BaseModel):
    """3D position coordinates."""

    x: float = Field(default=0.0, description="X coordinate in meters")
    y: float = Field(default=0.0, description="Y coordinate in meters")
    z: float = Field(default=0.0, description="Z coordinate in meters")

    def to_tuple(self) -> Tuple[float, float, float]:
        """Convert to tuple representation."""
        return (self.x, self.y, self.z)


class Orientation(BaseModel):
    """Quaternion orientation representation."""

    w: float = Field(default=1.0, description="Quaternion w component")
    x: float = Field(default=0.0, description="Quaternion x component")
    y: float = Field(default=0.0, description="Quaternion y component")
    z: float = Field(default=0.0, description="Quaternion z component")

    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to tuple representation."""
        return (self.w, self.x, self.y, self.z)


class EulerAngles(BaseModel):
    """Euler angle orientation (roll, pitch, yaw) in radians."""

    roll: float = Field(default=0.0, description="Roll angle in radians")
    pitch: float = Field(default=0.0, description="Pitch angle in radians")
    yaw: float = Field(default=0.0, description="Yaw angle in radians")

    def to_tuple(self) -> Tuple[float, float, float]:
        """Convert to tuple representation."""
        return (self.roll, self.pitch, self.yaw)


class Pose(BaseModel):
    """6-DOF pose combining position and orientation."""

    position: Position = Field(default_factory=Position, description="Position in 3D space")
    orientation: Orientation = Field(
        default_factory=Orientation, description="Quaternion orientation"
    )

    def get_position_tuple(self) -> Tuple[float, float, float]:
        """Get position as tuple."""
        return self.position.to_tuple()

    def get_orientation_tuple(self) -> Tuple[float, float, float, float]:
        """Get orientation as tuple."""
        return self.orientation.to_tuple()


class RgbColor(BaseModel):
    """RGB color representation."""

    r: float = Field(default=1.0, ge=0.0, le=1.0, description="Red component (0-1)")
    g: float = Field(default=1.0, ge=0.0, le=1.0, description="Green component (0-1)")
    b: float = Field(default=1.0, ge=0.0, le=1.0, description="Blue component (0-1)")
    a: float = Field(default=1.0, ge=0.0, le=1.0, description="Alpha component (0-1)")

    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to RGBA tuple."""
        return (self.r, self.g, self.b, self.a)


class BoundingBox(BaseModel):
    """Axis-aligned bounding box."""

    min_corner: Position = Field(description="Minimum corner of bounding box")
    max_corner: Position = Field(description="Maximum corner of bounding box")

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundingBox":
        """Ensure min <= max for all dimensions."""
        if self.min_corner.x > self.max_corner.x:
            raise ValueError("min_corner.x must be <= max_corner.x")
        if self.min_corner.y > self.max_corner.y:
            raise ValueError("min_corner.y must be <= max_corner.y")
        if self.min_corner.z > self.max_corner.z:
            raise ValueError("min_corner.z must be <= max_corner.z")
        return self

    def get_dimensions(self) -> Tuple[float, float, float]:
        """Get bounding box dimensions (width, height, depth)."""
        return (
            self.max_corner.x - self.min_corner.x,
            self.max_corner.y - self.min_corner.y,
            self.max_corner.z - self.min_corner.z,
        )


# ============================================================================
# Asset Reference
# ============================================================================


class AssetReference(BaseModel):
    """Reference to an external asset file (mesh, texture, etc.)."""

    path: str = Field(description="Path to asset file (relative or absolute)")
    file_type: Optional[str] = Field(default=None, description="File type (inferred if not set)")
    checksum: Optional[str] = Field(
        default=None, description="Optional checksum for integrity verification"
    )

    @field_validator("file_type", mode="before")
    @classmethod
    def infer_file_type(cls, v: Optional[str], info) -> Optional[str]:
        """Infer file type from path if not provided."""
        if v is not None:
            return v
        if "path" in info.data:
            path = info.data["path"]
            if "." in path:
                return path.rsplit(".", 1)[-1].lower()
        return v


class MeshAsset(AssetReference):
    """Mesh asset with optional scale and material."""

    scale: Tuple[float, float, float] = Field(
        default=(1.0, 1.0, 1.0), description="Scale factors (x, y, z)"
    )
    material: Optional[str] = Field(default=None, description="Optional material reference")


class TextureAsset(AssetReference):
    """Texture asset with optional properties."""

    wrap_mode: Literal["repeat", "clamp", "mirror"] = Field(
        default="repeat", description="Texture wrap mode"
    )
    filtering: Literal["nearest", "linear"] = Field(default="linear", description="Texture filtering")


# ============================================================================
# Physics Parameters
# ============================================================================


class PhysicsMaterial(BaseModel):
    """Physics material properties for contact dynamics."""

    name: str = Field(default="default", description="Material name")
    friction: float = Field(default=0.5, ge=0.0, le=2.0, description="Friction coefficient")
    restitution: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Coefficient of restitution (bounciness)"
    )
    damping: Optional[float] = Field(
        default=None, ge=0.0, description="Contact damping coefficient"
    )


class SoftBodyPhysics(BaseModel):
    """Soft body physics parameters for tissues."""

    stiffness: float = Field(
        default=1000.0, ge=0.0, description="Material stiffness (N/m)"
    )
    damping: float = Field(default=0.1, ge=0.0, le=1.0, description="Damping ratio")
    density: float = Field(default=1000.0, ge=0.0, description="Material density (kg/m³)")
    poissons_ratio: float = Field(
        default=0.45, ge=-1.0, le=0.5, description="Poisson's ratio"
    )
    youngs_modulus: float = Field(
        default=10000.0, ge=0.0, description="Young's modulus (Pa)"
    )
    elasticity: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Elasticity factor (0-1)"
    )
    bending_stiffness: float = Field(
        default=100.0, ge=0.0, description="Bending stiffness (N·m)"
    )
    self_collision: bool = Field(
        default=False, description="Enable self-collision for soft body"
    )
    yield_stress: Optional[float] = Field(
        default=None, ge=0.0, description="Yield stress for plastic deformation"
    )
    tear_threshold: Optional[float] = Field(
        default=None, ge=0.0, description="Stress threshold for tearing"
    )
    max_deformation: Optional[float] = Field(
        default=None, ge=0.0, description="Maximum allowed deformation"
    )


class RigidBodyPhysics(BaseModel):
    """Rigid body physics parameters."""

    mass: float = Field(default=1.0, ge=0.0, description="Mass in kg")
    inertia: Optional[Tuple[float, float, float, float, float, float]] = Field(
        default=None, description="Inertia tensor (ixx, iyy, izz, ixy, ixz, iyz)"
    )
    center_of_mass: Optional[Position] = Field(
        default=None, description="Center of mass offset from geometry center"
    )
    friction: float = Field(default=0.5, ge=0.0, le=2.0, description="Friction coefficient")
    restitution: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Coefficient of restitution"
    )
    linear_damping: float = Field(default=0.0, ge=0.0, description="Linear velocity damping")
    angular_damping: float = Field(default=0.0, ge=0.0, description="Angular velocity damping")


class PhysicsConfig(BaseModel):
    """Global physics configuration for the scene."""

    gravity: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, -9.81), description="Gravity vector (m/s²)"
    )
    timestep: float = Field(
        default=0.002, ge=0.0001, le=0.1, description="Simulation timestep (seconds)"
    )
    solver_iterations: int = Field(
        default=50, ge=1, le=500, description="Constraint solver iterations"
    )
    integrator: Literal["Euler", "RK4", "implicit"] = Field(
        default="implicit", description="Integration method"
    )
    contact_model: Literal["penalty", "constraint", "soft"] = Field(
        default="constraint", description="Contact dynamics model"
    )
    air_resistance: float = Field(default=0.0, ge=0.0, description="Air resistance coefficient")
    ground_plane: bool = Field(default=True, description="Whether to include a ground plane")
    ground_friction: float = Field(default=0.8, ge=0.0, le=2.0, description="Ground friction")
    ground_restitution: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ground restitution"
    )
    materials: List[PhysicsMaterial] = Field(
        default_factory=lambda: [PhysicsMaterial()],
        description="Physics material definitions",
    )


# ============================================================================
# Robot Configuration
# ============================================================================


class JointLimits(BaseModel):
    """Joint position and velocity limits."""

    lower: float = Field(description="Lower position limit (radians or meters)")
    upper: float = Field(description="Upper position limit (radians or meters)")
    velocity: float = Field(default=2.0, ge=0.0, description="Maximum velocity")
    effort: float = Field(default=100.0, ge=0.0, description="Maximum effort/torque")


class JointConfig(BaseModel):
    """Configuration for a single robot joint."""

    name: str = Field(description="Joint name")
    type: JointType = Field(default=JointType.REVOLUTE, description="Joint type")
    limits: JointLimits = Field(description="Joint limits")
    initial_position: float = Field(default=0.0, description="Initial joint position")
    damping: float = Field(default=0.1, ge=0.0, description="Joint damping")
    friction: float = Field(default=0.0, ge=0.0, description="Joint friction")


class EndEffectorConfig(BaseModel):
    """Configuration for robot end effector."""

    name: str = Field(default="end_effector", description="End effector name")
    type: str = Field(default="gripper", description="End effector type")
    max_aperture: float = Field(default=0.05, ge=0.0, description="Maximum opening width (m)")
    force_limit: float = Field(default=10.0, ge=0.0, description="Maximum gripping force (N)")
    mesh: Optional[MeshAsset] = Field(default=None, description="Optional mesh asset")
    pose: Optional[Pose] = Field(default=None, description="Pose relative to last link")


class RobotLink(BaseModel):
    """Configuration for a robot link."""

    name: str = Field(description="Link name")
    mesh: Optional[MeshAsset] = Field(default=None, description="Link mesh")
    visual_mesh: Optional[MeshAsset] = Field(
        default=None, description="Visual-only mesh"
    )
    collision_mesh: Optional[MeshAsset] = Field(
        default=None, description="Collision-only mesh"
    )
    physics: RigidBodyPhysics = Field(
        default_factory=RigidBodyPhysics, description="Physics properties"
    )
    visual_offset: Optional[Pose] = Field(
        default=None, description="Visual offset from collision geometry"
    )


class RobotConfig(BaseModel):
    """Complete robot configuration."""

    name: str = Field(description="Robot name/identifier")
    type: RobotType = Field(default=RobotType.CUSTOM, description="Robot type")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    # URDF/mesh reference
    urdf_path: Optional[str] = Field(
        default=None, description="Path to URDF file (if using URDF)"
    )
    mujoco_xml_path: Optional[str] = Field(
        default=None, description="Path to MuJoCo XML file"
    )

    # Direct definition
    links: List[RobotLink] = Field(default_factory=list, description="Robot links")
    joints: List[JointConfig] = Field(default_factory=list, description="Robot joints")
    end_effectors: List[EndEffectorConfig] = Field(
        default_factory=list, description="End effectors"
    )

    # Pose in scene
    base_pose: Pose = Field(default_factory=Pose, description="Base frame pose")

    # Control
    control_mode: Literal["position", "velocity", "torque", "effort"] = Field(
        default="position", description="Control mode"
    )
    control_rate: float = Field(default=100.0, ge=1.0, description="Control rate (Hz)")

    # Safety
    max_linear_velocity: float = Field(
        default=0.5, ge=0.0, description="Maximum linear velocity (m/s)"
    )
    max_angular_velocity: float = Field(
        default=1.0, ge=0.0, description="Maximum angular velocity (rad/s)"
    )
    workspace_limits: Optional[BoundingBox] = Field(
        default=None, description="Allowed workspace volume"
    )

    @model_validator(mode="after")
    def validate_robot_definition(self) -> "RobotConfig":
        """Ensure robot is defined either via file or direct definition."""
        has_file = self.urdf_path is not None or self.mujoco_xml_path is not None
        has_direct = len(self.links) > 0 or len(self.joints) > 0
        if not has_file and not has_direct:
            raise ValueError(
                "Robot must be defined either via urdf_path, mujoco_xml_path, "
                "or direct links/joints definition"
            )
        return self


# ============================================================================
# Tissue Configuration
# ============================================================================


class TissueMeshDefinition(BaseModel):
    """Mesh definition for tissue geometry."""

    mesh: Optional[MeshAsset] = Field(default=None, description="External mesh file")
    primitive: Optional[Literal["box", "sphere", "cylinder", "capsule", "plane"]] = Field(
        default=None, description="Primitive shape type"
    )
    dimensions: Optional[Tuple[float, float, float]] = Field(
        default=None, description="Dimensions for primitive shapes"
    )
    radius: Optional[float] = Field(default=None, description="Radius for sphere/cylinder")
    length: Optional[float] = Field(default=None, description="Length for cylinder/capsule")

    @model_validator(mode="after")
    def validate_geometry(self) -> "TissueMeshDefinition":
        """Ensure geometry is properly defined."""
        if self.mesh is not None:
            return self
        if self.primitive is not None:
            return self
        raise ValueError("Either mesh or primitive must be specified")


class TissueAttachment(BaseModel):
    """Tissue attachment point definition."""

    name: str = Field(description="Attachment point name")
    position: Position = Field(description="Position on tissue")
    fixed: bool = Field(default=True, description="Whether attachment is fixed")
    attachment_stiffness: float = Field(
        default=0.0, ge=0.0, description="Stiffness of attachment (for non-fixed)"
    )


class TissueConfig(BaseModel):
    """Complete tissue/organ configuration."""

    name: str = Field(description="Tissue/organ name")
    type: TissueType = Field(default=TissueType.CUSTOM, description="Tissue type")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    # Geometry
    geometry: TissueMeshDefinition = Field(description="Tissue geometry definition")

    # Physics
    soft_body: bool = Field(
        default=False, description="Whether tissue uses soft body physics"
    )
    physics: SoftBodyPhysics = Field(
        default_factory=SoftBodyPhysics, description="Soft body physics"
    )

    # Pose
    pose: Pose = Field(default_factory=Pose, description="Pose in scene")

    # Attachments (fixed points)
    attachments: List[TissueAttachment] = Field(
        default_factory=list, description="Fixed attachment points"
    )

    # Visual
    color: RgbColor = Field(
        default_factory=lambda: RgbColor(r=0.9, g=0.7, b=0.7),
        description="Tissue color (RGBA)",
    )
    texture: Optional[TextureAsset] = Field(default=None, description="Texture asset")

    # Medical properties
    anatomical_region: Optional[str] = Field(
        default=None, description="Anatomical region (e.g., 'abdomen', 'thorax')"
    )
    pathology: Optional[str] = Field(
        default=None, description="Pathological condition (if any)"
    )
    vitality: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Tissue health indicator"
    )


# ============================================================================
# Instrument Configuration
# ============================================================================


class InstrumentPhysics(BaseModel):
    """Physics properties for surgical instruments."""

    mass: float = Field(default=0.1, ge=0.0, description="Mass in kg")
    inertia_tensor: Optional[Tuple[float, float, float, float, float, float]] = Field(
        default=None, description="Inertia tensor components"
    )
    friction: float = Field(default=0.3, ge=0.0, le=1.0, description="Surface friction")
    damping: float = Field(default=0.05, ge=0.0, description="Movement damping")
    stiffness: float = Field(default=1e6, ge=0.0, description="Contact stiffness")


class CuttingProperties(BaseModel):
    """Properties for cutting instruments (scalpel, scissors, etc.)."""

    sharpness: float = Field(default=0.8, ge=0.0, le=1.0, description="Cutting edge sharpness")
    max_cut_depth: float = Field(default=0.02, ge=0.0, description="Maximum cut depth (m)")
    cutting_force: float = Field(default=1.0, ge=0.0, description="Required cutting force (N)")


class GraspingProperties(BaseModel):
    """Properties for grasping instruments (forceps, clamps, etc.)."""

    max_aperture: float = Field(default=0.02, ge=0.0, description="Maximum jaw opening (m)")
    grip_force: float = Field(default=5.0, ge=0.0, description="Maximum grip force (N)")
    jaw_angle: float = Field(default=30.0, ge=0.0, le=180.0, description="Jaw angle (degrees)")


class NeedleDriverProperties(BaseModel):
    """Properties for needle drivers."""

    compatible_needle_sizes: List[float] = Field(
        default_factory=lambda: [0.02, 0.03, 0.04],
        description="Compatible needle diameters (m)",
    )
    grip_force: float = Field(default=10.0, ge=0.0, description="Needle grip force (N)")
    rotation_range: Tuple[float, float] = Field(
        default=(-180.0, 180.0), description="Rotation range (degrees)"
    )


class InstrumentConfig(BaseModel):
    """Complete surgical instrument configuration."""

    name: str = Field(description="Instrument name/identifier")
    type: InstrumentType = Field(default=InstrumentType.CUSTOM, description="Instrument type")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    # Geometry
    mesh: Optional[MeshAsset] = Field(default=None, description="Instrument mesh")
    primitive: Optional[Literal["box", "sphere", "cylinder", "capsule"]] = Field(
        default=None, description="Primitive shape"
    )
    dimensions: Tuple[float, float, float] = Field(
        default=(0.01, 0.01, 0.1), description="Dimensions for primitive shapes"
    )

    # Physics
    physics: InstrumentPhysics = Field(
        default_factory=InstrumentPhysics, description="Physics properties"
    )

    # Type-specific properties
    cutting: Optional[CuttingProperties] = Field(
        default=None, description="Cutting properties (for cutting instruments)"
    )
    grasping: Optional[GraspingProperties] = Field(
        default=None, description="Grasping properties (for graspers)"
    )
    needle_driver: Optional[NeedleDriverProperties] = Field(
        default=None, description="Needle driver properties"
    )

    # Initial pose (if placed in scene)
    pose: Optional[Pose] = Field(default=None, description="Initial pose in scene")

    # Tool tips and interaction points
    tip_offset: Position = Field(
        default_factory=lambda: Position(x=0, y=0, z=0),
        description="Offset from center to tool tip",
    )

    # Sterilization and safety
    sterile: bool = Field(default=True, description="Whether instrument is sterile")
    disposable: bool = Field(default=False, description="Whether instrument is disposable")


# ============================================================================
# Environment Configuration
# ============================================================================


class CameraConfig(BaseModel):
    """Camera configuration for rendering."""

    name: str = Field(default="main_camera", description="Camera name")
    type: CameraType = Field(default=CameraType.PERSPECTIVE, description="Camera type")

    # Pose
    pose: Pose = Field(default_factory=Pose, description="Camera pose")

    # Look-at target (alternative to orientation)
    look_at: Optional[Position] = Field(
        default=None, description="Point to look at (alternative to orientation)"
    )

    # Field of view
    fov: float = Field(default=45.0, ge=1.0, le=180.0, description="Field of view (degrees)")
    aspect_ratio: float = Field(default=16.0 / 9.0, ge=0.1, description="Aspect ratio")

    # Near/far clipping
    near: float = Field(default=0.01, ge=0.001, description="Near clipping plane (m)")
    far: float = Field(default=100.0, ge=1.0, description="Far clipping plane (m)")

    # For orthographic cameras
    orthographic_width: Optional[float] = Field(
        default=None, description="Orthographic width"
    )
    orthographic_height: Optional[float] = Field(
        default=None, description="Orthographic height"
    )

    # Active camera
    active: bool = Field(default=True, description="Whether camera is active for rendering")


class LightConfig(BaseModel):
    """Light source configuration."""

    name: str = Field(default="main_light", description="Light name")
    type: LightType = Field(default=LightType.DIRECTIONAL, description="Light type")

    # Position (for point/spotlight)
    position: Optional[Position] = Field(
        default=None, description="Position for point/spotlight lights"
    )

    # Direction (for directional/spotlight)
    direction: Optional[Tuple[float, float, float]] = Field(
        default=None, description="Direction vector for directional/spotlight"
    )

    # Color and intensity
    color: RgbColor = Field(
        default_factory=lambda: RgbColor(r=1.0, g=1.0, b=1.0, a=1.0),
        description="Light color",
    )
    intensity: float = Field(default=1.0, ge=0.0, description="Light intensity")

    # Spotlight-specific
    inner_cone_angle: Optional[float] = Field(
        default=None, ge=0.0, le=180.0, description="Inner cone angle for spotlight (degrees)"
    )
    outer_cone_angle: Optional[float] = Field(
        default=None, ge=0.0, le=180.0, description="Outer cone angle for spotlight (degrees)"
    )

    # Shadow
    cast_shadows: bool = Field(default=True, description="Whether light casts shadows")
    shadow_softness: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Shadow softness"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_light_type(cls, data):
        """Validate that required fields are present for each light type."""
        if isinstance(data, dict):
            light_type = data.get("type")
            if light_type == LightType.POINT and data.get("position") is None:
                raise ValueError("Point lights require a position")
            if light_type == LightType.DIRECTIONAL and data.get("direction") is None:
                # Default to overhead light
                data["direction"] = (0.0, 0.0, -1.0)
            if light_type == LightType.SPOTLIGHT:
                if data.get("position") is None or data.get("direction") is None:
                    raise ValueError("Spotlights require position and direction")
        return data


class GroundPlaneConfig(BaseModel):
    """Ground plane configuration."""

    enabled: bool = Field(default=True, description="Whether ground plane is enabled")
    size: Tuple[float, float] = Field(
        default=(10.0, 10.0), description="Ground plane size (width, length) in meters"
    )
    color: RgbColor = Field(
        default_factory=lambda: RgbColor(r=0.5, g=0.5, b=0.5, a=1.0),
        description="Ground plane color",
    )
    texture: Optional[TextureAsset] = Field(default=None, description="Ground texture")
    friction: float = Field(default=0.8, ge=0.0, le=2.0, description="Ground friction")
    restitution: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ground restitution"
    )


class SurgicalTableConfig(BaseModel):
    """Surgical table/bed configuration."""

    name: str = Field(default="surgical_table", description="Table name")
    pose: Pose = Field(default_factory=Pose, description="Table pose")
    dimensions: Tuple[float, float, float] = Field(
        default=(2.0, 0.8, 0.5), description="Table dimensions (width, length, height)"
    )
    color: RgbColor = Field(
        default_factory=lambda: RgbColor(r=0.2, g=0.2, b=0.2, a=1.0),
        description="Table color",
    )
    mesh: Optional[MeshAsset] = Field(default=None, description="Table mesh")


class EnvironmentConfig(BaseModel):
    """Complete environment configuration."""

    name: str = Field(default="operating_room", description="Environment name")

    # Lighting
    lights: List[LightConfig] = Field(
        default_factory=lambda: [LightConfig(name="overhead", type=LightType.DIRECTIONAL)],
        description="Light sources",
    )

    # Cameras
    cameras: List[CameraConfig] = Field(
        default_factory=lambda: [CameraConfig(name="main_camera")],
        description="Camera configurations",
    )

    # Ground plane
    ground_plane: GroundPlaneConfig = Field(
        default_factory=GroundPlaneConfig, description="Ground plane configuration"
    )

    # Surgical table
    surgical_table: Optional[SurgicalTableConfig] = Field(
        default=None, description="Surgical table configuration"
    )

    # Environment mesh (room geometry)
    environment_mesh: Optional[MeshAsset] = Field(
        default=None, description="Optional environment mesh (e.g., operating room)"
    )

    # Background
    background_color: RgbColor = Field(
        default_factory=lambda: RgbColor(r=0.1, g=0.1, b=0.1, a=1.0),
        description="Background color",
    )
    skybox: Optional[TextureAsset] = Field(default=None, description="Skybox texture")

    # Ambient settings
    ambient_light: Tuple[float, float, float] = Field(
        default=(0.1, 0.1, 0.1), description="Ambient light color"
    )
    fog_enabled: bool = Field(default=False, description="Whether fog is enabled")
    fog_color: Optional[Tuple[float, float, float]] = Field(
        default=None, description="Fog color"
    )
    fog_distance: Optional[float] = Field(default=None, description="Fog distance")


# ============================================================================
# Task and Constraints
# ============================================================================


class TaskObjective(BaseModel):
    """Definition of a task objective."""

    name: str = Field(description="Objective name")
    description: str = Field(description="Objective description")
    success_criteria: str = Field(description="Success criteria description")
    failure_criteria: Optional[str] = Field(default=None, description="Failure criteria")
    weight: float = Field(default=1.0, ge=0.0, description="Objective weight")


class ConstraintConfig(BaseModel):
    """Constraint configuration for the scene."""

    name: str = Field(description="Constraint name")
    type: Literal["position", "orientation", "velocity", "force", "distance"] = Field(
        description="Constraint type"
    )
    target_entity: str = Field(description="Entity to constrain")
    reference_entity: Optional[str] = Field(default=None, description="Reference entity")
    limits: Tuple[float, float] = Field(description="Min and max limits")
    penalty_weight: float = Field(
        default=1.0, ge=0.0, description="Penalty weight for constraint violation"
    )
    description: Optional[str] = Field(default=None, description="Constraint description")


class RewardShaping(BaseModel):
    """Reward shaping configuration for RL training."""

    success_reward: float = Field(default=100.0, description="Reward for task completion")
    failure_penalty: float = Field(default=-100.0, description="Penalty for failure")
    time_penalty: float = Field(default=-0.01, description="Per-timestep penalty")
    distance_reward_scale: float = Field(default=1.0, description="Distance-based reward scaling")
    constraint_violation_penalty: float = Field(
        default=-1.0, description="Penalty for constraint violations"
    )
    collision_penalty: float = Field(default=-10.0, description="Penalty for collisions")
    tissue_damage_penalty: float = Field(default=-50.0, description="Penalty for tissue damage")


class TaskConfig(BaseModel):
    """Complete task definition."""

    name: str = Field(description="Task name")
    description: str = Field(description="Task description")
    objectives: List[TaskObjective] = Field(
        default_factory=list, description="Task objectives"
    )
    constraints: List[ConstraintConfig] = Field(
        default_factory=list, description="Task constraints"
    )
    reward_shaping: RewardShaping = Field(
        default_factory=RewardShaping, description="Reward shaping configuration"
    )
    max_episode_length: int = Field(
        default=1000, ge=1, description="Maximum episode length in timesteps"
    )
    time_limit: float = Field(default=60.0, ge=0.1, description="Time limit in seconds")
    success_threshold: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Success threshold (0-1)"
    )


# ============================================================================
# Domain Randomization
# ============================================================================


class PhysicsRandomization(BaseModel):
    """Physics parameter randomization."""

    enabled: bool = Field(default=False, description="Enable randomization")
    mass_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Mass randomization range (ratio)"
    )
    friction_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Friction randomization range"
    )
    damping_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Damping randomization range"
    )
    stiffness_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Stiffness randomization range"
    )
    gravity_range: Optional[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]] = Field(
        default=None, description="Gravity randomization ranges for (x, y, z)"
    )


class VisualRandomization(BaseModel):
    """Visual parameter randomization."""

    enabled: bool = Field(default=False, description="Enable randomization")
    color_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Color variation range"
    )
    texture_randomization: bool = Field(
        default=False, description="Enable texture randomization"
    )
    lighting_variation: Optional[Tuple[float, float]] = Field(
        default=None, description="Lighting intensity variation range"
    )
    camera_pose_noise: Optional[Tuple[float, float]] = Field(
        default=None, description="Camera pose noise (position, orientation)"
    )


class DynamicsRandomization(BaseModel):
    """Dynamics parameter randomization."""

    enabled: bool = Field(default=False, description="Enable randomization")
    joint_noise: Optional[Tuple[float, float]] = Field(
        default=None, description="Joint position/velocity noise"
    )
    action_noise: Optional[Tuple[float, float]] = Field(
        default=None, description="Action noise range"
    )
    delay_range: Optional[Tuple[float, float]] = Field(
        default=None, description="Action/reaction delay range"
    )


class DomainRandomizationConfig(BaseModel):
    """Complete domain randomization configuration."""

    physics: PhysicsRandomization = Field(
        default_factory=PhysicsRandomization, description="Physics randomization"
    )
    visual: VisualRandomization = Field(
        default_factory=VisualRandomization, description="Visual randomization"
    )
    dynamics: DynamicsRandomization = Field(
        default_factory=DynamicsRandomization, description="Dynamics randomization"
    )
    randomize_each_episode: bool = Field(
        default=True, description="Randomize at each episode reset"
    )
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")


# ============================================================================
# Scene Definition
# ============================================================================


class Metadata(BaseModel):
    """Scene metadata."""

    name: str = Field(default="Untitled Scene", description="Scene name")
    description: Optional[str] = Field(default=None, description="Scene description")
    version: str = Field(default="1.0.0", description="Scene version")
    author: Optional[str] = Field(default=None, description="Author name")
    created: Optional[str] = Field(default=None, description="Creation date")
    modified: Optional[str] = Field(default=None, description="Last modification date")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")


class SceneDefinition(BaseModel):
    """Complete scene definition for surgical robotics simulation."""

    # Metadata
    metadata: Metadata = Field(
        default_factory=lambda: Metadata(name="Untitled Scene"),
        description="Scene metadata",
    )

    # Physics
    physics: PhysicsConfig = Field(
        default_factory=PhysicsConfig, description="Physics configuration"
    )

    # Environment
    environment: EnvironmentConfig = Field(
        default_factory=EnvironmentConfig, description="Environment configuration"
    )

    # Entities
    robots: List[RobotConfig] = Field(
        default_factory=list, description="Robot configurations"
    )
    tissues: List[TissueConfig] = Field(
        default_factory=list, description="Tissue/organ configurations"
    )
    instruments: List[InstrumentConfig] = Field(
        default_factory=list, description="Instrument configurations"
    )

    # Task
    task: Optional[TaskConfig] = Field(
        default=None, description="Task configuration"
    )

    # Domain randomization
    domain_randomization: DomainRandomizationConfig = Field(
        default_factory=DomainRandomizationConfig,
        description="Domain randomization configuration",
    )

    # Simulator settings
    simulator: SimulatorType = Field(
        default=SimulatorType.MUJOCO, description="Preferred simulator backend"
    )

    # Additional assets
    assets: Dict[str, AssetReference] = Field(
        default_factory=dict, description="Additional asset references"
    )

    # Custom parameters
    custom: Dict[str, Any] = Field(
        default_factory=dict, description="Custom parameters for extensions"
    )

    def get_robot(self, name: str) -> Optional[RobotConfig]:
        """Get robot by name."""
        for robot in self.robots:
            if robot.name == name:
                return robot
        return None

    def get_tissue(self, name: str) -> Optional[TissueConfig]:
        """Get tissue by name."""
        for tissue in self.tissues:
            if tissue.name == name:
                return tissue
        return None

    def get_instrument(self, name: str) -> Optional[InstrumentConfig]:
        """Get instrument by name."""
        for instrument in self.instruments:
            if instrument.name == name:
                return instrument
        return None

    def get_camera(self, name: str) -> Optional[CameraConfig]:
        """Get camera by name."""
        for camera in self.environment.cameras:
            if camera.name == name:
                return camera
        return None

    def get_active_cameras(self) -> List[CameraConfig]:
        """Get all active cameras."""
        return [cam for cam in self.environment.cameras if cam.active]
