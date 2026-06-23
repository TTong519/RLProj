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

Lazy import discipline (debug: gui-no-render-under-mjpython):
    The submodules of this package (callbacks, environment, training,
    rllib) transitively import heavy third-party dependencies
    (stable_baselines3 -> torch -> tensorflow, ray). Eagerly importing
    them at package-init time made every `from surg_rl.rl.<submodule>
    import X` statement pay ~9-11s of import cost — even when the caller
    only wanted the lightweight `DifficultyLevel` enum (a leaf module
    with no surg_rl.* imports). This caused the GUI (`surg-rl-gui`) to
    freeze for ~11s inside `EditorWindow.__init__` (via
    `scene_definition.schema` -> `from surg_rl.rl.difficulty import
    DifficultyLevel`), blocking the QApplication event loop before
    `window.show()` and producing the macOS "Application Not Responding"
    state with no visible window.

    To fix this without breaking the public API (`from surg_rl.rl import
    SurgicalEnv`, etc.), the re-exports are deferred behind PEP 562 module
    ``__getattr__``. The first attribute access on the package triggers
    the heavy imports; callers that only import a submodule directly
    (e.g. ``from surg_rl.rl.difficulty import DifficultyLevel``) no longer
    pay the full cost. All production callers in ``src/`` use the
    ``from surg_rl.rl.<submodule> import X`` form, so they benefit
    immediately. Tests and examples that use ``from surg_rl.rl import X``
    still work via ``__getattr__``.
