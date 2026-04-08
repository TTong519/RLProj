"""Custom reward functions for surgical RL environments.

This module provides a collection of reward functions for surgical robotics
training, including distance-based rewards, success/failure rewards,
collision penalties, and composite reward functions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np


class RewardType(str, Enum):
    """Types of reward functions."""

    DISTANCE = "distance"
    SUCCESS = "success"
    COLLISION = "collision"
    TISSUE_DAMAGE = "tissue_damage"
    ACTION_PENALTY = "action_penalty"
    TIME_PENALTY = "time_penalty"
    ORIENTATION = "orientation"
    COMPOSITE = "composite"
    CUSTOM = "custom"


@dataclass
class RewardConfig:
    """Configuration for reward computation.

    Attributes:
        success_reward: Reward for successful task completion.
        failure_penalty: Penalty for task failure.
        distance_weight: Weight for distance-based reward.
        orientation_weight: Weight for orientation-based reward.
        action_penalty_weight: Weight for action magnitude penalty.
        time_penalty_weight: Weight for time step penalty.
        collision_penalty: Penalty for collisions.
        tissue_damage_penalty: Penalty for tissue damage.
        distance_threshold: Distance threshold for success (meters).
        angle_threshold: Angle threshold for success (radians).
        shape: Shape of distance reward ('linear', 'exponential', 'gaussian').
        scale: Scale factor for reward values.
    """

    success_reward: float = 100.0
    failure_penalty: float = -50.0
    distance_weight: float = 1.0
    orientation_weight: float = 0.5
    action_penalty_weight: float = 0.01
    time_penalty_weight: float = 0.001
    collision_penalty: float = -10.0
    tissue_damage_penalty: float = -5.0
    distance_threshold: float = 0.01  # 1cm
    angle_threshold: float = 0.1  # ~6 degrees
    shape: str = "exponential"
    scale: float = 1.0


@dataclass
class RewardResult:
    """Result of reward computation.

    Attributes:
        total: Total reward value.
        components: Individual reward components.
        info: Additional information about the reward computation.
    """

    total: float
    components: Dict[str, float] = field(default_factory=dict)
    info: Dict[str, Any] = field(default_factory=dict)

    def __add__(self, other: "RewardResult") -> "RewardResult":
        """Add two reward results."""
        combined_components = {**self.components, **other.components}
        for key in set(self.components.keys()) & set(other.components.keys()):
            combined_components[key] = self.components[key] + other.components[key]
        return RewardResult(
            total=self.total + other.total,
            components=combined_components,
            info={**self.info, **other.info},
        )

    def __mul__(self, scale: float) -> "RewardResult":
        """Scale a reward result."""
        return RewardResult(
            total=self.total * scale,
            components={k: v * scale for k, v in self.components.items()},
            info=self.info.copy(),
        )


class BaseRewardFunction(ABC):
    """Abstract base class for reward functions.

    All reward functions must implement the compute method which takes
    the current state and returns a RewardResult.
    """

    @abstractmethod
    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute the reward for the current step.

        Args:
            observation: Current observation dictionary.
            action: Action taken.
            info: Additional info from the environment.

        Returns:
            RewardResult with reward value and components.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state for a new episode."""
        pass


