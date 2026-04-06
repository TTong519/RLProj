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
]
