---
phase: 37-scene-level-difficulty-blocks-env-wiring
plan: 02
subsystem: rl
tags: [rl, rewards, environment, difficulty-blocks, tdd, precedence, curriculum-coexistence]
requires:
  - "37-01: TaskConfig.difficulty_blocks schema field + field_validator (scene-author input surface)"
  - "36-02: difficulty_wiring.compose_difficulty_overrides + ABSTRACT_TO_CONCRETE (D-05/D-06)"
  - "36-03: CurriculumScheduler additive progression_mode (continuous path baseline)"
provides:
  - "BaseRewardFunction.apply_params(params: dict[str, float]) -> None — no-op default (D-PLUMB-06)"
  - "6 task rewards .apply_params — single-key mapping (Q1 MINIMAL Option a)"
  - "apply_difficulty on 6 task rewards refactored to delegate self.apply_params(self.interpolate_params(difficulty)) — pure refactor"
  - "SurgicalEnvConfig.difficulty: float = 0.5 — Q2 config-level precedence field"
  - "SurgicalEnv._setup_rewards additive blocks branch (early return before router, Q4 enum guard, lazy local import)"
  - "tests/test_difficulty_blocks.py::TestPrecedenceTruthTable + test_blocks_inert_under_continuous_curriculum + test_apply_params_delegates_on_suturing"
affects:
  - "src/surg_rl/rl/rewards.py (BaseRewardFunction + 6 task rewards)"
  - "src/surg_rl/rl/environment.py (SurgicalEnvConfig + _setup_rewards)"
  - "tests/test_difficulty_blocks.py (appended 37-02 classes)"
tech-stack:
  added: []
  patterns:
    - "apply_params extraction (pure refactor: apply_difficulty delegates to apply_params(interpolate_params(d)))"
    - "additive early-return branch grafted before existing router (Q4 isinstance(enum) guard — continuous path byte-identical)"
    - "function-body lazy local import inside _setup_rewards (mirrors SceneLoader lazy import idiom — Pitfall 4)"
key-files:
  created:
    - ".planning/phases/37-scene-level-difficulty-blocks-env-wiring/37-02-SUMMARY.md"
  modified:
    - "src/surg_rl/rl/rewards.py"
    - "src/surg_rl/rl/environment.py"
    - "tests/test_difficulty_blocks.py"
decisions:
  - "Q1 MINIMAL (Option a): apply_params maps ONLY the single PARAM_BOUNDS key each task reward already maps in apply_difficulty. Inert override surface documented in TestPrecedenceTruthTable (Pitfall 2). Expansion deferred to a follow-up phase."
  - "Q2: SurgicalEnvConfig.difficulty: float = 0.5 added — makes the config.difficulty precedence level real and truth-table-testable as 4 distinct levels (Pitfall 1)."
  - "Q4: blocks apply ONLY when the resolved difficulty is a DifficultyLevel enum (isinstance guard). Under use_curriculum=True with a continuous scalar, blocks are INERT — continuous path byte-identical (TASK-09)."
  - "Pitfall 3 path (a): env does NOT patch TaskConfig.time_limit or max_episode_steps from difficulty_blocks — deferred to a follow-up phase; documented in blocks_time_limit_inert truth-table case."
metrics:
  duration: "~30 min"
  completed: 2026-06-24
  tasks: 3
  files: 3
status: complete
---

# Phase 37 Plan 02: Env-Reward Wiring for difficulty_blocks Summary

Wired the 4-level override-precedence chain through `SurgicalEnv._setup_rewards` (difficulty_blocks[level] > task.difficulty_level > config.difficulty > default 0.5) and extracted `apply_params(params)` on the 6 task rewards so a scene with `difficulty_blocks` produces a hard-mode environment at construction — additive, regression-anchored, with blocks inert under continuous curriculum (Q4).

## What Was Built

