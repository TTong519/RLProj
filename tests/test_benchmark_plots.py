"""Tests for benchmark PlotRenderer color constants (Phase 26 D-03)."""

from surg_rl.benchmark.plots import COLOR_PALETTE, DREAMER_COLOR


class TestDreamerColorConstant:
    """Regression tests for the DREAMER_COLOR literal in plots.py.

    The original constant was #d55e00 (a darker, redder orange). Phase 24
    UAT Test 9 (and the v0.4.0 audit) require #FF8C00 — a brighter,
    more distinguishable orange. This file pins the constant to the
    UAT value and guards against accidental regression.
    """

    def test_dreamer_color_matches_uat_spec(self):
        """Per Phase 24 UAT Test 9, DreamerV3 must use orange #FF8C00."""
        assert DREAMER_COLOR == "#FF8C00"

    def test_dreamer_color_is_distinct_from_sb3_palette(self):
        """Dreamer color must differ from all 5 SB3 algorithm colors."""
        assert DREAMER_COLOR not in COLOR_PALETTE

    def test_dreamer_color_is_six_char_hex(self):
        """Constant must be a 6-char uppercase hex string (matplotlib-compatible)."""
        assert isinstance(DREAMER_COLOR, str)
        assert DREAMER_COLOR.startswith("#")
        assert len(DREAMER_COLOR) == 7
        # All chars after # are hex digits
        int(DREAMER_COLOR[1:], 16)
