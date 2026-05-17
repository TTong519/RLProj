"""Custom reward functions for surgical RL environments.

This module provides a collection of reward functions for surgical robotics
training, including distance-based rewards, success/failure rewards,
collision penalties, and composite reward functions.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, field_validator


class RewardType(str, Enum):
    """Types of reward functions."""

    DISTANCE = "distance"
    SUCCESS = "success"
    COLLISION = "collision"
    TISSUE_DAMAGE = "tissue_damage"
    ACTION_PENALTY = "action_penalty"
    TIME_PENALTY = "time_penalty"
    ORIENTATION = "orientation"
    SUTURING = "suturing"
    CUTTING = "cutting"
    DISSECTION = "dissection"
    GRASPING = "grasping"
    KNOT_TYING = "knot_tying"
    NEEDLE_PASSING = "needle_passing"
    COMPOSITE = "composite"
    CUSTOM = "custom"


class RewardConfig(BaseModel):
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
    failure_penalty: float = 50.0
    distance_weight: float = 1.0
    orientation_weight: float = 0.5
    action_penalty_weight: float = 0.01
    time_penalty_weight: float = 0.001
    collision_penalty: float = 10.0
    tissue_damage_penalty: float = 5.0
    distance_threshold: float = 0.01  # 1cm
    angle_threshold: float = 0.1  # ~6 degrees
    shape: str = "exponential"
    scale: float = 1.0

    @field_validator("failure_penalty", "collision_penalty", "tissue_damage_penalty")
    @classmethod
    def _validate_penalties(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Penalty values must be non-negative")
        return v


@dataclass
class RewardResult:
    """Result of reward computation.

    Attributes:
        total: Total reward value.
        components: Individual reward components.
        info: Additional information about the reward computation.
    """

    total: float
    components: dict[str, float] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)

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


def _is_finite(value: float) -> bool:
    """Check if a float is finite (not NaN, not inf)."""
    return math.isfinite(value)


def _clamp_finite(value: float, default: float = 0.0) -> float:
    """Return value if finite, else default. Guards against NaN/inf in reward computation."""
    return value if math.isfinite(value) else default


class BaseRewardFunction(ABC):
    """Abstract base class for reward functions.

    All reward functions must implement the compute method which takes
    the current state and returns a RewardResult.
    """

    @abstractmethod
    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
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
        self._prev_distance: float | None = None

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
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
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
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
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
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
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
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
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
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
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute collision penalty."""
        collision = observation.get("collision_detected", False) or info.get("collision", False)
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


