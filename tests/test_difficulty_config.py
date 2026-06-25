"""Tests for DifficultyLevelConfig Pydantic v2 leaf model (Phase 36, TASK-06 / SC#1 / SC#5)."""

import pytest
from pydantic import ValidationError

from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig
import surg_rl.rl.difficulty as _difficulty_module


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