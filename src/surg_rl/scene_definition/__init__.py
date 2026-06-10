"""Scene definition module - Schema and validation for scene files.

This module provides Pydantic models for defining surgical robotics
training scenes, including robots, tissues, instruments, environments,
physics, and task definitions.
"""

from .loader import (
    AssetLoadError,
    AssetManager,
    # Classes
    SceneCache,
    SceneFileNotFoundError,
    SceneLoader,
    # Exceptions
    SceneLoaderError,
    SceneParseError,
    SceneValidationError,
    # Functions
    get_loader,
    load_scene,
    reset_loader,
    save_scene,
    validate_scene,
)
from .schema import (
    ArmConfig,
    ArmRole,
    # Assets
    AssetReference,
    BenchmarkConfig,
    BoundingBox,
    # Environment
    CameraConfig,
    CameraType,
    ConstraintConfig,
    CuttingProperties,
    DomainRandomizationConfig,
    DreamerConfig,
    DynamicsRandomization,
    EndEffectorConfig,
    EnvironmentConfig,
    EulerAngles,
    GraspingProperties,
    GroundPlaneConfig,
    InstrumentConfig,
    # Instrument
    InstrumentPhysics,
    InstrumentType,
    JointConfig,
    # Robot
    JointLimits,
    JointType,
    LightConfig,
    LightType,
    MeshAsset,
    # Scene
    Metadata,
    MultiAgentConfig,
    NeedleDriverProperties,
    Orientation,
    PhysicsConfig,
    # Physics
    PhysicsMaterial,
    # Domain randomization
    PhysicsRandomization,
    Pose,
    # Base models
    Position,
    PyBulletSoftBodyConfig,
    RewardShaping,
    RgbColor,
    RigidBodyPhysics,
    RobotConfig,
    RobotLink,
    RobotType,
    SceneDefinition,
    # Enums
    SimulatorType,
    SoftBodyPhysics,
    SurgicalTableConfig,
    TaskConfig,
    # Task
    TaskObjective,
    TextureAsset,
    TissueAttachment,
    TissueConfig,
    # Tissue
    TissueMeshDefinition,
    TissueType,
    VisualRandomization,
)

__all__ = [
    # Enums
    "SimulatorType",
    "RobotType",
    "TissueType",
    "InstrumentType",
    "JointType",
    "CameraType",
    "LightType",
    # Base models
    "Position",
    "Orientation",
    "EulerAngles",
    "Pose",
    "RgbColor",
    "BoundingBox",
    "BenchmarkConfig",
    # Assets
    "AssetReference",
    "MeshAsset",
    "TextureAsset",
    # Physics
    "PhysicsMaterial",
    "PyBulletSoftBodyConfig",
    "SoftBodyPhysics",
    "RigidBodyPhysics",
    "PhysicsConfig",
    # Robot
    "JointLimits",
    "JointConfig",
    "EndEffectorConfig",
    "RobotLink",
    "RobotConfig",
    # Tissue
    "TissueMeshDefinition",
    "TissueAttachment",
    "TissueConfig",
    # Instrument
    "InstrumentPhysics",
    "CuttingProperties",
    "GraspingProperties",
    "NeedleDriverProperties",
    "InstrumentConfig",
    # Environment
    "CameraConfig",
    "LightConfig",
    "GroundPlaneConfig",
    "SurgicalTableConfig",
    "EnvironmentConfig",
    # Task
    "TaskObjective",
    "ConstraintConfig",
    "RewardShaping",
    "TaskConfig",
    # Domain randomization
    "PhysicsRandomization",
    "VisualRandomization",
    "DynamicsRandomization",
    "DreamerConfig",
    "DomainRandomizationConfig",
    # Scene
    "Metadata",
    "MultiAgentConfig",
    "ArmConfig",
    "ArmRole",
    "SceneDefinition",
    # Loader exceptions
    "SceneLoaderError",
    "SceneFileNotFoundError",
    "SceneValidationError",
    "SceneParseError",
    "AssetLoadError",
    # Loader classes
    "SceneCache",
    "AssetManager",
    "SceneLoader",
    # Loader functions
    "get_loader",
    "reset_loader",
    "load_scene",
    "save_scene",
    "validate_scene",
]
