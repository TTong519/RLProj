---
phase: 29-task-02-3-difficulty-levels
plan: 01
subsystem: rl
tags: [difficulty, enum, rewards, pydantic-v2, tdd, pydantic-compatible]

# Dependency graph
requires:
  - phase: v0.4.0-Phase21
    provides: TaskResult hierarchy, 6 task-specific reward classes with PARAM_BOUNDS + interpolate_params, TaskRewardRouter
  - phase: 28-audit-gap-closure-retroactive
    provides: v0.4.1 milestone closure; TASK-02 3-difficulty-levels identified as the partial v0.4.0 audit gap
provides:
  - DifficultyLevel enum (EASY=0.0, MEDIUM=0.5, HARD=1.0) importable from `surg_rl.rl`
  - `_FloatMixin(float, Enum)` base class pattern for float-equal enum members (no stdlib FloatEnum)
  - `BaseRewardFunction.apply_difficulty(difficulty)` no-op default method
  - `get_params_for_difficulty(level)` classmethod on the 6 task reward classes (delegates to `interpolate_params`)
  - `apply_difficulty(difficulty)` per-subclass override on the 6 task reward classes (mutates a ctor field)
  - 20-test parametrize-heavy test suite covering scalar values, re-export, per-family direction, field mutation, generic-reward no-op, and delegation contract
affects:
  - phase: 29-task-02-3-difficulty-levels-29-02
  - topic: TaskRewardRouter wiring
  - topic: TaskConfig.difficulty_level
  - topic: CurriculumScheduler
  - topic: schema.py Pydantic integration

# Tech tracking
tech-stack:
  added:
    - Python stdlib `enum.Enum` (used with custom `float` mixin for value comparison)
  patterns:
    - "Leaf-module strategy: `difficulty.py` has zero imports from `surg_rl.*` to break the future `rewards.py <-> schema.py <-> difficulty.py` circular import"
    - "Duck-typed enum consumers: `get_params_for_difficulty(level)` uses `level.value` so any object with a `.value` attribute works (no type-level coupling to DifficultyLevel)"
    - "Override-on-subclass pattern for optional behavior: `BaseRewardFunction.apply_difficulty` is the safe default; 6 task subclasses opt in via override; 4 generic rewards inherit the no-op"
    - "Partial mapping accepted (D-PLUMB-02): not every PARAM_BOUNDS key needs a matching ctor field; `hasattr` guards make adding new ctor fields safe"

key-files:
  created:
    - src/surg_rl/rl/difficulty.py
    - tests/test_difficulty_levels.py
  modified:
    - src/surg_rl/rl/__init__.py
    - src/surg_rl/rl/rewards.py

key-decisions:
  - "Used `class _FloatMixin(float, Enum)` instead of plain `Enum` because Python's stdlib has no `FloatEnum`. Without the mixin, `DifficultyLevel.EASY == 0.0` would be False, breaking downstream code that compares enum members to floats (per plan §behavior)."
  - "Did NOT import `DifficultyLevel` inside `rewards.py`. The `level` type hint in `get_params_for_difficulty` is intentionally loose (any object with `.value` works), avoiding the documented `rewards.py <-> difficulty.py <-> schema.py` circular import risk."
  - "Chose `pass` semantics for `BaseRewardFunction.apply_difficulty` (no-op default) instead of raising NotImplementedError. Generic rewards have no difficulty mapping, and the plan explicitly requires they remain unaffected (D-PLUMB-06)."
  - "Per-subclass field mapping (D-PLUMB-02 partial mapping is acceptable): each task reward maps exactly one PARAM_BOUNDS key to one existing ctor field. The MAPPED_FIELDS dict in the test mirrors these choices."
  - "Did NOT add `DifficultyLevelConfig` Pydantic model (D-29-03 explicit exclusion). Schema integration is out of scope for this plan."

patterns-established:
  - "Leaf-module enum file: a new module containing only an enum (and its mixin) that has zero in-project imports. Use when multiple downstream modules need to reference the enum but should not couple to each other transitively."
  - "Apply-diffulty hook: optional mutation method on the abstract base, called once by the router after construction. Lets downstream overrides respond to a scalar difficulty without subclass-specific dispatcher code."

requirements-completed: [TASK-02-01, TASK-02-02, TASK-02-04]

# Metrics
duration: 10 min
completed: 2026-06-12
---

# Phase 29 Plan 01: DifficultyLevel Enum + Reward Wiring Summary

