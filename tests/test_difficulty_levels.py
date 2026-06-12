"""Tests for DifficultyLevel enum and its re-export.

D-TEST-01: DifficultyLevel enum exists with scalar values.
D-PLUMB-01: Re-exported from surg_rl.rl.
"""

import pytest


class TestDifficultyLevel:
    """Tests for the DifficultyLevel enum (TDD RED gate for task 1)."""

    def test_difficulty_level_importable_from_surg_rl_rl(self):
        """DifficultyLevel is importable from the surg_rl.rl package surface."""
        from surg_rl.rl import DifficultyLevel

        assert DifficultyLevel is not None

    def test_difficulty_level_easy_value(self):
        """DifficultyLevel.EASY has scalar value 0.0."""
        from surg_rl.rl import DifficultyLevel

        assert DifficultyLevel.EASY.value == 0.0

    def test_difficulty_level_medium_value(self):
        """DifficultyLevel.MEDIUM has scalar value 0.5."""
        from surg_rl.rl import DifficultyLevel

        assert DifficultyLevel.MEDIUM.value == 0.5

    def test_difficulty_level_hard_value(self):
        """DifficultyLevel.HARD has scalar value 1.0."""
        from surg_rl.rl import DifficultyLevel

        assert DifficultyLevel.HARD.value == 1.0

    def test_difficulty_level_easy_compares_to_float(self):
        """EASY member compares equal to its float value (Enum with float mixin)."""
        from surg_rl.rl import DifficultyLevel

        # Float mixin: enum.EASY == 0.0
        assert DifficultyLevel.EASY == 0.0
        assert DifficultyLevel.MEDIUM == 0.5
        assert DifficultyLevel.HARD == 1.0

    def test_difficulty_level_exported_in_all(self):
        """DifficultyLevel is in surg_rl.rl.__all__ (re-export contract)."""
        import surg_rl.rl as rl_pkg

        assert "DifficultyLevel" in rl_pkg.__all__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
