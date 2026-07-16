# Phase 41: Dock Layout Reset & CloseEvent Teardown - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix GUI bug #3 (dock-panel layout not reset on rerun) and add a `closeEvent` teardown harness so closing the editor mid-operation never crashes. This phase delivers **GUI-18** only:

- A `DockStateManager` that captures a factory-default dock layout and restores it on "Reset Layout" (including tabification/floating/closed state — which the current crude re-`addDockWidget` reset ignores).
- An `update_scene()` in-place-swap path on `ViewportPanel` and `SceneTreeView` so New/Open/undo/redo/LLM-accept stop destroying and recreating widgets (widget recreation is what resets dock geometry on rerun).
- A `closeEvent` teardown harness: every long-running panel gets a `stop()`, and `EditorWindow.closeEvent` tears them all down before `super().closeEvent()` — fixing the mid-LLM-call segfault / `RuntimeError: Internal C++ object already deleted`.
- A unique `objectName` on every dock so `saveState()`/`restoreState()` round-trip correctly.

**Out of scope (later phases):** render/sim decoupling + `SimStepWorker` + animated viewport (Phase 42 / GUI-11), multi-view (43), lighting (44), gizmos (45), recording (46), editing UX + multi-select (47), autosave + crash recovery + the duplicated `_refresh_recent_menu` fix (48 / GUI-17), scene generation (49–51). The `aboutToClose` teardown *contract* is established here so those phases' workers can plug in — but the workers themselves are not built here.

</domain>

<decisions>
## Implementation Decisions

### Reset Layout semantics

