"""Action space definitions for surgical RL environments.

This module provides action space definitions and processors for
surgical robotics RL environments, supporting joint-space control,
task-space control, and gripper actions.
"""

from dataclasses import dataclass
from enum import Enum

import gymnasium as gym
import numpy as np


class ActionType(str, Enum):
    """Types of action spaces for surgical environments."""

    JOINT_POSITIONS = "joint_positions"
    JOINT_VELOCITIES = "joint_velocities"
    JOINT_TORQUES = "joint_torques"
    ENDEFFECTOR_POSE = "endeffector_pose"
    ENDEFFECTOR_DELTA = "endeffector_delta"
    GRIPPER = "gripper"
    DISCRETE = "discrete"


class ActionScaling(str, Enum):
    """Scaling mode for action values."""

    NONE = "none"
    NORMALIZE = "normalize"
    CLIP = "clip"
    TANH = "tanh"


@dataclass
class ActionSpec:
    """Specification for a single action component.

    Attributes:
        name: Action name/identifier.
        action_type: Type of action.
        shape: Shape of the action array.
        low: Lower bound for continuous actions.
        high: Upper bound for continuous actions.
        num_actions: Number of discrete actions (for discrete action space).
        dtype: Data type of the action.
        scaling: Scaling mode for the action.
        description: Human-readable description.
    """

    name: str
    action_type: ActionType
    shape: tuple[int, ...]
    low: np.ndarray | None = None
    high: np.ndarray | None = None
    num_actions: int = 0
    dtype: type = np.float32
    scaling: ActionScaling = ActionScaling.NONE
    description: str = ""

    def get_space(self) -> gym.Space:
        """Create the Gymnasium space for this action.

        Returns:
            Gymnasium Space object (Box or Discrete).
        """
        if self.action_type == ActionType.DISCRETE:
            return gym.spaces.Discrete(self.num_actions)

        # Continuous action space
        low = self.low if self.low is not None else -np.ones(self.shape)
        high = self.high if self.high is not None else np.ones(self.shape)

        return gym.spaces.Box(
            low=low.astype(self.dtype),
            high=high.astype(self.dtype),
            shape=self.shape,
            dtype=self.dtype,
        )


@dataclass
class ActionConfig:
    """Configuration for the action space of a surgical environment.

    Attributes:
        action_type: Primary action type.
        num_joints: Number of robot joints.
        include_gripper: Whether to include gripper action.
        gripper_bounds: Bounds for gripper action (open, close).
        endeffector_dims: Dimensions for end-effector actions.
        scaling: Global scaling mode for actions.
        action_scale: Scale factor for delta actions.
        clip_actions: Whether to clip actions to bounds.
        relative_actions: Whether actions are relative (deltas) or absolute.
    """

    action_type: ActionType = ActionType.JOINT_POSITIONS
    num_joints: int = 7
    include_gripper: bool = True
    gripper_bounds: tuple[float, float] = (0.0, 1.0)
    endeffector_dims: int = 6  # x, y, z, roll, pitch, yaw
    scaling: ActionScaling = ActionScaling.NORMALIZE
    action_scale: float = 1.0
    clip_actions: bool = True
    relative_actions: bool = False
    num_actions: int = 3  # Number of discrete actions per DOF (for DISCRETE mode)


# ============================================================================
# Default Action Specifications
# ============================================================================

JOINT_POSITIONS_SPEC = ActionSpec(
    name="joint_positions",
    action_type=ActionType.JOINT_POSITIONS,
    shape=(7,),
    low=-np.pi * np.ones(7),
    high=np.pi * np.ones(7),
    scaling=ActionScaling.NORMALIZE,
    description="Joint position targets (radians)",
)

JOINT_VELOCITIES_SPEC = ActionSpec(
    name="joint_velocities",
    action_type=ActionType.JOINT_VELOCITIES,
    shape=(7,),
    low=-2.0 * np.ones(7),
    high=2.0 * np.ones(7),
    scaling=ActionScaling.NORMALIZE,
    description="Joint velocity targets (rad/s)",
)

JOINT_TORQUES_SPEC = ActionSpec(
    name="joint_torques",
    action_type=ActionType.JOINT_TORQUES,
    shape=(7,),
    low=-100.0 * np.ones(7),
    high=100.0 * np.ones(7),
    scaling=ActionScaling.NORMALIZE,
    description="Joint torque commands (N·m)",
)

