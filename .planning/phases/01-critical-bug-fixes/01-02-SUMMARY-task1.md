# Phase 01 Plan 02: RewardConfig Refactor Summary - Task 1

**Objective:** Refactor `RewardConfig` from a `@dataclass` to a Pydantic v2 `BaseModel`, enforce non-negative penalty values, remove `abs()` in `create_default_reward`, update tests, and add a regression test.

**Changes Made:**
- **Converted `RewardConfig`** from a `@dataclass` to a Pydantic v2 `BaseModel`.
- **Updated penalty defaults** to positive magnitudes:
  - `failure_penalty`: `-50.0` -> `50.0`
  - `collision_penalty`: `-10.0` -> `10.0`
  - `tissue_damage_penalty`: `-5.0` -> `5.0`
- **Added `@field_validator`** on `failure_penalty`, `collision_penalty`, `tissue_damage_penalty` to reject negative values with `ValueError`.
- **Removed `abs()`** calls around `config.collision_penalty` and `config.tissue_damage_penalty` in `create_default_reward`.
- **Added regression test** `test_reward_config_rejects_negative_penalty` asserting `ValidationError` on negative input.
- **Updated existing tests** that explicitly used negative defaults (e.g., `test_collision_penalty_is_negative` now passes positive `weight=10.0` through default config).

**Test Results:**
- `tests/test_rewards.py`: 43 passed
- `tests/test_rl.py`: 72 passed

**Commit Hash:** `6def4fe`