"""

from typing import Any

import importlib

# Lightweight submodules that are cheap to import (no heavy third-party
# deps). These are imported eagerly so they are available immediately.
from .difficulty import DifficultyLevel
from .task_results import (
    TASK_RESULT_MAP,
    CuttingResult,
    DissectionResult,
    GraspingResult,
    KnotTyingResult,
    NeedleInsertionResult,
    SuturingResult,
    TaskResult,
)

# Heavy submodules (callbacks -> stable_baselines3 -> torch -> tensorflow,
# environment -> simulators, training -> SB3, rllib -> ray) are deferred
# to PEP 562 __getattr__ below. This keeps `import surg_rl.rl` and
# `from surg_rl.rl.difficulty import DifficultyLevel` cheap.

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Observation
    "ObservationBuilder": (".observation", "ObservationBuilder"),
    "ObservationConfig": (".observation", "ObservationConfig"),
    "ObservationSpec": (".observation", "ObservationSpec"),
    "ObservationType": (".observation", "ObservationType"),
    "DEFAULT_SPECS": (".observation", "DEFAULT_SPECS"),
    "JOINT_POSITIONS_SPEC": (".observation", "JOINT_POSITIONS_SPEC"),
    "JOINT_VELOCITIES_SPEC": (".observation", "JOINT_VELOCITIES_SPEC"),
    "ENDEFFECTOR_POS_SPEC": (".observation", "ENDEFFECTOR_POS_SPEC"),
    "ENDEFFECTOR_QUAT_SPEC": (".observation", "ENDEFFECTOR_QUAT_SPEC"),
    "FORCE_TORQUE_SPEC": (".observation", "FORCE_TORQUE_SPEC"),
    "TISSUE_STATE_SPEC": (".observation", "TISSUE_STATE_SPEC"),
    "TARGET_POS_SPEC": (".observation", "TARGET_POS_SPEC"),
    "TARGET_QUAT_SPEC": (".observation", "TARGET_QUAT_SPEC"),
    "DISTANCE_TO_TARGET_SPEC": (".observation", "DISTANCE_TO_TARGET_SPEC"),
    "ANGLE_TO_TARGET_SPEC": (".observation", "ANGLE_TO_TARGET_SPEC"),
    "RGB_IMAGE_SPEC": (".observation", "RGB_IMAGE_SPEC"),
    "DEPTH_IMAGE_SPEC": (".observation", "DEPTH_IMAGE_SPEC"),
    "SEGMENTATION_SPEC": (".observation", "SEGMENTATION_SPEC"),
    # Action
    "ActionBuilder": (".action", "ActionBuilder"),
    "ActionConfig": (".action", "ActionConfig"),
    "ActionScaling": (".action", "ActionScaling"),
    "ActionSpec": (".action", "ActionSpec"),
    "ActionType": (".action", "ActionType"),
    "DEFAULT_ACTION_SPECS": (".action", "DEFAULT_ACTION_SPECS"),
    "ACTION_JOINT_POSITIONS_SPEC": (".action", "JOINT_POSITIONS_SPEC"),
    "ACTION_JOINT_VELOCITIES_SPEC": (".action", "JOINT_VELOCITIES_SPEC"),
    "JOINT_TORQUES_SPEC": (".action", "JOINT_TORQUES_SPEC"),
    "ENDEFFECTOR_POSE_SPEC": (".action", "ENDEFFECTOR_POSE_SPEC"),
    "ENDEFFECTOR_DELTA_SPEC": (".action", "ENDEFFECTOR_DELTA_SPEC"),
    "GRIPPER_SPEC": (".action", "GRIPPER_SPEC"),
    # Callbacks
    "CheckpointCallback": (".callbacks", "CheckpointCallback"),
    "CurriculumCallback": (".callbacks", "CurriculumCallback"),
    "EvaluationCallback": (".callbacks", "EvaluationCallback"),
    "TensorBoardCallback": (".callbacks", "TensorBoardCallback"),
    "TrainingProgressCallback": (".callbacks", "TrainingProgressCallback"),
    # Reward
    "ActionPenalty": (".rewards", "ActionPenalty"),
    "BaseRewardFunction": (".rewards", "BaseRewardFunction"),
    "CollisionPenalty": (".rewards", "CollisionPenalty"),
    "CompositeReward": (".rewards", "CompositeReward"),
    "DissectionReward": (".rewards", "DissectionReward"),
    "DistanceReward": (".rewards", "DistanceReward"),
    "NeedlePassingReward": (".rewards", "NeedlePassingReward"),
    "OrientationReward": (".rewards", "OrientationReward"),
    "RewardConfig": (".rewards", "RewardConfig"),
    "RewardResult": (".rewards", "RewardResult"),
    "RewardType": (".rewards", "RewardType"),
    "SuccessReward": (".rewards", "SuccessReward"),
    "SuturingReward": (".rewards", "SuturingReward"),
    "TimePenalty": (".rewards", "TimePenalty"),
    "create_default_reward": (".rewards", "create_default_reward"),
    # Environment
    "SurgicalEnv": (".environment", "SurgicalEnv"),
    "SurgicalEnvConfig": (".environment", "SurgicalEnvConfig"),
    "make_env": (".environment", "make_env"),
    "make_vec_env": (".environment", "make_vec_env"),
    # Training
    "AlgorithmConfig": (".training", "AlgorithmConfig"),
    "TrainingConfig": (".training", "TrainingConfig"),
    "TrainingManager": (".training", "TrainingManager"),
}

# Expose heavy submodules as attributes so tests can monkeypatch
# names like ``surg_rl.rl.environment.MuJoCoSimulator``.
_SUBMODULE_NAMES = frozenset({
    "action",
    "callbacks",
    "difficulty",
    "environment",
    "observation",
    "rewards",
    "rllib",
    "task_results",
    "task_reward_router",
    "task_termination",
    "training",
})


def __getattr__(name: str) -> Any:
    """Lazy import heavy submodules and selected public symbols."""
    if name in _SUBMODULE_NAMES:
        module = importlib.import_module(f".{name}", __package__)
        globals()[name] = module
        return module
    if name == "RllibConfig":
        from surg_rl.rl.rllib import RllibConfig  # type: ignore[import]

        globals()["RllibConfig"] = RllibConfig
        return RllibConfig
    if name == "train_rllib":
        from surg_rl.rl.rllib import train_rllib  # type: ignore[import]

        globals()["train_rllib"] = train_rllib
        return train_rllib

    spec = _LAZY_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    submodule, attr_name = spec
    module = importlib.import_module(submodule, __package__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


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
    # Difficulty presets (eagerly imported — leaf module)
    "DifficultyLevel",
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
    # Task results (eagerly imported — lightweight)
    "TaskResult",
    "SuturingResult",
    "KnotTyingResult",
    "NeedleInsertionResult",
    "GraspingResult",
    "CuttingResult",
    "DissectionResult",
    "TASK_RESULT_MAP",
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

