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

from surg_rl.rl.task_results import (
    CuttingResult,
    DissectionResult,
    GraspingResult,
    KnotTyingResult,
    NeedleInsertionResult,
    SuturingResult,
)


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

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Default implementation is a no-op for generic rewards (DistanceReward,
        ActionPenalty, TimePenalty, CollisionPenalty, OrientationReward,
        SuccessReward, CompositeReward). Task-specific subclasses
        (SuturingReward, DissectionReward, NeedlePassingReward,
        KnotTyingReward, GraspingReward, CuttingReward) override this
        method to map `interpolate_params(difficulty)` results to their
        own ctor fields. Called by TaskRewardRouter.build() after
        reward construction.

        The empty body is INTENTIONAL — see D-PLUMB-06: generic rewards
        must NOT be modified to consume difficulty. The override pattern
        in subclasses keeps this method load-bearing for the 6 task
        rewards while preserving the safe default for the 4 generic ones.

        Args:
            difficulty: Scalar difficulty in [0.0, 1.0] (0.0=EASY, 1.0=HARD).
        """
        # Intentional no-op default per D-PLUMB-06. The override pattern in
        # the 6 task-specific subclasses keeps this method load-bearing
        # while preserving the safe default for the 4 generic ones.
        return None  # noqa: B027


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

    PARAM_BOUNDS: dict[str, list[float]] = {
        "needle_position_tolerance": [0.02, 0.002],  # m (20mm → 2mm)
        "thread_tension_threshold": [1.0, 0.2],  # normalized
        "stitch_spacing_tolerance": [0.01, 0.002],  # m
        "time_limit": [120.0, 45.0],  # seconds
    }

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
        self._needle_dropped_flag: bool = False
        self._steps: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute suturing task reward."""
        self._steps += 1
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
            self._needle_dropped_flag = True
            reward += self.drop_penalty
            components["needle_drop"] = self.drop_penalty

        total = reward * self.weight
        total = _clamp_finite(total)
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={"stitches_completed": self._stitches_completed},
        )

    def reset(self) -> None:
        """Reset stitch counter."""
        self._stitches_completed = 0
        self._needle_dropped_flag = False
        self._steps = 0

    def check_success(self, difficulty: float) -> SuturingResult:
        """Check if the suturing task succeeded."""
        return SuturingResult(
            success=self._stitches_completed > 0,
            failure_reason=None if self._stitches_completed > 0 else "no_stitches",
            stitches_completed=self._stitches_completed,
            thread_tension_avg=0.0,
            difficulty=difficulty,
        )

    def check_failure(self, difficulty: float) -> SuturingResult:
        """Check if the suturing task failed."""
        dropped = getattr(self, "_needle_dropped_flag", False)
        if dropped:
            return SuturingResult(
                success=False,
                failure_reason="needle_dropped",
                stitches_completed=self._stitches_completed,
                thread_tension_avg=0.0,
                difficulty=difficulty,
            )
        return SuturingResult(
            success=True,
            failure_reason=None,
            stitches_completed=self._stitches_completed,
            thread_tension_avg=0.0,
            difficulty=difficulty,
        )

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar."""
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }

    @classmethod
    def get_params_for_difficulty(cls, level) -> dict[str, float]:
        """Public read-only accessor for difficulty parameters.

        Delegates to interpolate_params() — does NOT mutate the instance.
        Use apply_difficulty() to mutate. The type hint is intentionally
        `level` (no import) to avoid coupling this method to the
        DifficultyLevel enum at runtime; callers may pass a
        DifficultyLevel member (its .value is used implicitly) or any
        object with a .value attribute.
        """
        return cls.interpolate_params(level.value)

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02:
        partial mapping is acceptable). Unmapped keys are skipped.
        """
        params = self.interpolate_params(difficulty)
        if "needle_position_tolerance" in params and hasattr(self, "position_threshold"):
            self.position_threshold = params["needle_position_tolerance"]


