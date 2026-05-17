---
phase: 21-surgical-task-curriculum
plan: 02
subsystem: rl
tags: [rewards, curriculum, task-type, Pydantic-v2, NaN-guard, registry-dispatch, lerp-interpolation]

# Dependency graph
requires:
  - phase: 21-01
    provides: "TaskResult hierarchy (6 per-task sub-models + TASK_RESULT_MAP)"
provides:
  - "3 new RewardType enum values (CUTTING, GRASPING, KNOT_TYING)"
  - "NaN/inf guard utilities (_is_finite, _clamp_finite)"
  - "3 new reward subclasses: KnotTyingReward, GraspingReward, CuttingReward"
  - "check_success()/check_failure()/interpolate_params()/PARAM_BOUNDS on all 6 reward classes"
  - "TaskRewardRouter with TASK_REWARD_REGISTRY dispatch table"
affects: ["21-03", "21-04"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Registry dispatch (dict[str, type]) for task_type → reward class routing"
    - "Per-task PARAM_BOUNDS with lerp(difficulty) for continuous parameter interpolation"
    - "Protocol pattern (non-abstract check_success/check_failure) on task rewards"

key-files:
  created:
    - "src/surg_rl/rl/task_reward_router.py"
  modified:
    - "src/surg_rl/rl/rewards.py"

key-decisions:
  - "Registry dispatch (TASK_REWARD_REGISTRY) replaces fragile string-matching for task detection"
  - "check_success/check_failure/interpolate_params added as non-abstract protocol on task rewards (not on ABC)"
  - "TaskRewardRouter always returns list[BaseRewardFunction] — never None, always includes generic rewards"
  - "NeedlePassingReward task_type registered as 'needle_insertion' to match TaskConfig.task_type Literal"

patterns-established:
  - "Registry dispatch: dict[str, type[BaseRewardFunction]] for constant-time task routing"
  - "Per-task interpolate_params(): lerp(min, max, difficulty) with class-level PARAM_BOUNDS"

requirements-completed: [TASK-01, TASK-02, TASK-04]

# Metrics
duration: 6m30s
completed: 2026-05-17
---

# Phase 21 Plan 02: Task Reward Subclasses & Router Summary

**6 per-task reward subclasses with structured success/failure detection and registry-based routing for all surgical task types**

## Performance

- **Duration:** 6m 30s
- **Started:** 2026-05-17T21:01:59Z
- **Completed:** 2026-05-17T21:08:29Z
- **Tasks:** 3
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- 3 new RewardType enum values (CUTTING, GRASPING, KNOT_TYING) for complete task type coverage
- NaN/inf guard utilities (_is_finite, _clamp_finite) protecting all reward computation paths
- 3 new reward subclasses: KnotTyingReward, GraspingReward, CuttingReward — each with compute(), reset(), check_success(), check_failure(), interpolate_params(), PARAM_BOUNDS
- Existing SuturingReward, DissectionReward, NeedlePassingReward retrofitted with same methods for API uniformity across all 6 task types
- TaskRewardRouter with TASK_REWARD_REGISTRY (6 entries) providing O(1) dispatch from task_type string to reward class
- Router gracefully handles task_type=None (generic rewards only) and unknown task_type (warning + generic rewards)

## Task Commits

Each task was committed atomically:

1. **task 1: add RewardType enum values + NaN/inf guard utility** - `f3d6a1a` (feat)
2. **task 2: add 3 new reward subclasses (KnotTyingReward, GraspingReward, CuttingReward)** - `766fb9e` (feat)
3. **task 3: add check_success/check_failure/interpolate_params to existing classes + create TaskRewardRouter** - `d700773` (feat)

## Files Created/Modified
- `src/surg_rl/rl/rewards.py` - Modified: 3 new RewardType enums, NaN/inf guards, 3 new reward subclasses, 3 existing classes retrofitted with success/failure/interpolation methods
- `src/surg_rl/rl/task_reward_router.py` - Created: TaskRewardRouter with TASK_REWARD_REGISTRY (6 entries), GENERIC_REWARD_CLASSES, graceful None/unknown handling

## Decisions Made
- Registry dispatch (TASK_REWARD_REGISTRY) replaces fragile string-matching for task detection — single-line additions for new task types
- check_success/check_failure/interpolate_params added as non-abstract protocol on task rewards (not on ABC) — avoids breaking existing generic rewards
- TaskRewardRouter always returns list[BaseRewardFunction] — never None, always includes generic rewards for safety
- NeedlePassingReward task_type registered as 'needle_insertion' to match TaskConfig.task_type Literal values from schema
- _clamp_finite() wraps all 6 compute() methods to fulfill threat model T-21-04 (NaN/inf mitigation)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all 3 tasks passed verification on first attempt. Existing 43 test_rewards.py tests continue to pass with no regressions.

## User Setup Required

None - no external service configuration required. All new code uses existing dependencies (Pydantic v2, numpy, stdlib).

## Next Phase Readiness
- All 6 reward classes ready for Plan 03 integration (TaskRewardRouter wiring into reward creation pipeline)
- TASK_REWARD_REGISTRY provides the contract Plan 03 will consume
- check_success()/check_failure() return correct per-task TaskResult subclasses — ready for curriculum feedback loop

---
*Phase: 21-surgical-task-curriculum*
*Plan: 02*
*Completed: 2026-05-17*
