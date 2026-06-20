# Plan 33-01 Summary: EditorWindow Foundation

**Status:** Complete
**Wave:** 1
**Date:** 2026-06-19

## What Was Built

Phase 33 plan 33-01 ships the Phase 33 editor foundation:

- **`src/surg_rl/editor/_safe_error.py`** — pure-Python secret redactor
  (`safe_error_message()`) covering 5 patterns: OpenAI keys, Anthropic keys,
  xAI keys, Bearer tokens, env-var-style assignments. No PySide6 import.
- **`src/surg_rl/editor/_settings.py`** — `EditorSettings` QSettings wrapper
  for window geometry, recent files (5-cap, dedupe, most-recent-first), and
  last LLM provider. No API keys stored.
- **`src/surg_rl/editor/main_window.py`** — `EditorWindow(QMainWindow)` with
  4 QDockWidget panes (tree left, viewport center, properties right, LLM bottom),
  File/Edit/View/Help menu bar with shortcuts, drag-drop for `.json` files,
  status bar (path/sim/fps/validation), and QSettings geometry persistence.
- **`src/surg_rl/editor/app.py`** — `surg-rl-gui` console-script entrypoint
  wired to `EditorWindow`. CLI integration: `surg-rl-gui path/to/scene.json`
  opens the scene at startup.
- **`tests/test_gui_foundation.py`** — 13 regression tests across 5 test classes.

## Test Results

- **8** `TestSafeErrorMessage` tests pass (pure-Python, no Qt required).
- **4** `TestEditorSettings` tests skip on PySide6-free systems.
- **5** `TestMainWindow` tests skip on PySide6-free systems.
- **2** `TestAppMainGates` tests pass (`--help` exits 0; `--headless` exits 0).
- **1** `TestSurgRlCliIndependence` test passes (lacks `surg-rl` CLI does not
  import PySide6).
- Phase 31's 19-test regression suite (`test_gui_scaffold.py`) still passes —
  no regressions.

## Files Created/Modified

| File | Change | Lines |
|------|--------|-------|
| `src/surg_rl/editor/_safe_error.py` | New | 50 |
| `src/surg_rl/editor/_settings.py` | New | 60 |
| `src/surg_rl/editor/main_window.py` | New | 215 |
| `src/surg_rl/editor/app.py` | Modified (EditorWindow wiring) | +14 / -15 |
| `tests/test_gui_foundation.py` | New | 245 |

## Requirements Satisfied

- **GUI-08:** 4-pane QDockWidget layout (tree/viewport/properties/LLM)
- **GUI-09:** All error strings routed through `safe_error_message()`

## Deviations

- `app.main()` was extended but still uses the warn-and-exit `mjpython` gate
  (line `sys.exit(1)`). Plan 33-03 task 2 replaces this with `os.execvp`
  re-exec — the executor applied that replacement in dependency order (33-01
  first, then 33-03).
- `_empty_scene_stub()` helper added to support the ViewportPanel integration
  in 33-03 (slightly forward-looking).

## Next

Plan 33-02 (SchemaWalker + FieldRenderer) and Plan 33-03 (Viewport + mjpython
refactor) can run in parallel — they have no shared files. Both are scheduled
for Wave 2.
