"""Tests for task-specific reward functions.

Tests cover suturing, dissection, and needle passing rewards,
as well as the updated create_default_reward factory.
"""

import numpy as np
import pytest
from pydantic import ValidationError

from surg_rl.rl.rewards import (
    ActionPenalty,
    CollisionPenalty,
    CompositeReward,
    DissectionReward,
    DistanceReward,
    NeedlePassingReward,
    OrientationReward,
    RewardConfig,
    SuccessReward,
    SuturingReward,
    create_default_reward,
)

# ============================================================================
# Suturing Reward Tests
# ============================================================================


class TestSuturingReward:
    """Tests for SuturingReward."""

    def test_needle_position_reward(self):
        """Test reward when needle is near entry point."""
        reward_fn = SuturingReward(weight=1.0)
        obs = {
            "needle_pos": np.array([0.0, 0.0, 0.0]),
            "entry_point": np.array([0.0, 0.0, 0.0]),
        }
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total > 1.0  # exp(0) + bonus = 1 + 1 = 2
        assert "needle_position" in result.components

    def test_thread_tension_penalty(self):
        """Test penalty for excessive thread tension."""
        reward_fn = SuturingReward(weight=1.0, tension_threshold=0.5)
        obs = {"thread_tension": np.array([1.0])}
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total < 0
        assert "thread_tension" in result.components

    def test_stitch_completion_bonus(self):
        """Test bonus for completing a stitch."""
        reward_fn = SuturingReward(weight=1.0, completion_bonus=50.0)
        result1 = reward_fn.compute({}, np.zeros(7), {"stitches_completed": 1})
        assert result1.total == 50.0
        assert result1.info["stitches_completed"] == 1

        # Additional stitch
        result2 = reward_fn.compute({}, np.zeros(7), {"stitches_completed": 3})
        assert result2.total == 100.0  # 2 new stitches * 50
        assert result2.info["stitches_completed"] == 3

    def test_needle_drop_penalty(self):
        """Test penalty for dropping needle."""
        reward_fn = SuturingReward(weight=1.0, drop_penalty=-20.0)
        result = reward_fn.compute({}, np.zeros(7), {"needle_dropped": True})
        assert result.total == -20.0
        assert "needle_drop" in result.components

    def test_reset(self):
        """Test resetting internal state."""
        reward_fn = SuturingReward(weight=1.0)
        reward_fn.compute({}, np.zeros(7), {"stitches_completed": 2})
        reward_fn.reset()
        assert reward_fn._stitches_completed == 0

    def test_no_observations(self):
        """Test reward with no relevant observations."""
        reward_fn = SuturingReward(weight=1.0)
        result = reward_fn.compute({}, np.zeros(7), {})
        assert result.total == 0.0
        assert result.components == {}

    def test_suturing_reward_with_thread_tension(self):
        """H7: SuturingReward must penalise non-zero thread_tension."""
        reward_fn = SuturingReward(weight=1.0, tension_threshold=0.5)
        obs = {"thread_tension": np.array([1.0])}
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total < 0
        assert "thread_tension" in result.components


# ============================================================================
# Dissection Reward Tests
# ============================================================================


