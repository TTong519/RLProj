"""Scene definition module - Schema and validation for scene files.

This module provides Pydantic models for defining surgical robotics
training scenes, including robots, tissues, instruments, environments,
physics, and task definitions.
"""

from .schema import (
    # Enums
    SimulatorType,
    RobotType,
    TissueType,
    InstrumentType,
    JointType,
    CameraType,
    LightType,
    # Base models
    Position,
    Orientation,
    EulerAngles,
    Pose,
    RgbColor,
    BoundingBox,
    # Assets
    AssetReference,
    MeshAsset,
    TextureAsset,
    # Physics
    PhysicsMaterial,
    SoftBodyPhysics,
    RigidBodyPhysics,
    PhysicsConfig,
    # Robot
    JointLimits,
    JointConfig,
    EndEffectorConfig,
    RobotLink,
    RobotConfig,
    # Tissue
    TissueMeshDefinition,
    TissueAttachment,
    TissueConfig,
    # Instrument
    InstrumentPhysics,
    CuttingProperties,
    GraspingProperties,
    NeedleDriverProperties,
    InstrumentConfig,
    # Environment
    CameraConfig,
    LightConfig,
    GroundPlaneConfig,
    SurgicalTableConfig,
    EnvironmentConfig,
    # Task
    TaskObjective,
    ConstraintConfig,
    RewardShaping,
    TaskConfig,
    # Domain randomization
    PhysicsRandomization,
    VisualRandomization,
    DynamicsRandomization,
    DomainRandomizationConfig,
    # Scene
    Metadata,
    SceneDefinition,
)

from .loader import (
    # Exceptions
    SceneLoaderError,
    SceneFileNotFoundError,
    SceneValidationError,
    SceneParseError,
    AssetLoadError,
    # Classes
    SceneCache,
    AssetManager,
    SceneLoader,
    # Functions
    get_loader,
    reset_loader,
    load_scene,
    save_scene,
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
    # Assets
    "AssetReference",
    "MeshAsset",
    "TextureAsset",
    # Physics
    "PhysicsMaterial",
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
    "DomainRandomizationConfig",
    # Scene
    "Metadata",
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
]
