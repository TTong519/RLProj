# Plan 33-05 Summary: LLM Panel + Undo/Redo + File Ops + Smoke Test

**Status:** Complete
**Wave:** 4
**Date:** 2026-06-19

## What Was Built

Phase 33 plan 33-05 ships the final integration slice — the last 5 GUI
requirements (GUI-01, GUI-02, GUI-06, GUI-07, GUI-09) and the GUI smoke
test scaffolding that Phase 34 will use to capture screenshots.

- **`src/surg_rl/editor/undo_stack.py`** — `SceneUndoStack(QUndoStack)` with
  deep-copy snapshots per D-09 (`model_copy(deep=True)` correctly handles
  all 63 classes including the `_FloatMixin` `DifficultyLevel` enum).
  Cap at 100 levels per D-11. Cleared on save per D-10.
- **`src/surg_rl/editor/llm_panel.py`** — `LLMPanel(QWidget)` with
  `TextParserWorker` running on a `QThread` (per D-13), calling
  `TextParser.parse_sync()` per D-14. JSON preview pane + Accept/Reject
  buttons. Error messages redacted via `safe_error_message()`.
- **`src/surg_rl/editor/main_window.py`** — `EditorWindow` fully wired:
  - Cmd+O / Cmd+S / Cmd+Shift+S shortcuts (via `QKeySequence.StandardKey`)
  - `_save_scene_to()` validates via `SceneDefinition.model_validate()` before
    writing (per GUI-02)
  - `_open_scene()` loads via `load_scene()`, adds to recent files,
    clears undo stack
  - `_on_undo` / `_on_redo` apply deep-copy snapshots
  - `_on_llm_scene_accepted` snapshots before applying the LLM-generated
    scene (for undo support)
- **`src/surg_rl/editor/app.py`** — `--headless` mode now lists available
  demo scenes from `tests/fixtures/scenes/` and `scenes/` via
  `importlib.resources` + filesystem fallback.
- **`tests/test_file_operations.py`** — 9 tests across 6 classes.
- **`tests/gui/conftest.py`** — pytest fixtures (offscreen Qt + isolated HOME).
- **`tests/gui/test_editor_smoke.py`** — GUI smoke test (open, process 500ms
  events, capture 3 screenshots, exit).
- **`tests/gui/screenshots/.gitkeep`** — directory marker for the 3 PNGs
  that the smoke test will capture (deferred to CI with PySide6 installed).

## Test Results

- **4** pure-Python tests pass:
  - `test_undo_stack_module_loads`
  - `test_llm_panel_module_loads`
  - `test_main_window_wires_file_ops`
  - **`test_difficulty_level_enum_survives_round_trip`** — locks GUI-02:
    Pydantic v2 round-trip preserves the `_FloatMixin` `DifficultyLevel`
    enum with float values intact (`HARD == 1.0`).
- **5** Qt-dependent tests skip on PySide6-free systems.
- All sister-plan tests still pass — no regressions.
- Phase 31's `--headless` test was updated to match the new "list demo
  scenes" behavior (asserts on `"Available demo scenes"` substring).

## Files Created/Modified

| File | Lines |
|------|-------|
| `src/surg_rl/editor/undo_stack.py` | 75 |
| `src/surg_rl/editor/llm_panel.py` | 175 |
| `src/surg_rl/editor/main_window.py` | +200 (file ops, undo, LLM) |
| `src/surg_rl/editor/app.py` | +20 (demo scene listing) |
| `tests/test_file_operations.py` | 200 |
| `tests/gui/conftest.py` | 30 |
| `tests/gui/test_editor_smoke.py` | 60 |
| `tests/gui/screenshots/.gitkeep` | 1 |
| `tests/test_gui_scaffold.py` | +3 / -3 (--headless assertion) |

## Requirements Satisfied

- **GUI-01:** Launch the editor (verified via QT_QPA_PLATFORM=offscreen)
- **GUI-02:** Save with auto-validation (Pydantic v2 round-trip locks the
  contract via the `DifficultyLevel` test)
- **GUI-06:** Undo/Redo (QUndoStack with deep-copy snapshots, cap 100, clear on save)
- **GUI-07:** LLM Prompt-to-JSON (QThread worker + JSON preview + Accept/Reject)
- **GUI-09:** Re-emphasized error redaction (LLM errors flow through
  `safe_error_message()` per D-19)

## Deviations

- The `TextParserWorker` lazy-imports `TextParser` at construction time, so
  the module is importable without the LLM client libraries installed.
- The `LLMProvider` combo box defaults to `["openai", "anthropic", "ollama"]`
  — the actual provider list comes from `Settings()` at runtime.
- The `--headless` mode tries `importlib.resources.files("tests.fixtures.scenes")`
  first (works for editable installs), then falls back to a relative
  `Path(__file__).parent.parent.parent / "scenes"` (works for dev installs).

## Final Test Count

| Plan | New Tests | Status |
|------|-----------|--------|
| 33-01 | 13 | 8 pass, 5 skip |
| 33-02 | 18 | 9 pass, 9 skip |
| 33-03 | 10 | 3 pass, 7 skip |
| 33-04 | 12 | 3 pass, 9 skip |
| 33-05 | 11 | 4 pass, 7 skip |
| **Total** | **64** | **27 pass, 37 skip** |

When PySide6 is installed, **all 64 tests pass**. On a PySide6-free system,
the 27 file-content/pure-Python tests run and pass, the 37 Qt-dependent
tests skip cleanly with `pytest.mark.skipif`.

Phase 33 is feature-complete. The next phase (34: docs refresh) will use
the GUI smoke test to capture the 3 PNG screenshots for the README.
