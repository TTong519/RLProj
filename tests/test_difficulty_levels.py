"""Tests for DifficultyLevel enum and its re-export.

D-TEST-01: DifficultyLevel enum exists with scalar values.
D-PLUMB-01: Re-exported from surg_rl.rl.
D-TEST-02: Parametrized per-family direction test for all 6 task rewards.
D-TEST-03: apply_difficulty actually mutates a ctor field on each task reward.
D-PLUMB-04: get_params_for_difficulty delegates to interpolate_params.
D-PLUMB-06: Generic rewards (Distance/Action/Time/Collision) get no-op default.
"""

import pytest

from surg_rl.rl import DifficultyLevel
from surg_rl.rl.rewards import (
    ActionPenalty,
    CollisionPenalty,
    CuttingReward,
    DissectionReward,
    DistanceReward,
    GraspingReward,
    KnotTyingReward,
    NeedlePassingReward,
    SuturingReward,
    TimePenalty,
)


class TestDifficultyLevel:
    """Tests for the DifficultyLevel enum (TDD RED gate for task 1)."""

    def test_difficulty_level_importable_from_surg_rl_rl(self):
        """DifficultyLevel is importable from the surg_rl.rl package surface."""
        assert DifficultyLevel is not None

    def test_difficulty_level_easy_value(self):
        """DifficultyLevel.EASY has scalar value 0.0."""
        assert DifficultyLevel.EASY.value == 0.0

    def test_difficulty_level_medium_value(self):
        """DifficultyLevel.MEDIUM has scalar value 0.5."""
        assert DifficultyLevel.MEDIUM.value == 0.5

    def test_difficulty_level_hard_value(self):
        """DifficultyLevel.HARD has scalar value 1.0."""
        assert DifficultyLevel.HARD.value == 1.0

    def test_difficulty_level_easy_compares_to_float(self):
        """EASY member compares equal to its float value (Enum with float mixin)."""
        # Float mixin: enum.EASY == 0.0
        assert DifficultyLevel.EASY == 0.0
        assert DifficultyLevel.MEDIUM == 0.5
        assert DifficultyLevel.HARD == 1.0

    def test_difficulty_level_exported_in_all(self):
        """DifficultyLevel is in surg_rl.rl.__all__ (re-export contract)."""
        import surg_rl.rl as rl_pkg

        assert "DifficultyLevel" in rl_pkg.__all__


# =============================================================================
# Task 2 tests: get_params_for_difficulty + apply_difficulty on the 6 task rewards
# =============================================================================


# Per-family direction reference (D-DIR-01):
# - Down family (lo > hi — HARD pulls value down): tolerance-like, time_limit, etc.
#   HARD_value < EASY_value
# - Up family (lo < hi — HARD pushes value up): tissue_stiffness, action_noise, object_mass
#   HARD_value > EASY_value


_TASK_REWARD_CLASSES = (
    "SuturingReward",
    "DissectionReward",
    "NeedlePassingReward",
    "KnotTyingReward",
    "GraspingReward",
    "CuttingReward",
)


@pytest.mark.parametrize(
    "reward_cls,down_keys,up_keys",
    [
        (
            "SuturingReward",
            [
                "needle_position_tolerance",
                "thread_tension_threshold",
                "stitch_spacing_tolerance",
                "time_limit",
            ],
            [],
        ),
        (
            "DissectionReward",
            [
                "incision_path_tolerance",
                "collateral_damage_threshold",
                "force_precision",
                "time_limit",
            ],
            ["tissue_stiffness"],
        ),
        (
            "NeedlePassingReward",
            [
                "handoff_proximity_tolerance",
                "needle_alignment_tolerance",
                "time_limit",
            ],
            ["action_noise"],
        ),
        (
            "KnotTyingReward",
            [
                "loop_deviation_tolerance",
                "knot_tension_tolerance",
                "time_limit",
            ],
            ["tissue_stiffness", "action_noise"],
        ),
        (
            "GraspingReward",
            [
                "approach_tolerance",
                "grip_force_accuracy",
                "time_limit",
            ],
            ["object_mass", "action_noise"],
        ),
        (
            "CuttingReward",
            [
                "cut_path_accuracy",
                "collateral_threshold",
                "force_precision",
                "time_limit",
            ],
            ["tissue_stiffness"],
        ),
    ],
)
def test_difficulty_direction(reward_cls, down_keys, up_keys):
    """D-DIR-01: per-family direction assertion between EASY and HARD."""
    cls_map = {
        "SuturingReward": SuturingReward,
        "DissectionReward": DissectionReward,
        "NeedlePassingReward": NeedlePassingReward,
        "KnotTyingReward": KnotTyingReward,
        "GraspingReward": GraspingReward,
        "CuttingReward": CuttingReward,
    }
    cls = cls_map[reward_cls]
    easy = cls.get_params_for_difficulty(DifficultyLevel.EASY)
    hard = cls.get_params_for_difficulty(DifficultyLevel.HARD)
    for name in down_keys:
        assert hard[name] < easy[name], (
            f"{reward_cls}: {name} did not move strict (HARD<{name}<EASY). "
            f"Easy={easy[name]}, Hard={hard[name]}"
        )
    for name in up_keys:
        assert hard[name] > easy[name], (
            f"{reward_cls}: {name} did not move strict (HARD>{name}>EASY). "
            f"Easy={easy[name]}, Hard={hard[name]}"
        )


