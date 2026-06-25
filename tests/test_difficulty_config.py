"""Tests for DifficultyLevelConfig Pydantic v2 leaf model (Phase 36, TASK-06 / SC#1 / SC#5)."""

import pytest
from pydantic import ValidationError

from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig
import surg_rl.rl.difficulty as _difficulty_module

# Plan 02 (SC#2 / D-04) imports — the wiring layer under test.
from surg_rl.dynamics.difficulty_wiring import (  # noqa: E402
    ABSTRACT_TO_CONCRETE,
    DiscreteCurriculumConfig,
    compose_difficulty_overrides,
)
from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY  # noqa: E402
from surg_rl.rl.rewards import (  # noqa: E402
    CuttingReward,
    DissectionReward,
    GraspingReward,
    KnotTyingReward,
    NeedlePassingReward,
    SuturingReward,
)

# Override values inside the verified D-07 global union bounds (Plan 01).
_OVERRIDE_VALUES: dict[str, float] = {
    "tissue_stiffness": 120.0,  # [50.0, 300.0]
    "target_precision_tolerance": 0.02,  # [0.002, 0.3]
    "tool_position_noise": 0.04,  # [0.01, 0.08]
    "time_limit": 90.0,  # [30.0, 180.0]
}

# Test-oracle mirror of D-05 (must match ABSTRACT_TO_CONCRETE cell-for-cell).
# Keyed by task_type per the corrected D-03 (NOT TaskConfig.name).
_D05_ORACLE: dict[str, dict[str, str]] = {
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

_LEVELS = [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]

# Build the truth-table parametrize set: (task_type, level, abstract_field, override_value)
# for every (task_type, level, mapped-abstract-field) tuple per D-05.
_TRUTH_TABLE_CASES = [
    (task_type, level, abstract_field, _OVERRIDE_VALUES[abstract_field])
    for task_type, field_map in _D05_ORACLE.items()
    for level in _LEVELS
    for abstract_field in field_map
]


class TestDifficultyLevelConfig:
    """Tests for the DifficultyLevelConfig Pydantic v2 leaf model (SC#1)."""

    def test_default_none(self):
        """All four override fields default to None when unset."""
        config = DifficultyLevelConfig()
        assert config.tissue_stiffness is None
        assert config.target_precision_tolerance is None
        assert config.tool_position_noise is None
        assert config.time_limit is None

    def test_in_range_construction(self):
        """In-range values for all four fields construct and round-trip."""
        config = DifficultyLevelConfig(
            tissue_stiffness=100.0,
            target_precision_tolerance=0.01,
            tool_position_noise=0.03,
            time_limit=60.0,
        )
        assert config.tissue_stiffness == 100.0
        assert config.target_precision_tolerance == 0.01
        assert config.tool_position_noise == 0.03
        assert config.time_limit == 60.0

    @pytest.mark.parametrize(
        ("field_name", "bad_value"),
        [
            ("tissue_stiffness", 999.0),
            ("tissue_stiffness", 10.0),
            ("target_precision_tolerance", 0.001),
            ("target_precision_tolerance", 0.5),
            ("tool_position_noise", 0.2),
            ("time_limit", 200.0),
            ("time_limit", 10.0),
        ],
    )
    def test_out_of_range_rejected(self, field_name, bad_value):
        """Out-of-range values for each field raise ValidationError (D-07 global bounds)."""
        with pytest.raises(ValidationError):
            DifficultyLevelConfig(**{field_name: bad_value})

    def test_type_rejection(self):
        """Non-float types raise ValidationError at schema time."""
        with pytest.raises(ValidationError):
            DifficultyLevelConfig(tissue_stiffness="high")


class TestLeafImportAudit:
    """SC#5: rl/difficulty.py stays a zero-in-project-import leaf (D-08 / SC#5)."""

    def test_leaf_no_inproject_imports(self):
        """The leaf source contains no `surg_rl.` references outside comments."""
        source_path = _difficulty_module.__file__
        assert source_path is not None, "Could not resolve surg_rl.rl.difficulty __file__"
        with open(source_path, "r", encoding="utf-8") as fh:
            raw_lines = fh.readlines()
        # Strip comment-only lines (lines whose stripped form starts with '#').
        non_comment_lines = [
            line for line in raw_lines if not line.strip().startswith("#")
        ]
        remaining_source = "".join(non_comment_lines)
        assert "surg_rl." not in remaining_source, (
            "SC#5 violation: surg_rl.rl.difficulty contains an in-project import "
            "(substring 'surg_rl.' found outside comments)."
        )


class TestComposeDifficultyOverrides:
    """SC#2 truth table + D-04 unmapped-override-warns tests for the wiring layer."""

    def test_abstract_to_concrete_matches_d05_oracle(self):
        """ABSTRACT_TO_CONCRETE matches the D-05 oracle cell-for-cell (D-03 task_type keying)."""
        assert ABSTRACT_TO_CONCRETE == _D05_ORACLE

    @pytest.mark.parametrize(
        ("task_type", "level", "abstract_field", "override_value"),
        _TRUTH_TABLE_CASES,
    )
    def test_compose_truth_table(self, task_type, level, abstract_field, override_value):
        """SC#2: overriding one field changes ONLY the mapped concrete key.

        Every other key retains the interpolated value; the override is the
        absolute replacement (D-06), not a delta/multiplier.
        """
        reward_cls = TASK_REWARD_REGISTRY[task_type]
        baseline = reward_cls.interpolate_params(level.value)
        cfg = DifficultyLevelConfig(**{abstract_field: override_value})
        composed = compose_difficulty_overrides(task_type, level, cfg, reward_cls)

        concrete_key = ABSTRACT_TO_CONCRETE[task_type][abstract_field]
        # The mapped concrete key holds the absolute override value (D-06).
        assert composed[concrete_key] == override_value
        # Every other key retains the interpolated baseline value (SC#2).
        for key, baseline_val in baseline.items():
            if key == concrete_key:
                continue
            assert composed[key] == baseline_val, (
                f"key {key!r} changed from baseline {baseline_val} to {composed[key]} "
                f"when only {abstract_field!r} was overridden"
            )
        # The composed dict has exactly the baseline keys (no new/missing keys).
        assert set(composed.keys()) == set(baseline.keys())

    @pytest.mark.parametrize(("task_type", "level"), [
        (tt, lvl) for tt in _D05_ORACLE for lvl in _LEVELS
    ])
    def test_compose_empty_levels_equals_interpolation(self, task_type, level):
        """SC#2: an all-None config yields pure interpolate_params(level.value) (D-08)."""
        reward_cls = TASK_REWARD_REGISTRY[task_type]
        cfg = DifficultyLevelConfig()  # all four fields None
        composed = compose_difficulty_overrides(task_type, level, cfg, reward_cls)
        assert composed == reward_cls.interpolate_params(level.value)

    def test_discrete_curriculum_config_default_empty(self):
        """D-08: DiscreteCurriculumConfig defaults to an empty levels dict."""
        dcc = DiscreteCurriculumConfig()
        assert dcc.levels == {}

    def test_discrete_curriculum_config_holds_levels(self):
        """DiscreteCurriculumConfig wraps the levels dict (round-trip one entry)."""
        cfg = DifficultyLevelConfig(time_limit=90.0)
        dcc = DiscreteCurriculumConfig(levels={DifficultyLevel.MEDIUM: cfg})
        assert DifficultyLevel.MEDIUM in dcc.levels
        assert dcc.levels[DifficultyLevel.MEDIUM].time_limit == 90.0

    def test_unmapped_override_warns(self, caplog):
        """D-04: an unmapped override logs a warning and keeps the interpolated value.

        tissue_stiffness has no mapping for suturing per D-05 (suturing has no
        tissue_stiffness PARAM_BOUNDS key). The composer must warn via the logger
        and leave the composed dict equal to pure interpolation — no raise, no
        KeyError.
        """
        task_type = "suturing"
        level = DifficultyLevel.MEDIUM
        reward_cls = TASK_REWARD_REGISTRY[task_type]  # SuturingReward
        baseline = reward_cls.interpolate_params(level.value)

        cfg = DifficultyLevelConfig(tissue_stiffness=120.0)
        with caplog.at_level("WARNING", logger="surg_rl.dynamics.difficulty_wiring"):
            composed = compose_difficulty_overrides(task_type, level, cfg, reward_cls)

        # A warning was logged mentioning the unmapped field + task_type (D-04).
        warning_records = [
            r for r in caplog.records if r.levelname == "WARNING"
        ]
        assert warning_records, "D-04: expected a WARNING log for the unmapped override"
        msg = warning_records[0].getMessage()
        assert "tissue_stiffness" in msg
        assert "suturing" in msg

        # The composed dict equals pure interpolation (override is a no-op).
        assert composed == baseline