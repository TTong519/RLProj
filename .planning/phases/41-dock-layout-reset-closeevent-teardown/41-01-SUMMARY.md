---
phase: 41
plan: 01
subsystem: editor/dock-state
tags: [gui, dock-layout, bug-fix, tdd]
requires: [GUI-18]
provides: [DockStateManager, ViewportPanel.update_scene, SceneTreeView.update_scene]
affects: [src/surg_rl/editor/main_window.py, src/surg_rl/editor/viewport.py, src/surg_rl/editor/tree_view.py]
tech-stack:
  added: []
  patterns:
    - DockStateManager (factory-default QByteArray snapshot + code-level rebuild fallback)
    - in-place update_scene (no widget recreation — bug #3 root cause fix)
    - LazyImport discipline (Qt via surg_rl.editor proxies, not PySide6 directly)
key-files:
  created:
    - src/surg_rl/editor/dock_state.py
    - tests/test_dock_state.py
  modified:
    - src/surg_rl/editor/main_window.py
    - src/surg_rl/editor/viewport.py
    - src/surg_rl/editor/tree_view.py
decisions:
  - D-01 factory-default captured at first showEvent via QByteArray (primary) + code-level rebuild (fallback), NOT persisted to QSettings
  - D-02 Reset Layout = one action restoring factory default (restoreState primary, rebuild fallback)
  - D-03 _restore_geometry unchanged (the bug was widget recreation, not restore timing)
  - D-06 minimal update_scene on ViewportPanel + SceneTreeView only (PropertyForm NOT folded in)
  - D-07 unique objectName enforced via introspection pytest (TestDockObjectNames)
metrics:
  duration: 31m
  tasks: 3
  files: 5
  tests_added: 5
status: complete
---

# Phase 41 Plan 01: Dock Layout Reset + In-Place update_scene Summary

DockStateManager (factory-default QByteArray capture at first showEvent + restoreState-based Reset Layout) plus in-place update_scene() on ViewportPanel and SceneTreeView so New/Open/LLM-accept/undo/redo stop destroying and recreating widgets — closing bug #3 (dock panels not reset on rerun) and satisfying SC#1, SC#2, SC#4.

## What Was Built

### New: `src/surg_rl/editor/dock_state.py` — `DockStateManager`
- `capture_factory_default(window)`: guarded by a one-shot `_captured` bool (Pitfall 5 — `showEvent` can fire multiple times); captures `window.saveState()` once at first show.
- `reset_to_default(window) -> bool`: primary path `window.restoreState(factory QByteArray)` (restores tabification/floating/closed, not just area assignment); fallback `_rebuild_default_layout` re-adds docks to factory areas then re-captures (the D-01 fallback, NOT the primary).
- `_rebuild_default_layout(window)`: the ONLY place the crude pre-Phase-41 `addDockWidget` reset body is preserved — kept as the fallback, not the primary path.
- Qt imported via `from surg_rl.editor import QtCore, QtWidgets` (LazyImport proxies — NOT `from PySide6 import ...` at module top); factory default NOT persisted to QSettings (D-01).

### Modified: `src/surg_rl/editor/main_window.py`
- Added `from surg_rl.editor.dock_state import DockStateManager` import + `self._dock_state = DockStateManager()` in `__init__`.
- Replaced `_action_reset_layout` body (crude re-`addDockWidget`) with `self._dock_state.reset_to_default(self)` (D-02).
- Added `showEvent` override calling `self._dock_state.capture_factory_default(self)` then `super().showEvent(event)` (D-01; guard is inside the manager per Pitfall 5).
- Replaced `_refresh_viewport_and_tree` body (widget recreation: `new SceneTreeView`/`setWidget`/`new ViewportPanel`/`setCentralWidget`/`old_panel.stop()`) with in-place `self._tree_view.update_scene(...)` + `self._viewport_panel.update_scene(...)` (D-06). Removed the local `SceneTreeView`/`ViewportPanel` imports and the `node_selected` re-connect (the widget identity survives, so the `__init__` connection survives).
- `_restore_geometry` UNCHANGED (D-03 — the existing restore path is correct; the bug was widget recreation, not restore timing).
- `closeEvent` UNCHANGED (Plan 02 scope — no `aboutToClose` signal, no `closeEvent` extension).

### Modified: `src/surg_rl/editor/viewport.py` — `ViewportPanel.update_scene(scene)`
- Closes old simulator via the `stop()` `contextlib.suppress(AttributeError, OSError)` pattern (Pitfall 7).
- Sets `self._simulator = None` so `_tick` reloads via `_on_load_simulator` on the next tick.
- Swaps `self._scene`, calls `self.reset_camera()` (A3 — new scene = fresh view).
- `_running` stays True (render loop continues across the swap). NO `setCentralWidget`, NO new `ViewportPanel`.

### Modified: `src/surg_rl/editor/tree_view.py` — `SceneTreeView.update_scene(scene)`
- Swaps `self._scene`, `self._model.clear()` then re-sets horizontal header labels (`clear()` drops them).
- Re-runs `self._build_tree()` + `self.expandAll()`.
- Defensively re-wires `selectionModel().currentChanged.connect(self._on_selection_changed)` after `clear()` (A2 — `clear()` can reset the selection model on some Qt versions; the `customContextMenuRequested`/`node_selected` wiring on `self` is preserved). Added `contextlib` import.
- NO `setWidget`, NO new `SceneTreeView`.

### New: `tests/test_dock_state.py` — 5 tests (offscreen harness + 3 classes)
- Offscreen harness: module-top `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`, `_HAVE_PYSIDE6` try/except guard, module-level `pytestmark = pytest.mark.skipif(...)`, session-scoped `qapp` fixture, `isolated_home` fixture (`monkeypatch.setenv("HOME"...)` + `XDG_CONFIG_HOME` — mandatory so QSettings does not pollute the developer's real `~/Library/Preferences/com.SurgRL.SceneEditor.plist`).
- `TestDockObjectNames` (SC#4): `test_every_dock_has_unique_nonempty_objectname` — passes against the current 3 docks (`dock_scene_tree`/`dock_properties`/`dock_llm`); regression guard for future phases.
- `TestDockRoundTrip` (SC#1/#2): `test_reset_layout_restores_factory_default` (tabify → reset → `saveState() == factory`); `test_rearrange_close_reopen` (tabify → refresh → close → reopen → tabification restored via `tabifiedDockWidgets` structural assertion).
- `TestUpdateScene` (SC#2): `test_update_scene_does_not_recreate_viewport` + `test_update_scene_does_not_recreate_tree` — assert `id(w._viewport_panel)`/`id(w._tree_view)` unchanged across `_refresh_viewport_and_tree()` (the strict bug #3 regression guard — fails with the old widget-recreation code, passes with in-place swap).

## Task Breakdown

| Task | Type | tdd | Commit | Description |
|------|------|-----|--------|-------------|
| 1 | auto | false | `00e9610` | RED test scaffold (TestDockObjectNames passes; TestDockRoundTrip ImportError baseline) |
| 2 | auto | true | `ad1393f` | GREEN: DockStateManager + showEvent capture + reset_to_default wiring (SC#1, SC#4) |
| 3 | auto | true | `51df24d` | GREEN: ViewportPanel/SceneTreeView update_scene + rewired _refresh_viewport_and_tree + TestUpdateScene (SC#2) |

## Verification

- `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py -v` → 5 passed (TestDockObjectNames, TestDockRoundTrip x2, TestUpdateScene x2).
- `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_viewport.py tests/test_dock_state.py tests/gui/ -v` → 41 passed (no regression in the existing GUI tests).
- `PYTHONPATH=src pytest tests/` → exit 0 (full suite green — no regression in the 1,513-test baseline).
- `ruff check src/surg_rl/editor/dock_state.py src/surg_rl/editor/main_window.py src/surg_rl/editor/viewport.py src/surg_rl/editor/tree_view.py tests/test_dock_state.py` → All checks passed.
- `mypy src/surg_rl/editor` → 69 errors, all pre-existing LazyImport-proxy `Name not defined` patterns (the existing `QtGui.QCloseEvent`/`QtWidgets.QDockWidget`/etc. are the same class); Task 3 introduced 0 new errors (verified via `git stash` baseline comparison: 69 before and after Task 3). The editor module was never mypy-clean due to the LazyImport design — this is consistent with the existing baseline and out of scope for this plan.

## Success Criteria

- **SC#1** (Reset Layout restores factory-default arrangement incl. tabification/floating/closed): `TestDockRoundTrip::test_reset_layout_restores_factory_default` green — `saveState() == factory` after `_action_reset_layout()`.
- **SC#2** (rearrange → load scene → close → reopen restores saved layout): `TestDockRoundTrip::test_rearrange_close_reopen` green (tabification survives close+reopen) + `TestUpdateScene` green (`id` unchanged across `_refresh_viewport_and_tree` — no widget recreation).
- **SC#4** (every dock has a non-empty unique objectName): `TestDockObjectNames` green.
- Full suite green (1,513-test baseline + 5 new phase tests).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_rearrange_close_reopen` used byte-identical `saveState()` comparison**
- **Found during:** Task 2 verification
- **Issue:** The plan's test description suggested asserting `restoreState` restored the rearranged arrangement by comparing `saveState()` bytes across two different `EditorWindow` instances. Pixel geometry/splitter sizes legitimately differ across window instances even when the dock relationship (tabification) is correctly restored, so the byte comparison failed despite the structural arrangement being preserved.
- **Fix:** Switched to a structural assertion — `w2._properties_dock in w2.tabifiedDockWidgets(w2._tree_dock)` — which verifies the dock relationship that `saveState`/`restoreState` keys on via `objectName` (the actual SC#2 intent: "the tabified dock is still tabified"). Added a precondition assertion that the tabification exists after `tabifyDockWidget`.
- **Files modified:** `tests/test_dock_state.py`
- **Commit:** `ad1393f`

### Decisions Made

- **`test_rearrange_close_reopen` assertion shape:** structural (tabification) rather than byte-identical `saveState`, because pixel geometry is not part of the dock-relationship contract SC#2 targets. The byte-identical comparison is retained in `test_reset_layout_restores_factory_default` (same window before/after reset — byte-stable there).
- **`SceneTreeView.update_scene` defensive `selectionModel` re-wire:** the plan flagged A2 as "verify in implementation; if `clear()` resets selectionModel, re-wire." The re-wire is guarded with `contextlib.suppress(RuntimeError, TypeError)` and only connects if `selectionModel()` returns a non-None model — a defensive no-op when the connection already survives, a correct re-wire when `clear()` resets it.

## Known Stubs

None — all code paths are fully wired. `update_scene` swaps real `SceneDefinition` instances; `DockStateManager` captures/restores real `QByteArray` snapshots; no placeholder/TODO/FIXME markers in the new/modified files.

## Threat Flags

None — this plan touches only local Qt-client dock geometry + in-place widget state swap. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The threat model in the plan (T-41-01, T-41-02, T-41-SC) all dispositioned `accept` with no new user-facing error strings or QSettings keys introduced.

## TDD Gate Compliance

Plan 01 is `type: execute` (not `type: tdd` at the plan level), but Tasks 2 and 3 carry `tdd="true"`. The RED/GREEN gate sequence is satisfied:
1. **RED gate** (`00e9610`): `test(...)` commit — the TestDockRoundTrip tests fail with `ModuleNotFoundError: No module named 'surg_rl.editor.dock_state'` (honest RED baseline; no `pytest.skip`/`xfail`). `TestDockObjectNames` passes immediately (regression guard for already-correct behavior).
2. **GREEN gate** (`ad1393f` + `51df24d`): `feat(...)` commits — `DockStateManager` + `showEvent` + `update_scene` drive all 5 phase tests green.

## Self-Check: PASSED

- `tests/test_dock_state.py` — FOUND
- `src/surg_rl/editor/dock_state.py` — FOUND
- `src/surg_rl/editor/main_window.py` (modified) — FOUND
- `src/surg_rl/editor/viewport.py` (modified) — FOUND
- `src/surg_rl/editor/tree_view.py` (modified) — FOUND
- Commit `00e9610` (test RED) — FOUND
- Commit `ad1393f` (feat GREEN Task 2) — FOUND
- Commit `51df24d` (feat GREEN Task 3) — FOUND