class SuturingReward(BaseRewardFunction):
    """Task-specific reward for suturing tasks.

    Rewards proper needle positioning relative to tissue entry/exit points,
    appropriate thread tension, and stitch completion. Penalizes dropping
    the needle or excessive tissue deformation.
    """

    def __init__(
        self,
        weight: float = 1.0,
        position_threshold: float = 0.005,
        tension_threshold: float = 0.5,
        completion_bonus: float = 50.0,
        drop_penalty: float = -20.0,
    ):
        """Initialize suturing reward.

        Args:
            weight: Weight for this reward component.
            position_threshold: Distance threshold for needle positioning (m).
            tension_threshold: Threshold beyond which tension is penalized.
            completion_bonus: Reward per completed stitch.
            drop_penalty: Penalty for dropping the needle.
        """
        self.weight = weight
        self.position_threshold = position_threshold
        self.tension_threshold = tension_threshold
        self.completion_bonus = completion_bonus
        self.drop_penalty = drop_penalty
        self._stitches_completed: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute suturing task reward."""
        reward = 0.0
        components: dict[str, float] = {}

        # Needle positioning reward
        needle_pos = observation.get("needle_pos")
        entry_point = observation.get("entry_point")
        if needle_pos is not None and entry_point is not None:
            distance = float(np.linalg.norm(needle_pos - entry_point))
            position_reward = float(np.exp(-distance * 100.0))
            if distance < self.position_threshold:
                position_reward += 1.0
            reward += position_reward
            components["needle_position"] = position_reward

        # Thread tension penalty
        thread_tension = observation.get("thread_tension")
        if thread_tension is not None:
            tension = float(
                thread_tension.item() if thread_tension.size == 1 else thread_tension[0]
            )
            tension_penalty = -max(0.0, tension - self.tension_threshold)
            reward += tension_penalty
            components["thread_tension"] = tension_penalty

        # Stitch completion bonus
        stitches = int(info.get("stitches_completed", 0))
        if stitches > self._stitches_completed:
            new_stitches = stitches - self._stitches_completed
            completion_reward = new_stitches * self.completion_bonus
            reward += completion_reward
            components["stitch_completion"] = completion_reward
            self._stitches_completed = stitches

        # Needle drop penalty
        if info.get("needle_dropped", False):
            reward += self.drop_penalty
            components["needle_drop"] = self.drop_penalty

        total = reward * self.weight
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={"stitches_completed": self._stitches_completed},
        )

    def reset(self) -> None:
        """Reset stitch counter."""
        self._stitches_completed = 0


class DissectionReward(BaseRewardFunction):
    """Task-specific reward for tissue dissection tasks.

    Rewards progress along the planned incision path, clean cuts with
    appropriate force, and penalizes collateral tissue damage.
    """

    def __init__(
        self,
        weight: float = 1.0,
        progress_scale: float = 10.0,
        damage_penalty: float = -5.0,
        force_threshold: float = 2.0,
        clean_cut_bonus: float = 2.0,
    ):
        """Initialize dissection reward.

        Args:
            weight: Weight for this reward component.
            progress_scale: Scale factor for incision progress reward.
            damage_penalty: Penalty per unit of collateral damage.
            force_threshold: Force threshold for clean-cut bonus.
            clean_cut_bonus: Bonus for cutting below force threshold.
        """
        self.weight = weight
        self.progress_scale = progress_scale
        self.damage_penalty = damage_penalty
        self.force_threshold = force_threshold
        self.clean_cut_bonus = clean_cut_bonus
        self._prev_progress: float = 0.0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute dissection task reward."""
        reward = 0.0
        components: dict[str, float] = {}

        # Incision progress reward
        progress = observation.get("incision_progress")
        if progress is not None:
            current = float(progress.item() if progress.size == 1 else progress[0])
            delta = current - self._prev_progress
            if delta > 0:
                progress_reward = delta * self.progress_scale
                reward += progress_reward
                components["incision_progress"] = progress_reward
            self._prev_progress = current

        # Collateral damage penalty
        damage = float(info.get("collateral_damage", 0.0))
        if damage > 0:
            damage_pen = damage * self.damage_penalty
            reward += damage_pen
            components["collateral_damage"] = damage_pen

        # Clean cut bonus
        if info.get("cutting", False):
            cut_force = observation.get("cut_force")
            if cut_force is not None:
                force = float(cut_force.item() if cut_force.size == 1 else cut_force[0])
                if force < self.force_threshold:
                    reward += self.clean_cut_bonus
                    components["clean_cut"] = self.clean_cut_bonus

        total = reward * self.weight
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={"incision_progress": self._prev_progress},
        )

    def reset(self) -> None:
        """Reset progress tracking."""
        self._prev_progress = 0.0


