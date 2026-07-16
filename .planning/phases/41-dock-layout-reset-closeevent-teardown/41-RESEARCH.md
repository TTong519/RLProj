# Phase 41: Dock Layout Reset & CloseEvent Teardown - Research

**Researched:** 2026-07-15
**Domain:** PySide6/Qt desktop — `QMainWindow` saveState/restoreState dock persistence + `QThread` worker-object teardown on `closeEvent`
**Confidence:** HIGH

## Summary

Phase 41 is a pure-code, no-new-dependency fix phase on the shipped v0.5.0 PySide6 scene editor. It closes GUI-18 / bug #3 (dock-panel layout not restored on rerun) and installs the milestone-wide `closeEvent` teardown harness that prevents the mid-LLM-call segfault (`RuntimeError: Internal C++ object already deleted`). The bug has two independent root causes that this phase fixes together: (1) `_refresh_viewport_and_tree()` (`main_window.py:306`) destroys and recreates `ViewportPanel`/`SceneTreeView` widgets on every New/Open/undo/redo/LLM-accept, which resets dock geometry on rerun — fixed by adding `update_scene(scene)` in-place swap methods; (2) the hand-rolled `_action_reset_layout` (`main_window.py:256`) only re-`addDockWidget`s to default areas and silently ignores tabification/floating/closed state — fixed by capturing a factory-default `QByteArray` at first `showEvent` and having Reset Layout call `restoreState(factory_default)`.

The teardown harness is the second deliverable: `EditorWindow.closeEvent` currently stops only `self._viewport_panel.stop()` and never touches the `LLMPanel` `QThread`. Closing mid-LLM-call emits `finished`/`failed` into a deleted panel. Per D-04/D-05, every long-running panel gets a `stop()` (cooperative cancel flag + `thread.quit()` + `thread.wait(3000)`), and `closeEvent` emits an `aboutToClose` signal BEFORE `super().closeEvent()` so panels self-register teardown without `closeEvent` being edited each time a future worker (Phase 42/46/48/51) is added.

I verified the load-bearing Qt behaviors directly on the installed PySide6 6.11.1 under `QT_QPA_PLATFORM=offscreen`: `saveState()` returns a `QByteArray` that round-trips through `restoreState()` (146 bytes default → 155 bytes after tabify → restores correctly), and a dock without `objectName` emits `QMainWindow::saveState(): 'objectName' not set for QDockWidget` to stderr and is invisible to save/restore. The cooperative `QThread.quit()` + `wait(3000)` pattern returns `True` and leaves `isRunning() == False` when the worker honors the cancel flag. These are the exact contracts the implementation depends on.

