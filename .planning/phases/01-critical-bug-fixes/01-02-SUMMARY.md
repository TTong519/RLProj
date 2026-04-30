# Phase 01 Plan 02 Summary: Reward Sign, Curriculum Dynamics, and LightConfig Mutation

## Overview

Fixed three cross-module correctness bugs in the Surg-RL codebase: reward sign contract (BUG-04), incomplete curriculum parameter application (BUG-06), and in-place mutation of input dicts in `LightConfig` (BUG-07).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Refactor `RewardConfig` to Pydantic BaseModel, enforce non-negative penalties, remove `abs()` in `create_default_reward` | `6def4fe` | `src/surg_rl/rl/rewards.py`, `tests/test_rewards.py` |
| 2 | Fix `CurriculumScheduler.apply_parameters` to apply dynamics overrides and store them for downstream use | `91cf2c7` | `src/surg_rl/dynamics/curriculum.py`, `tests/test_dynamics.py` |
| 3 | Fix `LightConfig` validator to copy input dict before mutation, add regression test | `1d7fdbe` | `src/surg_rl/scene_definition/schema.py`, `tests/test_schema.py` |

## Test Results

- `tests/test_rewards.py`: 43 passed
- `tests/test_dynamics.py`: 67 passed
- `tests/test_schema.py`: 59 passed
- **Combined (`PYTHONPATH=src pytest tests/test_rewards.py tests/test_dynamics.py tests/test_schema.py -x -q`)**: **169 passed**

## Key Changes

1. **`RewardConfig`** is now a Pydantic v2 `BaseModel` with `@field_validator` on penalty magnitudes (must be ≥ 0). Default penalty values changed from negative to positive (e.g., `collision_penalty=10.0`).
2. **`create_default_reward`** no longer wraps penalties with `abs()`, preserving the sign contract.
3. **`CurriculumScheduler.apply_parameters`** now consumes `snapshot.dynamics` fields (`action_noise`, `joint_noise`, `delay`) and stores them on the scheduler; logs at `debug` level when no simulator setter is available.
4. **`LightConfig.validate_light_type`** copies `data = dict(data)` before mutating, preventing side effects on caller dicts.

## Deviations from Plan

- **None.** All three tasks executed exactly as specified in `01-02-PLAN.md`.

## Artifacts

- `src/surg_rl/rl/rewards.py`
- `src/surg_rl/dynamics/curriculum.py`
- `src/surg_rl/scene_definition/schema.py`
- `tests/test_rewards.py`
- `tests/test_dynamics.py`
- `tests/test_schema.py`

## Requirements Coverage

| Requirement | Covered |
|-------------|---------|
| BUG-04 | ✅ |
| BUG-06 | ✅ |
| BUG-07 | ✅ |
