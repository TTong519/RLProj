---
phase: 41-dock-layout-reset-closeevent-teardown
verified: 2026-07-15T00:00:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 41: Dock Layout Reset & CloseEvent Teardown Verification Report

**Phase Goal:** User can reset the editor layout to default (dock panels restore on rerun) and closing the editor mid-operation does not crash — fixes bug #3 (dock panels not reset on rerun).
**Verified:** 2026-07-15
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC#1 — User clicks "Reset Layout" and dock panels restore to the factory-default arrangement (tabification/floating/closed state included) — bug #3 closed | VERIFIED | `dock_state.py` DockStateManager: `capture_factory_default` (one-shot `_captured` guard, Pitfall 5) + `reset_to_default` (primary `window.restoreState(factory QByteArray)` + fallback `_rebuild_default_layout`). `main_window.py:271-272` `_action_reset_layout` delegates to `self._dock_state.reset_to_default(self)` (no direct `addDockWidget`). `main_window.py:379-385` `showEvent` captures factory default at first show. Behavioral: `TestDockRoundTrip::test_reset_layout_restores_factory_default` PASSED — asserts `after.data() == factory.data()` after tabify+reset. |
| 2 | SC#2 — User rearranges docks, closes the editor, reopens it — the saved layout restores on rerun (not a broken state); widget-recreation root cause fixed | VERIFIED | `main_window.py:316-325` `_refresh_viewport_and_tree` body = `self._tree_view.update_scene(...)` + `self._viewport_panel.update_scene(...)` — NO `setCentralWidget`, NO `setWidget`, NO new widget construction. `viewport.py:399-415` `update_scene` closes old simulator (`contextlib.suppress`), sets `_simulator=None`, swaps `_scene`, calls `reset_camera()`. `tree_view.py:99-120` `update_scene` clears model, re-sets headers, re-runs `_build_tree`, `expandAll`, defensively re-wires `selectionModel`. `_restore_geometry` L370-377 UNCHANGED (D-03 honored). Behavioral: `TestDockRoundTrip::test_rearrange_close_reopen` PASSED (tabification survives close+reopen) + `TestUpdateScene` x2 PASSED (`id()` unchanged across refresh — no widget recreation). |
| 3 | SC#3 — User closes the editor mid-LLM-call — editor exits cleanly without segfault or `RuntimeError: Internal C++ object already deleted` | VERIFIED | `llm_panel.py:130-158` `LLMPanel.stop()`: sets `_worker.setProperty("_cancelled", True)`, calls `_thread.quit()`, `_thread.wait(3000)`, logs `logger.warning` on timeout. NO `thread.terminate()`, NO `thread.deleteLater()` in stop() body (only docstring mentions — the existing `thread.finished.connect(self._thread.deleteLater)` at L125 is correctly preserved). `main_window.py:59` `aboutToClose = QtCore.Signal()` at class-body top. `main_window.py:132` `self.aboutToClose.connect(self._llm_panel.stop)` (D-04 wiring). `main_window.py:387-404` `closeEvent` emits `aboutToClose` (broad try/except) BEFORE `_viewport_panel.stop()` + `save_window` + `super().closeEvent(event)` (emit on L393, super on L404 — order confirmed). `_on_cancel` L160-164 delegates to `stop()`. Behavioral: `TestCloseMidCallMockSlow` PASSED (real in-flight thread + stop() → thread exits cleanly; D-09b always-on backstop) + `TestAboutToClose` PASSED (closeEvent → aboutToClose → stop wiring via Mock; D-04 guard). The two tests compose: closeEvent emits aboutToClose (TestAboutToClose) → aboutToClose wired to stop() (L132) → stop() exits thread cleanly (TestCloseMidCallMockSlow). |
| 4 | SC#4 — Every dock panel has a unique `objectName` so `saveState()`/`restoreState()` round-trip correctly | VERIFIED | `main_window.py:113` `dock_scene_tree`, L118 `dock_properties`, L123 `dock_llm` — all non-empty, unique. Behavioral: `TestDockObjectNames::test_every_dock_has_unique_nonempty_objectname` PASSED (collects `findChildren(QDockWidget)`, asserts `all(names)` + `len(names) == len(set(names))`). |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/surg_rl/editor/dock_state.py` | DockStateManager with capture-once guard, restoreState primary, rebuild fallback | VERIFIED | 99 lines. `class DockStateManager` with `capture_factory_default` (guarded by `_captured` bool), `reset_to_default -> bool` (primary `restoreState`, fallback `_rebuild_default_layout`), `_rebuild_default_layout`. Qt via LazyImport proxies (`from surg_rl.editor import QtCore, QtWidgets` — NOT `from PySide6`). No QSettings persistence of factory state (D-01). |
| `src/surg_rl/editor/viewport.py` | `ViewportPanel.update_scene(scene)` — closes old simulator, sets `_simulator=None`, swaps scene, resets camera; no setCentralWidget | VERIFIED | L399-415 `update_scene`. `contextlib.suppress(AttributeError, OSError)` simulator close, `self._simulator = None`, `self._scene = scene`, `self.reset_camera()`. No `setCentralWidget`, no new `ViewportPanel`. |
| `src/surg_rl/editor/tree_view.py` | `SceneTreeView.update_scene(scene)` — clear+rebuild, re-set headers, expandAll, re-wire selectionModel | VERIFIED | L99-120 `update_scene`. `self._model.clear()`, re-sets `setHorizontalHeaderLabels`, `_build_tree()`, `expandAll()`, defensive `selectionModel().currentChanged.connect` via `contextlib.suppress(RuntimeError, TypeError)`. No `setWidget`, no new `SceneTreeView`. |
| `src/surg_rl/editor/main_window.py` | `_action_reset_layout` delegates to `reset_to_default`; `showEvent` captures factory; `_refresh_viewport_and_tree` calls update_scene; `aboutToClose` signal + closeEvent emit before super; `__init__`/`_build_dock_widgets` wiring | VERIFIED | L271-272 reset layout delegates. L379-385 showEvent capture. L316-325 refresh = update_scene calls (no widget recreation). L59 `aboutToClose = QtCore.Signal()` (noqa: N815). L132 `aboutToClose.connect(self._llm_panel.stop)`. L387-404 closeEvent emits before super. L66 `self._dock_state = DockStateManager()` in `__init__`. |
| `src/surg_rl/editor/llm_panel.py` | `LLMPanel.stop()` cooperative cancel + quit + wait(3000) + timeout log; NO terminate/deleteLater; `_on_cancel` delegates; module logger | VERIFIED | L130-158 `stop()`. L14 `logger = get_logger(__name__)`. L145-149 cancel flag via `setProperty("_cancelled", True)`. L150-156 `thread.quit()` + `thread.wait(3000)` + `logger.warning` on timeout. L160-164 `_on_cancel` delegates to `stop()`. No `terminate()`, no `deleteLater()` in stop() executable body. |
| `tests/test_dock_state.py` | Offscreen harness + TestDockObjectNames + TestDockRoundTrip + TestUpdateScene + TestCloseMidCallMockSlow + TestCloseMidCallRealProvider + TestAboutToClose | VERIFIED | 338 lines. Module-top `QT_QPA_PLATFORM=offscreen` + `_HAVE_PYSIDE6` guard + `pytestmark` + session-scoped `qapp` + `isolated_home` fixture (HOME + XDG_CONFIG_HOME redirect). All 7 test classes present. 7 passed, 1 skipped (TestCloseMidCallRealProvider — expected per D-09a, no LLM_API_KEY). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `EditorWindow._action_reset_layout` | `DockStateManager.reset_to_default` | `self._dock_state.reset_to_default(self)` (D-02) | WIRED | main_window.py:271-272 |
| `EditorWindow.showEvent` (first show) | `DockStateManager.capture_factory_default` | `self._dock_state.capture_factory_default(self)` (D-01, guarded) | WIRED | main_window.py:384 |
| `EditorWindow._refresh_viewport_and_tree` | `ViewportPanel.update_scene` + `SceneTreeView.update_scene` | `self._tree_view.update_scene(...)` + `self._viewport_panel.update_scene(...)` (D-06) | WIRED | main_window.py:324-325 |
| `DockStateManager._factory_state` | `QMainWindow.saveState()` QByteArray | captured once at first showEvent (D-01) | WIRED | dock_state.py:49 |
| `EditorWindow.closeEvent` | `LLMPanel.stop()` | `aboutToClose.emit()` → `self._llm_panel.stop` slot (D-04/D-05) | WIRED | main_window.py:393 emit + L132 connect |
| `EditorWindow.__init__`/`_build_dock_widgets` | `aboutToClose.connect(self._llm_panel.stop)` | after `_llm_panel` construction (D-04) | WIRED | main_window.py:132 |
| `LLMPanel.stop()` | `worker.setProperty('_cancelled', True)` + `thread.quit()` + `thread.wait(3000)` | cooperative teardown (D-05) | WIRED | llm_panel.py:145-156 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `dock_state.py` `_factory_state` | `QByteArray` | `window.saveState()` | Yes — real Qt dock arrangement snapshot | FLOWING |
| `viewport.py` `update_scene` | `_scene` | caller `_refresh_viewport_and_tree` passes `self._scene or _empty_scene_stub()` | Yes — real `SceneDefinition` (or valid empty stub) | FLOWING |
| `tree_view.py` `update_scene` | `_scene` | caller `_refresh_viewport_and_tree` | Yes — real `SceneDefinition` | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase SC#1-4 tests | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen venv/bin/pytest tests/test_dock_state.py -v` | 7 passed, 1 skipped (TestCloseMidCallRealProvider — no LLM_API_KEY, expected per D-09a; D-09b mock backstop covers SC#3) | PASS |
| SC#1 reset restores factory byte-identical | TestDockRoundTrip::test_reset_layout_restores_factory_default | PASSED — `after.data() == factory.data()` | PASS |
| SC#2 tabification survives close+reopen | TestDockRoundTrip::test_rearrange_close_reopen | PASSED — `_properties_dock in tabifiedDockWidgets(_tree_dock)` | PASS |
| SC#2 no widget recreation (id stable) | TestUpdateScene x2 | PASSED — `id(w._viewport_panel)`/`id(w._tree_view)` unchanged | PASS |
| SC#3 mid-LLM-call clean exit (mock backstop) | TestCloseMidCallMockSlow | PASSED — `not thread.isRunning()` after stop() | PASS |
| SC#3 real-provider path | TestCloseMidCallRealProvider | SKIPPED — no LLM_API_KEY (D-09a gated; mock backstop covers SC#3) | SKIP (expected) |
| D-04 closeEvent → aboutToClose → stop wiring | TestAboutToClose | PASSED — `mock_llm_stop.call_count >= 1` | PASS |
| SC#4 unique objectName | TestDockObjectNames | PASSED — `all(names)` + `len(names) == len(set(names))` | PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| (none) | — | — | SKIPPED — phase has no probe scripts; verification is via pytest GUI tests (offscreen Qt harness) per VALIDATION.md |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GUI-18 | 41-01, 41-02 | User can reset the editor layout to default (dock panels restore on rerun), and closing the editor mid-operation does not crash — fixes bug #3 via DockStateManager + closeEvent teardown harness | SATISFIED | SC#1 (Plan 01), SC#2 (Plan 01), SC#3 (Plan 02), SC#4 (Plan 01) all verified above. REQUIREMENTS.md L31 marked `[x]` complete. Traceability table L70 maps GUI-18 → Phase 41. |