class DissectionReward(BaseRewardFunction):
    """Task-specific reward for tissue dissection tasks.

    Rewards progress along the planned incision path, clean cuts with
    appropriate force, and penalizes collateral tissue damage.
    """

    PARAM_BOUNDS: dict[str, list[float]] = {
        "incision_path_tolerance": [0.01, 0.002],  # m
        "collateral_damage_threshold": [0.05, 0.01],  # allowable damage
        "force_precision": [3.0, 1.0],  # N threshold
        "tissue_stiffness": [50.0, 200.0],  # N/m
        "time_limit": [180.0, 60.0],  # seconds
    }

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
        self._clean_cuts: int = 0
        self._cut_attempts: int = 0
        self._damage_accum: float = 0.0
        self._steps: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute dissection task reward."""
        self._steps += 1
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
            self._damage_accum += damage
            damage_pen = damage * self.damage_penalty
            reward += damage_pen
            components["collateral_damage"] = damage_pen

        # Clean cut bonus
        if info.get("cutting", False):
            self._cut_attempts += 1
            cut_force = observation.get("cut_force")
            if cut_force is not None:
                force = float(cut_force.item() if cut_force.size == 1 else cut_force[0])
                if force < self.force_threshold:
                    self._clean_cuts += 1
                    reward += self.clean_cut_bonus
                    components["clean_cut"] = self.clean_cut_bonus

        total = reward * self.weight
        total = _clamp_finite(total)
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={"incision_progress": self._prev_progress},
        )

    def reset(self) -> None:
        """Reset progress tracking."""
        self._prev_progress = 0.0
        self._clean_cuts = 0
        self._cut_attempts = 0
        self._damage_accum = 0.0
        self._steps = 0

    def check_success(self, difficulty: float) -> DissectionResult:
        """Check if the dissection task succeeded."""
        return DissectionResult(
            success=self._prev_progress >= 0.95,
            failure_reason=None if self._prev_progress >= 0.95 else "incision_incomplete",
            incision_completion=self._prev_progress,
            clean_cut_ratio=self._clean_cuts / max(1, self._cut_attempts),
            difficulty=difficulty,
        )

    def check_failure(self, difficulty: float) -> DissectionResult:
        """Check if the dissection task failed."""
        if getattr(self, "_damage_accum", 0.0) > 0.5:
            return DissectionResult(
                success=False,
                failure_reason="excessive_collateral_damage",
                incision_completion=self._prev_progress,
                clean_cut_ratio=self._clean_cuts / max(1, self._cut_attempts),
                difficulty=difficulty,
            )
        return DissectionResult(
            success=True,
            failure_reason=None,
            incision_completion=self._prev_progress,
            clean_cut_ratio=self._clean_cuts / max(1, self._cut_attempts),
            difficulty=difficulty,
        )

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar."""
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }

    @classmethod
    def get_params_for_difficulty(cls, level) -> dict[str, float]:
        """Public read-only accessor for difficulty parameters.

        Delegates to interpolate_params() — does NOT mutate the instance.
        Use apply_difficulty() to mutate.
        """
        return cls.interpolate_params(level.value)

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
        """
        params = self.interpolate_params(difficulty)
        if "force_precision" in params and hasattr(self, "force_threshold"):
            self.force_threshold = params["force_precision"]


class NeedlePassingReward(BaseRewardFunction):
    """Task-specific reward for needle passing/handoff tasks.

    Rewards proximity of the needle to the receiving instrument,
    successful handoffs, and penalizes dropping the needle.
    """

    PARAM_BOUNDS: dict[str, list[float]] = {
        "handoff_proximity_tolerance": [0.05, 0.01],  # m
        "needle_alignment_tolerance": [0.3, 0.05],  # rad
        "action_noise": [0.01, 0.06],  # std dev
        "time_limit": [90.0, 30.0],  # seconds
    }

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
        self._needle_dropped_flag: bool = False
        self._steps: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute needle passing task reward."""
        self._steps += 1
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
            self._needle_dropped_flag = True
            reward += self.drop_penalty
            components["needle_drop"] = self.drop_penalty

        total = reward * self.weight
        total = _clamp_finite(total)
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={"handoffs_completed": self._handoffs_completed},
        )

    def reset(self) -> None:
        """Reset handoff counter."""
        self._handoffs_completed = 0
        self._needle_dropped_flag = False
        self._steps = 0

    def check_success(self, difficulty: float) -> NeedleInsertionResult:
        """Check if the needle passing task succeeded."""
        return NeedleInsertionResult(
            success=self._handoffs_completed > 0,
            failure_reason=None if self._handoffs_completed > 0 else "no_handoffs",
            insertion_depth=float(self._handoffs_completed),
            deviation_angle=0.0,
            difficulty=difficulty,
        )

    def check_failure(self, difficulty: float) -> NeedleInsertionResult:
        """Check if the needle passing task failed."""
        if getattr(self, "_needle_dropped_flag", False):
            return NeedleInsertionResult(
                success=False,
                failure_reason="needle_dropped",
                insertion_depth=float(self._handoffs_completed),
                deviation_angle=0.0,
                difficulty=difficulty,
            )
        return NeedleInsertionResult(
            success=True,
            failure_reason=None,
            insertion_depth=float(self._handoffs_completed),
            deviation_angle=0.0,
            difficulty=difficulty,
        )

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar."""
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }

    @classmethod
    def get_params_for_difficulty(cls, level) -> dict[str, float]:
        """Public read-only accessor for difficulty parameters.

        Delegates to interpolate_params() — does NOT mutate the instance.
        Use apply_difficulty() to mutate.
        """
        return cls.interpolate_params(level.value)

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
        """
        params = self.interpolate_params(difficulty)
        if "handoff_proximity_tolerance" in params and hasattr(self, "handoff_threshold"):
            self.handoff_threshold = params["handoff_proximity_tolerance"]


