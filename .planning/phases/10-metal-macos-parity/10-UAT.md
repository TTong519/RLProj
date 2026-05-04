---
status: complete
phase: 10-metal-macos-parity
source:
  - 10-01-SUMMARY.md
  - 10-02-SUMMARY.md
  - 10-03-SUMMARY.md
  - 10-04-SUMMARY.md
started: 2026-05-03T21:05:00Z
updated: 2026-05-03T21:10:00Z
---

## Current Test

## Current Test

[testing complete]

## Tests

### 1. MPS device auto-resolution
expected: Running `get_torch_device("auto")` on this macOS machine returns `"mps"` and logs unified memory info (e.g., "unified memory: 24.0 GB") plus the MPS speed caveat at INFO level.
result: pass

### 2. MPS fallback warns once
expected: Calling `mps_fallback_to_cpu("test_op")` emits a WARNING log. A second call is silent.
result: pass

### 3. Zero macOS xfail markers
expected: Running `rg "xfail.*darwin" tests/test_simulators.py` returns zero matches.
result: pass

### 4. Full test suite — 775 passed, no regressions
expected: `pytest tests/ -m "not integration"` completes with 775 passed. Soft-body roundtrip test shows PASSED (not XPASS).
result: pass
note: User observed 780 passed on local run (likely env-dependent test inclusion)

### 5. CI includes macOS runner
expected: `.github/workflows/ci.yml` includes `macos-latest` in the matrix with Python 3.11, uses mjpython for pytest, and ignores ROS2 test files.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