No orphaned requirements — GUI-18 is the only requirement assigned to Phase 41 and it is fully covered by the two plans.

### Locked Decisions D-01..D-09 (Context) — Honor Check

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01 factory-default captured at first showEvent (QByteArray primary + code-level rebuild fallback), NOT persisted to QSettings | HONORED | `dock_state.py` capture+rebuild; no QSettings calls; `_factory_state` is in-memory only |
| D-02 Reset Layout = one action restoring factory default | HONORED | `_action_reset_layout` body = single `reset_to_default` call |
| D-03 `_restore_geometry` unchanged (bug was widget recreation, not restore timing) | HONORED | main_window.py:370-377 unchanged — still `load_window()` + `restoreState` |
| D-04 aboutToClose signal, closeEvent emits before super, panels register stop() in __init__ | HONORED | main_window.py:59 signal, L132 connect, L393 emit before L404 super |
| D-05 stop() = cancel flag + thread.quit() + thread.wait(3000); log and proceed on timeout; no terminate | HONORED | llm_panel.py:145-156; no `terminate()` in stop() body |
| D-06 minimal update_scene on ViewportPanel + SceneTreeView only (PropertyForm NOT folded in) | HONORED | update_scene added to viewport.py + tree_view.py only; PropertyForm untouched |
| D-07 unique objectName enforced via introspection pytest | HONORED | TestDockObjectNames passes |
| D-08 offscreen GUI tests via QT_QPA_PLATFORM=offscreen | HONORED | test_dock_state.py module-top `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` |
| D-09 two-pronged SC#3 verification (mock-slow always-on + real-provider skipif) | HONORED | TestCloseMidCallMockSlow (always-on, PASSED) + TestCloseMidCallRealProvider (skipif, SKIPPED without key) |