class DistanceReward(BaseRewardFunction):
    """Distance-based reward function.

    Provides reward based on the distance between the end effector
    and a target position. Supports linear, exponential, and
    Gaussian reward shapes.

    The reward is computed as:
    - linear: r = -distance * scale
    - exponential: r = exp(-distance * scale)
    - gaussian: r = exp(-(distance^2) / (2 * sigma^2))
    """

    def __init__(
        self,
        weight: float = 1.0,
        shape: str = "exponential",
        scale: float = 10.0,
        sigma: float = 0.05,
        threshold: float = 0.01,
    ):
        """Initialize distance reward.

        Args:
            weight: Weight for this reward component.
            shape: Reward shape ('linear', 'exponential', 'gaussian').
            scale: Scale factor for the reward.
            sigma: Standard deviation for Gaussian shape.
            threshold: Distance threshold for success.
        """
        self.weight = weight
        self.shape = shape
        self.scale = scale
        self.sigma = sigma
        self.threshold = threshold
        self._prev_distance: Optional[float] = None

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute distance-based reward."""
        end_pos = observation.get("endeffector_pos")
        target_pos = observation.get("target_pos")
        distance_obs = observation.get("distance_to_target")

        # Get distance
        if distance_obs is not None:
            distance = float(distance_obs[0])
        elif end_pos is not None and target_pos is not None:
            distance = float(np.linalg.norm(end_pos - target_pos))
        elif info.get("distance_to_target") is not None:
            distance = info["distance_to_target"]
        else:
            return RewardResult(
                total=0.0,
                components={"distance": 0.0},
                info={"distance": float("inf")},
            )

        # Compute shaped reward
        if self.shape == "linear":
            reward = -distance * self.scale
        elif self.shape == "exponential":
            reward = np.exp(-distance * self.scale)
        elif self.shape == "gaussian":
            reward = np.exp(-(distance**2) / (2 * self.sigma**2))
        else:
            reward = -distance

        # Add shaping bonus for approaching target
        shaping = 0.0
        if self._prev_distance is not None:
            shaping = self._prev_distance - distance
        self._prev_distance = distance

        total = (reward + shaping) * self.weight
        success = distance < self.threshold

        return RewardResult(
            total=total,
            components={
                "distance": reward * self.weight,
                "distance_shaping": shaping * self.weight,
            },
            info={
                "distance": distance,
                "success": success,
                "approaching": shaping > 0,
            },
        )

    def reset(self) -> None:
        """Reset distance tracking."""
        self._prev_distance = None


class OrientationReward(BaseRewardFunction):
    """Orientation-based reward function.

    Provides reward based on the angular distance between the
    end effector orientation and a target orientation.
    """

    def __init__(
        self,
        weight: float = 0.5,
        scale: float = 5.0,
        threshold: float = 0.1,
    ):
        """Initialize orientation reward.

        Args:
            weight: Weight for this reward component.
            scale: Scale factor for the reward.
            threshold: Angle threshold for success (radians).
        """
        self.weight = weight
        self.scale = scale
        self.threshold = threshold

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute orientation-based reward."""
        angle_obs = observation.get("angle_to_target")

        if angle_obs is not None:
            angle = float(angle_obs[0])
        elif info.get("angle_to_target") is not None:
            angle = info["angle_to_target"]
        else:
            return RewardResult(
                total=0.0,
                components={"orientation": 0.0},
                info={},
            )

        reward = np.exp(-angle * self.scale)
        success = angle < self.threshold

        return RewardResult(
            total=reward * self.weight,
            components={"orientation": reward * self.weight},
            info={"angle": angle, "orientation_success": success},
        )

    def reset(self) -> None:
        """No internal state to reset."""
        pass


class ActionPenalty(BaseRewardFunction):
    """Penalty for large actions (energy efficiency).

    Penalizes the agent for taking large actions, encouraging
    smooth, energy-efficient motions.
    """

    def __init__(
        self,
        weight: float = 0.01,
        penalty_type: str = "l2",
    ):
        """Initialize action penalty.

        Args:
            weight: Weight for this penalty.
            penalty_type: Type of penalty ('l1', 'l2', 'max').
        """
        self.weight = weight
        self.penalty_type = penalty_type

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute action penalty."""
        if self.penalty_type == "l1":
            penalty = float(np.sum(np.abs(action)))
        elif self.penalty_type == "l2":
            penalty = float(np.sum(np.square(action)))
        elif self.penalty_type == "max":
            penalty = float(np.max(np.abs(action)))
        else:
            penalty = float(np.sum(np.square(action)))

        return RewardResult(
            total=-penalty * self.weight,
            components={"action_penalty": -penalty * self.weight},
            info={"action_magnitude": penalty},
        )

    def reset(self) -> None:
        """No internal state to reset."""
        pass


class TimePenalty(BaseRewardFunction):
    """Penalty per time step to encourage efficiency."""

    def __init__(self, weight: float = 0.001):
        """Initialize time penalty.

        Args:
            weight: Penalty per step.
        """
        self.weight = weight
        self._step = 0

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute time penalty."""
        self._step += 1
        return RewardResult(
            total=-self.weight,
            components={"time_penalty": -self.weight},
            info={"step": self._step},
        )

    def reset(self) -> None:
        """Reset step counter."""
        self._step = 0


