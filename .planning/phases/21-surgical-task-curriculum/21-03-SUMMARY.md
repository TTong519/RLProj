---
phase: 21-surgical-task-curriculum
plan: 03
subsystem: dynamics + rl
tags: [curriculum, task-params, reward-routing, task-termination, integration]
depends_on:
  provides: [curriculum-task-integration, reward-router-wiring, per-task-check-success-delegation]
  requires: ["21-01", "21-02"]
  affects: ["21-04"]
tech-stack:
  added: []
  patterns: [registry-based-dispatch, per-task-reward-delegation, hysteresis-oscillation-prevention]
key-files:
  created: []
  modified:
    - src/surg_rl/dynamics/curriculum.py
    - src/surg_rl/rl/environment.py
    - src/surg_rl/rl/task_termination.py
decisions:
  - D-08: task_param_bounds merges into sampled parameter overrides during sample_parameters()
  - D-09: CurriculumScheduler.episode_end_with_task_result() consumes structured TaskResult
  - D-10: apply_parameters() confirmed untouched — zero modifications (verified by md5)
metrics:
  duration: "5m49s"
  completed_date: "2026-05-17"
---

# Phase 21 Plan 03: Task Curriculum Integration

**One-liner:** Wires TaskRewardRouter into SurgicalEnv reward init, extends CurriculumScheduler for per-task parameters and TaskResult consumption, and delegates check_task_success to per-task reward methods — all additive, zero modifications to Phase 3 curriculum fix.

## Tasks Executed

| # | Name | Type | Commit | Result |
|---|------|------|--------|--------|
| 1 | Extend CurriculumStageConfig + CurriculumScheduler for TaskResult and per-task parameters | auto | c3cfd2a | `task_param_bounds` field added; `episode_end_with_task_result()` and `_should_regress()` methods added; `difficulty_hysteresis` on `CurriculumConfig`; parameter merging in `sample_parameters()` |
| 2 | Wire TaskRewardRouter into SurgicalEnv reward initialization | auto | 0a3ae17 | Router used when `task_type` is set; `CompositeReward` wraps router output; `create_default_reward()` fallback preserved; `_task_difficulty` tracked from controller |
| 3 | Update task_termination.py to delegate to per-task reward check_success | auto | 7705c50 | `check_task_success()` accepts optional `reward_fn`; per-task delegation before generic heuristics; `get_task_result()` utility; existing heuristics preserved |

## Deviations from Plan

None — plan executed exactly as written.

## Acceptance Criteria Results

### Task 1: Curriculum

- [x] `task_param_bounds` ≥2 occurrences in curriculum.py (5 found)
- [x] `difficulty_hysteresis` ≥2 occurrences (3 found)
- [x] `def episode_end_with_task_result` count = 1
- [x] `def _should_regress` count = 1
- [x] `apply_parameters()` method body has zero changes — verified by content comparison
- [x] `_should_advance()` and `update_curriculum()` have zero changes
- [x] All 20 existing curriculum tests pass
- [x] `CurriculumStageConfig(task_param_bounds={'a': [0,1]})` constructs without error

### Task 2: Environment Router

- [x] `TaskRewardRouter` ≥1 occurrence in environment.py (3 found)
- [x] `CompositeReward` ≥1 occurrence (2 found)
- [x] `create_default_reward` ≥1 occurrence (2 found — fallback preserved)
- [x] `task_type` ≥2 occurrences (5 found)
- [x] `SurgicalEnv` imports cleanly
- [x] Router path tested: `task_type="suturing"` → CompositeReward with SuturingReward
- [x] Fallback path tested: `task_type=None` → create_default_reward()

### Task 3: Task Termination

- [x] `reward_fn.*check_success` ≥1 occurrence (7 found)
- [x] `def get_task_result` count = 1
- [x] `check_task_success()` signature includes `reward_fn: Any = None`
- [x] `_parse_distance_criteria` preserved (2 occurrences)
- [x] `_quaternion_angle` preserved (2 occurrences)
- [x] Per-task delegation runs before generic heuristics
- [x] Backward compat: `reward_fn=None` → only generic heuristics

### Full Test Suite

- [x] 913 tests passed, 0 failures (`pytest tests/ -m "not integration"`)

## Key Links Verified

| From | To | Via | Pattern | Status |
|------|-----|-----|---------|--------|
| `environment.py` | `task_reward_router.py` | `TaskRewardRouter.build()` at init | `TaskRewardRouter` import | ✓ |
| `task_termination.py` | `rewards.py` | per-task `check_success()` delegation | `check_success` | ✓ |
| `curriculum.py` | `task_results.py` | `episode_end_with_task_result()` | `TaskResult` | ✓ |

## D-10 Verification

`apply_parameters()` method body is byte-for-byte identical to commit 844f7f6. Verified by extracting the method from both commits and comparing content. Zero modifications confirmed.

## Threat Mitigations Applied

- **T-21-06 (Tampering):** task_type constrained to Literal[6] at Pydantic parse time — no code injection possible through router
- **T-21-07 (DoS):** `difficulty_hysteresis` = 0.05 added to `CurriculumConfig`; `_should_regress()` requires `success_rate < threshold - 0.2 - hysteresis` — prevents difficulty oscillation
- **T-21-08 (Info Disclosure):** TaskResult.metrics contain summary statistics only — accepted as low risk
- **T-21-09 (Elevation of Privilege):** `check_task_success()` delegation is guarded by `hasattr(reward_fn, 'check_success')` + try/except — falls through to generic heuristics on any error

## Key Decisions

- D-08: `task_param_bounds` merges into `parameter_overrides` within `sample_parameters()` — `difficulty` remains single source of truth
- D-09: `episode_end_with_task_result()` consumes structured `TaskResult` (success, metrics, difficulty) and delegates to standard `episode_end` pipeline
- D-10: `apply_parameters()` is **never** modified — curriculum changes are strictly additive