**DifficultyLevel enum (EASY=0.0, MEDIUM=0.5, HARD=1.0) with float-mixin semantics, plus per-task `get_params_for_difficulty` and `apply_difficulty` overrides on all 6 task reward classes — preserving the existing `interpolate_params` source of truth and leaving the 4 generic rewards unaffected via a no-op `BaseRewardFunction` default.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-12T17:30:25Z
- **Completed:** 2026-06-12T17:40:29Z
- **Tasks:** 2 (TDD with RED/GREEN/REFACTOR gates)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- **DifficultyLevel enum lives.** EASY=0.0, MEDIUM=0.5, HARD=1.0 with float-mixin semantics (`DifficultyLevel.EASY == 0.0` is True). Re-exported from `surg_rl.rl` (import block + `__all__` entry).
- **Leaf-module strategy verified.** `src/surg_rl/rl/difficulty.py` has zero imports from `surg_rl.*`, satisfying the circular-import risk noted in CONTEXT.md. Plan 29-02 can safely import this from `rewards.py` and `schema.py` without creating a cycle.
- **All 6 task reward classes get the new surface.** Each has `get_params_for_difficulty(level)` (delegating to `interpolate_params`) and `apply_difficulty(difficulty)` (mutating a single ctor field). The 4 generic rewards (`DistanceReward`, `ActionPenalty`, `TimePenalty`, `CollisionPenalty`) plus `OrientationReward`/`SuccessReward`/`CompositeReward` inherit a no-op default from `BaseRewardFunction`.
- **Per-family direction tests pass for all 6 task types.** For each task, at least one down-family `PARAM_BOUNDS` key satisfies `HARD < EASY`; for tasks that have an up-family key (`tissue_stiffness`, `action_noise`, `object_mass`), `HARD > EASY` is also verified.
- **20-test suite in `tests/test_difficulty_levels.py` — all green.** Pre-existing `test_rewards.py` (43 tests) unchanged; broader non-integration suite (1017 tests) clean.

## Task Commits

Each task was committed atomically (TDD: test → feat → optional refactor):

1. **task 1: DifficultyLevel enum + re-export**
   - `8480eba` (test) — RED: 6 failing enum tests
   - `9170109` (feat) — GREEN: enum implementation + `__init__.py` re-export
2. **task 2: apply_difficulty + get_params_for_difficulty on 6 task rewards**
   - `c35db85` (test) — RED: 14 failing tests (6 direction + 6 mutation + 1 no-op + 1 delegation)
   - `308a2f3` (feat) — GREEN: `BaseRewardFunction` no-op + 6 subclass overrides
   - `9c4f32b` (refactor) — `# noqa: B027` rationale + test import hoisting (lint cleanup)

## Files Created/Modified

- `src/surg_rl/rl/difficulty.py` — **new**. Contains `_FloatMixin(float, Enum)` and `DifficultyLevel` (EASY=0.0, MEDIUM=0.5, HARD=1.0). Module docstring explains the leaf-module strategy.
- `src/surg_rl/rl/__init__.py` — added `from .difficulty import DifficultyLevel` to the import block (between callbacks and environment) and `"DifficultyLevel"` to `__all__` (alphabetized between action and reward sections).
- `src/surg_rl/rl/rewards.py` — added `BaseRewardFunction.apply_difficulty` (no-op default) and `get_params_for_difficulty` + `apply_difficulty` overrides on each of the 6 task reward classes. No ctor signatures changed; 130 added lines.
- `tests/test_difficulty_levels.py` — **new**. 20 tests: `TestDifficultyLevel` (6 enum), `test_difficulty_direction` (6 parametrized), `test_apply_difficulty_mutates_field` (6 parametrized), `test_generic_rewards_apply_difficulty_is_noop`, `test_get_params_delegates_to_interpolate_params`. 273 lines.

## Decisions Made

