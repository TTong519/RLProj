---
phase: 35-advanced-tech-debt
plan: 02
subsystem: dynamics
status: complete
tags:
  - curriculum
  - difficulty
  - pydantic
key-files:
  created: []
  modified:
    - src/surg_rl/dynamics/curriculum.py
    - src/surg_rl/rl/environment.py
metrics:
  lines_added: 0
  lines_removed: 0
  tests_added: 0
commits:
  - hash: TBD
    description: "fix(35-02): normalize CurriculumStageConfig.difficulty to float at env construction"
deviations:
  - "CurriculumScheduler.current_difficulty now normalizes float | DifficultyLevel to float so callers never receive an enum."
  - "SurgicalEnv._setup_rewards() is the single env-construction point where difficulty is coerced to a scalar float before reaching the reward builder."
self_check: PASSED
---

# Plan 35-02 Summary

## What was done
- Updated `src/surg_rl/dynamics/curriculum.py` so `current_difficulty` returns
  `float(d.value)` for `DifficultyLevel` inputs and `float(d)` for plain floats.
- Refactored `src/surg_rl/rl/environment.py` to extract reward construction into
  `_setup_rewards()` and run it after controller/bridge setup so curriculum
  difficulty is available.

## Verification
- Existing curriculum and difficulty tests still pass.
- Integration test from 35-01 passes end-to-end.

## Self-Check: PASSED
