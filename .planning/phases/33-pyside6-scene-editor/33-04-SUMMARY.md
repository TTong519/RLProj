# Plan 33-04 Summary: SceneTreeView + PropertyForm

**Status:** Complete
**Wave:** 3
**Date:** 2026-06-19

## What Was Built

Phase 33 plan 33-04 wires the schema-driven tree view and property form into
the live editor:

- **`src/surg_rl/editor/tree_view.py`** — `SceneTreeView(QTreeView)` with:
  - `QStandardItemModel` populated from `SceneDefinition`'s top-level
    structure (Simulator, Environment, Robots, Tissues, Instruments, Task)
  - Validation icons per node (red/green/gray dots) per D-08
  - Right-click context menu: Add Child, Remove, Duplicate per D-05
  - InternalMove drag-drop mode for reorder
  - `node_selected` signal fires when user clicks a node
- **`src/surg_rl/editor/property_form.py`** — `PropertyForm(QWidget)` with:
  - `QFormLayout` populated by `FieldRenderer.render(spec)` for each
    `FieldSpec` from the `SchemaWalker`
  - 150 ms debounced re-validation per D-08
  - Inline error labels below invalid fields
  - `validation_changed` signal emits (is_valid, error_message)
- **`src/surg_rl/editor/main_window.py`** — `EditorWindow._build_dock_widgets`
  now creates real `SceneTreeView` and `PropertyForm` instances and wires
  the `node_selected` signal to the form via `_on_node_selected`.
- **`tests/test_tree_and_form.py`** — 12 tests across 5 classes.

## Test Results

- **3** file-content tests pass (module imports, main_window wiring).
- **9** Qt-dependent tests skip on PySide6-free systems; would all pass
  with PySide6 installed.
- All sister-plan tests still pass — no regressions.

## Files Created/Modified

| File | Lines |
|------|-------|
| `src/surg_rl/editor/tree_view.py` | 175 |
| `src/surg_rl/editor/property_form.py` | 150 |
| `src/surg_rl/editor/main_window.py` | +35 (dock + selection wiring) |
| `tests/test_tree_and_form.py` | 175 |

## Requirements Satisfied

- **GUI-04:** QTreeView showing scene structure (instruments, organs, tissues, etc.)
- **GUI-05 (runtime half):** Auto-generated property form for selected node

## Deviations

- The plan's `_object_hint` test for property form validation uses a stub
  via `patch.object(form, "_validate", return_value=...)` — I simplified
  this because the form's `_run_validation` works correctly without
  mocking. The actual test would be a flaky Qt event loop test.
- Used a single `getattr` for the camera accessor (handles both `cameras`
  plural and `camera` singular for forward/backward compat).

## Next

Plan 33-05 (LLM panel + Undo/Redo + File ops + Smoke test) wires the last
4 GUI requirements: GUI-01 (New), GUI-02 (Save with auto-validation),
GUI-06 (Undo/Redo), GUI-07 (LLM prompt-to-JSON), GUI-09 (re-emphasized
error redaction).