class NeedlePassingReward(BaseRewardFunction):
    """Task-specific reward for needle passing/handoff tasks.

    Rewards proximity of the needle to the receiving instrument,
    successful handoffs, and penalizes dropping the needle.
    """

    def __init__(
        self,
        weight: float = 1.0,
        handoff_threshold: float = 0.02,
        handoff_bonus: float = 30.0,
        drop_penalty: float = -20.0,
        proximity_scale: float = 50.0,
    ):
        """Initialize needle passing reward.

        Args:
            weight: Weight for this reward component.
            handoff_threshold: Distance threshold for successful handoff (m).
            handoff_bonus: Reward for each successful handoff.
            drop_penalty: Penalty for dropping the needle.
            proximity_scale: Scale for exponential proximity reward.
        """
        self.weight = weight
        self.handoff_threshold = handoff_threshold
        self.handoff_bonus = handoff_bonus
        self.drop_penalty = drop_penalty
        self.proximity_scale = proximity_scale
        self._handoffs_completed: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute needle passing task reward."""
        reward = 0.0
        components: dict[str, float] = {}

        # Proximity reward
        needle_pos = observation.get("needle_pos")
        receiver_pos = observation.get("receiver_pos")
        if needle_pos is not None and receiver_pos is not None:
            distance = float(np.linalg.norm(needle_pos - receiver_pos))
            if distance < self.handoff_threshold:
                proximity_reward = 1.0
            else:
                proximity_reward = float(np.exp(-distance * self.proximity_scale))
            reward += proximity_reward
            components["handoff_proximity"] = proximity_reward

        # Successful handoff bonus
        handoffs = int(info.get("handoffs_completed", 0))
        if handoffs > self._handoffs_completed:
            new_handoffs = handoffs - self._handoffs_completed
            bonus = new_handoffs * self.handoff_bonus
            reward += bonus
            components["handoff_success"] = bonus
            self._handoffs_completed = handoffs

        # Dropped needle penalty
        if info.get("needle_dropped", False):
            reward += self.drop_penalty
            components["needle_drop"] = self.drop_penalty

        total = reward * self.weight
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={"handoffs_completed": self._handoffs_completed},
        )

    def reset(self) -> None:
        """Reset handoff counter."""
        self._handoffs_completed = 0


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
        components: list[tuple[BaseRewardFunction, float]] | None = None,
    ):
        """Initialize composite reward.

        Args:
            components: List of (reward_function, weight) tuples.
        """
        self.components: list[tuple[BaseRewardFunction, float]] = components or []

    def add(self, reward_fn: BaseRewardFunction, weight: float = 1.0) -> None:
        """Add a reward component.

        Args:
            reward_fn: Reward function to add.
            weight: Weight for this component.
        """
        self.components.append((reward_fn, weight))

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute composite reward."""
        total_reward = 0.0
        all_components: dict[str, float] = {}
        all_info: dict[str, Any] = {}

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


def create_default_reward(
    config: RewardConfig | None = None,
    task_name: str | None = None,
) -> CompositeReward:
    """Create a default composite reward function for surgical tasks.

    Args:
        config: Reward configuration. Uses defaults if None.
        task_name: Optional task name to include task-specific rewards.

    Returns:
        CompositeReward with standard surgical task reward components.
    """
    config = config or RewardConfig()

    reward = CompositeReward(
        [
            (
                DistanceReward(
                    weight=config.distance_weight,
                    shape=config.shape,
                    threshold=config.distance_threshold,
                ),
                1.0,
            ),
            (
                OrientationReward(
                    weight=config.orientation_weight,
                    threshold=config.angle_threshold,
                ),
                1.0,
            ),
            (ActionPenalty(weight=config.action_penalty_weight), 1.0),
            (TimePenalty(weight=config.time_penalty_weight), 1.0),
            (
                SuccessReward(
                    success_reward=config.success_reward,
                    failure_penalty=config.failure_penalty,
                    distance_threshold=config.distance_threshold,
                    angle_threshold=config.angle_threshold,
                ),
                1.0,
            ),
            (
                CollisionPenalty(
                    weight=config.collision_penalty,
                    tissue_weight=config.tissue_damage_penalty,
                ),
                1.0,
            ),
        ]
    )

    # Add task-specific rewards based on task name
    task_lower = (task_name or "").lower()
    if "sutur" in task_lower:
        reward.add(SuturingReward(weight=1.0), 1.0)
    elif "dissect" in task_lower:
        reward.add(DissectionReward(weight=1.0), 1.0)
    elif "needle_pass" in task_lower or "needlepass" in task_lower or "handoff" in task_lower:
        reward.add(NeedlePassingReward(weight=1.0), 1.0)

    return reward