### Task 1 (RED) — `tests/test_difficulty_blocks.py`
Appended 3 new test groups after `TestNamingAudit` (37-01's classes untouched):
- `TestPrecedenceTruthTable.test_precedence_resolution` — parametrized SC#2 truth table over 5 cases: `(blocks, HARD)`, `(task_difficulty_level, HARD)`, `(config_difficulty, 0.25)`, `(default, None)`, `(blocks_time_limit_inert, HARD)`. For each case it loads `scenes/simple_suturing.json`, sets `task.difficulty_level` to the `DifficultyLevel` level (so the Q4 enum guard fires for blocks cases), authors `difficulty_blocks` when `blocks_present`, constructs `SurgicalEnv(SurgicalEnvConfig(scene=..., difficulty=config_level))`, and asserts `env._task_difficulty == expected_scalar` + the `SuturingReward.position_threshold` matches the expected composed/interpolated value. The `blocks` case asserts the mapped override (0.008) reaches `position_threshold` (distinct from the HARD interpolated baseline 0.002). The `blocks_time_limit_inert` case documents Pitfall 2 + Pitfall 3 path (a): `time_limit` override composes into the dict but is INERT on `position_threshold` AND `env._scene.task.time_limit` stays 120.0 (authored) AND `env.config.max_episode_steps` stays 1000 (env does not patch from blocks).
- `test_blocks_inert_under_continuous_curriculum` — Pitfall 6 / Q4: constructs an env with `use_curriculum=True` + `difficulty_blocks` present, overrides the curriculum's `current_difficulty` to a continuous scalar 0.37 (via `SimpleNamespace`), re-runs `_setup_rewards`, asserts `env._task_difficulty == 0.37` and `position_threshold == interpolate_params(0.37)["needle_position_tolerance"]` (NOT the blocks override 0.008). Restores the real curriculum before `env.close()` so teardown is clean.
- `test_apply_params_delegates_on_suturing` — regression-anchored refactor test: `apply_difficulty(1.0)` produces `position_threshold == interpolate_params(1.0)["needle_position_tolerance"]` (v0.5.0 observable output unchanged); then `apply_params(composed_dict)` directly sets `position_threshold == composed_dict["needle_position_tolerance"] == 0.008`.

RED confirmed: 6 failed (SurgicalEnvConfig.difficulty missing / apply_params missing), 1 passed (curriculum coexistence — a regression guard trivially true before the blocks branch exists, remains green after via the Q4 guard).

### Task 2 (GREEN) — `src/surg_rl/rl/rewards.py`
- Added `BaseRewardFunction.apply_params(self, params: dict[str, float]) -> None` — no-op default with `# noqa: B027` + D-PLUMB-06 rationale (mirrors `apply_difficulty` docstring structure).
- Refactored `apply_difficulty` on each of the 6 task rewards into a one-line delegate `self.apply_params(self.interpolate_params(difficulty))` + a new `apply_params` that maps the SAME single PARAM_BOUNDS key → ctor field (Q1 MINIMAL Option a):
  - SuturingReward: `needle_position_tolerance` → `position_threshold`
  - DissectionReward: `force_precision` → `force_threshold`
  - NeedlePassingReward: `handoff_proximity_tolerance` → `handoff_threshold`
  - KnotTyingReward: `loop_deviation_tolerance` → `loop_deviation_threshold`
  - GraspingReward: `approach_tolerance` → `grasp_threshold`
  - CuttingReward: `force_precision` → `force_threshold`
- `interpolate_params` and `PARAM_BOUNDS` untouched (anti-pattern — would break TASK-09). `apply_difficulty` docstrings note the P37 delegation ("Observable output unchanged").
- `grep -c 'def apply_params'` = 7 (1 base + 6 task); `grep -c 'self.apply_params(self.interpolate_params(difficulty))'` = 6.

### Task 3 (GREEN) — `src/surg_rl/rl/environment.py`
- Added `SurgicalEnvConfig.difficulty: float = 0.5` as the last dataclass field (Q2 — makes the `config.difficulty` precedence level real; default 0.5 preserves v0.5.0 behavior). Updated the Attributes docstring.
- Grafted the additive blocks branch in `_setup_rewards` AFTER `self._task_difficulty = difficulty_float` and BEFORE the existing `if task_type is not None:` router branch. The branch:
  1. Reads `blocks = getattr(self._scene.task, "difficulty_blocks", None)`.
  2. Guards on `blocks is not None and isinstance(difficulty, DifficultyLevel) and task is not None and task_type is not None and difficulty in blocks` (Q4 — a continuous scalar fails `isinstance` → blocks INERT, continuous path byte-identical).
  3. Lazy-local imports `compose_difficulty_overrides` + `TASK_REWARD_REGISTRY` inside the branch (Pitfall 4 — NOT module-level; mirrors the SceneLoader lazy import idiom).
  4. Composes `params = compose_difficulty_overrides(task_type, difficulty, blocks[difficulty], reward_cls)` (D-06 additive).
  5. Builds `reward_list = TaskRewardRouter(difficulty=difficulty_float).build(task_type)` (which calls `apply_difficulty` first), then `reward_list[0].apply_params(params)` overrides the mapped key with the composed value.
  6. Sets `self._reward_fn = CompositeReward(...)` and early-returns.
- The existing curriculum branch (`:504-510`) and router branch (`:516-521`) are NOT edited — they are the fallthrough. No `TaskConfig.time_limit` / `max_episode_steps` patching (Pitfall 3 path a — deferred). `reset()` untouched (blocks apply at construction, not reset).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Truth-table blocks cases require `task.difficulty_level` set to a DifficultyLevel**
- **Found during:** Task 3 (GREEN gate)
- **Issue:** The plan's action text for the truth-table said "a TaskConfig carrying task_type="suturing", the appropriate difficulty_level, and difficulty_blocks when blocks_present" but the parametrize `(source, level, ...)` tuples did not make explicit that the `level` (HARD) must be set as `task.difficulty_level` for the blocks cases. With `task.difficulty_level=None` and `config.difficulty=0.5`, the resolved `difficulty` is the float 0.5, so the Q4 `isinstance(difficulty, DifficultyLevel)` guard correctly skips the blocks branch — the blocks override is never applied and `_task_difficulty` is 0.5, not 1.0. This is the Q4 guard working as designed, not a code bug; the test setup was underspecified.
- **Fix:** Updated `TestPrecedenceTruthTable.test_precedence_resolution` to set `scene.task.difficulty_level = level` whenever `level` is a `DifficultyLevel` (covers the `blocks`, `task_difficulty_level`, and `blocks_time_limit_inert` cases). The `config_difficulty` (level=0.25) and `default` (level=None) cases leave `task.difficulty_level=None` so the config/default precedence levels are exercised. This makes the 4 precedence levels distinct and truth-table-testable as the plan requires.
- **Files modified:** `tests/test_difficulty_blocks.py`
- **Commit:** `9377b74`

**2. [Rule 1 - Bug] `test_blocks_inert_under_continuous_curriculum` must restore the real curriculum before `env.close()`**
- **Found during:** Task 1 (RED)
- **Issue:** The test swaps `env._controller._curriculum` for a `SimpleNamespace(current_difficulty=0.37)` to drive the continuous-scalar path. `env.close()` calls `self._controller.stop()` which calls `self._curriculum.stop()`; `SimpleNamespace` has no `stop` → `AttributeError` at teardown, masking the real assertion path.
- **Fix:** Captured `real_curriculum` before the swap and restored it in the `finally` block before `env.close()`. The teardown is now clean and the test's assertions are the load-bearing RED signal.
- **Files modified:** `tests/test_difficulty_blocks.py`
- **Commit:** `5fcccfc` (RED) — the fix was in place from the first RED commit

### Out-of-Scope Pre-Existing Debt (NOT fixed — scope boundary)

- `src/surg_rl/rl/environment.py` has 5 pre-existing ruff errors (F821 `ControllerBridge` at :208, SIM105 at :611, two errors at :805, one at :906) and pre-existing black reformatting debt (line 513 `difficulty_float` coercion + line 677 `passthrough_step` RuntimeError string). Verified pre-existing via `git stash` — the file was not ruff/black-clean before this plan. My added lines (SurgicalEnvConfig.difficulty field at :101 + the blocks branch at ~:519-562) are ruff-clean and black-clean (not in the black diff). Left unchanged per the scope-boundary rule.
- `tests/test_rl_environment.py` crashes with a fatal Python error at teardown on Python 3.14 (pre-existing — reproduced on clean `main` via `git stash`). Unrelated to this plan's changes; the core difficulty suite (220 tests) passes cleanly.

## Validation

- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py -v` → 16 passed (9 from 37-01 + 7 from 37-02: 5 truth-table cases + curriculum-coexistence + apply_params-delegate)
- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestPrecedenceTruthTable tests/test_difficulty_blocks.py::test_blocks_inert_under_continuous_curriculum -v` → 6 passed (SC#2 + Pitfall 6)
- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_levels.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_dynamics.py -v` → 220 passed (TASK-09 additive-regression gate — continuous curriculum + apply_difficulty output unchanged)
- `grep -c 'def apply_params' src/surg_rl/rl/rewards.py` → 7 (1 base no-op + 6 task rewards)
- `grep -c 'self.apply_params(self.interpolate_params(difficulty))' src/surg_rl/rl/rewards.py` → 6 (all 6 apply_difficulty methods delegate)
- `grep -c 'difficulty: float = 0.5' src/surg_rl/rl/environment.py` → 1 field declaration (Q2; +1 match on `self._task_difficulty: float = 0.5` which is the pre-existing init default, distinct)
- `grep -c 'difficulty_blocks' src/surg_rl/rl/environment.py` → 3 (getattr read + branch guard + `blocks[difficulty]` index)
- `grep -c 'isinstance(difficulty, DifficultyLevel)' src/surg_rl/rl/environment.py` → 2 (pre-existing coerce at :513 + new Q4 guard in the blocks branch)
- `grep -n 'from surg_rl.dynamics.difficulty_wiring' src/surg_rl/rl/environment.py` → line 542, INSIDE `_setup_rewards` (function-body local, NOT module top — Pitfall 4 guard)
- `ruff check src/surg_rl/rl/rewards.py` → clean
- `black --check src/surg_rl/rl/rewards.py` → clean
- `ruff check src/surg_rl/rl/environment.py` → 5 pre-existing errors (unchanged from baseline; my added lines clean)
- `black --check src/surg_rl/rl/environment.py` → pre-existing reformatting debt (unchanged; my added lines clean)

## TDD Gate Compliance

- RED gate: `test(37-02):` commit `5fcccfc` — 6 new tests fail before rewards/env changes (SurgicalEnvConfig.difficulty missing, apply_params missing). 1 curriculum-coexistence regression guard passed trivially (blocks branch absent → blocks inert → Q4 invariant holds vacuously; remains green after the branch is added via the isinstance guard).
- GREEN gate (rewards): `feat(37-02):` commit `dac09e8` — `test_apply_params_delegates_on_suturing` + `test_difficulty_levels.py` + `test_difficulty_config.py` green (132 passed); truth-table still fails (env branch pending).
- GREEN gate (env): `feat(37-02):` commit `9377b74` — `TestPrecedenceTruthTable` + `test_blocks_inert_under_continuous_curriculum` green; TASK-09 additive gate green (220 passed).

## Known Stubs

None. The 4-level precedence is fully wired at construction. The Q1 MINIMAL inert surface (non-mapped override keys compose into the params dict but never reach a ctor field) is intentional and documented in `TestPrecedenceTruthTable` (Pitfall 2); expanding the mapping (Option b) is deferred to a follow-up phase by design. The Pitfall 3 path (a) inert surface (`time_limit` override does not patch `TaskConfig.time_limit` / `max_episode_steps`) is also intentional and documented in `blocks_time_limit_inert`; patching the env's `max_episode_steps` from blocks is deferred to a follow-up phase.

## Threat Flags

None. No new security-relevant surface beyond the plan's `<threat_model>`:
- T-37-04 (override composition tampering) — mitigated by reusing P36-02 `compose_difficulty_overrides` (D-06 additive + D-04 warn-never-raise) + the Q4 `isinstance(difficulty, DifficultyLevel)` guard.
- T-37-05 (Pitfall 2 inert surface) — mitigated by documenting the inert surface in `TestPrecedenceTruthTable` (Q1 MINIMAL); not hidden.
- T-37-06 (Pitfall 4 module-level import) — mitigated by lazy-local import inside `_setup_rewards` (verified by grep at line 542).
- T-37-07 (TASK-09 continuous path) — mitigated by the additive early-return + Q4 guard; 220-test additive gate green.
- T-37-08 (apply_params refactor regression) — mitigated by pure extraction; `test_apply_params_delegates_on_suturing` + `test_difficulty_levels.py` green.
- No new network/auth/file-access surface. `SurgicalEnvConfig.difficulty` is a researcher-facing config scalar (default 0.5); `apply_params` is an in-process method call.

## Self-Check: PASSED

- `tests/test_difficulty_blocks.py` — FOUND (modified)
- `src/surg_rl/rl/rewards.py` — FOUND (modified)
- `src/surg_rl/rl/environment.py` — FOUND (modified)
- `.planning/phases/37-scene-level-difficulty-blocks-env-wiring/37-02-SUMMARY.md` — FOUND
- Commit `5fcccfc` (test/RED) — FOUND
- Commit `dac09e8` (feat/GREEN-rewards) — FOUND
- Commit `9377b74` (feat/GREEN-env) — FOUND