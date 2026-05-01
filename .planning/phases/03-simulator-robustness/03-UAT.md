---
status: testing
phase: 03-simulator-robustness
source:
  - .planning/phases/03-simulator-robustness/03-01-SUMMARY.md
  - .planning/phases/03-simulator-robustness/03-02-SUMMARY.md
started: 2026-04-30T05:30:00Z
updated: 2026-04-30T05:30:00Z
---

## Current Test

number: 1
name: Soft-body mesh caching reduces reset time
expected: |
  Running the dedicated test `TestSoftBodyMeshCaching::test_reset_under_100ms_on_suturing_scene` passes and the soft-body episode reset completes in under 100 milliseconds.
awaiting: user response

## Tests

### 1. Soft-body mesh caching reduces reset time
expected: Soft-body episode reset completes in <100ms on suturing scene (verified by test)
result: pending

### 2. Vectorized mesh generation is fast
expected: Procedural mesh generation for a 64³ box completes in under 1 second (verified by test)
result: pending

### 3. PyBullet state round-trip parity
expected: get_state → set_state → get_state yields identical qpos/qvel (within 1e-6) and body_positions (within 1e-3)
result: pending

### 4. MuJoCo state round-trip parity
expected: get_state → set_state → get_state yields qpos/qvel identical within 1e-6
result: pending

### 5. Soft-body node position capture and restore
expected: get_state captures soft-body node positions; set_state restores them; observation after restore matches observation before save (within 1e-3)
result: pending

### 6. TrainingManager eval env caching
expected: evaluate() reuses a cached evaluation environment on the second and subsequent calls when config is unchanged; config mismatch triggers creation of a new env
result: pending

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0

## Gaps

[none yet]
