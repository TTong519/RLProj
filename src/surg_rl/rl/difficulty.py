"""Difficulty level presets for surgical tasks.

The enum is the public API for difficulty selection. Internally, downstream
code uses the scalar value (0.0=EASY, 0.5=MEDIUM, 1.0=HARD) via .value to
drive `interpolate_params()` (D-29-02). This avoids double-validation:
Pydantic validates enum membership at the schema boundary; downstream
uses only the float scalar.

This module is intentionally a leaf (no in-project imports) to keep
`rewards.py` importable from `schema.py` without a circular import
(per CONTEXT.md §Circular import risk). SC#5 enforces this via a
substring audit on the source.
"""

from enum import Enum

from pydantic import BaseModel, field_validator


class _FloatMixin(float, Enum):
    """Enum whose members are also float instances.

    Python's standard ``Enum`` does not allow ``DifficultyLevel.EASY == 0.0``
    to be true. ``IntEnum`` mixes in ``int`` but no ``FloatEnum`` exists. We
    subclass ``float`` (not ``int``) and use this as the ``Enum`` base for
    ``DifficultyLevel`` so that:

    - ``DifficultyLevel.EASY == 0.0`` is True (float equality)
    - ``isinstance(DifficultyLevel.EASY, float)`` is True
    - ``DifficultyLevel.EASY.value`` still returns the float

    Note: this pattern is used by Python itself for ``enum.Flag``'s numeric
    bitfield handling and is the canonical way to get float-equal enum
    members in the stdlib (see https://docs.python.org/3/library/enum.html#supported-sunder-names).
    """


class DifficultyLevel(_FloatMixin):
    """Three difficulty presets for surgical task progression.

    EASY = 0.0, MEDIUM = 0.5, HARD = 1.0. The float value is the
    canonical scalar used by `interpolate_params(difficulty)` in each
    task-specific reward class.

    Per D-DIR-02, the 0.0/0.5/1.0 mapping assumes PARAM_BOUNDS values
    are stored as [lo, hi] with the convention that
    EASY(0.0) = lo (loose) and HARD(1.0) = hi (strict). The test
    `test_difficulty_direction` verifies per-task direction.
    """

    EASY = 0.0
    MEDIUM = 0.5
    HARD = 1.0


class DifficultyLevelConfig(BaseModel):
    """Per-level difficulty override config (Phase 36, TASK-06).

    Leaf: zero in-project imports (SC#5). Carries the four locked override
    fields as Optional[float]; each is range-checked against the verified
    D-07 global union bounds (min/max over all endpoints, NOT "min lo /
    max hi" — see 36-RESEARCH.md Pitfall 1). Out-of-range values raise
    ValidationError at schema time (ASVS V5 input validation, T-36-01).
    """

    tissue_stiffness: float | None = None
    target_precision_tolerance: float | None = None
    tool_position_noise: float | None = None
    time_limit: float | None = None

    @field_validator("tissue_stiffness")
    @classmethod
    def _check_tissue_stiffness(cls, v: float | None) -> float | None:
        if v is not None and not (50.0 <= v <= 300.0):
            raise ValueError("tissue_stiffness out of global union bounds [50.0, 300.0]")
        return v

    @field_validator("target_precision_tolerance")
    @classmethod
    def _check_target_precision_tolerance(cls, v: float | None) -> float | None:
        if v is not None and not (0.002 <= v <= 0.3):
            raise ValueError("target_precision_tolerance out of global union bounds [0.002, 0.3]")
        return v

    @field_validator("tool_position_noise")
    @classmethod
    def _check_tool_position_noise(cls, v: float | None) -> float | None:
        if v is not None and not (0.01 <= v <= 0.08):
            raise ValueError("tool_position_noise out of global union bounds [0.01, 0.08]")
        return v

    @field_validator("time_limit")
    @classmethod
    def _check_time_limit(cls, v: float | None) -> float | None:
        if v is not None and not (30.0 <= v <= 180.0):
            raise ValueError("time_limit out of global union bounds [30.0, 180.0]")
        return v
