"""Tests for TaskConfig.difficulty_blocks scene-author field (Phase 37, TASK-08 / SC#1 / SC#5).

SC#1: Scene JSON with ``task.difficulty_blocks`` for all three levels (EASY/MEDIUM/HARD)
      round-trips through Pydantic v2 validation with authored values preserved.
      A scene WITHOUT ``difficulty_blocks`` still loads with ``scene.task.difficulty_blocks is None``
      (6 existing v0.4.0 scenes unaffected). Malformed blocks (out-of-range overrides) are
      rejected at scene-load time (ASVS V5 / T-37-01).

SC#5: ``difficulty_blocks`` is the canonical spelling across PROJECT.md, schema, and STATE.md;
      the prior plural-s drift spelling is gone (subprocess grep audit).

This file is shared across plans 37-01/02/03. Plan 37-01 adds ONLY the SC#1 round-trip +
SC#5 naming-audit tests below. Plans 37-02/37-03 add their own test classes.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from surg_rl.dynamics.difficulty_wiring import (
    ABSTRACT_TO_CONCRETE,
    compose_difficulty_overrides,
)
from surg_rl.rl import DifficultyLevel
from surg_rl.rl.difficulty import DifficultyLevelConfig
from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
from surg_rl.rl.rewards import (
    CuttingReward,
    DissectionReward,
    GraspingReward,
    KnotTyingReward,
    NeedlePassingReward,
    SuturingReward,
)
from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY, TaskRewardRouter
from surg_rl.scene_definition.loader import SceneLoader, SceneValidationError
from surg_rl.scene_definition.schema import TaskConfig


# =============================================================================
# SC#1 — scene JSON round-trip for TaskConfig.difficulty_blocks
# =============================================================================


class TestSceneBlocksRoundTrip:
    """SC#1: ``difficulty_blocks`` round-trips through Pydantic v2 + SceneLoader."""

    #: Inline scene JSON fixture with all three levels authored (RESEARCH.md:558-572).
    #: Override values are inside the verified D-07 global union bounds
    #: for ``target_precision_tolerance`` ([0.002, 0.3]).
    BLOCKS_SCENE_JSON = json.dumps(
        {
            "metadata": {"name": "suturing_with_blocks", "version": "0.6.0"},
            "scene": {"id": "suturing_blocks", "environment": "operating_room"},
            "task": {
                "name": "suturing_task",
                "description": "Suturing with per-level difficulty blocks",
                "task_type": "suturing",
                "difficulty_level": 1.0,
                "difficulty_blocks": {
                    "EASY": {"target_precision_tolerance": 0.02},
                    "MEDIUM": {"target_precision_tolerance": 0.005},
                    "HARD": {"target_precision_tolerance": 0.002},
                },
            },
        }
    )

    def test_scene_with_blocks_round_trips(self):
        """SC#1: a scene with all 3 levels of difficulty_blocks round-trips with values preserved."""
        scene = SceneLoader().load_from_string(self.BLOCKS_SCENE_JSON, format="json")

        assert scene.task is not None
        blocks = scene.task.difficulty_blocks
        assert blocks is not None
        assert isinstance(blocks, dict)
        # DifficultyLevel enum keys (Pydantic v2 coerces JSON string keys by float value).
        assert DifficultyLevel.EASY in blocks
        assert DifficultyLevel.MEDIUM in blocks
        assert DifficultyLevel.HARD in blocks
        # Authored override values preserved on each DifficultyLevelConfig value.
        assert blocks[DifficultyLevel.EASY].target_precision_tolerance == 0.02
        assert blocks[DifficultyLevel.MEDIUM].target_precision_tolerance == 0.005
        assert blocks[DifficultyLevel.HARD].target_precision_tolerance == 0.002

        # Re-serialization round-trip: model_dump() -> TaskConfig.model_validate preserves values.
        dump = scene.model_dump()
        re_validated = TaskConfig.model_validate(dump["task"])
        assert re_validated.difficulty_blocks is not None
        assert (
            re_validated.difficulty_blocks[DifficultyLevel.HARD].target_precision_tolerance == 0.002
        )
        assert (
            re_validated.difficulty_blocks[DifficultyLevel.EASY].target_precision_tolerance == 0.02
        )

    @pytest.mark.parametrize(
        "scene_file",
        [
            "simple_suturing.json",
            "knot_tying.json",
            "needle_insertion.json",
            "grasping.json",
            "cutting.json",
            "dissection.json",
        ],
    )
    def test_existing_scenes_load_without_blocks(self, scene_file):
        """SC#1 negative: the 6 v0.4.0 task scenes load with ``difficulty_blocks is None``.

        Canonical SC#1 negative regression name — shared with 37-03 Task 2 and
        37-VALIDATION.md row 37-SC1-neg.
        """
        scene_path = Path(__file__).parent.parent / "scenes" / scene_file
        if not scene_path.exists():
            pytest.skip(f"scenes/{scene_file} not found")
        scene = SceneLoader().load(str(scene_path))
        assert scene.task is not None
        assert scene.task.difficulty_blocks is None

    def test_malformed_blocks_rejected(self):
        """SC#1 / T-37-01: an out-of-range override raises at scene-load time (ASVS V5)."""
        malformed_json = json.dumps(
            {
                "metadata": {"name": "malformed_blocks", "version": "0.6.0"},
                "scene": {"id": "malformed", "environment": "operating_room"},
                "task": {
                    "name": "suturing_task",
                    "description": "Malformed blocks — out of D-07 bounds",
                    "task_type": "suturing",
                    "difficulty_level": 1.0,
                    "difficulty_blocks": {
                        "HARD": {"target_precision_tolerance": 999.0},  # outside [0.002, 0.3]
                    },
                },
            }
        )
        # SceneLoader wraps pydantic.ValidationError as SceneValidationError; both
        # are acceptable signals that validation rejected the malformed input.
        with pytest.raises((SceneValidationError, ValidationError)):
            SceneLoader().load_from_string(malformed_json, format="json")