class TestDissectionReward:
    """Tests for DissectionReward."""

    def test_incision_progress_reward(self):
        """Test reward for making incision progress."""
        reward_fn = DissectionReward(weight=1.0, progress_scale=10.0)
        obs = {"incision_progress": np.array([0.1])}
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total == pytest.approx(1.0, abs=1e-6)  # 0.1 * 10
        assert "incision_progress" in result.components

    def test_progress_no_reward_for_regression(self):
        """Test no reward when progress decreases."""
        reward_fn = DissectionReward(weight=1.0)
        obs1 = {"incision_progress": np.array([0.5])}
        reward_fn.compute(obs1, np.zeros(7), {})

        obs2 = {"incision_progress": np.array([0.3])}
        result = reward_fn.compute(obs2, np.zeros(7), {})
        assert result.total == 0.0
        assert "incision_progress" not in result.components

    def test_collateral_damage_penalty(self):
        """Test penalty for collateral tissue damage."""
        reward_fn = DissectionReward(weight=1.0, damage_penalty=-5.0)
        result = reward_fn.compute({}, np.zeros(7), {"collateral_damage": 2.0})
        assert result.total == -10.0
        assert "collateral_damage" in result.components

    def test_clean_cut_bonus(self):
        """Test bonus for clean cuts with low force."""
        reward_fn = DissectionReward(weight=1.0, force_threshold=2.0, clean_cut_bonus=2.0)
        obs = {"cut_force": np.array([1.0])}
        result = reward_fn.compute(obs, np.zeros(7), {"cutting": True})
        assert result.total == 2.0
        assert "clean_cut" in result.components

    def test_no_clean_cut_bonus_when_force_high(self):
        """Test no bonus when cutting force is above threshold."""
        reward_fn = DissectionReward(weight=1.0, force_threshold=2.0, clean_cut_bonus=2.0)
        obs = {"cut_force": np.array([3.0])}
        result = reward_fn.compute(obs, np.zeros(7), {"cutting": True})
        assert result.total == 0.0
        assert "clean_cut" not in result.components

    def test_reset(self):
        """Test resetting progress tracking."""
        reward_fn = DissectionReward(weight=1.0)
        obs = {"incision_progress": np.array([0.5])}
        reward_fn.compute(obs, np.zeros(7), {})
        reward_fn.reset()
        assert reward_fn._prev_progress == 0.0

    def test_dissection_reward_with_cut_force(self):
        """H7: DissectionReward must use cut_force observation."""
        reward_fn = DissectionReward(weight=1.0, force_threshold=2.0, clean_cut_bonus=2.0)
        obs = {"cut_force": np.array([5.0])}
        result = reward_fn.compute(obs, np.zeros(7), {"cutting": True})
        assert result.total == 0.0  # force above threshold → no bonus
        assert "clean_cut" not in result.components


# ============================================================================
# Needle Passing Reward Tests
# ============================================================================


