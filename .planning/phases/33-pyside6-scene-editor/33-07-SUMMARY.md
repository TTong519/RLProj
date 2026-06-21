---
phase: 33-pyside6-scene-editor
plan: 07
subsystem: ui
tags: [pyside6, viewport, qtimer, mujoco-renderer, close-event, shutdown]

requires:
  - phase: 33-pyside6-scene-editor (plans 01-05)
    provides: "ViewportPanel + EditorWindow with render loop and closeEvent"
provides:
  - "Hardened viewport render loop with _running flag (halts cleanly on stop)"
  - "MuJoCo Renderer __del__ AttributeError guard in stop() and __del__"
  - "Fixed silent render-loop death (simulator-unavailable branch now reschedules)"
  - "EditorWindow.closeEvent stops viewport before Qt teardown"
  - "Launch smoke test verifying window shows + 500ms event processing"
affects: [33-pyside6-scene-editor (UAT verification), editor-launch, shutdown]

tech-stack:
  added: []
  patterns: ["_running flag for self-rescheduling QTimer loops", "try/except (AttributeError, OSError) around external-C-library close()", "stop() before super().closeEvent() pattern for Qt cleanup ordering"]

key-files:
  created: []
  modified:
    - src/surg_rl/editor/viewport.py
    - src/surg_rl/editor/main_window.py
    - tests/test_viewport.py

key-decisions:
  - "_running flag checked at top of _tick (early return if False) and before rescheduling (only if True) — prevents dangling QTimer callbacks after window close"
  - "try/except (AttributeError, OSError) around simulator.close() in stop() — swallows MuJoCo Renderer.__del__ AttributeError('_gl_context') during interpreter shutdown instead of propagating"
  - "__del__ method calls stop() in try/except — best-effort cleanup during interpreter shutdown"
  - "closeEvent calls _viewport_panel.stop() in try/except BEFORE super().closeEvent() — Qt teardown order matters"
  - "Simulator-unavailable branch reschedules instead of returning silently — prevents render loop from dying unnoticed"

patterns-established:
  - "Self-rescheduling QTimer loops must guard with a _running flag checked at top and before reschedule"
  - "External C-library close() calls must be wrapped in try/except (AttributeError, OSError) — __del__ crashes during shutdown are expected"
  - "Qt window closeEvent must stop background timers/simulators BEFORE super().closeEvent()"

requirements-completed: [GUI-01, GUI-03, GUI-08]

duration: ~10min
completed: 2026-06-20
status: complete
---

# Plan 33-07 Summary: Viewport Render Loop Hardening + closeEvent Wiring

**Hardened viewport against MuJoCo Renderer __del__ crash, added _running flag to halt QTimer cleanly, and wired closeEvent to stop viewport before Qt teardown — editor no longer freezes on launch**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 3

## Accomplishments
- `ViewportPanel` now has a `_running` flag: `stop()` sets it False, `_tick()` checks it at top (early return) and before rescheduling (only if True) — prevents dangling QTimer callbacks after window close
- `stop()` wraps `simulator.close()` in `try/except (AttributeError, OSError)` — swallows MuJoCo's `Renderer.__del__` `AttributeError('_gl_context')` during interpreter shutdown instead of propagating to the user
- `__del__` method added to `ViewportPanel` — calls `stop()` in try/except for best-effort cleanup during interpreter shutdown
- Fixed silent render-loop death: when `_on_load_simulator` returns None, `_tick` now reschedules via `QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)` instead of returning silently (the original bug killed the loop unnoticed)
- `EditorWindow.closeEvent` now calls `self._viewport_panel.stop()` in try/except BEFORE `super().closeEvent()` — prevents dangling QTimer and MuJoCo `__del__` crash during Qt teardown
- Launch smoke test verifies the window appears and processes 500ms of events without freezing — locks Gap 2 truth "window opens and remains responsive"

## Task Commits

Each task was committed atomically (TDD: test → fix):

1. **Task 1: Harden viewport render loop with _running flag + __del__ guard** — `29a8508` (test RED) + `068c63f` (feat GREEN)
2. **Task 2: Wire closeEvent to stop viewport + add launch smoke test** — `f3fee1d` (test RED) + `d3b8f74` (fix GREEN — closeEvent wiring)

