---
phase: 07
slug: real-time-rendering
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
---

# Phase 07 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | pytest.ini (pythonpath = src) |
| **Quick run command** | `PYTHONPATH=src pytest tests/unit/test_rendering.py -q` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -q` |
| **Estimated runtime** | ~5s (render suite), ~50s (full) |

## Per-requirement Verification Map

| Requirement | Description | Test Files | Status |
|-------------|-------------|-----------|--------|
| RENDER-01 | Non-blocking human render | test_rendering.py (TestMuJoCoViewer, TestSurgicalEnvViewer, TestPyBulletViewer) | COVERED |
| RENDER-02 | <5ms step() overhead | test_rendering.py (TestStepOverhead.test_step_with_viewer_not_blocked) | COVERED |
| RENDER-03 | 30 FPS throttle | test_rendering.py (TestRenderThread.test_calls_sync_at_interval) + config defaults | COVERED |
| RENDER-04 | --render-human CLI flag | test_rendering.py (TestCliRenderHumanWiring) + cli.py wiring (fixed 2026-05-03) | COVERED |
| RENDER-05 | Clean shutdown | test_rendering.py (test_close_calls_stop_viewer, test_sigint_handler_crashes_gracefully) | COVERED |

## Gap Closure

| Gap | Description | Fix | Test |
|-----|-------------|-----|------|
| RENDER-04 | --render-human/--render-fps dead code in CLI | render_mode + render_fps wired to TrainingConfig (cli.py:348-349) | TestCliRenderHumanWiring (3 tests) |

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Live viewer window opens | RENDER-01 | Requires display | `surg-rl train --render-human` on desktop |
| Viewer closes on Ctrl+C | RENDER-05 | Requires display + interaction | Run with --render-human, press Ctrl+C |

## Validation Sign-Off

- [x] All 5 RENDER requirements have automated tests
- [x] RENDER-04 dead code fixed + tested (2026-05-03)
- [x] Manual-only items are display-dependent, not code gaps
- [x] `nyquist_compliant: true`

**Approval:** approved 2026-05-03
