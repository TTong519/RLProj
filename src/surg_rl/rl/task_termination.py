"""Backend-agnostic task success detection for surgical environments.

This module provides heuristics that operate solely on observations and
scene task definitions, without reaching into simulator internals.
Phase 21 extends check_task_success() to delegate to per-task reward
check_success() methods, with generic heuristics as fallback.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from surg_rl.rl.task_results import TaskResult
from surg_rl.scene_definition.schema import SceneDefinition, TaskConfig
from surg_rl.simulators.base_simulator import Observation


def _parse_distance_criteria(text: str) -> float | None:
    """Try to extract a distance threshold from a criteria string.

    Handles patterns like 'distance < 0.02', 'reach target within 0.05m'.
    """
    if text is None:
        return None
    lower = text.lower()
    # Look for a number preceded by a comparison symbol or unit suffix
    tokens = lower.split()
    for i, token in enumerate(tokens):
        if token in ("<", "<=", "=", "==") and i + 1 < len(tokens):
            try:
                val = float(tokens[i + 1].replace("m", ""))
                return val
            except ValueError:
                pass
        # "within 0.05m" or "0.05 m"
        try:
            val = float(token.replace("m", ""))
            return val
        except ValueError:
            pass
    return None


def check_task_success(
    scene: SceneDefinition,
    observation: Observation,
    target_pos: np.ndarray | None = None,
    target_quat: np.ndarray | None = None,
    info: dict[str, Any] | None = None,
    reward_fn: Any = None,  # Phase 21: per-task reward with check_success()
) -> tuple[bool, dict[str, Any]]:
    """Check whether task success criteria are satisfied.

    This is fully backend-agnostic: it uses simulator ``Observation`` fields
    and scene ``TaskConfig`` / ``TaskObjective`` definitions only.

    Returns:
        Tuple of (success: bool, info: dict).
    """
    if scene.task is None:
        return False, {}

    task: TaskConfig = scene.task
    info = info or {}
    success = False
    details: dict[str, Any] = {}

    # Phase 21: Delegate to per-task reward check_success if available (D-06)
    if reward_fn is not None and hasattr(reward_fn, "check_success"):
        try:
            # Get difficulty from info or default
            difficulty = float(info.get("difficulty", 0.5))
            task_result: TaskResult = reward_fn.check_success(difficulty)
            if task_result.success:
                return True, {
                    "task_type": task.task_type,
                    "success": True,
                    "difficulty": difficulty,
                    "metrics": task_result.metrics,
                }
            # Not a success via per-task check — fall through to generic heuristics
            # but keep the task_result for downstream consumption
            info["_task_result"] = task_result
        except Exception:
            pass  # Fall through to generic heuristics on any error

    # ------------------------------------------------------------------
    # 1. Distance-based heuristic (end-effector → target)
    # ------------------------------------------------------------------
    ee_pos = observation.end_effector_pos if observation else None
    if ee_pos is not None and target_pos is not None:
        distance = float(np.linalg.norm(ee_pos - target_pos))
        details["distance"] = distance

        # Scene-level global threshold
        threshold = getattr(task, "success_threshold", 0.02)
        success = distance <= threshold

        # Per-objective refinement
        if task.objectives:
            for obj in task.objectives:
                parsed = _parse_distance_criteria(obj.success_criteria)
                if parsed is not None:
                    success = success and (distance <= parsed)

    # ------------------------------------------------------------------
    # 2. Orientation-based heuristic (end-effector → target)
    # ------------------------------------------------------------------
    ee_quat = observation.end_effector_quat if observation else None
    if ee_quat is not None and target_quat is not None:
        angle = _quaternion_angle(ee_quat, target_quat)
        details["orientation_error"] = angle
        if success:
            success = angle <= math.radians(15.0)

    # ------------------------------------------------------------------
    # 3. Custom info flags (e.g. from reward functions)
    # ------------------------------------------------------------------
    if info.get("success", False):
        success = True

    return success, details


def _quaternion_angle(q1: np.ndarray, q2: np.ndarray) -> float:
    """Angle (radians) between two quaternions."""
    dot = float(np.clip(np.abs(np.dot(q1, q2)), 0.0, 1.0))
    return 2.0 * math.acos(dot)


def get_task_result(
    scene: SceneDefinition,
    reward_fn: Any = None,
    difficulty: float = 0.5,
) -> TaskResult | None:
    """Get structured TaskResult from per-task reward.

    Phase 21: Wraps reward.check_success() with safe fallback.

    Args:
        scene: Scene definition.
        reward_fn: Reward function with check_success().
        difficulty: Current difficulty level.

    Returns:
        TaskResult if reward_fn has check_success, None otherwise.
    """
    if reward_fn is not None and hasattr(reward_fn, "check_success"):
        try:
            return reward_fn.check_success(difficulty)
        except Exception:
            return None
    return None