class TestNeedlePassingReward:
    """Tests for NeedlePassingReward."""

    def test_proximity_reward(self):
        """Test reward when needle is close to receiver."""
        reward_fn = NeedlePassingReward(weight=1.0, handoff_threshold=0.02)
        obs = {
            "needle_pos": np.array([0.0, 0.0, 0.0]),
            "receiver_pos": np.array([0.01, 0.0, 0.0]),
        }
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total == 1.0
        assert "handoff_proximity" in result.components

    def test_proximity_reward_exponential(self):
        """Test exponential proximity reward when far."""
        reward_fn = NeedlePassingReward(weight=1.0, proximity_scale=50.0)
        obs = {
            "needle_pos": np.array([0.0, 0.0, 0.0]),
            "receiver_pos": np.array([0.1, 0.0, 0.0]),
        }
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert 0.0 < result.total < 1.0
        assert "handoff_proximity" in result.components

    def test_handoff_bonus(self):
        """Test bonus for successful handoff."""
        reward_fn = NeedlePassingReward(weight=1.0, handoff_bonus=30.0)
        result = reward_fn.compute({}, np.zeros(7), {"handoffs_completed": 1})
        assert result.total == 30.0
        assert result.info["handoffs_completed"] == 1

    def test_multiple_handoffs(self):
        """Test bonus for multiple handoffs."""
        reward_fn = NeedlePassingReward(weight=1.0, handoff_bonus=30.0)
        result = reward_fn.compute({}, np.zeros(7), {"handoffs_completed": 3})
        assert result.total == 90.0
        assert result.info["handoffs_completed"] == 3

    def test_needle_drop_penalty(self):
        """Test penalty for dropping needle."""
        reward_fn = NeedlePassingReward(weight=1.0, drop_penalty=-20.0)
        result = reward_fn.compute({}, np.zeros(7), {"needle_dropped": True})
        assert result.total == -20.0
        assert "needle_drop" in result.components

    def test_reset(self):
        """Test resetting handoff counter."""
        reward_fn = NeedlePassingReward(weight=1.0)
        reward_fn.compute({}, np.zeros(7), {"handoffs_completed": 2})
        reward_fn.reset()
        assert reward_fn._handoffs_completed == 0

    def test_no_observations(self):
        """Test reward with no relevant observations."""
        reward_fn = NeedlePassingReward(weight=1.0)
        result = reward_fn.compute({}, np.zeros(7), {})
        assert result.total == 0.0
        assert result.components == {}

    def test_needle_passing_reward_with_receiver_pos(self):
        """H7: NeedlePassingReward must compute distance-based reward with receiver_pos."""
        reward_fn = NeedlePassingReward(weight=1.0, handoff_threshold=0.02)
        obs = {
            "needle_pos": np.array([0.0, 0.0, 0.0]),
            "receiver_pos": np.array([0.01, 0.0, 0.0]),
        }
        result = reward_fn.compute(obs, np.zeros(7), {})
        assert result.total > 0
        assert "handoff_proximity" in result.components


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestCreateDefaultReward:
    """Tests for create_default_reward with task-specific rewards."""

    def test_default_reward_no_task(self):
        """Test default reward without task name."""
        reward_fn = create_default_reward()
        assert isinstance(reward_fn, CompositeReward)

    def test_suturing_task_reward(self):
        """Test that suturing task includes SuturingReward."""
        reward_fn = create_default_reward(task_name="suturing_task")
        assert isinstance(reward_fn, CompositeReward)
        # Check that at least one component is a SuturingReward
        types = [type(r) for r, _ in reward_fn.components]
        assert SuturingReward in types

    def test_dissection_task_reward(self):
        """Test that dissection task includes DissectionReward."""
        reward_fn = create_default_reward(task_name="dissection_task")
        types = [type(r) for r, _ in reward_fn.components]
        assert DissectionReward in types

    def test_needle_passing_task_reward(self):
        """Test that needle passing task includes NeedlePassingReward."""
        reward_fn = create_default_reward(task_name="needle_passing_task")
        types = [type(r) for r, _ in reward_fn.components]
        assert NeedlePassingReward in types

    def test_needle_passing_variant_names(self):
        """Test various needle passing task name variants."""
        for name in ["needlepass_task", "handoff_task", "NeedlePass"]:
            reward_fn = create_default_reward(task_name=name)
            types = [type(r) for r, _ in reward_fn.components]
            assert NeedlePassingReward in types, f"Failed for task name: {name}"

    def test_unknown_task_no_extra_rewards(self):
        """Test that unknown tasks only get generic rewards."""
        reward_fn = create_default_reward(task_name="unknown_task")
        types = [type(r) for r, _ in reward_fn.components]
        assert SuturingReward not in types
        assert DissectionReward not in types
        assert NeedlePassingReward not in types

    def test_composite_reward_computation(self):
        """Test that composite with task-specific rewards computes correctly."""
        reward_fn = create_default_reward(task_name="suturing")
        obs = {
            "distance_to_target": np.array([0.1]),
            "needle_pos": np.array([0.0, 0.0, 0.0]),
            "entry_point": np.array([0.0, 0.0, 0.0]),
        }
        action = np.random.randn(8)
        result = reward_fn.compute(obs, action, {"terminated": False})
        assert result.total != 0
        # Should have components from generic + suturing rewards
        assert len(result.components) > 0
        reward_fn.reset()

    def test_collision_penalty_is_negative(self):
        """CollisionPenalty must produce a negative reward on collision."""
        from surg_rl.rl.rewards import RewardConfig

        composite = create_default_reward(RewardConfig())
        obs = {}
        action = np.zeros(7)
        info = {"collision": True, "tissue_damage": 0.0, "collision_force": 0.0}

        result = composite.compute(obs, action, info)
        collision_component = [v for k, v in result.components.items() if "collision" in k]
        assert collision_component
        assert all(
            v <= 0 for v in collision_component
        ), f"Collision penalty must be negative, got {collision_component}"
        assert (
            result.total <= 0
        ), f"Total reward on collision should be non-positive, got {result.total}"


