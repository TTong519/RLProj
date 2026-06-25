"""Tests for the additive discrete progression_mode on CurriculumScheduler
(Phase 36, TASK-07 / SC#3) and the advance_stage continuous-path parity gate
(SC#4).

The discrete axis is strictly additive: ``CurriculumConfig.progression_mode``
defaults to ``"continuous"`` so the v0.5.0 ``advance_stage`` path stays
byte-identical. When ``progression_mode="discrete"`` the scheduler walks
``DifficultyLevel.EASY -> MEDIUM -> HARD`` via ``set_difficulty_level`` /
``advance_level`` (D-12: HARD is terminal -> ``advance_level`` returns
``False``). The shared success-rate gate is the extracted
``_meets_success_threshold`` helper (corrected D-11).
"""

import pytest

from surg_rl.dynamics.curriculum import (
    CurriculumConfig,
    CurriculumScheduler,
    CurriculumStage,
)
from surg_rl.rl.difficulty import DifficultyLevel


class TestDiscreteProgression:
    """SC#3 — discrete EASY->MEDIUM->HARD progression axis."""

    def test_init_discrete_defaults(self):
        """Discrete-mode scheduler starts at EASY with difficulty 0.0."""
        cfg = CurriculumConfig(progression_mode="discrete")
        scheduler = CurriculumScheduler(curriculum_config=cfg)

        assert scheduler._current_level == DifficultyLevel.EASY
        assert scheduler.current_difficulty == 0.0

    def test_set_difficulty_level(self):
        """set_difficulty_level is a manual override of _current_level (D-12)."""
        cfg = CurriculumConfig(progression_mode="discrete")
        scheduler = CurriculumScheduler(curriculum_config=cfg)

        scheduler.set_difficulty_level(DifficultyLevel.HARD)

        assert scheduler._current_level == DifficultyLevel.HARD
        assert scheduler.current_difficulty == 1.0

    def test_advance_level_transitions(self):
        """advance_level walks EASY->MEDIUM->HARD->False (D-12 terminal)."""
        cfg = CurriculumConfig(progression_mode="discrete")
        scheduler = CurriculumScheduler(curriculum_config=cfg)

        # EASY -> MEDIUM
        assert scheduler.advance_level() is True
        assert scheduler._current_level == DifficultyLevel.MEDIUM
        assert scheduler.current_difficulty == 0.5

        # MEDIUM -> HARD
        assert scheduler.advance_level() is True
        assert scheduler._current_level == DifficultyLevel.HARD
        assert scheduler.current_difficulty == 1.0

        # HARD is terminal (D-12)
        assert scheduler.advance_level() is False
        assert scheduler._current_level == DifficultyLevel.HARD

    def test_current_difficulty_mode_branch_continuous(self):
        """Default continuous mode returns the v0.5.0 EASY stage scalar 0.25."""
        scheduler = CurriculumScheduler()

        assert scheduler.current_difficulty == 0.25

    def test_advance_level_auto_advances_on_success_rate(self):
        """Discrete mode auto-advances _current_level via episode_end pipeline.

        Mirrors test_dynamics.py:393-411 auto-advancement shape. With
        advancement_window=10, min_success_rate=0.7, and all-success episodes,
        advance_level (routed through update_curriculum) must advance
        _current_level beyond EASY (corrected D-11 gate).
        """
        cfg = CurriculumConfig(
            progression_mode="discrete",
            auto_advance=True,
            advancement_window=10,
            min_success_rate=0.7,
        )
        scheduler = CurriculumScheduler(curriculum_config=cfg)
        scheduler.start()

        for _i in range(15):
            scheduler.reset()
            scheduler.episode_end({"success": 1, "reward": 100}, simulator=None)

        assert scheduler._current_level != DifficultyLevel.EASY


class TestAdvanceStageParity:
    """SC#3 / SC#4 — continuous advance_stage path unchanged from v0.5.0."""

    def test_advance_stage_unchanged(self):
        """Continuous advance_stage transitions match the v0.5.0 baseline.

        Parity anchor mirroring
        test_dynamics.py::TestCurriculumScheduler::test_stage_progression:
        EASY->MEDIUM->HARD->EXPERT->False with current_difficulty scalars
        0.25 / 0.5 / 0.75 / 1.0.
        """
        scheduler = CurriculumScheduler()

        assert scheduler.current_stage == CurriculumStage.EASY
        assert scheduler.current_difficulty == 0.25

        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.MEDIUM
        assert scheduler.current_difficulty == 0.5

        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.HARD
        assert scheduler.current_difficulty == 0.75

        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.EXPERT
        assert scheduler.current_difficulty == 1.0

        assert scheduler.advance_stage() is False  # Already at max