- **Float-mixin enum over plain `Enum`.** Python's stdlib provides `IntEnum` for int-equal enums but no `FloatEnum`. Subclassing `float` (`_FloatMixin(float, Enum)`) is the canonical workaround documented in the stdlib enum docs. Without it, `DifficultyLevel.EASY == 0.0` would be False and the plan's behavior section would fail.
- **No DifficultyLevel import in rewards.py.** The `level` parameter in `get_params_for_difficulty` is duck-typed (any object with `.value`). This keeps `rewards.py` importable from `schema.py` without a cycle. Plan 29-02's schema work can import both modules without coupling them through `rewards.py`.
- **No-op `BaseRewardFunction.apply_difficulty`.** Required by D-PLUMB-06: the 4 generic rewards must not be modified to consume difficulty. The `pass  # noqa: B027` body is the smallest change that satisfies the spec; subclasses opt in via override.
- **Partial mapping per task reward (D-PLUMB-02).** Each task reward maps exactly one `PARAM_BOUNDS` key to one ctor field. The test's `MAPPED_FIELDS` dict documents the choice. Future plans can extend the mapping without breaking the existing test contract.
- **No new `DifficultyLevelConfig` Pydantic model (D-29-03 explicit exclusion).** Plan 29-02 owns the schema integration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Float equality for enum members required `_FloatMixin` base class**
- **Found during:** task 1 GREEN phase (after initial `class DifficultyLevel(Enum)` implementation)
- **Issue:** Standard `Enum` does not mix in `float`, so `DifficultyLevel.EASY == 0.0` is False. The plan's `<behavior>` section explicitly required this comparison to succeed.
- **Fix:** Introduced `class _FloatMixin(float, Enum)` as the base for `DifficultyLevel`. This gives `DifficultyLevel.EASY == 0.0` True semantics (the underlying value is a float). All 6 RED tests passed after the change.
- **Files modified:** `src/surg_rl/rl/difficulty.py`
- **Verification:** `PYTHONPATH=src python -c "from surg_rl.rl import DifficultyLevel; print(DifficultyLevel.EASY == 0.0)"` prints `True`.
- **Committed in:** `9170109` (part of task 1 GREEN commit)

**2. [Rule 1 - Bug] Ruff B027 false positive on no-op ABC method**
- **Found during:** post-GREEN lint sweep
- **Issue:** Ruff flagged `BaseRewardFunction.apply_difficulty` as an empty ABC method missing the `@abstractmethod` decorator. The empty body is INTENTIONAL per D-PLUMB-06 (generic rewards must be unaffected).
- **Fix:** Replaced `pass` with `return None  # noqa: B027` and added a comment block above explaining the no-op default rationale. The `# noqa` marker is what ruff recognizes.
- **Files modified:** `src/surg_rl/rl/rewards.py`
- **Verification:** `ruff check src/surg_rl/rl/difficulty.py src/surg_rl/rl/rewards.py tests/test_difficulty_levels.py` reports `All checks passed!`. All 20 tests still pass.
- **Committed in:** `9c4f32b` (refactor commit)

**3. [Rule 1 - Bug] Ruff I001 unsorted imports in test file**
- **Found during:** post-GREEN lint sweep
- **Issue:** The 6 reward-class imports were inside test functions (to keep them next to their use), which ruff flagged as un-sorted.
- **Fix:** Hoisted all 6 reward-class imports to the module-level import block (alphabetized). No test logic changed.
- **Files modified:** `tests/test_difficulty_levels.py`
- **Verification:** `ruff check` clean. All 20 tests still pass.
- **Committed in:** `9c4f32b` (refactor commit)

---

**Total deviations:** 3 auto-fixed (3 bug — all lint/behavior alignment with plan's stated requirements; no scope creep)
**Impact on plan:** All auto-fixes are required to satisfy the plan's `<behavior>` section and lint-clean mandate. No new features, no skipped steps.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for plan 29-02 (TaskRewardRouter + TaskConfig + CurriculumScheduler wiring):
- The `DifficultyLevel` enum is importable from `surg_rl.rl` (the public surface Plan 29-02 will use).
- The 6 task reward classes have `get_params_for_difficulty(level)` and `apply_difficulty(difficulty)` — the router can call these directly.
- `BaseRewardFunction.apply_difficulty` no-op default means the router can call it generically on any reward instance without isinstance checks.
- No blockers.

---

*Phase: 29-task-02-3-difficulty-levels*
*Completed: 2026-06-12*

## Self-Check: PASSED

- All key files exist on disk (difficulty.py, test_difficulty_levels.py, 29-01-SUMMARY.md)
- All 5 commits exist in git log (2 RED + 2 GREEN + 1 REFACTOR)
- TDD gate sequence valid: test(8480eba) → feat(9170109) → test(c35db85) → feat(308a2f3) → refactor(9c4f32b)
- 20/20 difficulty tests pass; 43/43 pre-existing reward tests pass; 1017/1017 broader non-integration tests pass
- ruff + black clean on all 4 modified files