# ============================================================================
# Branch Coverage Tests
# ============================================================================


class TestDistanceRewardBranches:
    def test_distance_from_info_dict(self):
        RewardConfig()
        reward_fn = DistanceReward(weight=1.0, shape="linear", scale=1.0)
        obs = {"distance_to_target": None}
        action = np.zeros(3)
        info = {"distance_to_target": 0.5}
        result = reward_fn.compute(obs, action, info)
        assert result.total != 0.0

    def test_unknown_shape_defaults_to_negative_distance(self):
        reward_fn = DistanceReward(weight=1.0, shape="unknown", scale=1.0)
        obs = {"distance_to_target": np.array([0.2])}
        action = np.zeros(3)
        info = {}
        result = reward_fn.compute(obs, action, info)
        assert result.total < 0

    def test_no_distance_data_returns_zero(self):
        reward_fn = DistanceReward()
        obs = {}
        action = np.zeros(3)
        info = {}
        result = reward_fn.compute(obs, action, info)
        assert result.total == 0.0
        assert result.components["distance"] == 0.0


class TestOrientationRewardBranches:
    def test_no_angle_data_returns_zero(self):
        reward_fn = OrientationReward()
        obs = {}
        action = np.zeros(3)
        info = {}
        result = reward_fn.compute(obs, action, info)
        assert result.total == 0.0
        assert result.components["orientation"] == 0.0


class TestActionPenaltyBranches:
    def test_max_penalty_type(self):
        reward_fn = ActionPenalty(penalty_type="max")
        action = np.array([1.0, -2.0, 0.5])
        result = reward_fn.compute({}, action, {})
        assert result.total <= 0

    def test_unknown_penalty_type_defaults_l2(self):
        reward_fn = ActionPenalty(penalty_type="unknown")
        action = np.array([1.0, 1.0])
        result = reward_fn.compute({}, action, {})
        assert result.total < 0


class TestSuccessRewardBranches:
    def test_distance_based_success(self):
        reward_fn = SuccessReward(distance_threshold=0.1)
        obs = {"distance_to_target": np.array([0.05])}
        action = np.zeros(3)
        info = {"terminated": True}
        result = reward_fn.compute(obs, action, info)
        assert result.total > 0


class TestCollisionPenaltyBranches:
    def test_collision_force_penalty(self):
        reward_fn = CollisionPenalty()
        obs = {}
        action = np.zeros(3)
        info = {"collision": True, "collision_force": 5.0}
        result = reward_fn.compute(obs, action, info)
        assert result.total < 0


class TestCompositeRewardAdd:
    def test_add_method_appends_component(self):
        composite = CompositeReward()
        dr = DistanceReward()
        composite.add(dr, weight=1.0)
        assert len(composite.components) == 1


class TestCreateDefaultRewardBranches:
    def test_task_specific_suturing(self):
        reward = create_default_reward(task_name="suturing_task")
        assert isinstance(reward, CompositeReward)
        assert len(reward.components) > 5  # default + suturing

    def test_task_specific_dissection(self):
        reward = create_default_reward(task_name="dissection_task")
        assert isinstance(reward, CompositeReward)
        assert len(reward.components) > 5

    def test_task_specific_needle_passing(self):
        reward = create_default_reward(task_name="needle_passing_task")
        assert isinstance(reward, CompositeReward)
        assert len(reward.components) > 5


class TestRewardConfigValidation:
    """Regression tests for RewardConfig Pydantic model."""

    def test_reward_config_rejects_negative_penalty(self):
        """RewardConfig must reject negative penalty values."""
        with pytest.raises(ValidationError):
            RewardConfig(collision_penalty=-10.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