- **D-01:** Factory-default layout is captured **both** ways — a `QByteArray` snapshot taken once at the first `showEvent` (primary, always reflects the actual built layout even if code defaults drift) AND a code-level rebuild method that re-adds the docks in the factory arrangement as a fallback when the snapshot is missing/corrupt. `DockStateManager` (new `editor/dock_state.py`) owns both. The factory default is recomputed each launch from the built docks — it is NOT persisted to QSettings.
- **D-02:** "Reset Layout" is **one** action = restore the factory-default arrangement (discards the user's current customization). Matches roadmap SC#1 literally. The user's last-saved arrangement reappears only via close+reopen (SC#2). No separate "Restore Saved Layout" menu item in this phase.
- **D-03:** The user's saved dock layout is still restored in `__init__` via `_restore_geometry()` (docks are built before it is called). The bug is widget recreation in `_refresh_viewport_and_tree`, **not** restore timing — fix the recreation (D-06) and the existing restore path works. The Pitfall 2 "defer restoreState to showEvent" timing fix is NOT needed here; revisit only if dock-build ordering changes later.

### closeEvent teardown harness (milestone-wide contract)

- **D-04:** `aboutToClose` signal (registry pattern). `EditorWindow.closeEvent` emits `aboutToClose` BEFORE `super().closeEvent()`; every long-running panel registers its `stop()` as a slot on `aboutToClose` (wired in `__init__`, or via a small registry mixin that auto-wires any panel that declares a `stop()`). New panels in Phase 42 (`SimStepWorker`), 46 (recorder), 48 (autosave), and 51 (VLM) just declare `stop()` + connect to `aboutToClose` — no `closeEvent` edit needed. This is the milestone-wide teardown contract that prevents a repeat of bug #3's "forgot to stop this panel" class of crash.
- **D-05:** `stop()` semantics = set a cooperative cancel flag, call `thread.quit()`, then `thread.wait(3000)`. If `wait()` times out (hung parser), **log a warning and proceed with close anyway** — best-effort, NEVER block the user from quitting. No `thread.terminate()` (force-kill risks leaving SDK/parser state inconsistent). Applied to `LLMPanel` in this phase; the same shape is the template for every future worker's `stop()`.

### update_scene refactor depth

- **D-06:** **Minimal.** Add `update_scene(scene)` to `ViewportPanel` and `SceneTreeView` only — the two widgets `_refresh_viewport_and_tree()` currently recreates. `New`/`Open`/`LLM-accept` (and the now-safe `undo`/`redo` path) call `update_scene()` instead of recreating widgets, so dock geometry survives. `PropertyForm` is NOT folded into in-place update in this phase. `undo`/`redo` keep calling `_refresh_viewport_and_tree()` — now safe because it uses `update_scene()` and no longer recreates. A broader refactor (direct `update_scene()` on undo/redo, in-place `PropertyForm`) is deferred — revisit only if undo/redo flicker is reported.

### objectName enforcement + test approach

- **D-07:** Unique-`objectName` requirement (SC#4) is enforced via an **introspection pytest**: build `EditorWindow` offscreen, collect all `QDockWidget` children, assert each has a non-empty, unique `objectName`. Catches any future dock added without an `objectName`. No call-site guard helper in this phase.
- **D-08:** GUI-state tests run offscreen via `QT_QPA_PLATFORM=offscreen` `QApplication`. Dock round-trip (SC#1/#2): rearrange docks via the API, `save_window`, reload `EditorWindow`, assert `restoreState` restored the arrangement (tabification/floating/closed included).
- **D-09:** Close-mid-call clean-exit (SC#3) is verified **two** ways: (a) a real short provider call **gated behind `skipif` when no API key** (guards the true provider path when keys are present), AND (b) a **mock-slow-parser** test (`monkeypatch TextParser.parse_sync` to sleep) that **always** runs offscreen as the regression backstop, so SC#3 is guarded even without keys. Both assert a clean exit: no segfault, no `RuntimeError: Internal C++ object already deleted`, `thread.wait()` returned.

### Claude's Discretion

- Exact `objectName` strings for any new docks (follow the existing `dock_scene_tree` / `dock_properties` / `dock_llm` convention).
- `DockStateManager` internal shape and whether `aboutToClose` is a plain `Signal` on `EditorWindow` vs. a registry mixin — implementer's choice, so long as the D-04 contract holds.
- Test file naming/placement (follow the existing `tests/test_gui_scaffold.py` offscreen pattern).
- Status-bar wording on Reset Layout / close.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary & requirements
- `.planning/REQUIREMENTS.md` §GUI-18 — the requirement this phase delivers (the WHAT)
- `.planning/ROADMAP.md` (Phase 41 entry, lines 45–55) — phase goal, 4 success criteria, ordering, dependency note
- `.planning/PROJECT.md` §"Current Milestone: v0.7.0" + "Key context" — milestone context; the locked decision that bug #3 is a SEPARATE root cause (QMainWindow saveState/restoreState + widget recreation) from bugs #1/#2 (render/sim coupling)

### v0.7.0 research (the bug #3 root-cause analysis + pitfalls — HIGH confidence, directly observed in code)
- `.planning/research/SUMMARY.md` §"Bug Reconciliation — the three known GUI bugs" — bug #3 root cause in `EditorWindow`/`_refresh_viewport_and_tree`; the `DockStateManager` + `update_scene()` fix is owned by GUI-18
- `.planning/research/SUMMARY.md` §"Critical Pitfalls" #2 (dock-state restore silently no-ops) and #3 (QThread worker leak on close) — the two pitfalls this phase prevents
- `.planning/research/PITFALLS.md` — full 8-pitfall catalog; Pitfalls 2 and 3 are in scope here
- `.planning/research/STACK.md` / `ARCHITECTURE.md` — confirm no new deps (GUI-18 is pure code on existing PySide6)

### Prior phase context (the editor this phase fixes — inherited decisions)
- `.planning/phases/33-pyside6-scene-editor/33-CONTEXT.md` — D-17 (4-pane dock layout), D-18 (File menu + Reset Layout action), D-13 (LLM `QThread` worker pattern). These are the locked foundation Phase 41 modifies.

### Existing source modules (integration points — MUST read)
- `src/surg_rl/editor/main_window.py` — `EditorWindow`: `_build_dock_widgets` (objectNames already set), `_action_reset_layout` (the crude re-`addDockWidget` to replace per D-01/D-02), `_refresh_viewport_and_tree` (the widget-recreation to replace per D-06), `closeEvent` (the teardown to add per D-04/D-05), `_restore_geometry` (the existing restore path, kept per D-03)
- `src/surg_rl/editor/llm_panel.py` — `LLMPanel` + `TextParserWorker`: the `QThread`/`_worker` pattern (D-13); `_on_cancel` already sets `_cancelled` + `thread.quit()` — `stop()` (D-05) generalizes it and adds `wait(3000)`
- `src/surg_rl/editor/viewport.py` — `ViewportPanel`: `_tick`/`stop`; add `update_scene()` (D-06). NOTE: this file is mid-modification on `main` (uncommitted) — read the current state before editing
- `src/surg_rl/editor/tree_view.py` — `SceneTreeView`: add `update_scene()` (D-06)
- `src/surg_rl/editor/_settings.py` — `EditorSettings.save_window`/`load_window`: the existing QSettings persistence plumbing (geometry + `saveState()`); extend only if needed, do not rebuild
- `src/surg_rl/editor/undo_stack.py` — `SceneUndoStack`: undo/redo snapshot mechanism (unchanged this phase)
- `src/surg_rl/editor/_safe_error.py` — `safe_error_message()`: redactor for any error shown to the user

### Codebase maps (reusable patterns + conventions)
- `.planning/codebase/ARCHITECTURE.md` — editor subsystem overview
- `.planning/codebase/STACK.md` — `[gui]` extra + `LazyImport` + `HAS_GUI` sentinel
- `.planning/codebase/TESTING.md` — class-based test grouping; the offscreen-subprocess GUI test pattern Phase 31/33 established
- `.planning/codebase/CONVENTIONS.md` — naming/ABC conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`EditorSettings.save_window(geometry, state)` / `load_window()`** (`_settings.py`) — already persists window geometry + `saveState()` via platform-native QSettings and `_restore_geometry()` already calls `restoreState()`. The persistence *plumbing* exists; the bug is widget recreation + the crude reset action + the missing factory-default snapshot. Extend, don't rebuild.
- **`LLMPanel._thread` / `_worker` `QThread` pattern** (Phase 33 D-13) — the only long-running `QThread` in Phase 41. `_on_cancel` already sets a `_cancelled` property and calls `thread.quit()`; `stop()` (D-05) generalizes that and adds `thread.wait(3000)`.
- **`_safe_error.safe_error_message()`** — redactor applied to any error string before it reaches the user; reuse for any teardown-timeout warning surfaced to the status bar.
- **`SceneUndoStack`** (Phase 33-05) — undo/redo snapshot mechanism; unchanged this phase (undo/redo keep calling `_refresh_viewport_and_tree`, now safe per D-06).

### Established Patterns
- **`LazyImport` + `HAS_GUI` sentinel** (`editor/__init__.py`) — keep PySide6 import-optional; new `editor/dock_state.py` follows the same lazy-import discipline.
- **Console-script `surg-rl-gui` separate from the Typer CLI** — no `surg-rl gui` subcommand.
- **Offscreen GUI tests via `QT_QPA_PLATFORM=offscreen` + `PYTHONPATH=src`** — the Phase 31/33 `tests/test_gui_scaffold.py` pattern; Phase 41's dock/teardown tests follow it.
- **`objectName` convention** — `dock_scene_tree`, `dock_properties`, `dock_llm` already set on the three existing docks; any new dock follows `dock_<slug>`.

### Integration Points
- **`EditorWindow.closeEvent`** (`main_window.py:373`) — emit `aboutToClose` (D-04), then call `super().closeEvent()`. Currently only calls `self._viewport_panel.stop()` — the `LLMPanel` `QThread` is not stopped (the mid-LLM-call crash).
- **`EditorWindow._action_reset_layout`** (`main_window.py:256`) — replace the crude re-`addDockWidget` with `DockStateManager.reset_to_default()` → `restoreState(factory_default)` (D-01/D-02).
- **`EditorWindow._refresh_viewport_and_tree`** (`main_window.py:306`) — call `update_scene()` on viewport + tree instead of `new ViewportPanel(...)` / `setCentralWidget` / `setWidget` (D-06).
- **`EditorWindow.showEvent`** — capture the factory-default `QByteArray` at first show, guarded to run once (D-01).
- **`EditorWindow.__init__`** — register each long-running panel's `stop()` on `aboutToClose` (D-04).
- **`LLMPanel`** — add `stop()` (cooperative cancel + `thread.quit()` + `thread.wait(3000)`) (D-05).
- **`ViewportPanel` + `SceneTreeView`** — add `update_scene(scene)` (D-06).

</code_context>

<specifics>
## Specific Ideas

No specific user references or "I want it like X" moments — the user wants the bug fixed per the roadmap success criteria with the research-recommended approach, and made explicit implementation choices only on the four gray areas above. The two-state model (Reset = factory default; reopen = user's last-saved) and the `aboutToClose` registry contract are the two design anchors downstream agents should treat as locked.

</specifics>

<deferred>
## Deferred Ideas

- **"Restore Saved Layout" as a separate menu item** — considered (would let users recover their customization after a Reset without restarting); rejected for this phase to keep the menu minimal per SC#1. Could be a future UX nicety.
- **Code-level rebuild as the primary reset mechanism** — rejected (the first-show `QByteArray` snapshot is primary because it always reflects the actual built layout); kept only as the D-01 fallback.
- **`thread.terminate()` force-kill on `wait()` timeout** — rejected (risks leaving SDK/parser state inconsistent); D-05 logs and proceeds instead.
- **Folding `PropertyForm` into in-place update + direct `update_scene()` on undo/redo** — the broader `update_scene` refactor; rejected for this phase (minimal per D-06). Revisit only if undo/redo flicker is reported.
- **Duplicated `_refresh_recent_menu` block fix** — belongs to **Phase 48 (GUI-17)**, NOT Phase 41. The v0.7.0 research `SUMMARY.md`'s older draft mentioned folding it into the (then-combined) Phase 41, but the final `ROADMAP.md`/`REQUIREMENTS.md` assigns GUI-17 to Phase 48. Respect the ROADMAP boundary — do not fix it here.

</deferred>

---

*Phase: 41-dock-layout-reset-closeevent-teardown*
*Context gathered: 2026-07-15*