class KnotTyingReward(BaseRewardFunction):
    """Task-specific reward for knot-tying tasks.

    Rewards proximity of the needle to the loop center, appropriate thread
    tension, and knot completion. Penalizes dropping the needle.
    """

    PARAM_BOUNDS: dict[str, list[float]] = {
        "loop_deviation_tolerance": [0.03, 0.005],  # m
        "knot_tension_tolerance": [0.5, 0.05],  # normalized
        "tissue_stiffness": [50.0, 200.0],  # N/m (higher = harder)
        "action_noise": [0.01, 0.08],  # std dev
        "time_limit": [120.0, 45.0],  # seconds
    }

    def __init__(
        self,
        weight: float = 1.0,
        loop_deviation_threshold: float = 0.01,
        tension_threshold: float = 0.5,
        knot_completion_bonus: float = 50.0,
        drop_penalty: float = -20.0,
    ):
        self.weight = weight
        self.loop_deviation_threshold = loop_deviation_threshold
        self.tension_threshold = tension_threshold
        self.knot_completion_bonus = knot_completion_bonus
        self.drop_penalty = drop_penalty
        self._knots_completed: int = 0
        self._needle_dropped: bool = False
        self._tension_accum: float = 0.0
        self._tension_samples: int = 0
        self._steps: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute knot-tying task reward."""
        self._steps += 1
        reward = 0.0
        components: dict[str, float] = {}

        # Loop deviation reward (needle position relative to loop center)
        needle_pos = observation.get("needle_pos")
        loop_center = observation.get("loop_center")
        if needle_pos is not None and loop_center is not None:
            distance = float(np.linalg.norm(needle_pos - loop_center))
            position_reward = float(np.exp(-distance * 100.0))
            reward += position_reward
            components["loop_deviation"] = position_reward

        # Thread tension penalty
        thread_tension = observation.get("thread_tension")
        if thread_tension is not None:
            tension = float(
                thread_tension.item() if thread_tension.size == 1 else thread_tension[0]
            )
            self._tension_accum += tension
            self._tension_samples += 1
            tension_penalty = -max(0.0, tension - self.tension_threshold)
            reward += tension_penalty
            components["thread_tension"] = tension_penalty

        # Knot completion bonus
        knots = int(info.get("knots_completed", 0))
        if knots > self._knots_completed:
            new_knots = knots - self._knots_completed
            completion_reward = new_knots * self.knot_completion_bonus
            reward += completion_reward
            components["knot_completion"] = completion_reward
            self._knots_completed = knots

        # Needle drop penalty
        if info.get("needle_dropped", False):
            self._needle_dropped = True
            reward += self.drop_penalty
            components["needle_drop"] = self.drop_penalty

        total = reward * self.weight
        total = _clamp_finite(total)
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={
                "knots_completed": self._knots_completed,
                "knot_tension_avg": self._tension_accum / max(1, self._tension_samples),
            },
        )

    def reset(self) -> None:
        """Reset knot tracking state."""
        self._knots_completed = 0
        self._needle_dropped = False
        self._tension_accum = 0.0
        self._tension_samples = 0
        self._steps = 0

    def check_success(self, difficulty: float) -> KnotTyingResult:
        """Check if the knot-tying task succeeded."""
        return KnotTyingResult(
            success=self._knots_completed > 0,
            failure_reason=None if self._knots_completed > 0 else "no_knots_completed",
            knots_completed=self._knots_completed,
            knot_tension_avg=self._tension_accum / max(1, self._tension_samples),
            difficulty=difficulty,
        )

    def check_failure(self, difficulty: float) -> KnotTyingResult:
        """Check if the knot-tying task failed."""
        dropped = getattr(self, "_needle_dropped", False)
        if dropped:
            return KnotTyingResult(
                success=False,
                failure_reason="needle_dropped",
                knots_completed=self._knots_completed,
                knot_tension_avg=self._tension_accum / max(1, self._tension_samples),
                difficulty=difficulty,
            )
        if self._knots_completed == 0 and self._steps > 100:
            return KnotTyingResult(
                success=False,
                failure_reason="no_progress",
                knots_completed=0,
                knot_tension_avg=0.0,
                difficulty=difficulty,
            )
        return KnotTyingResult(
            success=True,
            failure_reason=None,
            knots_completed=self._knots_completed,
            knot_tension_avg=self._tension_accum / max(1, self._tension_samples),
            difficulty=difficulty,
        )

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar."""
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }

    @classmethod
    def get_params_for_difficulty(cls, level) -> dict[str, float]:
        """Public read-only accessor for difficulty parameters.

        Delegates to interpolate_params() — does NOT mutate the instance.
        Use apply_difficulty() to mutate.
        """
        return cls.interpolate_params(level.value)

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
        """
        params = self.interpolate_params(difficulty)
        if "loop_deviation_tolerance" in params and hasattr(self, "loop_deviation_threshold"):
            self.loop_deviation_threshold = params["loop_deviation_tolerance"]


class GraspingReward(BaseRewardFunction):
    """Task-specific reward for grasping tasks.

    Rewards proximity of the gripper to the target object, appropriate
    grip force, and stable grasp. Penalizes dropping the object.
    """

    PARAM_BOUNDS: dict[str, list[float]] = {
        "approach_tolerance": [0.05, 0.005],  # m
        "grip_force_accuracy": [2.0, 0.3],  # N tolerance (lower = harder)
        "object_mass": [0.01, 0.1],  # kg (heavier = harder)
        "action_noise": [0.01, 0.06],  # std dev
        "time_limit": [90.0, 30.0],  # seconds
    }

    def __init__(
        self,
        weight: float = 1.0,
        grasp_threshold: float = 0.01,
        grip_force_range: tuple[float, float] = (0.5, 2.0),
        approach_bonus: float = 5.0,
        grasp_bonus: float = 50.0,
        drop_penalty: float = -20.0,
    ):
        self.weight = weight
        self.grasp_threshold = grasp_threshold
        self.grip_force_range = grip_force_range
        self.approach_bonus = approach_bonus
        self.grasp_bonus = grasp_bonus
        self.drop_penalty = drop_penalty
        self._grasp_stable_steps: int = 0
        self._object_dropped: bool = False
        self._force_accum: float = 0.0
        self._force_samples: int = 0
        self._steps: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute grasping task reward."""
        self._steps += 1
        reward = 0.0
        components: dict[str, float] = {}

        # Approach reward (distance to target object)
        gripper_pos = observation.get("gripper_pos")
        target_object_pos = observation.get("target_object_pos")
        if gripper_pos is not None and target_object_pos is not None:
            distance = float(np.linalg.norm(gripper_pos - target_object_pos))
            approach_reward = float(np.exp(-distance * 50.0))
            reward += approach_reward
            components["approach"] = approach_reward

        # Grip force reward
        grip_force = observation.get("grip_force")
        if grip_force is not None:
            force = float(grip_force.item() if grip_force.size == 1 else grip_force[0])
            self._force_accum += force
            self._force_samples += 1
            if self.grip_force_range[0] <= force <= self.grip_force_range[1]:
                reward += 1.0
                components["grip_force"] = 1.0
            else:
                components["grip_force"] = 0.0

        # Grasp detection
        grasp_detected = observation.get("grasp_detected")
        if grasp_detected is not None:
            gd = float(grasp_detected.item() if grasp_detected.size == 1 else grasp_detected[0])
            if gd > 0.5:
                self._grasp_stable_steps += 1
                reward += self.grasp_bonus
                components["grasp_success"] = self.grasp_bonus

        # Object dropped penalty
        if info.get("object_dropped", False):
            self._object_dropped = True
            reward += self.drop_penalty
            components["object_drop"] = self.drop_penalty

        total = reward * self.weight
        total = _clamp_finite(total)
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={
                "grasp_stable_steps": self._grasp_stable_steps,
                "grip_force_avg": self._force_accum / max(1, self._force_samples),
            },
        )

    def reset(self) -> None:
        """Reset grasp tracking state."""
        self._grasp_stable_steps = 0
        self._object_dropped = False
        self._force_accum = 0.0
        self._force_samples = 0
        self._steps = 0

    def check_success(self, difficulty: float) -> GraspingResult:
        """Check if the grasping task succeeded."""
        stable = self._grasp_stable_steps >= 50
        return GraspingResult(
            success=stable,
            failure_reason=None if stable else "grasp_not_stable",
            grasp_stable=stable,
            grip_force_avg=self._force_accum / max(1, self._force_samples),
            difficulty=difficulty,
        )

    def check_failure(self, difficulty: float) -> GraspingResult:
        """Check if the grasping task failed."""
        if getattr(self, "_object_dropped", False):
            return GraspingResult(
                success=False,
                failure_reason="object_dropped",
                grasp_stable=False,
                grip_force_avg=self._force_accum / max(1, self._force_samples),
                difficulty=difficulty,
            )
        if self._steps > 50 and self._grasp_stable_steps == 0:
            return GraspingResult(
                success=False,
                failure_reason="no_grasp_attempt",
                grasp_stable=False,
                grip_force_avg=0.0,
                difficulty=difficulty,
            )
        return GraspingResult(
            success=True,
            failure_reason=None,
            grasp_stable=True,
            grip_force_avg=self._force_accum / max(1, self._force_samples),
            difficulty=difficulty,
        )

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar."""
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }

    @classmethod
    def get_params_for_difficulty(cls, level) -> dict[str, float]:
        """Public read-only accessor for difficulty parameters.

        Delegates to interpolate_params() — does NOT mutate the instance.
        Use apply_difficulty() to mutate.
        """
        return cls.interpolate_params(level.value)

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
        """
        params = self.interpolate_params(difficulty)
        if "approach_tolerance" in params and hasattr(self, "grasp_threshold"):
            self.grasp_threshold = params["approach_tolerance"]


