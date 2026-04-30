---
phase: "01"
plan: "03"
subsystem: "utils, rl"
tags: ["security", "config", "logging", "training", "vecenv"]
requires: []
provides: []
affects: ["src/surg_rl/utils/config.py", "src/surg_rl/utils/logging.py", "src/surg_rl/rl/training.py", ".env.example"]
tech-stack:
  added: []
  patterns: ["Pydantic Settings validator", "logging.Filter subclass", "VecEnv API normalization"]
key-files:
  created:
    - tests/test_logging.py
  modified:
    - src/surg_rl/utils/config.py
    - src/surg_rl/utils/logging.py
    - src/surg_rl/rl/training.py
    - .env.example
    - tests/test_config.py
    - tests/test_rl_training.py
decisions:
  - Reject known placeholder strings in Settings.llm_api_key (case-insensitive match)
  - Use regex filter with sk-prefix patterns to mask API keys in logs (**** + last 4 chars)
  - Normalize VecEnv reset() tuples and list-of-dicts info before extracting task_success
metrics:
  duration: "~15 min"
  completed-date: "2026-04-29"
  tests-passed: 553
  tests-total: 553
  files-changed: 7
  commits: 3
---

# Phase 01 Plan 03: Harden Settings, Mask Logs, Fix evaluate()

## Summary

Executed three atomic fixes: hardened `Settings` to reject placeholder API keys (SEC-01), added
`SensitiveDataFilter` to mask OpenAI/Anthropic keys in log output (SEC-02), and made
`TrainingManager.evaluate()` robust to both `VecEnv` tuple resets and list-of-dicts `info`
(BUG-08). All tests pass (553 passed, including newly added regression tests, 1 xfailed, 3
xpassed as expected).

## Commits

| # | Commit | Files | Description |
|---|--------|-------|-------------|
| 1 | `c35f048` | `src/surg_rl/utils/config.py`, `.env.example`, `tests/test_config.py` | Reject placeholder API keys in Settings |
| 2 | `95a67aa` | `src/surg_rl/utils/logging.py`, `tests/test_logging.py` | Mask API keys in log output |
| 3 | `d1667f7` | `src/surg_rl/rl/training.py`, `tests/test_rl_training.py` | Robust evaluate() for VecEnv tuple reset and list info |

## Tasks Completed

### Task 1: Harden Settings and .env.example (SEC-01)
- Added `@field_validator("llm_api_key", mode="before")` on `Settings`.
- Rejects `your_api_key_here`, `YOUR_API_KEY`, `REPLACE_ME`, `sk-xxxxxxxx`, `xxxxxx`.
- Updated `.env.example` to comment out the key with instructions.
- Added tests: `test_settings_rejects_placeholder_api_key`, `test_settings_allows_real_api_key`.

### Task 2: Add API Key Masking to Log Output (SEC-02)
- Created `SensitiveDataFilter(logging.Filter)` matching `sk-[A-Za-z0-9]{20,}` and `sk-ant-[A-Za-z0-9-]{20,}`.
- Replaces matches with `****` + last 4 characters.
- Applies filter to both console and file handlers in `setup_logging()`.
- Added `tests/test_logging.py` with regression tests for message masking, args masking,
  `sk-ant-*` keys, non-sensitive passthrough, and short-key behavior.

### Task 3: Fix evaluate() for DummyVecEnv and SubprocVecEnv (BUG-08)
- VecEnv `reset()`: handled both `obs` and `(obs, info)` return shapes.
- VecEnv `step()`: `info` is a `list[dict]`; now extracts `task_success` from the first env's
  dict (`info[0]`) when appropriate.
- Added regression tests: `test_evaluate_vec_env_with_tuple_reset` (num_envs=1, tuple reset),
  `test_evaluate_subproc_vec_env` (num_envs=2, list-of-dicts info).
- Verified existing `test_evaluate_non_vec_env` and `test_evaluate_vec_env` still pass.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All new code is fully wired and tested.

## Threat Flags

None beyond the explicitly mitigated placeholders.

## Self-Check: PASSED

- All created files exist: `tests/test_logging.py` ✔
- All commits exist and verified: `c35f048`, `95a67aa`, `d1667f7` ✔
- Full test suite: 553 passed, 0 failed ✔