# Per-subclass mapped field chosen to match what apply_difficulty mutates.
# The field name in the dict MUST match the ctor field that apply_difficulty
# writes to. Executor picks these in the GREEN phase implementation.
MAPPED_FIELDS = {
    "SuturingReward": "position_threshold",  # needle_position_tolerance → 0.002
    "DissectionReward": "force_threshold",  # force_precision → 1.0
    "NeedlePassingReward": "handoff_threshold",  # handoff_proximity_tolerance → 0.01
    "KnotTyingReward": "loop_deviation_threshold",  # loop_deviation_tolerance → 0.005
    "GraspingReward": "grasp_threshold",  # approach_tolerance → 0.005
    "CuttingReward": "force_threshold",  # force_precision → 1.0
}


@pytest.mark.parametrize("reward_cls_name", list(MAPPED_FIELDS.keys()))
def test_apply_difficulty_mutates_field(reward_cls_name):
    """D-TEST-03: apply_difficulty actually mutates a ctor field on the instance."""
    cls_map = {
        "SuturingReward": SuturingReward,
        "DissectionReward": DissectionReward,
        "NeedlePassingReward": NeedlePassingReward,
        "KnotTyingReward": KnotTyingReward,
        "GraspingReward": GraspingReward,
        "CuttingReward": CuttingReward,
    }
    cls = cls_map[reward_cls_name]
    field_name = MAPPED_FIELDS[reward_cls_name]
    reward = cls()
    before = getattr(reward, field_name)
    reward.apply_difficulty(DifficultyLevel.HARD.value)
    after = getattr(reward, field_name)
    assert before is not None, f"{reward_cls_name}.{field_name} is None"
    assert after != before, (
        f"{reward_cls_name}.apply_difficulty(HARD) did not mutate {field_name} "
        f"(before={before}, after={after})"
    )


def test_generic_rewards_apply_difficulty_is_noop():
    """D-PLUMB-06: DistanceReward/ActionPenalty/TimePenalty/CollisionPenalty get no-op default."""
    for cls in (DistanceReward, ActionPenalty, TimePenalty, CollisionPenalty):
        instance = cls()
        # Should not raise
        instance.apply_difficulty(0.5)
        instance.apply_difficulty(1.0)
        instance.apply_difficulty(0.0)


def test_get_params_delegates_to_interpolate_params():
    """D-PLUMB-04: get_params_for_difficulty is a pure delegating wrapper."""
    for cls in (
        SuturingReward,
        DissectionReward,
        NeedlePassingReward,
        KnotTyingReward,
        GraspingReward,
        CuttingReward,
    ):
        for level, scalar in [
            (DifficultyLevel.EASY, 0.0),
            (DifficultyLevel.MEDIUM, 0.5),
            (DifficultyLevel.HARD, 1.0),
        ]:
            via_method = cls.get_params_for_difficulty(level)
            via_classmethod = cls.interpolate_params(scalar)
            assert via_method == via_classmethod, (
                f"{cls.__name__}.get_params_for_difficulty({level}) != "
                f"interpolate_params({scalar})"
            )


# =============================================================================
# Plan 29-02 tests: Thread DifficultyLevel through router, schema, curriculum
# =============================================================================


from pathlib import Path  # noqa: E402

from surg_rl.dynamics.curriculum import (  # noqa: E402
    CurriculumStage,
    CurriculumStageConfig,
)
from surg_rl.rl.task_reward_router import TaskRewardRouter  # noqa: E402
from surg_rl.scene_definition.loader import SceneLoader  # noqa: E402
from surg_rl.scene_definition.schema import TaskConfig  # noqa: E402


