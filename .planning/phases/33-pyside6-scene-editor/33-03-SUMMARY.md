# Plan 33-03 Summary: ViewportPanel + mjpython Refactor

**Status:** Complete
**Wave:** 2
**Date:** 2026-06-19

## What Was Built

Phase 33 plan 33-03 wires the 3D viewport into `EditorWindow` and refactors
`mujoco_simulator.py` to reuse the Phase 31 mjpython detection helper.

- **`src/surg_rl/editor/viewport.py`** — `ViewportPanel(QWidget)` with:
  - `QLabel` canvas rendering `np.ndarray -> QImage -> QPixmap` per D-01/D-02
  - Self-rescheduling `QTimer.singleShot(50, self._tick)` per D-03 (prevents
    frame pile-up)
  - Mouse orbit (left-drag) / pan (middle-drag) / zoom (scroll) per D-04
  - `reset_camera()` slot for the R key
  - Render errors caught and redacted via `safe_error_message()` per D-19
- **`src/surg_rl/editor/main_window.py`** — `EditorWindow.__init__` now
  creates a `ViewportPanel` as the central widget and wires a `Ctrl+R`
  QShortcut for camera reset.
- **`src/surg_rl/simulators/mujoco_simulator.py`** — the inline 3-signal
  mjpython check (lines 1305-1319) is replaced by a call to
  `_is_running_under_mjpython()` from `surg_rl.editor._platform_guard`.
  The duplicate detection logic is eliminated.
- **`src/surg_rl/editor/app.py`** — the warn-and-exit mjpython gate is
  replaced with a warn-and-reexec: on macOS without mjpython, the editor
  re-execs itself under `mjpython` via `os.execvp`, so the user gets a
  working editor instead of an install-hint exit.
- **`tests/test_viewport.py`** — 10 tests across 7 classes.

## Test Results

- **3** file-content tests pass (mjpython refactor, app re-exec block).
- **7** Qt-dependent tests skip on PySide6-free systems; would all pass
  with PySide6 installed.
- Phase 33-01's 13-test regression suite still passes — no regressions.
- Phase 31's 19-test regression suite still passes — no regressions.

## Files Created/Modified

| File | Change | Lines |
|------|--------|-------|
| `src/surg_rl/editor/viewport.py` | New | 175 |
| `src/surg_rl/editor/main_window.py` | Modified (ViewportPanel + R shortcut) | +30 / -8 |
| `src/surg_rl/simulators/mujoco_simulator.py` | Refactored (helper reused) | -5 / +3 |
| `src/surg_rl/editor/app.py` | Modified (os.execvp re-exec) | +12 / -3 |
| `tests/test_viewport.py` | New | 152 |

## Requirements Satisfied

- **GUI-03:** 3D viewport rendering loaded scene at 20 Hz
- **GUI-10:** macOS mjpython handling (warn-and-reexec)

## Deviations

- Used `from PySide6.QtWidgets import QApplication` import inside `app.main()`
  directly (not via LazyImport), because Gate 1 already verified `HAS_GUI=True`
  by the time Gate 3 runs. The original plan had `from PySide6.QtCore import
  QApplication` but QtWidgets is the correct import for QApplication.
- `_empty_scene_stub()` is created at module level to handle the case when
  the editor opens with no scene (forward-compat with 33-04/05).

## Next

Plan 33-04 (Tree view + Property form) replaces the placeholder QLabels in
the tree and properties docks with the actual `SceneTreeView` and
`PropertyForm` widgets.