### Prohibitions — Respect Check

| Prohibition | Status | Evidence |
|-------------|--------|----------|
| Must NOT persist factory-default QByteArray to QSettings | RESPECTED | `dock_state.py` makes zero QSettings calls; `_factory_state` is in-memory only |
| Must NOT recreate ViewportPanel/SceneTreeView in `_refresh_viewport_and_tree` | RESPECTED | main_window.py:316-325 body calls only `update_scene()`; grep for `setCentralWidget|setWidget|ViewportPanel(|SceneTreeView(` in that method body returns 0 |
| Must NOT capture factory-default on every showEvent (Pitfall 5 — one-shot guard) | RESPECTED | `dock_state.py:47` `if self._captured: return` — idempotent |
| Must NOT block quit on wait() timeout (D-05) | RESPECTED | llm_panel.py:152-156 logs warning and proceeds; no raise, no loop |
| Must NOT call thread.terminate() (D-05) | RESPECTED | grep `terminate(` in stop() executable body returns 0 (only docstring mentions) |
| Must NOT call thread.deleteLater() synchronously in stop() (Pitfall 4) | RESPECTED | only `deleteLater` in file is L125 `self._thread.finished.connect(self._thread.deleteLater)` (pre-existing correct wiring, excluded by grep) |
| aboutToClose emitted BEFORE super().closeEvent() | RESPECTED | main_window.py:393 emit < L404 super (line order confirmed) |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/surg_rl/editor/main_window.py` | 23 | `_PLACEHOLDER_TEXT` constant (pre-existing Phase 33 stub leftover) | Info | None — pre-existing, not introduced by Phase 41; `_build_central_viewport` (L98-100) is a dead `pass` method already replaced by `ViewportPanel` in `__init__`. Out of scope for this phase. |
| `src/surg_rl/editor/main_window.py` | 358-368 | `_refresh_recent_menu` body duplicated (clear+add block run twice) | Info | None — this is the "duplicated `_refresh_recent_menu` latent bug" explicitly deferred to Phase 48 / GUI-17 per 41-CONTEXT.md `<deferred>`. Out of scope for Phase 41. |

No `TBD`/`FIXME`/`XXX` markers in any Phase 41-modified file. No placeholder returns in new code. No hardcoded empty data flowing to rendering.

### Human Verification Required

None — VALIDATION.md "Manual-Only Verifications" table is explicitly empty ("All phase behaviors have automated verification"). All four SCs are covered by always-running offscreen pytest tests:

- SC#1: TestDockRoundTrip::test_reset_layout_restores_factory_default (PASSED)
- SC#2: TestDockRoundTrip::test_rearrange_close_reopen + TestUpdateScene x2 (PASSED)
- SC#3: TestCloseMidCallMockSlow (always-on D-09b backstop, PASSED) + TestAboutToClose (D-04 wiring guard, PASSED). The D-09a real-provider test (TestCloseMidCallRealProvider) is intentionally skipif-gated behind LLM_API_KEY — its skip is expected behavior, not a gap; the mock-slow backstop covers SC#3 unconditionally per D-09 design.
- SC#4: TestDockObjectNames (PASSED)

### Gaps Summary

No gaps found. All four success criteria are verified against the actual codebase (implementation files read in full + behavioral test run: 7 passed, 1 expected skip). All six artifacts exist, are substantive, and are wired. All seven key links are wired. All nine locked decisions (D-01..D-09) are honored. All seven prohibitions are respected. GUI-18 is satisfied and marked complete in REQUIREMENTS.md.

The two informational items (`_PLACEHOLDER_TEXT` and the duplicated `_refresh_recent_menu`) are both pre-existing and explicitly out of scope for Phase 41 — the latter is documented as deferred to Phase 48 / GUI-17 in 41-CONTEXT.md.

---

_Verified: 2026-07-15_
_Verifier: Claude (gsd-verifier)_