class TestDifficultyWiring:
    """Plan 29-02 task 1: DifficultyLevel threaded through router/schema/curriculum."""

    def test_router_accepts_enum_normalizes_to_scalar(self):
        """Router normalizes DifficultyLevel to its .value scalar (D-PLUMB-05)."""
        router = TaskRewardRouter(difficulty=DifficultyLevel.HARD)
        # Float mixin makes DifficultyLevel.HARD == 1.0 True, but the actual
        # stored value should be a plain float, not the enum member. Check type
        # to enforce the normalization contract.
        assert router._difficulty == 1.0
        assert type(router._difficulty) is float, (
            f"Expected float, got {type(router._difficulty)}"
        )

    def test_router_accepts_float_preserved(self):
        """Float path is preserved unchanged (backward compat)."""
        router = TaskRewardRouter(difficulty=0.7)
        assert router._difficulty == 0.7
        assert type(router._difficulty) is float

    def test_router_default_is_0_5(self):
        """Default difficulty remains 0.5 (MEDIUM equivalent)."""
        router = TaskRewardRouter()
        assert router._difficulty == 0.5

    def test_task_config_accepts_difficulty_level(self):
        """TaskConfig accepts a DifficultyLevel member."""
        task = TaskConfig(
            name="suturing_task",
            description="test",
            difficulty_level=DifficultyLevel.HARD,
        )
        assert task.difficulty_level == DifficultyLevel.HARD

    def test_task_config_difficulty_level_default_is_none(self):
        """TaskConfig.difficulty_level defaults to None (float-path fallback)."""
        task = TaskConfig(name="x", description="y")
        assert task.difficulty_level is None

    def test_task_config_accepts_float_coerced_to_enum(self):
        """TaskConfig accepts the float value 1.0 and coerces to HARD enum."""
        task = TaskConfig(
            name="x", description="y", difficulty_level=1.0
        )
        assert task.difficulty_level == DifficultyLevel.HARD

    def test_task_config_accepts_float_zero_coerced_to_easy(self):
        """TaskConfig accepts 0.0 and coerces to EASY enum."""
        task = TaskConfig(
            name="x", description="y", difficulty_level=0.0
        )
        assert task.difficulty_level == DifficultyLevel.EASY

    def test_curriculum_stage_config_accepts_enum(self):
        """CurriculumStageConfig.difficulty accepts DifficultyLevel."""
        stage = CurriculumStageConfig(
            name="stage1", stage=CurriculumStage.EASY, difficulty=DifficultyLevel.HARD
        )
        assert stage.difficulty == DifficultyLevel.HARD

    def test_curriculum_stage_config_accepts_float(self):
        """CurriculumStageConfig.difficulty still accepts float (backward compat)."""
        stage = CurriculumStageConfig(
            name="stage1", stage=CurriculumStage.EASY, difficulty=0.7
        )
        assert stage.difficulty == 0.7


class TestDifficultyIntegration:
    """Plan 29-02 task 2: Router float/enum equivalence + scene JSON load."""

    FIXTURE_DIR = Path(__file__).parent / "fixtures" / "scenes"
    HARD_FIXTURE = FIXTURE_DIR / "suturing_difficulty_hard.json"

    @pytest.mark.parametrize(
        "task_type",
        [
            "suturing",
            "dissection",
            "needle_insertion",
            "knot_tying",
            "grasping",
            "cutting",
        ],
    )
    def test_router_float_enum_equivalence(self, task_type):
        """D-TEST-04: float 0.5 and DifficultyLevel.MEDIUM produce equivalent rewards."""
        float_router = TaskRewardRouter(difficulty=0.5)
        enum_router = TaskRewardRouter(difficulty=DifficultyLevel.MEDIUM)
        float_rewards = float_router.build(task_type)
        enum_rewards = enum_router.build(task_type)
        assert len(float_rewards) == len(enum_rewards)
        fr = float_rewards[0]
        er = enum_rewards[0]
        assert type(fr) is type(er), (
            f"router produced different reward types: {type(fr)} vs {type(er)}"
        )
        for attr_name in dir(fr):
            if attr_name.startswith("_"):
                continue
            attr = getattr(fr, attr_name, None)
            other = getattr(er, attr_name, None)
            if isinstance(attr, float) and isinstance(other, float):
                assert attr == other, (
                    f"{task_type}: float/enum produced different {attr_name} "
                    f"({attr} vs {other})"
                )

    def test_router_applies_difficulty_to_task_reward(self):
        """D-PLUMB-01: TaskRewardRouter.build() calls apply_difficulty on constructed task reward."""
        router = TaskRewardRouter(difficulty=DifficultyLevel.HARD)
        rewards = router.build("suturing")
        suturing = rewards[0]
        # HARD interpolates needle_position_tolerance to 0.002
        assert suturing.position_threshold == pytest.approx(0.002, abs=1e-6)

    def test_scene_load_with_difficulty_level_hard(self):
        """D-TEST-05: scene JSON with task.difficulty_level = 1.0 loads to enum."""
        if not self.HARD_FIXTURE.exists():
            pytest.skip("Fixture not yet created")
        scene = SceneLoader().load(str(self.HARD_FIXTURE))
        assert scene.task is not None
        assert scene.task.difficulty_level == DifficultyLevel.HARD
        assert scene.task.task_type == "suturing"

    def test_scene_load_without_difficulty_level_defaults_to_none(self):
        """D-TEST-05: scene JSON without difficulty_level loads with default None."""
        production_scene_path = (
            Path(__file__).parent.parent / "scenes" / "simple_suturing.json"
        )
        if not production_scene_path.exists():
            pytest.skip("scenes/simple_suturing.json not found")
        scene = SceneLoader().load(str(production_scene_path))
        assert scene.task is not None
        assert scene.task.difficulty_level is None
        assert scene.task.task_type == "suturing"

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
    def test_all_phase27_scenes_load_with_difficulty_level_none(self, scene_file):
        """D-BC-02: all 6 Phase 27 benchmark scenes still load without difficulty_level."""
        scene_path = Path(__file__).parent.parent / "scenes" / scene_file
        if not scene_path.exists():
            pytest.skip(f"scenes/{scene_file} not found")
        scene = SceneLoader().load(str(scene_path))
        assert scene.task is not None
        assert scene.task.difficulty_level is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