ENDEFFECTOR_POSE_SPEC = ActionSpec(
    name="endeffector_pose",
    action_type=ActionType.ENDEFFECTOR_POSE,
    shape=(6,),
    low=-np.concatenate([np.ones(3), np.pi * np.ones(3)]),
    high=np.concatenate([np.ones(3), np.pi * np.ones(3)]),
    scaling=ActionScaling.NORMALIZE,
    description="End-effector pose target (x, y, z, roll, pitch, yaw)",
)

ENDEFFECTOR_DELTA_SPEC = ActionSpec(
    name="endeffector_delta",
    action_type=ActionType.ENDEFFECTOR_DELTA,
    shape=(6,),
    low=-0.05 * np.ones(6),
    high=0.05 * np.ones(6),
    scaling=ActionScaling.NONE,
    description="End-effector delta pose (dx, dy, dz, droll, dpitch, dyaw)",
)

GRIPPER_SPEC = ActionSpec(
    name="gripper",
    action_type=ActionType.GRIPPER,
    shape=(1,),
    low=np.array([0.0]),
    high=np.array([1.0]),
    scaling=ActionScaling.NONE,
    description="Gripper open/close (0=closed, 1=open)",
)


# ============================================================================
# Action Builder
# ============================================================================

DEFAULT_ACTION_SPECS: dict[ActionType, ActionSpec] = {
    ActionType.JOINT_POSITIONS: JOINT_POSITIONS_SPEC,
    ActionType.JOINT_VELOCITIES: JOINT_VELOCITIES_SPEC,
    ActionType.JOINT_TORQUES: JOINT_TORQUES_SPEC,
    ActionType.ENDEFFECTOR_POSE: ENDEFFECTOR_POSE_SPEC,
    ActionType.ENDEFFECTOR_DELTA: ENDEFFECTOR_DELTA_SPEC,
    ActionType.GRIPPER: GRIPPER_SPEC,
}