class CuttingReward(BaseRewardFunction):
    """Task-specific reward for cutting tasks.

    Rewards progress along the cut path, clean cuts with appropriate force,
    and penalizes collateral tissue damage.
    """

    PARAM_BOUNDS: dict[str, list[float]] = {
        "cut_path_accuracy": [0.01, 0.002],  # m deviation tolerance
        "collateral_threshold": [0.05, 0.01],  # allowable damage (lower = stricter)
        "force_precision": [3.0, 1.0],  # N (lower = harder to stay under)
        "tissue_stiffness": [50.0, 300.0],  # N/m (higher = harder)
        "time_limit": [120.0, 60.0],  # seconds
    }

    def __init__(
        self,
        weight: float = 1.0,
        cut_progress_scale: float = 10.0,
        collateral_penalty: float = -5.0,
        force_threshold: float = 3.0,
        completion_bonus: float = 100.0,
    ):
        self.weight = weight
        self.cut_progress_scale = cut_progress_scale
        self.collateral_penalty = collateral_penalty
        self.force_threshold = force_threshold
        self.completion_bonus = completion_bonus
        self._prev_progress: float = 0.0
        self._cut_complete: bool = False
        self._damage_accum: float = 0.0
        self._steps: int = 0

    def compute(
        self,
        observation: dict[str, np.ndarray],
        action: np.ndarray,
        info: dict[str, Any],
    ) -> RewardResult:
        """Compute cutting task reward."""
        self._steps += 1
        reward = 0.0
        components: dict[str, float] = {}

        # Cut progress reward
        cut_progress = observation.get("cut_progress")
        if cut_progress is not None:
            current = float(cut_progress.item() if cut_progress.size == 1 else cut_progress[0])
            delta = current - self._prev_progress
            if delta > 0:
                progress_reward = delta * self.cut_progress_scale
                reward += progress_reward
                components["cut_progress"] = progress_reward
            self._prev_progress = current

        # Collateral damage penalty
        damage = observation.get("collateral_damage")
        if damage is not None:
            dmg = float(damage.item() if damage.size == 1 else damage[0])
            self._damage_accum += dmg
            if dmg > 0:
                damage_pen = dmg * self.collateral_penalty
                reward += damage_pen
                components["collateral_damage"] = damage_pen

        # Clean cut bonus (force below threshold)
        cut_force = observation.get("cut_force")
        if cut_force is not None:
            force = float(cut_force.item() if cut_force.size == 1 else cut_force[0])
            if force < self.force_threshold:
                components["clean_cut"] = 1.0
            else:
                components["clean_cut"] = 0.0

        # Cut completion bonus
        if info.get("cut_complete", False):
            self._cut_complete = True
            reward += self.completion_bonus
            components["cut_complete"] = self.completion_bonus

        total = reward * self.weight
        total = _clamp_finite(total)
        return RewardResult(
            total=total,
            components={k: v * self.weight for k, v in components.items()},
            info={
                "cut_progress": self._prev_progress,
                "collateral_damage": self._damage_accum,
            },
        )

    def reset(self) -> None:
        """Reset cutting tracking state."""
        self._prev_progress = 0.0
        self._cut_complete = False
        self._damage_accum = 0.0
        self._steps = 0

    def check_success(self, difficulty: float) -> CuttingResult:
        """Check if the cutting task succeeded."""
        complete = self._cut_complete
        return CuttingResult(
            success=complete,
            failure_reason=None if complete else "cut_incomplete",
            cut_completion=self._prev_progress,
            collateral_damage=self._damage_accum,
            difficulty=difficulty,
        )

    def check_failure(self, difficulty: float) -> CuttingResult:
        """Check if the cutting task failed."""
        if self._damage_accum > 1.0:
            return CuttingResult(
                success=False,
                failure_reason="excessive_collateral_damage",
                cut_completion=self._prev_progress,
                collateral_damage=self._damage_accum,
                difficulty=difficulty,
            )
        if self._steps > 100 and self._prev_progress < 0.1:
            return CuttingResult(
                success=False,
                failure_reason="cut_not_started",
                cut_completion=0.0,
                collateral_damage=0.0,
                difficulty=difficulty,
            )
        return CuttingResult(
            success=True,
            failure_reason=None,
            cut_completion=self._prev_progress,
            collateral_damage=self._damage_accum,
            difficulty=difficulty,
        )

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar."""
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }

    @classmethod
    def get_params_for_difficulty(cls, level) -> dict[str, float]:
        """Public read-only accessor for difficulty parameters.

        Delegates to interpolate_params() — does NOT mutate the instance.
        Use apply_difficulty() to mutate.
        """
        return cls.interpolate_params(level.value)

    def apply_difficulty(self, difficulty: float) -> None:
        """Apply interpolated difficulty parameters to this reward instance.

        Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
        """
        params = self.interpolate_params(difficulty)
        if "force_precision" in params and hasattr(self, "force_threshold"):
            self.force_threshold = params["force_precision"]


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