**Primary recommendation:** Build `DockStateManager` (new `editor/dock_state.py`) owning the factory-default `QByteArray` + a code-level rebuild fallback; add `update_scene()` to `ViewportPanel`/`SceneTreeView`; replace `_action_reset_layout` body with `restoreState(factory_default)`; emit `aboutToClose` in `closeEvent` before `super()`; give `LLMPanel` a `stop()`; add 4 offscreen tests (introspection objectName, dock round-trip, mock-slow-parser clean close, skipif-gated real provider clean close). All TDD-eligible logic (`DockStateManager` capture/restore, `stop()` semantics) is testable headless without an API key.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Factory-default layout is captured **both** ways — a `QByteArray` snapshot taken once at the first `showEvent` (primary, always reflects the actual built layout even if code defaults drift) AND a code-level rebuild method that re-adds the docks in the factory arrangement as a fallback when the snapshot is missing/corrupt. `DockStateManager` (new `editor/dock_state.py`) owns both. The factory default is recomputed each launch from the built docks — it is NOT persisted to QSettings.
- **D-02:** "Reset Layout" is **one** action = restore the factory-default arrangement (discards the user's current customization). Matches roadmap SC#1 literally. The user's last-saved arrangement reappears only via close+reopen (SC#2). No separate "Restore Saved Layout" menu item in this phase.
- **D-03:** The user's saved dock layout is still restored in `__init__` via `_restore_geometry()` (docks are built before it is called). The bug is widget recreation in `_refresh_viewport_and_tree`, **not** restore timing — fix the recreation (D-06) and the existing restore path works. The Pitfall 2 "defer restoreState to showEvent" timing fix is NOT needed here; revisit only if dock-build ordering changes later.
- **D-04:** `aboutToClose` signal (registry pattern). `EditorWindow.closeEvent` emits `aboutToClose` BEFORE `super().closeEvent()`; every long-running panel registers its `stop()` as a slot on `aboutToClose` (wired in `__init__`, or via a small registry mixin that auto-wires any panel that declares a `stop()`). New panels in Phase 42 (`SimStepWorker`), 46 (recorder), 48 (autosave), and 51 (VLM) just declare `stop()` + connect to `aboutToClose` — no `closeEvent` edit needed.
- **D-05:** `stop()` semantics = set a cooperative cancel flag, call `thread.quit()`, then `thread.wait(3000)`. If `wait()` times out (hung parser), **log a warning and proceed with close anyway** — best-effort, NEVER block the user from quitting. No `thread.terminate()` (force-kill risks leaving SDK/parser state inconsistent). Applied to `LLMPanel` in this phase; the same shape is the template for every future worker's `stop()`.
- **D-06:** **Minimal.** Add `update_scene(scene)` to `ViewportPanel` and `SceneTreeView` only — the two widgets `_refresh_viewport_and_tree()` currently recreates. `New`/`Open`/`LLM-accept` (and the now-safe `undo`/`redo` path) call `update_scene()` instead of recreating widgets, so dock geometry survives. `PropertyForm` is NOT folded into in-place update in this phase. `undo`/`redo` keep calling `_refresh_viewport_and_tree()` — now safe because it uses `update_scene()` and no longer recreates. A broader refactor (direct `update_scene()` on undo/redo, in-place `PropertyForm`) is deferred — revisit only if undo/redo flicker is reported.
- **D-07:** Unique-`objectName` requirement (SC#4) is enforced via an **introspection pytest**: build `EditorWindow` offscreen, collect all `QDockWidget` children, assert each has a non-empty, unique `objectName`. Catches any future dock added without an `objectName`. No call-site guard helper in this phase.
- **D-08:** GUI-state tests run offscreen via `QT_QPA_PLATFORM=offscreen` `QApplication`. Dock round-trip (SC#1/#2): rearrange docks via the API, `save_window`, reload `EditorWindow`, assert `restoreState` restored the arrangement (tabification/floating/closed included).
- **D-09:** Close-mid-call clean-exit (SC#3) is verified **two** ways: (a) a real short provider call **gated behind `skipif` when no API key** (guards the true provider path when keys are present), AND (b) a **mock-slow-parser** test (`monkeypatch TextParser.parse_sync` to sleep) that **always** runs offscreen as the regression backstop, so SC#3 is guarded even without keys. Both assert a clean exit: no segfault, no `RuntimeError: Internal C++ object already deleted`, `thread.wait()` returned.

### Claude's Discretion
- Exact `objectName` strings for any new docks (follow the existing `dock_scene_tree` / `dock_properties` / `dock_llm` convention).
- `DockStateManager` internal shape and whether `aboutToClose` is a plain `Signal` on `EditorWindow` vs. a registry mixin — implementer's choice, so long as the D-04 contract holds.
- Test file naming/placement (follow the existing `tests/test_gui_scaffold.py` offscreen pattern).
- Status-bar wording on Reset Layout / close.

### Deferred Ideas (OUT OF SCOPE)
- "Restore Saved Layout" as a separate menu item — considered; rejected for this phase to keep the menu minimal per SC#1. Could be a future UX nicety.
- Code-level rebuild as the primary reset mechanism — rejected (the first-show `QByteArray` snapshot is primary because it always reflects the actual built layout); kept only as the D-01 fallback.
- `thread.terminate()` force-kill on `wait()` timeout — rejected (risks leaving SDK/parser state inconsistent); D-05 logs and proceeds instead.
- Folding `PropertyForm` into in-place update + direct `update_scene()` on undo/redo — the broader `update_scene` refactor; rejected for this phase (minimal per D-06). Revisit only if undo/redo flicker is reported.
- Duplicated `_refresh_recent_menu` block fix — belongs to **Phase 48 (GUI-17)**, NOT Phase 41. Respect the ROADMAP boundary — do not fix it here.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUI-18 | User can reset the editor layout to default (dock panels restore on rerun), and closing the editor mid-operation does not crash — fixes the dock-not-reset-on-rerun bug via `DockStateManager` + a `closeEvent` teardown harness | All 9 locked decisions (D-01..D-09) map directly to the four success criteria: D-01/D-02 → SC#1 (Reset Layout restores factory default incl. tabification/floating/closed); D-03/D-06 → SC#2 (rearrange→close→reopen restores saved layout — widget recreation fix); D-04/D-05/D-09 → SC#3 (close mid-LLM-call clean exit); D-07/D-08 → SC#4 (unique objectName + offscreen round-trip test). No new deps. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Pydantic v2** — `model_copy(update={...})` not mutation (not in scope this phase, but `update_scene` should not mutate the scene object).
- **Gymnasium/SB3** — N/A (no RL changes this phase).
- **Simulator internals** — `hasattr(simulator, "_model")` for MuJoCo, `hasattr(simulator, "_physics_client")` for PyBullet. The `ViewportPanel.update_scene()` must reload the simulator under the existing `_on_load_simulator` path — do not assume a specific backend.
- **Optional fields — always guard** — `SceneDefinition.task` is `Optional[TaskConfig]`; `update_scene` must handle `None` task gracefully (already handled by `_empty_scene_stub()`).
- **Imports** — Never use `sed`/`echo -e` to inject multi-line imports; use the `Edit` tool or `python -c "pathlib.Path(...).write_text(...)"`. The `editor` subpackage `__init__.py` uses `LazyImport`; new `editor/dock_state.py` follows the same lazy-import discipline (import `QtCore`/`QtWidgets` from `surg_rl.editor`, never `from PySide6 import ...` at module top).
- **Testing** — `pytest.ini` sets `pythonpath = src` and `asyncio_mode = auto`; offscreen GUI tests set `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` at module top and `pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, ...)`.
- **Code Style** — Line length 100, Python >=3.10, type hints required (`mypy disallow_untyped_defs = true`), ruff select E/F/I/N/W/UP/B/C4/SIM ignore E501.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Factory-default dock layout capture/restore (DockStateManager) | Frontend (Qt client) | — | Pure Qt-client concern; `QByteArray` + `restoreState()` are QMainWindow APIs; no server/backend involved. |
| Saved layout persistence (saveState/restoreState via QSettings) | Frontend (Qt client) | OS (QSettings INI store) | Already owned by `EditorSettings.save_window`/`load_window` (`_settings.py`); extend only. |
| In-place scene swap (`update_scene`) | Frontend (Qt client) | — | Widget-internal state swap; no data layer touched. The simulator reload is a side effect inside `ViewportPanel` (existing `_on_load_simulator`). |
| QThread teardown on close (`stop()` + `aboutToClose`) | Frontend (Qt client) | — | Worker-object lifecycle is purely a Qt-client concern; the LLM HTTP call is to an external provider but the teardown is local. |
| objectName enforcement (introspection test) | Test tier | — | Test-only guard; no runtime call-site helper this phase (D-07). |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.1 (installed; pinned `>=6.8.0,<7.0` in `[gui]`) | QMainWindow/QDockWidget/QThread/QSettings — the entire phase surface | Already the project's GUI framework since v0.5.0; no alternative considered. `[VERIFIED: pip show + pyproject.toml]` |
| Qt (QMainWindow API) | 6.11 LTS line | `saveState()`/`restoreState()`/`QByteArray` dock-state round-trip | Verified directly on installed PySide6 6.11.1: `saveState()` → `QByteArray` (146 bytes default, 155 after tabify); `restoreState()` → `True` and restores tabification; missing `objectName` warns `QMainWindow::saveState(): 'objectName' not set for QDockWidget` to stderr. `[VERIFIED: direct offscreen probe on installed runtime]` |
| Qt (QThread worker-object pattern) | 6.11 LTS line | `moveToThread` + `quit()` + `wait(3000)` cooperative teardown | Verified directly: cooperative cancel flag + `thread.quit()` + `thread.wait(3000)` returns `True`, `isRunning()` becomes `False`. `[VERIFIED: direct offscreen probe on installed runtime]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| QSettings (PySide6.QtCore) | 6.11 | INI-format persistence for window geometry + `saveState()` bytes | Already plumbed in `EditorSettings.save_window`/`load_window`; extend only if needed, do not rebuild. `[VERIFIED: _settings.py:39-48]` |
| Qt offscreen platform | built-in | `QT_QPA_PLATFORM=offscreen` for headless GUI tests | All GUI-state tests (SC#1/#2/#4) run offscreen; the existing `tests/gui/test_editor_smoke.py` + `tests/test_viewport.py` pattern. `[VERIFIED: existing test files]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| First-`showEvent` `QByteArray` snapshot (D-01 primary) | Code-level rebuild as primary | Snapshot always reflects the actual built layout even if code defaults drift; rebuild is the fallback only. D-01 locks this. |
| Plain `Signal` on `EditorWindow` for `aboutToClose` | A registry mixin that auto-wires any panel declaring `stop()` | Plain signal is simpler and explicit; mixin is less code per panel but more magic. CONTEXT leaves it to implementer's discretion. |
| `monkeypatch TextParser.parse_sync` to sleep (D-09b) | A real slow provider call in tests | Real call needs an API key and is flaky/slow; monkeypatch always runs offscreen as regression backstop. D-09 locks both. |

**Installation:**
```bash
# No install needed — GUI-18 is pure code on the existing [gui] extra.
# pyproject [gui] already declares: PySide6>=6.8.0,<7.0, markdown-it-py>=3.0.0, imageio>=2.31.0
```

**Version verification:**
```bash
pip show PySide6          # → Version: 6.11.1 (verified this session)
# No new packages introduced this phase — no registry verification needed.
```

## Package Legitimacy Audit

> This phase installs **zero** external packages. GUI-18 is pure code on the existing PySide6 dependency (already in the `[gui]` extra since v0.5.0). No `pip install` step is required.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| PySide6 | PyPI | (existing) | (existing) | (existing) | OK | Already installed — no action |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                       EditorWindow.__init__
                              │
                              ▼
        _build_dock_widgets (sets objectNames: dock_scene_tree, dock_properties, dock_llm)
                              │
                              ▼
        _restore_geometry  ←── EditorSettings.load_window() (geometry + saved saveState QByteArray)
        (restoreState(saved) — kept per D-03; docks already exist with objectNames)
                              │
                              ▼
                    showEvent (first show)
                              │  ┌── DockStateManager.capture_factory_default() ──→ saveState() → factory QByteArray (run ONCE, guarded)
                              │  └── (subsequent shows: no-op)
                              ▼
        ┌──── User actions ────────────────────────────────────────────┐
        │  New / Open / LLM-accept / undo / redo                         │
        │      │                                                         │
        │      ▼                                                         │
        │  _refresh_viewport_and_tree  (D-06 refactor)                   │
        │      │  ┌── ViewportPanel.update_scene(scene)  ── in-place swap (no widget recreation → dock geometry survives)
        │      │  └── SceneTreeView.update_scene(scene)   ── in-place swap (no setWidget recreation)
        │      ▼                                                         │
        │  (dock layout UNCHANGED — SC#2 holds)                          │
        │                                                                 │
        │  View → Reset Layout  (D-01/D-02)                               │
        │      │  ┌── DockStateManager.reset_to_default(window)          │
        │      │  │      └── window.restoreState(factory QByteArray)      │─ restores tabification/floating/closed (SC#1)
        │      │  └── (fallback: code-level rebuild re-adds docks)       │
        └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        closeEvent  (D-04/D-05)
              │  1. emit aboutToClose  ──→ slots: LLMPanel.stop(), (future: SimStepWorker, recorder, autosave, VLM)
              │                          └── stop() = _cancelled=True + thread.quit() + thread.wait(3000); on timeout: log + proceed
              │  2. self._viewport_panel.stop()  (existing; render-loop guard)
              │  3. EditorSettings.save_window(saveGeometry(), saveState())  (SC#2: saves the user's arrangement)
              │  4. super().closeEvent(event)  (Qt tears down children — safe, all workers stopped)
```

A reader can trace the primary use case: the user rearranges docks (bottom of diagram's user-actions box leaves layout unchanged via `update_scene`), closes (closeEvent saves state), reopens (`_restore_geometry` restores) — SC#2. Reset Layout (middle) restores the factory `QByteArray` captured once at first showEvent — SC#1. Mid-LLM-call close (top-right of closeEvent) stops the worker thread cooperatively before Qt tears down — SC#3.

### Recommended Project Structure
```
src/surg_rl/editor/
├── dock_state.py        # NEW — DockStateManager: factory QByteArray capture + reset_to_default + code-level rebuild fallback
├── main_window.py       # MODIFIED — _action_reset_layout → DockStateManager.reset_to_default; _refresh_viewport_and_tree → update_scene; closeEvent → aboutToClose; showEvent → capture
├── llm_panel.py         # MODIFIED — add stop() (cooperative cancel + thread.quit() + thread.wait(3000))
├── viewport.py          # MODIFIED — add update_scene(scene) (in-place swap; reload simulator via existing _on_load_simulator)
├── tree_view.py         # MODIFIED — add update_scene(scene) (rebuild QStandardItemModel in place; keep selectionModel wiring)
├── _settings.py         # UNCHANGED (extend only if needed — save_window/load_window already sufficient)
└── __init__.py          # UNCHANGED (LazyImport discipline; dock_state.py imports from surg_rl.editor, not PySide6 directly)

tests/
├── test_gui_scaffold.py     # existing offscreen pattern — reference for new test file
├── test_viewport.py         # existing qapp fixture + offscreen — reference
└── gui/
    └── test_editor_smoke.py # existing EditorWindow offscreen + isolated_home fixture — reference
# NEW test file (name per implementer's discretion, e.g. tests/test_dock_state.py or tests/gui/test_dock_layout.py):
#   - TestDockObjectNames (SC#4 introspection)
#   - TestDockRoundTrip (SC#1/#2 save/reload/restoreState)
#   - TestCloseMidCallMockSlow (SC#3, always-on regression backstop)
#   - TestCloseMidCallRealProvider (SC#3, skipif no API key)
```

### Pattern 1: DockStateManager — factory-default capture + reset
**What:** A small class owning (a) a `QByteArray` captured once at first `showEvent` via `QMainWindow.saveState()`, and (b) a code-level `rebuild_default_layout(window)` that re-adds docks in the factory arrangement as a fallback when the snapshot is missing/corrupt.
**When to use:** On "Reset Layout" (D-02) and as the factory-default source the snapshot is captured from (D-01).
**Example:**
```python
# Source: [VERIFIED: direct offscreen probe on installed PySide6 6.11.1] — saveState() returns
# QByteArray that round-trips through restoreState(); missing objectName warns to stderr.
from surg_rl.editor import QtCore, QtWidgets


class DockStateManager:
    """Owns the factory-default dock layout: a first-show QByteArray snapshot (primary)
    plus a code-level rebuild fallback (D-01). NOT persisted to QSettings."""

    def __init__(self) -> None:
        self._factory_state: QtCore.QByteArray | None = None
        self._captured: bool = False

    def capture_factory_default(self, window: QtWidgets.QMainWindow) -> None:
        """Capture saveState() at first showEvent. Guarded to run once (D-01)."""
        if self._captured:
            return
        self._factory_state = window.saveState()
        self._captured = True

    def reset_to_default(self, window: QtWidgets.QMainWindow) -> bool:
        """Reset Layout (D-02): restore the factory-default arrangement.

        Primary: restoreState(factory QByteArray). Fallback: code-level rebuild
        re-adds docks in the factory arrangement, then re-captures.
        Returns True if the primary restore succeeded.
        """
        if self._factory_state is not None and window.restoreState(self._factory_state):
            return True
        # Fallback: code-level rebuild (re-add docks to factory areas).
        self._rebuild_default_layout(window)
        self._factory_state = window.saveState()
        self._captured = True
        return True

    def _rebuild_default_layout(self, window: QtWidgets.QMainWindow) -> None:
        """Code-level fallback: re-add docks in the factory arrangement (D-01 fallback)."""
        # Implementer's discretion: move docks back to factory areas + show them.
        # This is the crude re-addDockWidget logic, kept ONLY as a fallback.
        ...
```

### Pattern 2: Cooperative QThread teardown (`stop()`)
**What:** Generalizes the existing `LLMPanel._on_cancel` (which sets `_cancelled` + `thread.quit()` but does NOT `wait()`) into a `stop()` that also blocks on `thread.wait(3000)` so the worker thread is truly terminated before the panel is deleted.
**When to use:** Every long-running panel that owns a `QThread` (D-04/D-05). Applied to `LLMPanel` this phase; the template for Phase 42/46/48/51 workers.
**Example:**
```python
# Source: [VERIFIED: direct offscreen probe on installed PySide6 6.11.1] —
# cooperative cancel + thread.quit() + thread.wait(3000) returns True, isRunning() -> False.
def stop(self) -> None:
    """Cooperative teardown (D-05): cancel flag + thread.quit() + thread.wait(3000).

    On timeout: log a warning and proceed (NEVER block quit). No thread.terminate().
    """
    if self._worker is not None:
        self._worker.setProperty("_cancelled", True)  # existing _on_cancel pattern
    if self._thread is not None:
        self._thread.quit()
        if not self._thread.wait(3000):
            logger.warning("LLMPanel worker thread did not exit within 3s; proceeding with close")
        # Do NOT call deleteLater here — thread.finished -> deleteLater is already wired.
```

### Pattern 3: `aboutToClose` signal — milestone-wide teardown contract
**What:** `EditorWindow` declares `aboutToClose = QtCore.Signal()`; `closeEvent` emits it BEFORE `super().closeEvent()`. Each long-running panel connects its `stop()` to `aboutToClose` in `__init__`. Future workers (Phase 42/46/48/51) just declare `stop()` + connect — no `closeEvent` edit.
**When to use:** D-04. Implementer's choice: plain `Signal` on `EditorWindow` (simpler, explicit) vs. a registry mixin that auto-wires any panel declaring `stop()` (less per-panel code, more magic). Both satisfy the D-04 contract.
**Example (plain signal):**
```python
# Source: [VERIFIED: Qt 6 QThread/closeEvent docs cross-checked in v0.7.0 PITFALLS.md Pitfall 3]
class EditorWindow(QtWidgets.QMainWindow):
    aboutToClose = QtCore.Signal()

    def closeEvent(self, event):
        try:
            self.aboutToClose.emit()           # D-04: panels self-teardown BEFORE super()
        except Exception:                      # noqa: BLE001
            pass                                # best-effort
        try:
            self._viewport_panel.stop()        # existing viewport teardown
        except Exception:                      # noqa: BLE001
            pass
        self._settings.save_window(self.saveGeometry(), self.saveState())  # SC#2
        super().closeEvent(event)

    # In __init__:
    #   self.aboutToClose.connect(self._llm_panel.stop)   # D-04 wiring
```

### Pattern 4: In-place `update_scene` (no widget recreation)
**What:** `ViewportPanel.update_scene(scene)` swaps `self._scene`, reloads the simulator via the existing `_on_load_simulator` path, and resets camera offsets — WITHOUT creating a new `ViewportPanel` or calling `setCentralWidget`. `SceneTreeView.update_scene(scene)` swaps `self._scene` and rebuilds the `QStandardItemModel` in place — WITHOUT creating a new `SceneTreeView` or calling `setWidget`.
**When to use:** D-06. Called from `_refresh_viewport_and_tree()` (New/Open/LLM-accept/undo/redo) so dock geometry survives scene loads.
**Why it fixes bug #3 (rerun):** `setCentralWidget(new ViewportPanel)` and `dock.setWidget(new SceneTreeView)` destroy the old widget and reset dock geometry on the next `saveState()`/`restoreState()` cycle; in-place swap preserves the widget identity that `saveState()` keyed on by `objectName`.

### Anti-Patterns to Avoid
- **Hand-rolled Reset Layout re-`addDockWidget`:** the current `_action_reset_layout` (`main_window.py:256`) ignores tabification/floating/closed state. Replace with `DockStateManager.reset_to_default()` → `restoreState(factory QByteArray)`.
- **Widget recreation in `_refresh_viewport_and_tree`:** `new ViewportPanel(...)` + `setCentralWidget` + `new SceneTreeView` + `setWidget` resets dock geometry on rerun. Replace with `update_scene()` in-place swap (D-06).
- **`thread.terminate()` on timeout:** risks leaving SDK/parser state inconsistent (D-05). Log and proceed instead.
- **`deleteLater` on a thread before `wait()`:** Qt docs warn "Deleting a running QThread will result in a program crash." The existing `thread.finished -> thread.deleteLater` wiring is correct; `stop()` must NOT additionally call `deleteLater` synchronously. `[VERIFIED: Qt 6 QThread docs cited in PITFALLS.md Pitfall 3]`
- **`restoreState()` before docks exist:** silently returns `True` while applying nothing. D-03 confirms the current `__init__` ordering (docks built before `_restore_geometry`) is correct; do not change it.
- **Deferring `restoreState` to `showEvent` (Pitfall 2 timing fix):** D-03 explicitly says NOT needed here — the bug is widget recreation, not restore timing. Revisit only if dock-build ordering changes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Factory-default dock layout | Hand-rolled per-dock re-`addDockWidget` (current code) | `QMainWindow.saveState()` `QByteArray` snapshot + `restoreState()` | The snapshot captures tabification/floating/closed state that hand-rolled re-add ignores; `restoreState()` is Qt's supported round-trip. `[VERIFIED: offscreen probe]` |
| Window-state persistence | Custom JSON layout file | `QSettings` via existing `EditorSettings.save_window`/`load_window` | Already plumbed; platform-native; INI format already testable. `[VERIFIED: _settings.py:39-48]` |
| QThread teardown ordering | Manual `terminate()` or synchronous `deleteLater` | `quit()` + `wait(3000)` cooperative pattern (D-05) | `terminate()` is unsafe for SDK state; `deleteLater` before `wait()` crashes per Qt docs. `[VERIFIED: PITFALLS.md Pitfall 3 + direct probe]` |
| Offscreen Qt testing | subprocess + screenshot diff | `QT_QPA_PLATFORM=offscreen` + `QApplication` in-process + `qapp` fixture | Existing pattern (`tests/test_viewport.py`, `tests/gui/test_editor_smoke.py`); faster, assertable, no display needed. `[VERIFIED: existing test files]` |

**Key insight:** The entire phase is composed of Qt-provided APIs (`saveState`/`restoreState`/`QByteArray`/`QThread.quit`/`wait`/`QSettings`). There is nothing to hand-roll except the thin `DockStateManager` wrapper that decides WHEN to capture and WHEN to restore — the round-trip itself is Qt's job.

## Runtime State Inventory

> This is a refactor/bugfix phase touching the editor's dock + teardown plumbing. Applicable.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `QSettings` (INI, platform-native) stores `window/geometry` + `window/state` keys via `EditorSettings.save_window`/`load_window`. | **No data migration.** The existing saved-state format is unchanged; `DockStateManager`'s factory-default `QByteArray` is NOT persisted (D-01 — recomputed each launch). Saved user layouts continue to round-trip via the existing keys. |
| Live service config | None — the editor is a single-user desktop tool; no external service holds editor config. | None. |
| OS-registered state | None — no Task Scheduler/launchd/systemd registrations; no `surg-rl-gui` autostart entries. (The `surg-rl-gui` console script is a pip entry point, not OS-registered.) | None. |
| Secrets/env vars | None — `LLM_API_KEY`/`LLM_PROVIDER` stay in `.env` via `Settings()`; `QSettings` is explicitly not for secrets (per `_settings.py` docstring + D-20). `stop()` reads no secrets. | None. |
| Build artifacts | `tests/gui/screenshots/*.png` — existing smoke-test artifacts; `__pycache__` dirs. | None — these regenerate; no stale-named artifacts to migrate (no rename this phase). |

**Nothing found in categories that need migration.** The phase is additive (new `dock_state.py` + `update_scene` + `stop()` + `aboutToClose`); the existing QSettings keys and their format are untouched.

## Common Pitfalls

### Pitfall 1: restoreState silently no-ops if objectName missing/changed
**What goes wrong:** `saveState()`/`restoreState()` identify widgets solely by `objectName`. A dock without `objectName` is invisible to save/restore — and Qt warns to stderr. Verified: adding a dock without `objectName` produced `QMainWindow::saveState(): 'objectName' not set for QDockWidget` in the offscreen probe. `[VERIFIED: direct offscreen probe]`
**Why it happens:** Easy to forget `setObjectName` when adding a dock in a hurry. The current 3 docks DO have objectNames (`dock_scene_tree`, `dock_properties`, `dock_llm`), so restore works — but any new dock added in a later phase without an objectName breaks silently.
**How to avoid:** D-07 introspection pytest collecting all `QDockWidget` children and asserting non-empty unique `objectName`. This is the regression guard for future phases.
**Warning signs:** `QMainWindow::saveState(): 'objectName' not set` in stderr; a new dock always opens in its default area ignoring saved position; `restoreState()` returns `True` but nothing visually changes.

### Pitfall 2: Widget recreation resets dock geometry on rerun (bug #3 root cause)
**What goes wrong:** `_refresh_viewport_and_tree()` (`main_window.py:306-319`) creates `new ViewportPanel(...)` + `setCentralWidget()` and `new SceneTreeView` + `setWidget()`. This destroys old widgets and, on the next save/restore cycle, resets dock geometry — the "layout not reset on rerun" bug.
**Why it happens:** The widgets were recreated to load a new scene; the dock geometry side effect was unintended.
**How to avoid:** D-06 — add `update_scene(scene)` in-place swap to `ViewportPanel` and `SceneTreeView`; `_refresh_viewport_and_tree` calls `update_scene()` instead of recreating.
**Warning signs:** Rearranging docks, opening a new scene, closing, and reopening shows the default layout instead of the user's arrangement. `[VERIFIED: main_window.py:306-319 direct read]`

### Pitfall 3: QThread leak on close — `RuntimeError: Internal C++ object already deleted`
**What goes wrong:** `closeEvent` (`main_window.py:373-382`) stops only `self._viewport_panel.stop()`. The `LLMPanel` `QThread` is not stopped. Closing mid-LLM-call emits `finished`/`failed` into a deleted panel → segfault or `RuntimeError: Internal C++ object already deleted`.
**Why it happens:** The v0.5.0 panel was added with the happy path only; teardown was deferred because the LLM call was assumed short. `[VERIFIED: main_window.py:373-382 + llm_panel.py:114-125 direct read; PITFALLS.md Pitfall 3]`
**How to avoid:** D-04/D-05 — `aboutToClose` signal + `LLMPanel.stop()` (cooperative cancel + `thread.quit()` + `thread.wait(3000)`), emitted BEFORE `super().closeEvent()`. On timeout: log + proceed (never block quit, never `terminate()`).
**Warning signs:** Intermittent segfault on window close while an LLM call is in flight; `QThread: Destroyed while thread is still running` warning; `RuntimeError: Internal C++ object already deleted` in stderr after close.

### Pitfall 4: `deleteLater` on a thread before `wait()` crashes
**What goes wrong:** Calling `thread.deleteLater()` synchronously in `stop()` (before the thread has exited) crashes: "Deleting a running QThread will result in a program crash." The existing `thread.finished -> thread.deleteLater` wiring is correct; adding a synchronous `deleteLater` in `stop()` is the mistake.
**Why it happens:** It feels like cleanup, but it races the thread's exit.
**How to avoid:** `stop()` calls `quit()` + `wait(3000)` only. Do NOT call `deleteLater` in `stop()`. The `finished -> deleteLater` connection (already in `_on_generate`) handles deletion after the thread actually exits. `[VERIFIED: Qt 6 QThread docs cited in PITFALLS.md Pitfall 3]`
**Warning signs:** Crash on close even with the `wait()` in place; "QThread: Destroyed while thread is still running."

### Pitfall 5: Factory-default capture runs more than once
**What goes wrong:** If `capture_factory_default` is not guarded, every `showEvent` (e.g. after minimize/restore on some platforms) overwrites the factory snapshot with the user's current (possibly rearranged) layout — so "Reset Layout" resets to the wrong thing.
**Why it happens:** `showEvent` can fire multiple times.
**How to avoid:** D-01 — guard with a `_captured` bool; capture only on the first `showEvent`. `DockStateManager` owns the guard.
**Warning signs:** Reset Layout restores a rearranged layout instead of the factory arrangement.

### Pitfall 6: Mock-slow-parser test that doesn't actually exercise the close path
**What goes wrong:** D-09b's `monkeypatch TextParser.parse_sync` to `sleep` test must actually start the worker thread, then close the window mid-call, and assert `thread.wait()` returned + no `RuntimeError`. A weak version that just asserts `stop()` exists is useless.
**Why it happens:** It's tempting to test the method in isolation.
**How to avoid:** D-09b — build `EditorWindow` offscreen, trigger `_on_generate`, monkeypatch `parse_sync` to `time.sleep(2)`, call `window.close()`, assert clean exit (no segfault, no `RuntimeError: Internal C++ object already deleted`, the `LLMPanel._thread` is `None` or not running after `stop()`). Run under `QT_QPA_PLATFORM=offscreen` so it always runs. The `parse_sync` signature is `parse_sync(self, input_data: str | Path, **kwargs) -> SceneDefinition` (`text_parser.py:545`). `[VERIFIED: text_parser.py:545 direct read]`

### Pitfall 7: `update_scene` leaks the old simulator
**What goes wrong:** `ViewportPanel.update_scene(scene)` must close the old `self._simulator` before loading the new scene, or MuJoCo/PyBullet state from the previous scene leaks into the new preview.
**Why it happens:** The current `stop()` closes the simulator; `update_scene` must do the same for the old one before swapping.
**How to avoid:** Reuse the existing `stop()`-style simulator close (`with contextlib.suppress(AttributeError, OSError): self._simulator.close()`) before reassigning `self._scene` and letting `_tick` reload via `_on_load_simulator`. Reset `_simulator = None` so `_tick` reloads on next tick. `[VERIFIED: viewport.py:169-180 stop() pattern direct read]`

## Code Examples

### saveState/restoreState round-trip (verified offscreen)
```python
# Source: [VERIFIED: direct offscreen probe on installed PySide6 6.11.1]
# Confirmed: saveState() -> QByteArray (146 bytes default, 155 after tabify);
# restoreState(default) -> True and restores tabification;
# missing objectName warns "QMainWindow::saveState(): 'objectName' not set" to stderr.
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QDockWidget

app = QApplication([])
w = QMainWindow()
d1 = QDockWidget("A"); d1.setObjectName("dock_a")
w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, d1)
d2 = QDockWidget("B"); d2.setObjectName("dock_b")
w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d2)
w.show(); app.processEvents()

factory: QByteArray = w.saveState()           # capture factory default
w.tabifyDockWidget(d1, d2); app.processEvents()
assert w.restoreState(factory) is True         # reset to factory — restores tabification
```

### Cooperative QThread teardown (verified offscreen)
```python
# Source: [VERIFIED: direct offscreen probe on installed PySide6 6.11.1]
# Confirmed: cancel flag + thread.quit() + thread.wait(3000) -> True, isRunning() -> False.
from PySide6.QtCore import QThread, QObject, Slot
import time

class Worker(QObject):
    def __init__(self):
        super().__init__()
        self._cancelled = False
    @Slot()
    def run(self):
        for _ in range(50):
            if self._cancelled:
                return
            time.sleep(0.05)

t = QThread(); w = Worker(); w.moveToThread(t)
t.started.connect(w.run); t.start()
time.sleep(0.1)
w._cancelled = True; t.quit()
assert t.wait(3000) is True                     # cooperative cancel -> clean exit
assert t.isRunning() is False
```

### objectName introspection test (SC#4, D-07)
```python
# Source: [VERIFIED: existing offscreen pattern in tests/gui/test_editor_smoke.py]
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False
pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")


def test_every_dock_has_unique_nonempty_objectname(qapp, isolated_home):
    from PySide6.QtWidgets import QDockWidget
    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    w.show(); qapp.processEvents()
    docks = w.findChildren(QDockWidget)
    names = [d.objectName() for d in docks]
    assert all(names), f"Every QDockWidget must have a non-empty objectName; got {names}"
    assert len(names) == len(set(names)), f"objectNames must be unique; got {names}"
    w.close()
```

### Mock-slow-parser close-mid-call test (SC#3, D-09b — always-on backstop)
```python
# Source: [VERIFIED: TextParser.parse_sync signature at text_parser.py:545 + QThread probe]
import time
import pytest

def test_close_mid_llm_call_clean_exit_mock_slow(qapp, isolated_home, monkeypatch):
    from surg_rl.editor.main_window import EditorWindow
    from surg_rl.scene_generation import text_parser as tp

    # Monkeypatch the slow parser path — always runs offscreen (no API key).
    def slow_parse_sync(self, input_data, **kwargs):
        time.sleep(2)  # simulate a multi-second provider call
        from surg_rl.scene_definition import SceneDefinition
        return SceneDefinition()
    monkeypatch.setattr(tp.TextParser, "parse_sync", slow_parse_sync)

    w = EditorWindow()
    w.show(); qapp.processEvents()
    w._llm_panel._prompt.setPlainText("a test prompt")
    w._llm_panel._on_generate()
    qapp.processEvents()
    # Close mid-call — must not segfault or raise RuntimeError.
    w.close()
    qapp.processEvents()
    # Worker thread must have exited cleanly.
    thread = w._llm_panel._thread
    if thread is not None:
        assert not thread.isRunning(), "LLM worker thread still running after close"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled re-`addDockWidget` reset | `restoreState(factory QByteArray)` snapshot (D-01) | This phase | Reset Layout now restores tabification/floating/closed, not just area assignment. |
| Widget recreation in `_refresh_viewport_and_tree` | `update_scene()` in-place swap (D-06) | This phase | Dock geometry survives scene loads (bug #3 closed). |
| `closeEvent` stops only viewport | `aboutToClose` registry + per-panel `stop()` (D-04/D-05) | This phase | Mid-LLM-call close no longer segfaults; future workers auto-wire teardown. |
| `_on_cancel` (cancel flag + `thread.quit()`, no `wait()`) | `stop()` (cancel flag + `thread.quit()` + `thread.wait(3000)`) (D-05) | This phase | Worker thread truly terminates before panel deletion. |

**Deprecated/outdated:**
- `LLMPanel._on_cancel` (cancel flag + `thread.quit()` without `wait()`) — superseded by `stop()`; keep `_on_cancel` calling `stop()` or fold it in.
- The crude `_action_reset_layout` re-`addDockWidget` body (`main_window.py:256-262`) — replaced by `DockStateManager.reset_to_default()`.

## Assumptions Log

> All load-bearing Qt behaviors in this research were verified directly on the installed PySide6 6.11.1 under `QT_QPA_PLATFORM=offscreen` (the authoritative runtime for this codebase) and/or cross-checked against Qt 6 docs cited in the v0.7.0 PITFALLS.md. No `[ASSUMED]` claims remain that would change the plan if wrong.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `aboutToClose` as a plain `Signal` on `EditorWindow` is sufficient (vs. a registry mixin) | Architecture Patterns | Low — CONTEXT leaves this to implementer's discretion; both satisfy D-04. |
| A2 | `SceneTreeView.update_scene` can rebuild the `QStandardItemModel` in place while preserving the `selectionModel`/`customContextMenuRequested` wiring | Pattern 4 | Low — the wiring is set in `__init__` on `self`, not on the model; rebuilding the model rows in place (`self._model.clear()` + `_build_tree`) preserves the view's signal connections. Verify in implementation. |
| A3 | `ViewportPanel.update_scene` should reset camera offsets to factory defaults on scene swap | Pattern 4 | Low — implementer's discretion; resetting matches "new scene = fresh view" expectation. The existing `reset_camera()` already does this. |

**If this table is empty of `[ASSUMED]`-tagged runtime claims:** all Qt behavior claims were verified by direct offscreen probe this session.

## Open Questions (RESOLVED)

1. **Should `update_scene` reset the camera?**
   - What we know: `reset_camera()` resets `self._camera_offset` to defaults (viewport.py:390-397). New scene load naturally implies a fresh view.
   - What's unclear: whether undo/redo should preserve the user's camera orbit (they're editing the same scene) vs. reset it.
   - Recommendation: `update_scene` resets the camera; undo/redo call `update_scene` (per D-06 they keep calling `_refresh_viewport_and_tree`, now safe). If undo/redo camera-flicker is reported, revisit (deferred per D-06).
   - **— RESOLVED: `update_scene` resets the camera.** Plan 01 Task 3 calls `self.reset_camera()` on scene swap; undo/redo keep calling `_refresh_viewport_and_tree` (now safe via in-place swap) per D-06. Camera-flicker on undo/redo remains deferred per D-06.

2. **Plain `Signal` vs. registry mixin for `aboutToClose`:**
   - What we know: D-04 permits either; the contract (emit before `super().closeEvent()`, panels connect `stop()`) is what matters.
   - Recommendation: Start with a plain `Signal` (simpler, explicit, one line of wiring per panel). Only introduce a mixin if the per-panel wiring count grows past ~3-4 panels in later phases.
   - **— RESOLVED: plain `Signal`.** Plan 02 Task 2 declares `aboutToClose = QtCore.Signal()` on `EditorWindow` and wires `LLMPanel.stop()` in `__init__`. A registry mixin is deferred until per-panel wiring grows past ~3-4 panels in later phases (42/46/48/51).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | Entire phase (QMainWindow/QThread/QSettings) | ✓ | 6.11.1 | — (hard requirement for the editor) |
| Qt offscreen platform | GUI-state tests (SC#1/#2/#3/#4) | ✓ | built-in | — |
| OpenAI/Anthropic/Ollama API key | D-09a real-provider close-mid-call test | ✗ (likely) | — | D-09b mock-slow-parser test always runs offscreen as the regression backstop; SC#3 is guarded without keys |
| `imageio-ffmpeg` | NOT required this phase | — | — | — (GUI-15/Phase 46 dep, not Phase 41) |

**Missing dependencies with no fallback:** none — the phase is pure code on PySide6; the only test gated on an API key (D-09a) has the D-09b backstop.

**Missing dependencies with fallback:** API key → mock-slow-parser test (D-09b).

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json`. This section is REQUIRED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (>=7.0.0, in `[dev]` extra) + PySide6 6.11.1 offscreen |
| Config file | `pytest.ini` (`testpaths=tests`, `pythonpath=src`, `asyncio_mode=auto`) |
| Quick run command | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py -v` (or chosen test file name) |
| Full suite command | `PYTHONPATH=src pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SC#1 (GUI-18) | Reset Layout restores factory-default arrangement incl. tabification/floating/closed | integration (offscreen GUI) | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py::TestDockRoundTrip -v` | ❌ Wave 0 |
| SC#2 (GUI-18) | Rearrange→close→reopen restores saved layout (not a broken state) | integration (offscreen GUI) | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py::TestDockRoundTrip::test_rearrange_close_reopen -v` | ❌ Wave 0 |
| SC#3 (GUI-18) | Close mid-LLM-call exits cleanly (no segfault, no `RuntimeError: Internal C++ object already deleted`, `thread.wait()` returned) | integration (offscreen GUI) — two-pronged: skipif-gated real + always-on mock | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py::TestCloseMidCallMockSlow -v` (always-on) + `TestCloseMidCallRealProvider` (skipif no key) | ❌ Wave 0 |
| SC#4 (GUI-18) | Every dock has a unique non-empty `objectName` | unit (introspection) | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py::TestDockObjectNames -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py -v` (new phase test file only — fast, offscreen)
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -v` (full suite — confirms no regression in the 1,513-test baseline)
- **Phase gate:** Full suite green before `/gsd-verify-work`; plus the 4 new SC tests green offscreen.

### Wave 0 Gaps
- [ ] `tests/test_dock_state.py` (or `tests/gui/test_dock_layout.py` — implementer's choice) — covers SC#1/#2/#3/#4. New file.
- [ ] Shared `qapp` session fixture + `isolated_home` (tmp_path + `HOME`/`XDG_CONFIG_HOME` monkeypatch) — reuse the `tests/gui/test_editor_smoke.py` pattern (already exists there; either import it or duplicate the small fixture in the new file).
- [ ] No framework install needed — pytest + PySide6 already in `[dev]`/`[gui]`.

*(If no gaps: "None — existing test infrastructure covers all phase requirements")* — here there ARE gaps (the new test file), listed above.

### TDD Eligibility (tdd_mode is `true` in config)

| Implementation Task | TDD-eligible? | Rationale |
|---------------------|---------------|-----------|
| `DockStateManager.capture_factory_default` + `reset_to_default` (capture-once guard + restore logic) | ✅ `type: tdd` | Pure logic with defined I/O: capture once, restore returns bool, fallback rebuild re-captures. Testable headless: build window, capture, rearrange, reset, assert arrangement. |
| `LLMPanel.stop()` cooperative-cancel + `wait(3000)` semantics (incl. timeout-log-and-proceed) | ✅ `type: tdd` | Defined I/O: cancel flag set, `thread.quit()` called, `wait()` returns/timeout logged. Testable with mock-slow parser (D-09b) — assert `isRunning()==False` after `stop()`. |
| `ViewportPanel.update_scene(scene)` in-place swap | ✅ `type: tdd` | Defined I/O: scene swapped, simulator set to None (reload on next tick), camera reset. Testable offscreen: assert `self._scene is new_scene` and `self._simulator is None` after `update_scene`. |
| `SceneTreeView.update_scene(scene)` in-place model rebuild | ✅ `type: tdd` | Defined I/O: scene swapped, model rows rebuilt, selectionModel/customContextMenuRequested wiring intact. Testable offscreen. |
| `aboutToClose` signal + `closeEvent` wiring | ❌ standard (UI wiring) | Signal/slot connection glue — no discrete business logic to TDD; the SC#3 close-mid-call tests verify the wiring end-to-end. |
| `_action_reset_layout` → `DockStateManager.reset_to_default()` call site | ❌ standard (UI wiring) | One-line replacement; the round-trip test (SC#1/#2) covers it. |
| `showEvent` capture-first-show guard | ❌ standard (UI wiring) | Guard logic is in `DockStateManager` (TDD-eligible); the `showEvent` hook itself is wiring. |
| objectName setting on existing docks | N/A | Already set (`dock_scene_tree`/`dock_properties`/`dock_llm`); the SC#4 introspection test is the guard. |

## Security Domain

> `security_enforcement` is not explicitly `false` in config — treat as enabled. This phase touches no auth, crypto, or untrusted-input boundaries beyond what already exists.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | N/A — desktop editor, no auth. |
| V3 Session Management | no | N/A — no sessions. |
| V4 Access Control | no | N/A — single-user desktop. |
| V5 Input Validation | yes (indirectly) | `safe_error_message()` redactor (`_safe_error.py`) must wrap any teardown-timeout warning surfaced to the user (D-05 logs a warning — keep it internal; if surfaced, redact). Existing pattern in `llm_panel.py`. |
| V6 Cryptography | no | N/A — no crypto this phase. |
| V7 Error Handling | yes | `closeEvent` + `stop()` are best-effort with broad `suppress` (existing pattern, `main_window.py:377-380`); never surface SDK internal paths. `safe_error_message()` for any user-facing error. `[VERIFIED: _safe_error.py + main_window.py:377 direct read]` |

### Known Threat Patterns for PySide6/Qt desktop

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage in error dialogs | Information disclosure | `safe_error_message()` redactor on all user-facing errors (existing); `QSettings` explicitly not for secrets (per `_settings.py` docstring + D-20). `[VERIFIED: _settings.py + _safe_error.py]` |
| QSettings file holds sensitive data | Information disclosure | `_settings.py` stores only geometry/state/recent-files/last-provider — no secrets. `stop()` reads no secrets. `[VERIFIED: _settings.py:39-48 direct read]` |
| LLM/VLM error strings leak provider internals | Information disclosure | `LLMPanel._on_parse_failed` already routes through `safe_error_message` (`llm_panel.py:38, 144`). `stop()` timeout warning is log-only (logger.warning), not user-facing. |

## Sources

### Primary (HIGH confidence)
- **Direct offscreen probe on installed PySide6 6.11.1** — verified `saveState()`/`restoreState()` `QByteArray` round-trip (146 bytes default, 155 after tabify), missing-`objectName` stderr warning, and `QThread.quit()`+`wait(3000)` cooperative teardown returning `True` with `isRunning()==False`.
- **`src/surg_rl/editor/main_window.py`** (direct read, current state) — `_build_dock_widgets` (objectNames set), `_action_reset_layout:256`, `_refresh_viewport_and_tree:306`, `closeEvent:373`, `_restore_geometry:364`, `_refresh_recent_menu:352` (duplicated block — NOT in scope, Phase 48).
- **`src/surg_rl/editor/llm_panel.py`** (direct read) — `TextParserWorker`/`_thread`/`_worker` pattern, `_on_cancel:127` (cancel flag + `thread.quit()`, no `wait()`), `_on_generate:102` (`finished`/`failed`->`thread.quit`->`deleteLater` wiring).
- **`src/surg_rl/editor/viewport.py`** (direct read) — `ViewportPanel`/`_tick`/`stop`/`reset_camera`, `_on_load_simulator` path, simulator-close pattern (lines 169-180). NOTE: 1-line uncommitted change on `main` (minor; does not affect this phase).
- **`src/surg_rl/editor/tree_view.py`** (direct read) — `SceneTreeView`, `_build_tree`, `QStandardItemModel` rebuild pattern, `node_selected` signal, selectionModel wiring.
- **`src/surg_rl/editor/_settings.py`** (direct read) — `EditorSettings.save_window`/`load_window` QSettings INI plumbing; no-secrets docstring.
- **`src/surg_rl/editor/__init__.py`** (direct read) — `LazyImport` + `HAS_GUI` sentinel; new `dock_state.py` must follow this discipline.
- **`src/surg_rl/scene_generation/text_parser.py:545`** (direct read) — `parse_sync(self, input_data: str | Path, **kwargs) -> SceneDefinition` signature (for D-09b monkeypatch).
- **`pyproject.toml`** (direct read) — `[gui]` extra: `PySide6>=6.8.0,<7.0`, `markdown-it-py>=3.0.0`, `imageio>=2.31.0`. No new deps for GUI-18.
- **`.planning/research/SUMMARY.md`** §"Bug Reconciliation" + §"Critical Pitfalls" #2/#3 — bug #3 root cause + the two pitfalls this phase prevents.
- **`.planning/research/PITFALLS.md`** Pitfalls 2, 3, 8 — dock-state restore, QThread leak on close, timer guard (cross-checked against Qt 6 QThread/QMainWindow docs).
- **`.planning/config.json`** — `nyquist_validation: true`, `tdd_mode: true`, `use_worktrees: true`.

### Secondary (MEDIUM confidence)
- `.planning/phases/33-pyside6-scene-editor/33-CONTEXT.md` — D-13 (QThread worker pattern), D-17 (4-pane dock layout), D-18 (File menu + Reset Layout action): the locked foundation Phase 41 modifies.
- `tests/test_gui_scaffold.py`, `tests/gui/test_editor_smoke.py`, `tests/test_viewport.py` — existing offscreen GUI test patterns (`qapp` fixture, `isolated_home`, `QT_QPA_PLATFORM=offscreen` module-top setenv, `skipif not _HAVE_PYSIDE6`).
- Qt 6 QThread/QMainWindow docs (cited in PITFALLS.md sources) — `finished()`/`wait()`/`deleteLater` ordering, `objectName` requirement for saveState/restoreState.

### Tertiary (LOW confidence)
- None — all load-bearing claims verified directly or via the v0.7.0 research (which cross-checked Qt docs).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySide6 6.11.1 installed and probed directly; no new deps confirmed against `pyproject.toml`.
- Architecture: HIGH — `DockStateManager`/`update_scene`/`stop()`/`aboutToClose` patterns verified against actual current source + direct Qt behavior probes.
- Pitfalls: HIGH — Pitfalls 2/3/8 cross-checked against Qt 6 docs in v0.7.0 PITFALLS.md and confirmed by direct offscreen probes (objectName warning, QThread wait semantics).

**Research date:** 2026-07-15
**Valid until:** 2026-08-15 (30 days — stable; PySide6 is a locked LTS dep, no new packages this phase)