class SuccessReward(BaseRewardFunction):
    """Sparse success/failure reward.

    Provides a large positive reward for success and a negative
    penalty for failure. Can be used in combination with shaping rewards.
    """

    def __init__(
        self,
        success_reward: float = 100.0,
        failure_penalty: float = -50.0,
        distance_threshold: float = 0.01,
        angle_threshold: float = 0.1,
    ):
        """Initialize success reward.

        Args:
            success_reward: Reward for task success.
            failure_penalty: Penalty for task failure.
            distance_threshold: Distance threshold for success.
            angle_threshold: Angle threshold for success (radians).
        """
        self.success_reward = success_reward
        self.failure_penalty = failure_penalty
        self.distance_threshold = distance_threshold
        self.angle_threshold = angle_threshold

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute success/failure reward."""
        # Check if terminated
        terminated = info.get("terminated", False)
        truncated = info.get("truncated", False)

        if not (terminated or truncated):
            return RewardResult(total=0.0, components={"success": 0.0}, info={})

        # Check success criteria
        success = info.get("success", False)

        # Check distance-based success
        distance_obs = observation.get("distance_to_target")
        if distance_obs is not None:
            distance = float(distance_obs[0])
            if distance < self.distance_threshold:
                success = True

        if success:
            return RewardResult(
                total=self.success_reward,
                components={"success": self.success_reward},
                info={"task_success": True},
            )
        else:
            return RewardResult(
                total=self.failure_penalty,
                components={"success": self.failure_penalty},
                info={"task_success": False},
            )

    def reset(self) -> None:
        """No internal state to reset."""
        pass


class CollisionPenalty(BaseRewardFunction):
    """Penalty for collisions with obstacles or tissue."""

    def __init__(
        self,
        weight: float = 10.0,
        tissue_weight: float = 5.0,
    ):
        """Initialize collision penalty.

        Args:
            weight: Penalty weight for general collisions.
            tissue_weight: Additional penalty for tissue damage.
        """
        self.weight = weight
        self.tissue_weight = tissue_weight

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute collision penalty."""
        collision = info.get("collision", False)
        tissue_damage = info.get("tissue_damage", 0.0)
        collision_force = info.get("collision_force", 0.0)

        penalty = 0.0
        if collision:
            penalty -= self.weight
        if tissue_damage > 0:
            penalty -= tissue_damage * self.tissue_weight
        penalty -= collision_force * 0.1  # Force-proportional penalty

        return RewardResult(
            total=penalty,
            components={
                "collision_penalty": -self.weight if collision else 0.0,
                "tissue_damage_penalty": -tissue_damage * self.tissue_weight,
            },
            info={
                "collision": collision,
                "tissue_damage": tissue_damage,
            },
        )

    def reset(self) -> None:
        """No internal state to reset."""
        pass


class CompositeReward(BaseRewardFunction):
    """Composite reward function combining multiple reward components.

    Allows combining different reward functions with configurable weights.

    Example:
        >>> reward_fn = CompositeReward([
        ...     (DistanceReward(weight=1.0), 1.0),
        ...     (ActionPenalty(weight=0.01), 0.5),
        ...     (TimePenalty(weight=0.001), 1.0),
        ...     (SuccessReward(), 1.0),
        ... ])
    """

    def __init__(
        self,
        components: Optional[List[Tuple[BaseRewardFunction, float]]] = None,
    ):
        """Initialize composite reward.

        Args:
            components: List of (reward_function, weight) tuples.
        """
        self.components: List[Tuple[BaseRewardFunction, float]] = components or []

    def add(self, reward_fn: BaseRewardFunction, weight: float = 1.0) -> None:
        """Add a reward component.

        Args:
            reward_fn: Reward function to add.
            weight: Weight for this component.
        """
        self.components.append((reward_fn, weight))

    def compute(
        self,
        observation: Dict[str, np.ndarray],
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> RewardResult:
        """Compute composite reward."""
        total_reward = 0.0
        all_components: Dict[str, float] = {}
        all_info: Dict[str, Any] = {}

        for reward_fn, weight in self.components:
            result = reward_fn.compute(observation, action, info)
            total_reward += result.total * weight
            for key, value in result.components.items():
                all_components[f"{key}_w{weight:.1f}"] = value * weight
            all_info.update(result.info)

        return RewardResult(
            total=total_reward,
            components=all_components,
            info=all_info,
        )

    def reset(self) -> None:
        """Reset all component reward functions."""
        for reward_fn, _ in self.components:
            reward_fn.reset()


# ============================================================================
# Factory Function
# ============================================================================

def create_default_reward(config: Optional[RewardConfig] = None) -> CompositeReward:
    """Create a default composite reward function for surgical tasks.

    Args:
        config: Reward configuration. Uses defaults if None.

    Returns:
        CompositeReward with standard surgical task reward components.
    """
    config = config or RewardConfig()

    reward = CompositeReward([
        (DistanceReward(
            weight=config.distance_weight,
            shape=config.shape,
            threshold=config.distance_threshold,
        ), 1.0),
        (OrientationReward(
            weight=config.orientation_weight,
            threshold=config.angle_threshold,
        ), 1.0),
        (ActionPenalty(weight=config.action_penalty_weight), 1.0),
        (TimePenalty(weight=config.time_penalty_weight), 1.0),
        (SuccessReward(
            success_reward=config.success_reward,
            failure_penalty=config.failure_penalty,
            distance_threshold=config.distance_threshold,
            angle_threshold=config.angle_threshold,
        ), 1.0),
        (CollisionPenalty(
            weight=config.collision_penalty,
            tissue_weight=config.tissue_damage_penalty,
        ), 1.0),
    ])

    return reward