## Files Created/Modified
- `src/surg_rl/editor/viewport.py` — Added `_running` flag in `__init__`, `__del__` method, `try/except (AttributeError, OSError)` around `simulator.close()` in `stop()`, `_running` guard at top and before reschedule in `_tick()`, reschedule in simulator-unavailable branch, `_start()` sets `_running = True`
- `src/surg_rl/editor/main_window.py` — `closeEvent` now calls `self._viewport_panel.stop()` in try/except before `super().closeEvent()`
- `tests/test_viewport.py` — Added `TestViewportRenderLoopGuard` (4 tests: `test_stop_halts_render_loop`, `test_tick_recovers_from_simulator_none`, `test_del_guarded_against_attribute_error`, `test_render_error_reschedules`) and `TestEditorLaunchGuard` (2 tests: `test_close_event_stops_viewport`, `test_editor_launches_without_freeze`)

## Decisions Made
- **`_running` flag over QTimer.stop():** The render loop uses `QTimer.singleShot(50, self._tick)` self-rescheduling (D-03 pattern), not a recurring `QTimer.start(50)`. There's no timer object to `.stop()` — the flag is the correct mechanism.
- **Swallow `AttributeError` in `simulator.close()`:** MuJoCo's `Renderer.__del__` is a known issue (GL context already garbage-collected during interpreter shutdown). Patching MuJoCo is out of scope; swallowing the error during teardown is the standard mitigation.
- **Continue (not exit) on render errors:** The render loop already had this pattern (catch exception, show error, reschedule). Task 1 locks it with `test_render_error_reschedules` and fixes the one branch that broke it (simulator-unavailable).
- **`closeEvent` stop before Qt teardown:** Qt teardown in `super().closeEvent()` can trigger widget destruction while the viewport's QTimer is still firing. Stopping the viewport first prevents the dangling callback.

## Deviations from Plan

None — plan executed exactly as written. One minor process note: the executor's task 2 commit initially only included the test changes, not the `closeEvent` fix. The orchestrator detected this (uncommitted `main_window.py` change left in working tree after the executor returned an empty result) and committed the fix separately (`d3b8f74`) with the same task 2 message. This is a recovery from a truncated executor result, not a plan deviation.

## Issues Encountered
- **Pre-existing test failures in test_gui_foundation.py and test_file_operations.py (not caused by this plan):** 4 tests fail (`test_main_window_can_be_constructed`, `test_close_event_persists_geometry`, `test_last_provider_round_trip`, `test_save_writes_valid_json`). Verified these fail with the pre-33-07 code too (checked out `696ae5f` and re-ran — same failures). Root causes:
  - `QDockWidget.title()` does not exist in PySide6 (test_gui_foundation.py:166) — pre-existing API misuse
  - `EditorWindow` lacks `_undo_stack` attribute when `_save_scene_to` is called without full `__init__` (test_file_operations.py constructs a partial EditorWindow) — pre-existing test fixture issue
  These are pre-existing issues unrelated to 33-07's changes (which only touch `viewport.py`, `closeEvent`, and new tests in `test_viewport.py`).
- **Executor result truncation:** Both executor subagents returned empty/truncated results without creating SUMMARY.md. The orchestrator verified completion via spot-checks (commits present, tests pass) and created SUMMARY.md manually following the #2070 fallback rule.

## Gap Closure

| UAT Gap | Test | Severity | Closed By | How |
|---------|------|----------|-----------|-----|
| App freezes/no window (MuJoCo `__del__` crash + dangling QTimer) | 2 | major | 33-07 task 1 | `_running` flag halts render loop + `__del__`/`stop()` try/except swallows `AttributeError('_gl_context')` |
| App freezes/no window (closeEvent doesn't stop viewport) | 2 | major | 33-07 task 2 | `closeEvent` calls `_viewport_panel.stop()` before Qt teardown + launch smoke test verifies window shows + 500ms events |
| App freezes/no window (silent render-loop death) | 2 | major | 33-07 task 1 | simulator-unavailable branch reschedules instead of returning silently |

## Next Phase Readiness
- Gap 2 (app freezes) fully closed: 33-06 handled the mjpython re-exec component; 33-07 handled the viewport `__del__`/QTimer/closeEvent component. Together they close UAT Gap 2.
- All 6 new tests pass; no regressions in `test_viewport.py` (16/16 pass).
- The 4 pre-existing failures in `test_gui_foundation.py` / `test_file_operations.py` are documented as pre-existing and out of scope for this gap closure plan. They should be addressed in a future tech-debt phase.

---
*Phase: 33-pyside6-scene-editor*
*Plan: 07*
*Completed: 2026-06-20*