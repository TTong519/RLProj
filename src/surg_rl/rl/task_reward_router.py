"""Task reward router with registry-based dispatch.

Maps TaskConfig.task_type to a list of BaseRewardFunction instances.
Replaces the fragile string-matching in create_default_reward().
"""

from typing import Any

from surg_rl.rl.difficulty import DifficultyLevel
from surg_rl.rl.rewards import (
    ActionPenalty,
    BaseRewardFunction,
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
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# D-02: Registry maps task_type -> reward class
TASK_REWARD_REGISTRY: dict[str, type[BaseRewardFunction]] = {
    "suturing": SuturingReward,
    "dissection": DissectionReward,
    "needle_insertion": NeedlePassingReward,
    "knot_tying": KnotTyingReward,
    "grasping": GraspingReward,
    "cutting": CuttingReward,
}

GENERIC_REWARD_CLASSES: list[type[BaseRewardFunction]] = [
    DistanceReward,
    ActionPenalty,
    TimePenalty,
    CollisionPenalty,
]


class TaskRewardRouter:
    """Routes task_type to a list of reward function instances.

    D-03: Returns list[BaseRewardFunction] that plugs into CompositeReward
    without any changes to CompositeReward.

    Phase 29: Accepts DifficultyLevel | float for difficulty, normalizes to
    a scalar internally (D-PLUMB-05). Calls apply_difficulty() on the
    constructed task-specific reward (D-PLUMB-01).
    """

    def __init__(self, difficulty: float | DifficultyLevel = 0.5):
        """Construct router with a difficulty scalar or DifficultyLevel preset.

        Per D-PLUMB-05: DifficultyLevel is normalized to its scalar .value
        internally; float path is preserved unchanged. Backward compatible:
        TaskRewardRouter(difficulty=0.5) still works exactly as before.
        """
        if isinstance(difficulty, DifficultyLevel):
            self._difficulty = float(difficulty.value)
        else:
            self._difficulty = float(difficulty)

    def build(
        self,
        task_type: str | None,
        **reward_kwargs: Any,
    ) -> list[BaseRewardFunction]:
        """Build reward list from task_type.

        Returns:
            List of [task_specific_reward] + generic_rewards.
            For None or unknown task_type, returns only generic rewards.
            Never returns None — contract guarantees list[BaseRewardFunction].
        """
        rewards: list[BaseRewardFunction] = []

        if task_type is not None:
            reward_cls = TASK_REWARD_REGISTRY.get(task_type)
            if reward_cls is not None:
                task_reward = reward_cls(**reward_kwargs)
                # D-PLUMB-01: Apply difficulty to the constructed reward. The
                # 4 generic rewards inherit the no-op default from
                # BaseRewardFunction (D-PLUMB-06), so this call is a no-op
                # for them. The call must happen AFTER the task reward is
                # appended so apply_difficulty can mutate the live instance.
                task_reward.apply_difficulty(self._difficulty)
                rewards.append(task_reward)
            else:
                logger.warning(f"Unknown task_type={task_type!r}, using generic rewards only")

        # D-03: Always add generic rewards — CompositeReward expects non-empty list
        for cls in GENERIC_REWARD_CLASSES:
            rewards.append(cls())

        return rewards
