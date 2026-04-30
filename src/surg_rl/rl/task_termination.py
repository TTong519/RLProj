"""Backend-agnostic task success detection for surgical environments.

This module provides heuristics that operate solely on observations and
scene task definitions, without reaching into simulator internals.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

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