class ActionBuilder:
    """Build action spaces and process actions for surgical environments.

    This class creates Gymnasium-compatible action spaces based on
    configuration and processes raw actions for the simulator.

    Example:
        >>> config = ActionConfig(
        ...     action_type=ActionType.JOINT_POSITIONS,
        ...     num_joints=7,
        ...     include_gripper=True,
        ... )
        >>> builder = ActionBuilder(config)
        >>> action_space = builder.get_action_space()
        >>> processed = builder.process_action(raw_action)
    """

    def __init__(
        self,
        config: ActionConfig | None = None,
        custom_specs: dict[str, ActionSpec] | None = None,
    ):
        """Initialize the action builder.

        Args:
            config: Action configuration. Uses defaults if None.
            custom_specs: Custom action specifications.
        """
        self.config = config or ActionConfig()
        self.custom_specs = custom_specs or {}

        # Build action specs
        self._specs: dict[str, ActionSpec] = {}
        self._build_specs()

        # Previous action for relative mode
        self._last_action: np.ndarray | None = None

    def _build_specs(self) -> None:
        """Build action specifications from configuration."""
        # Primary action
        primary_type = self.config.action_type
        if primary_type in DEFAULT_ACTION_SPECS:
            spec = DEFAULT_ACTION_SPECS[primary_type]
            # Adjust for number of joints
            if primary_type in (
                ActionType.JOINT_POSITIONS,
                ActionType.JOINT_VELOCITIES,
                ActionType.JOINT_TORQUES,
            ):
                n = self.config.num_joints
                low_val = spec.low[0] if spec.low is not None else -1.0
                high_val = spec.high[0] if spec.high is not None else 1.0
                spec = ActionSpec(
                    name=spec.name,
                    action_type=spec.action_type,
                    shape=(n,),
                    low=low_val * np.ones(n),
                    high=high_val * np.ones(n),
                    scaling=spec.scaling,
                    description=spec.description,
                )
            self._specs[spec.name] = spec
        elif primary_type == ActionType.DISCRETE:
            self._specs["discrete"] = ActionSpec(
                name="discrete",
                action_type=ActionType.DISCRETE,
                shape=(self.config.num_joints,),
                num_actions=self.config.num_actions,
                description="Discrete joint actions",
            )

        if self.config.include_gripper and primary_type != ActionType.GRIPPER:
            gripper_spec = ActionSpec(
                name="gripper",
                action_type=ActionType.GRIPPER,
                shape=(1,),
                low=np.array([self.config.gripper_bounds[0]]),
                high=np.array([self.config.gripper_bounds[1]]),
                num_actions=self.config.num_actions,
                scaling=ActionScaling.NONE,
                description="Gripper open/close",
            )
            self._specs["gripper"] = gripper_spec

        # Custom specs
        for name, spec in self.custom_specs.items():
            self._specs[name] = spec

    def get_action_space(self) -> gym.Space:
        """Create the Gymnasium action space.

        Returns:
            Gymnasium Space object matching the action configuration.
        """
        if self.config.action_type == ActionType.DISCRETE:
            n = self.config.num_joints
            num_actions = self.config.num_actions
            if self.config.include_gripper and n > 1:
                return gym.spaces.MultiDiscrete([num_actions] * (n + 1))
            return gym.spaces.Discrete(num_actions)

        total_size = 0
        lows = []
        highs = []

        for _name, spec in self._specs.items():
            size = int(np.prod(spec.shape))
            total_size += size
            low = spec.low.flatten() if spec.low is not None else -np.ones(size)
            high = spec.high.flatten() if spec.high is not None else np.ones(size)
            lows.append(low)
            highs.append(high)

        low = np.concatenate(lows) if lows else -np.ones(total_size)
        high = np.concatenate(highs) if highs else np.ones(total_size)

        return gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    def process_action(self, action: np.ndarray) -> np.ndarray:
        """Process a raw action from the RL agent for the simulator.

        Applies scaling, clipping, and relative action transformations.

        Args:
            action: Raw action from the agent.

        Returns:
            Processed action ready for the simulator.

        Raises:
            NotImplementedError: If the action type lacks full backend support.
        """
        if self.config.action_type in ():
            raise NotImplementedError(
                f"Action type {self.config.action_type} is not yet supported. "
                f"Configure the simulator action_mode directly for pose control."
            )

        action = np.array(action, dtype=np.float32)

        # Clip actions if configured
        if self.config.clip_actions:
            if self.config.scaling == ActionScaling.NORMALIZE:
                action = np.clip(action, -1.0, 1.0)
            else:
                action_space = self.get_action_space()
                action = np.clip(action, action_space.low, action_space.high)

        # Apply scaling
        if self.config.scaling == ActionScaling.NORMALIZE:
            action = self._normalize_action(action)
        elif self.config.scaling == ActionScaling.TANH:
            action = np.tanh(action)
            # Map from (-1, 1) to (low, high)
            low, high = self.get_action_space().low, self.get_action_space().high
            action = low + (action + 1.0) / 2.0 * (high - low)

        # Apply action scale for delta actions
        if self.config.relative_actions and self._last_action is not None:
            action = self._last_action + action * self.config.action_scale

        self._last_action = action.copy()
        return action

    def _normalize_action(self, action: np.ndarray) -> np.ndarray:
        """Normalize action to the action space range.

        Args:
            action: Raw action (assumed to be in [-1, 1]).

        Returns:
            Action scaled to the action space bounds.
        """
        action_space = self.get_action_space()
        low = action_space.low
        high = action_space.high

        # Scale from [-1, 1] to [low, high]
        return low + (action + 1.0) * (high - low) / 2.0

    def split_action(self, action: np.ndarray) -> dict[str, np.ndarray]:
        """Split a combined action into named components.

        Args:
            action: Combined action vector.

        Returns:
            Dictionary mapping action names to their components.
        """
        result = {}
        idx = 0
        for name, spec in self._specs.items():
            size = int(np.prod(spec.shape))
            result[name] = action[idx : idx + size].reshape(spec.shape)
            idx += size
        return result

    def get_action_size(self) -> int:
        """Get the total size of the action vector.

        Returns:
            Total number of action dimensions.
        """
        total = 0
        for spec in self._specs.values():
            total += int(np.prod(spec.shape))
        return total

    def reset(self) -> None:
        """Reset internal state (e.g., last action for relative mode)."""
        self._last_action = None
