"""Pydantic v2 TaskResult hierarchy for structured surgical task success/failure detection.

This module defines a base ``TaskResult`` model and six per-task sub-models that provide
typed, validated, self-describing results from task-specific reward functions. These
results feed into curriculum progression and benchmarking.

Design contract (D-07):
    - All task-specific reward classes return a ``TaskResult`` subclass from
      ``check_success()`` / ``check_failure()``.
    - The ``metrics`` dict must contain summary statistics only (never raw observation
      arrays or simulator state). Reward class authors own content safety.
    - All construction uses standard Pydantic validation (never ``model_construct()``).

Module-level mapping:
    ``TASK_RESULT_MAP`` maps ``task_type`` strings (matching
    ``TaskConfig.task_type`` values) to the corresponding ``TaskResult``
    subclass. Plan 02 (TaskRewardRouter) consumes this map.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "TaskResult",
    "SuturingResult",
    "KnotTyingResult",
    "NeedleInsertionResult",
    "GraspingResult",
    "CuttingResult",
    "DissectionResult",
    "TASK_RESULT_MAP",
]


class TaskResult(BaseModel):
    """D-07: Base structured result for task success/failure detection.

    All per-task result sub-models inherit from this base. Fields are
    validated on construction via standard Pydantic v2 behaviour (no
    ``model_construct()``).
    """

    success: bool = Field(description="Whether the task succeeded")
    failure_reason: str | None = Field(
        default=None, description="Reason for failure (None if success)"
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Task-specific metrics for benchmarking"
    )
    difficulty: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Difficulty level at episode end"
    )


class SuturingResult(TaskResult):
    """Structured result for suturing task episodes."""

    stitches_completed: int = Field(default=0, ge=0)
    thread_tension_avg: float = Field(default=0.0, ge=0.0)


class KnotTyingResult(TaskResult):
    """Structured result for knot-tying task episodes."""

    knots_completed: int = Field(default=0, ge=0)
    knot_tension_avg: float = Field(default=0.0, ge=0.0)


class NeedleInsertionResult(TaskResult):
    """Structured result for needle-insertion task episodes."""

    insertion_depth: float = Field(default=0.0, ge=0.0)
    deviation_angle: float = Field(default=0.0, ge=0.0)


class GraspingResult(TaskResult):
    """Structured result for grasping task episodes."""

    grasp_stable: bool = Field(default=False)
    grip_force_avg: float = Field(default=0.0, ge=0.0)


class CuttingResult(TaskResult):
    """Structured result for cutting task episodes."""

    cut_completion: float = Field(default=0.0, ge=0.0, le=1.0)
    collateral_damage: float = Field(default=0.0, ge=0.0)


class DissectionResult(TaskResult):
    """Structured result for dissection task episodes."""

    incision_completion: float = Field(default=0.0, ge=0.0, le=1.0)
    clean_cut_ratio: float = Field(default=1.0, ge=0.0, le=1.0)


# ----------------------------------------------------------------
# Module-level dispatch map — consumed by Plan 02 TaskRewardRouter
# ----------------------------------------------------------------

TASK_RESULT_MAP: dict[str, type[TaskResult]] = {
    "suturing": SuturingResult,
    "knot_tying": KnotTyingResult,
    "needle_insertion": NeedleInsertionResult,
    "grasping": GraspingResult,
    "cutting": CuttingResult,
    "dissection": DissectionResult,
}
