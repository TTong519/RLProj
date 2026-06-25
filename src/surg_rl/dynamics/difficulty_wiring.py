"""Wiring layer for per-level difficulty overrides (Phase 36, TASK-06).

Holds the abstract->concrete PARAM_BOUNDS mapping (D-05), the
DiscreteCurriculumConfig wrapper (D-08), and the additive
compose_difficulty_overrides helper (D-06). Imports DifficultyLevel +
DifficultyLevelConfig from rl.difficulty one-way (no cycle).

Architecture (one-way edges, SC#5):
    dynamics.difficulty_wiring -> rl.difficulty (leaf)
    dynamics.curriculum        -> dynamics.difficulty_wiring (Plan 03)
The wiring module imports ONLY the leaf. It does NOT import curriculum,
scene_definition, or task_reward_router -- the composition helper receives
``reward_cls`` as a parameter (RESEARCH.md Open Q3), so no reverse edge and
no Pydantic cross-package cycle is created.
"""

from typing import Any

from pydantic import BaseModel, Field

from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# D-05 abstract->concrete PARAM_BOUNDS mapping, keyed by task_type per the
# corrected D-03 (NOT TaskConfig.name -- see RESEARCH.md Pitfall 2). Validated
# cell-by-cell against rewards.py PARAM_BOUNDS. Empty cells mean the abstract
# field has no mapping for that task (D-04: warn + keep interpolated value).
ABSTRACT_TO_CONCRETE: dict[str, dict[str, str]] = {
    "suturing": {
        "target_precision_tolerance": "needle_position_tolerance",
        "time_limit": "time_limit",
    },
    "dissection": {
        "tissue_stiffness": "tissue_stiffness",
        "target_precision_tolerance": "incision_path_tolerance",
        "time_limit": "time_limit",
    },
    "needle_insertion": {
        "target_precision_tolerance": "needle_alignment_tolerance",
        "tool_position_noise": "action_noise",
        "time_limit": "time_limit",
    },
    "knot_tying": {
        "tissue_stiffness": "tissue_stiffness",
        "target_precision_tolerance": "loop_deviation_tolerance",
        "tool_position_noise": "action_noise",
        "time_limit": "time_limit",
    },
    "grasping": {
        "target_precision_tolerance": "approach_tolerance",
        "tool_position_noise": "action_noise",
        "time_limit": "time_limit",
    },
    "cutting": {
        "tissue_stiffness": "tissue_stiffness",
        "target_precision_tolerance": "cut_path_accuracy",
        "time_limit": "time_limit",
    },
}

# The four override field names on DifficultyLevelConfig (D-01 abstract aliases).
_ABSTRACT_FIELDS: tuple[str, ...] = (
    "tissue_stiffness",
    "target_precision_tolerance",
    "tool_position_noise",
    "time_limit",
)


class DiscreteCurriculumConfig(BaseModel):
    """Wrapper for per-level DifficultyLevelConfig overrides (D-08).

    ``levels`` maps each DifficultyLevel to its override config. The default
    empty dict means "no overrides" -- compose_difficulty_overrides then
    returns the pure interpolate_params(level.value) baseline for every level
    (D-08). Consumers (Plan 03 CurriculumScheduler) look up the per-level
    config and pass it through the composer.
    """

    levels: dict[DifficultyLevel, DifficultyLevelConfig] = Field(default_factory=dict)


def compose_difficulty_overrides(
    task_type: str,
    level: DifficultyLevel,
    config: DifficultyLevelConfig,
    reward_cls: Any,
) -> dict[str, float]:
    """Compose per-level overrides additively over interpolate_params (D-06).

    Compute the interpolated baseline dict FIRST (D-06), then for each SET
    (non-None) abstract override field, look up the concrete PARAM_BOUNDS key
    via ABSTRACT_TO_CONCRETE[task_type] and replace that key's value with the
    ABSOLUTE override value (not a delta/multiplier). Unoverridden keys retain
    the interpolated value. An override field with no mapping for the loaded
    task_type logs a warning and keeps the interpolated value (D-04 -- never
    raises KeyError).

    Args:
        task_type: One of the 6 TASK_REWARD_REGISTRY keys (suturing, dissection,
            needle_insertion, knot_tying, grasping, cutting). Unknown task_type
            yields an empty mapping -- all override fields warn-and-no-op.
        level: DifficultyLevel preset (EASY/MEDIUM/HARD); .value drives
            interpolate_params.
        config: DifficultyLevelConfig carrying 0-4 SET override fields.
        reward_cls: The task-specific reward class (e.g. SuturingReward) whose
            ``interpolate_params`` classmethod provides the additive baseline.
            Passed in by the caller (RESEARCH.md Open Q3) -- this module does
            NOT import task_reward_router.

    Returns:
        A dict equal to ``reward_cls.interpolate_params(level.value)`` except
        on mapped overridden keys, which hold the absolute override value.
    """
    # D-06: interpolate FIRST to establish the additive baseline.
    composed: dict[str, float] = reward_cls.interpolate_params(level.value)
    task_map = ABSTRACT_TO_CONCRETE.get(task_type, {})
    for abstract_field in _ABSTRACT_FIELDS:
        override_value = getattr(config, abstract_field)
        if override_value is None:
            continue
        concrete_key = task_map.get(abstract_field)
        if concrete_key is None:
            # D-04: unmapped override -- warn + keep interpolated value (no raise).
            logger.warning(
                "override field %r has no mapping for task_type=%r; " "keeping interpolated value",
                abstract_field,
                task_type,
            )
            continue
        # D-06: ABSOLUTE replacement (not a delta/multiplier).
        composed[concrete_key] = override_value
    return composed