# =============================================================================
# SC#5 — naming audit (canonical spelling = difficulty_blocks)
# =============================================================================


class TestNamingAudit:
    """SC#5: the prior plural-s drift spelling is gone from canonical docs."""

    def test_no_drift_spelling_in_canonical_docs(self):
        """SC#5: ``difficulty_levels`` (the drift spelling) is absent from canonical docs.

        Greps PROJECT.md, STATE.md, and the src/ tree. Historical milestone archives
        under ``.planning/milestones/`` are intentionally excluded (they are frozen
        historical record). ``grep`` exits 1 when no matches are found.
        """
        result = subprocess.run(
            ["grep", "-rn", "difficulty_levels",
             ".planning/PROJECT.md", ".planning/STATE.md", "src/surg_rl/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "drift spelling `difficulty_levels` still present in canonical docs:\n"
            f"{result.stdout}"
        )


# =============================================================================
# SC#2 — _setup_rewards override-precedence truth table (Plan 37-02, TASK-08)
# =============================================================================


def _load_suturing_scene() -> "object":
    """Load scenes/simple_suturing.json as the truth-table base scene.

    The scene carries ``task.task_type == "suturing"`` and an authored
    ``task.time_limit == 120.0`` (used by the Pitfall 3 inert assertion).
    """
    scene_path = Path(__file__).parent.parent / "scenes" / "simple_suturing.json"
    if not scene_path.exists():
        pytest.skip("scenes/simple_suturing.json not found")
    return SceneLoader().load(str(scene_path))


class TestPrecedenceTruthTable:
    """SC#2: ``_setup_rewards`` resolves the 4-level precedence

        difficulty_blocks[level] > task.difficulty_level > config.difficulty > default 0.5

    Pitfall 2 (inert ctor surface, Q1 MINIMAL Option a): ``apply_params`` maps ONLY
    the single ``PARAM_BOUNDS`` key each task reward already maps in
    ``apply_difficulty``. Other composed keys (e.g. ``time_limit``) sit in the
    composed dict but never reach a ctor field — they are INERT on the reward
    ctor surface. Pitfall 3 path (a): the env does NOT patch
    ``TaskConfig.time_limit`` or ``max_episode_steps`` from difficulty_blocks
    (deferred to a follow-up phase); the ``time_limit`` override composes into
    the params dict but is inert on both the reward ctor and the env truncation
    surface.
    """

    @pytest.mark.parametrize(
        ("source", "level", "expected_scalar", "blocks_present"),
        [
            # blocks > all: HARD blocks override target_precision_tolerance=0.008
            ("blocks", DifficultyLevel.HARD, 1.0, True),
            # task.difficulty_level (no blocks) -> existing router path
            ("task_difficulty_level", DifficultyLevel.HARD, 1.0, False),
            # config.difficulty (no blocks, no task.difficulty_level) -> Q2 field
            ("config_difficulty", 0.25, 0.25, False),
            # default 0.5
            ("default", None, 0.5, False),
            # Pitfall 3 path (a) + Pitfall 2: time_limit override composes into
            # the dict but is inert on the reward ctor surface AND the env does
            # not patch TaskConfig.time_limit / max_episode_steps.
            ("blocks_time_limit_inert", DifficultyLevel.HARD, 1.0, True),
        ],
    )
    def test_precedence_resolution(
        self, source, level, expected_scalar, blocks_present
    ):
        """SC#2 parametrized truth table: 4 precedence levels + inert surface."""
        scene = _load_suturing_scene()
        # Reset negotiable fields to a clean baseline per case.
        scene.task.difficulty_level = None
        scene.task.difficulty_blocks = None
        config_difficulty = 0.5  # SurgicalEnvConfig.difficulty default (Q2)

        # The `level` param doubles as the task.difficulty_level for the
        # blocks / task_difficulty_level cases (a DifficultyLevel enum). For
        # config_difficulty it is the config.difficulty scalar; for default
        # it is None. blocks fire ONLY when the resolved difficulty is a
        # DifficultyLevel (Q4 guard), so the blocks cases require
        # task.difficulty_level = level.
        if isinstance(level, DifficultyLevel):
            scene.task.difficulty_level = level

        if source == "blocks":
            # Mapped override: target_precision_tolerance -> needle_position_tolerance
            # -> position_threshold. Value 0.008 is inside D-07 bounds [0.002, 0.3]
            # and DISTINCT from the HARD interpolated baseline (0.002) so the
            # override is observable.
            scene.task.difficulty_blocks = {
                DifficultyLevel.HARD: DifficultyLevelConfig(
                    target_precision_tolerance=0.008
                )
            }
        elif source == "config_difficulty":
            config_difficulty = 0.25
        elif source == "blocks_time_limit_inert":
            # time_limit IS mapped for suturing (ABSTRACT_TO_CONCRETE), so it
            # composes into the dict, but SuturingReward.apply_params maps ONLY
            # needle_position_tolerance -> position_threshold. time_limit is
            # therefore INERT on the reward ctor surface (Pitfall 2). The env
            # does NOT patch TaskConfig.time_limit or max_episode_steps
            # (Pitfall 3 path a — deferred).
            scene.task.difficulty_blocks = {
                DifficultyLevel.HARD: DifficultyLevelConfig(time_limit=90.0)
            }

        config = SurgicalEnvConfig(
            scene=scene,
            render_mode=None,
            difficulty=config_difficulty,
        )
        env = SurgicalEnv(config)
        try:
            assert env._task_difficulty == pytest.approx(expected_scalar), (
                f"source={source}: _task_difficulty={env._task_difficulty} "
                f"expected={expected_scalar}"
            )

            # The reward fn is always a CompositeReward for a tasked scene.
            assert env._reward_fn is not None
            reward_list = [r for (r, _w) in env._reward_fn.components]
            suturing = next(
                (r for r in reward_list if isinstance(r, SuturingReward)), None
            )
            assert suturing is not None, "SuturingReward not in composite"

            if source == "blocks":
                # Mapped override reached the ctor field (0.008, NOT 0.002).
                assert suturing.position_threshold == pytest.approx(
                    0.008, abs=1e-9
                ), (
                    "blocks override did not reach SuturingReward.position_threshold "
                    f"(got {suturing.position_threshold})"
                )
            elif source == "task_difficulty_level":
                # HARD interpolated baseline (no blocks) -> 0.002.
                assert suturing.position_threshold == pytest.approx(
                    SuturingReward.interpolate_params(1.0)[
                        "needle_position_tolerance"
                    ],
                    abs=1e-9,
                )
            elif source == "config_difficulty":
                assert suturing.position_threshold == pytest.approx(
                    SuturingReward.interpolate_params(0.25)[
                        "needle_position_tolerance"
                    ],
                    abs=1e-9,
                )
            elif source == "default":
                assert suturing.position_threshold == pytest.approx(
                    SuturingReward.interpolate_params(0.5)[
                        "needle_position_tolerance"
                    ],
                    abs=1e-9,
                )
            elif source == "blocks_time_limit_inert":
                # Pitfall 2: time_limit override composed into the dict but
                # INERT on the reward ctor surface — position_threshold stays
                # at the HARD interpolated baseline (0.002), NOT 90.0.
                assert suturing.position_threshold == pytest.approx(
                    SuturingReward.interpolate_params(1.0)[
                        "needle_position_tolerance"
                    ],
                    abs=1e-9,
                ), (
                    "time_limit override leaked into position_threshold "
                    f"(got {suturing.position_threshold})"
                )
                # Pitfall 3 path (a): env does NOT patch TaskConfig.time_limit
                # from difficulty_blocks. Authored value was 120.0.
                assert env._scene.task.time_limit == 120.0, (
                    "TaskConfig.time_limit was patched from difficulty_blocks "
                    f"(got {env._scene.task.time_limit})"
                )
                # Pitfall 3 path (a): env does NOT patch max_episode_steps
                # from difficulty_blocks.
                assert env.config.max_episode_steps == 1000, (
                    "config.max_episode_steps was patched from difficulty_blocks "
                    f"(got {env.config.max_episode_steps})"
                )
        finally:
            env.close()


def test_blocks_inert_under_continuous_curriculum():
    """Pitfall 6 / Q4: blocks are INERT when the resolved difficulty is a
    continuous scalar (use_curriculum=True drives a float, NOT a DifficultyLevel).

    The new blocks branch guards on ``isinstance(difficulty, DifficultyLevel)``;
    a continuous scalar (0.37) fails the guard -> the existing router branch
    runs with the scalar -> blocks never compose. The continuous-curriculum
    path is byte-identical (TASK-09 additive gate).
    """
    scene = _load_suturing_scene()
    scene.task.difficulty_blocks = {
        DifficultyLevel.HARD: DifficultyLevelConfig(
            target_precision_tolerance=0.008
        )
    }
    config = SurgicalEnvConfig(
        scene=scene,
        render_mode=None,
        use_curriculum=True,
    )
    env = SurgicalEnv(config)
    real_curriculum = env._controller._curriculum if env._controller is not None else None
    try:
        # Override the curriculum's current_difficulty with a continuous scalar
        # (0.37) that is NOT a DifficultyLevel, then re-resolve rewards. The
        # blocks branch must skip -> existing router path runs with 0.37.
        assert env._controller is not None
        assert real_curriculum is not None
        env._controller._curriculum = SimpleNamespace(current_difficulty=0.37)
        env._setup_rewards()

        assert env._task_difficulty == pytest.approx(0.37, abs=1e-9), (
            f"expected continuous scalar 0.37, got {env._task_difficulty}"
        )
        # Blocks override value is 0.008; the interpolated value at 0.37 is
        # 0.02 + (0.002 - 0.02) * 0.37 = 0.0155 - must NOT equal 0.008.
        expected_interpolated = SuturingReward.interpolate_params(0.37)[
            "needle_position_tolerance"
        ]
        reward_list = [r for (r, _w) in env._reward_fn.components]
        suturing = next(r for r in reward_list if isinstance(r, SuturingReward))
        assert suturing.position_threshold == pytest.approx(
            expected_interpolated, abs=1e-9
        ), (
            "blocks override leaked through under continuous curriculum "
            f"(got {suturing.position_threshold}, expected {expected_interpolated})"
        )
        assert suturing.position_threshold != pytest.approx(0.008, abs=1e-9)
    finally:
        # Restore the real curriculum so env.close() can stop it cleanly.
        if env._controller is not None and real_curriculum is not None:
            env._controller._curriculum = real_curriculum
        env.close()


def test_apply_params_delegates_on_suturing():
    """Regression-anchored refactor test (v0.5.0 observable output unchanged).

    ``apply_difficulty(1.0)`` must produce the SAME ctor-field value as before
    the P37 refactor (it now delegates to ``apply_params(interpolate_params(1.0))``).
    Then ``apply_params(composed_dict)`` directly sets the mapped ctor field to
    ``composed_dict[concrete_key]``.
    """
    reward = SuturingReward()
    reward.apply_difficulty(1.0)
    expected_hard = SuturingReward.interpolate_params(1.0)[
        "needle_position_tolerance"
    ]
    assert reward.position_threshold == pytest.approx(expected_hard, abs=1e-9), (
        f"apply_difficulty(1.0) delegate broke: got {reward.position_threshold}, "
        f"expected {expected_hard}"
    )

    # Now drive apply_params directly with a composed dict whose
    # needle_position_tolerance differs from the interpolated baseline.
    composed = compose_difficulty_overrides(
        "suturing",
        DifficultyLevel.HARD,
        DifficultyLevelConfig(target_precision_tolerance=0.008),
        SuturingReward,
    )
    assert composed["needle_position_tolerance"] == 0.008
    reward.apply_params(composed)
    assert reward.position_threshold == pytest.approx(0.008, abs=1e-9), (
        f"apply_params did not map composed dict to position_threshold "
        f"(got {reward.position_threshold})"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])