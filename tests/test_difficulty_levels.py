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
    from surg_rl.rl.rewards import (
        DissectionReward,
        GraspingReward,
        CuttingReward,
        KnotTyingReward,
        NeedlePassingReward,
        SuturingReward,
    )

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
    from surg_rl.rl.rewards import (
        DissectionReward,
        GraspingReward,
        CuttingReward,
        KnotTyingReward,
        NeedlePassingReward,
        SuturingReward,
    )

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
    from surg_rl.rl.rewards import (
        ActionPenalty,
        CollisionPenalty,
        DistanceReward,
        TimePenalty,
    )

    for cls in (DistanceReward, ActionPenalty, TimePenalty, CollisionPenalty):
        instance = cls()
        # Should not raise
        instance.apply_difficulty(0.5)
        instance.apply_difficulty(1.0)
        instance.apply_difficulty(0.0)


def test_get_params_delegates_to_interpolate_params():
    """D-PLUMB-04: get_params_for_difficulty is a pure delegating wrapper."""
    from surg_rl.rl.rewards import (
        DissectionReward,
        GraspingReward,
        CuttingReward,
        KnotTyingReward,
        NeedlePassingReward,
        SuturingReward,
    )

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
