"""Difficulty level presets for surgical tasks.

The enum is the public API for difficulty selection. Internally, downstream
code uses the scalar value (0.0=EASY, 0.5=MEDIUM, 1.0=HARD) via .value to
drive `interpolate_params()` (D-29-02). This avoids double-validation:
Pydantic validates enum membership at the schema boundary; downstream
uses only the float scalar.

This module is intentionally a leaf (no imports from `surg_rl.*`) to keep
`rewards.py` importable from `schema.py` without a circular import
(per CONTEXT.md §Circular import risk).
"""

from enum import Enum


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
