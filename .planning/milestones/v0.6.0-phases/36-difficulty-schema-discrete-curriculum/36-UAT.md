---
status: complete
phase: 36-difficulty-schema-discrete-curriculum
source: [36-01-SUMMARY.md, 36-02-SUMMARY.md, 36-03-SUMMARY.md]
started: 2026-06-25T04:53:51Z
updated: 2026-06-25T05:20:10Z
---

## Current Test

[testing complete]

## Tests

### 1. DifficultyLevelConfig rejects out-of-range override values
expected: Constructing DifficultyLevelConfig(tissue_stiffness=400.0) raises a Pydantic ValidationError mentioning tissue_stiffness + bound [50.0, 300.0]; in-range values construct and round-trip.
result: pass

### 2. DifficultyLevelConfig all-None default equals no overrides
expected: DifficultyLevelConfig() constructs with all four override fields None (no overrides set) — the neutral baseline used by the wiring layer.
result: pass

### 3. difficulty.py leaf has zero in-project imports (SC#5)
expected: `grep -v '^\s*#' src/surg_rl/rl/difficulty.py | grep -c 'surg_rl\.'` returns 0 — the leaf imports only stdlib + pydantic, no surg_rl.* imports.
result: pass

### 4. compose_difficulty_overrides overrides only the mapped concrete key
expected: For task_type="suturing", level=MEDIUM, with a target_precision_tolerance override, compose_difficulty_overrides returns interpolate_params(MEDIUM) with ONLY the mapped concrete key (needle_position_tolerance) replaced by the override value; every other key and the key set are unchanged.
result: pass

### 5. Unmapped override warns and keeps interpolation (no raise)
expected: A tissue_stiffness override on "suturing" (no tissue_stiffness mapping per D-05) logs a WARNING and returns pure interpolation — no KeyError, no exception raised.
result: pass

### 6. DiscreteCurriculumConfig defaults to empty levels
expected: DiscreteCurriculumConfig().levels is an empty dict; round-tripping a per-level config holds the levels mapping.
result: pass

### 7. Discrete-mode scheduler starts at EASY (current_difficulty 0.0)
expected: A CurriculumScheduler with progression_mode="discrete" starts with current_difficulty == 0.0 (EASY).
result: pass

### 8. set_difficulty_level manually overrides the current level
expected: scheduler.set_difficulty_level(DifficultyLevel.HARD) sets current_difficulty == 1.0.
result: pass

### 9. advance_level walks EASY→MEDIUM→HARD→terminal under a passing window
expected: With a passing success-rate window, advance_level returns True (EASY→MEDIUM), True (MEDIUM→HARD), then False at HARD (terminal); current_difficulty moves 0.5 then 1.0.
result: pass

### 10. Continuous advance_stage path unchanged (parity)
expected: A default (continuous) CurriculumScheduler still progresses EASY→MEDIUM→HARD→EXPERT with current_difficulty scalars 0.25 / 0.5 / 0.75 / 1.0 — Phase 36 added the discrete axis additively without altering continuous behavior.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]