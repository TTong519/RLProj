"""RL training module - Gymnasium environments and training pipeline.

This module provides reinforcement learning training infrastructure for
surgical robotics, including:

- SurgicalEnv: Gymnasium-compatible environment wrapper
- Observation/action space definitions and builders
- Custom reward functions for surgical tasks
- Training pipeline with Stable-Baselines3 integration
- Custom training callbacks

Main Classes:
    SurgicalEnv: Gymnasium environment for surgical robotics
    SurgicalEnvConfig: Configuration for the environment
    ObservationBuilder: Build observation spaces and extract observations
    ActionBuilder: Build action spaces and process actions
    CompositeReward: Composite reward function
    TrainingManager: Manage RL training runs

Example:
    >>> from surg_rl.rl import SurgicalEnv, SurgicalEnvConfig
    >>> from surg_rl.rl import make_env, TrainingManager, TrainingConfig
    >>>
    >>> # Create environment
    >>> env = make_env("scenes/suturing.json")
    >>>
    >>> # Or use SurgicalEnv directly
    >>> config = SurgicalEnvConfig(scene_path="scenes/suturing.json")
    >>> env = SurgicalEnv(config)
    >>>
    >>> # Train with SB3
    >>> manager = TrainingManager(TrainingConfig(
    ...     scene_path="scenes/suturing.json",
    ...     total_timesteps=100000,
    ... ))
    >>> model = manager.train()
"""

# Observation spaces
# Action spaces
from .action import (
    DEFAULT_ACTION_SPECS,
    ENDEFFECTOR_DELTA_SPEC,
    ENDEFFECTOR_POSE_SPEC,
    GRIPPER_SPEC,
    JOINT_TORQUES_SPEC,
    ActionBuilder,
    ActionConfig,
    ActionScaling,
    ActionSpec,
    ActionType,
)
from .action import (
    JOINT_POSITIONS_SPEC as ACTION_JOINT_POSITIONS_SPEC,
)
from .action import (
    JOINT_VELOCITIES_SPEC as ACTION_JOINT_VELOCITIES_SPEC,
)

# Callbacks
from .callbacks import (
    CheckpointCallback,
    CurriculumCallback,
    EvaluationCallback,
    TensorBoardCallback,
    TrainingProgressCallback,
)

# Environment
from .environment import (
    SurgicalEnv,
    SurgicalEnvConfig,
    make_env,
    make_vec_env,
)
from .observation import (
    ANGLE_TO_TARGET_SPEC,
    DEFAULT_SPECS,
    DEPTH_IMAGE_SPEC,
    DISTANCE_TO_TARGET_SPEC,
    ENDEFFECTOR_POS_SPEC,
    ENDEFFECTOR_QUAT_SPEC,
    FORCE_TORQUE_SPEC,
    # Default specs
    JOINT_POSITIONS_SPEC,
    JOINT_VELOCITIES_SPEC,
    RGB_IMAGE_SPEC,
    SEGMENTATION_SPEC,
    TARGET_POS_SPEC,
    TARGET_QUAT_SPEC,
    TISSUE_STATE_SPEC,
    ObservationBuilder,
    ObservationConfig,
    ObservationSpec,
    ObservationType,
)

# Reward functions
from .rewards import (
    ActionPenalty,
    BaseRewardFunction,
    CollisionPenalty,
    CompositeReward,
    DissectionReward,
    DistanceReward,
    NeedlePassingReward,
    OrientationReward,
    RewardConfig,
    RewardResult,
    RewardType,
    SuccessReward,
    SuturingReward,
    TimePenalty,
    create_default_reward,
)

# Training
from .training import (
    AlgorithmConfig,
    TrainingConfig,
    TrainingManager,
)

__all__ = [
    # Observation
    "ObservationBuilder",
    "ObservationConfig",
    "ObservationSpec",
    "ObservationType",
    "DEFAULT_SPECS",
    "JOINT_POSITIONS_SPEC",
    "JOINT_VELOCITIES_SPEC",
    "ENDEFFECTOR_POS_SPEC",
    "ENDEFFECTOR_QUAT_SPEC",
    "FORCE_TORQUE_SPEC",
    "TISSUE_STATE_SPEC",
    "TARGET_POS_SPEC",
    "TARGET_QUAT_SPEC",
    "DISTANCE_TO_TARGET_SPEC",
    "ANGLE_TO_TARGET_SPEC",
    "RGB_IMAGE_SPEC",
    "DEPTH_IMAGE_SPEC",
    "SEGMENTATION_SPEC",
    # Action
    "ActionBuilder",
    "ActionConfig",
    "ActionScaling",
    "ActionSpec",
    "ActionType",
    "DEFAULT_ACTION_SPECS",
    "ACTION_JOINT_POSITIONS_SPEC",
    "ACTION_JOINT_VELOCITIES_SPEC",
    "JOINT_TORQUES_SPEC",
    "ENDEFFECTOR_POSE_SPEC",
    "ENDEFFECTOR_DELTA_SPEC",
    "GRIPPER_SPEC",
    # Reward
    "ActionPenalty",
    "BaseRewardFunction",
    "CollisionPenalty",
    "CompositeReward",
    "DissectionReward",
    "DistanceReward",
    "NeedlePassingReward",
    "OrientationReward",
    "RewardConfig",
    "RewardResult",
    "RewardType",
    "SuccessReward",
    "SuturingReward",
    "TimePenalty",
    "create_default_reward",
    # Environment
    "SurgicalEnv",
    "SurgicalEnvConfig",
    "make_env",
    "make_vec_env",
    # Training
    "AlgorithmConfig",
    "TrainingConfig",
    "TrainingManager",
    # Callbacks
    "CheckpointCallback",
    "CurriculumCallback",
    "EvaluationCallback",
    "TensorBoardCallback",
    "TrainingProgressCallback",
]
