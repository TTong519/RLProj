# Phase 41: Dock Layout Reset & CloseEvent Teardown - Pattern Map

**Mapped:** 2026-07-15
**Files analyzed:** 8 (2 new + 6 modified)
**Analogs found:** 8 / 8 (every new/modified file has a real on-disk analog — all modifications read the file itself; both new files have same-package siblings to mirror)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/surg_rl/editor/dock_state.py` (NEW) | service / state-manager | request-response (capture/restore on demand) | `src/surg_rl/editor/undo_stack.py` + `src/surg_rl/editor/_settings.py` | exact (same-package state-manager + lazy-import discipline) |
| `tests/test_dock_state.py` (NEW, name per implementer) | test | request-response (offscreen GUI introspection + round-trip) | `tests/gui/conftest.py` + `tests/test_viewport.py` + `tests/test_gui_scaffold.py` | exact (offscreen `qapp` + `isolated_home` + `pytestmark skipif`) |
| `src/surg_rl/editor/main_window.py` (MODIFIED) | controller / QMainWindow | event-driven (close, show, reset) + request-response (refresh) | the file itself | exact (read current method bodies) |
| `src/surg_rl/editor/llm_panel.py` (MODIFIED) | component / QThread owner | event-driven (worker lifecycle) | the file itself (`_on_cancel`) | exact (generalize existing pattern) |
| `src/surg_rl/editor/viewport.py` (MODIFIED) | component / render surface | event-driven (render loop) + in-place state swap | the file itself (`stop()`/`_tick`) | exact (mirror existing simulator-close + guard pattern) |
| `src/surg_rl/editor/tree_view.py` (MODIFIED) | component / QTreeView | CRUD (model rebuild) | the file itself (`_build_tree`) | exact (in-place model rebuild) |
| `src/surg_rl/editor/_settings.py` (MODIFIED — extend only if needed) | config / persistence | file-I/O (QSettings INI) | the file itself | exact (no change expected per D-03) |
| `src/surg_rl/editor/__init__.py` (UNCHANGED — reference for lazy-import discipline) | package init | N/A | the file itself | N/A |

## Pattern Assignments

### `src/surg_rl/editor/dock_state.py` (NEW — service / state-manager)

**Analogs:** `src/surg_rl/editor/undo_stack.py` (same-package state-manager class) + `src/surg_rl/editor/_settings.py` (small QSettings/QByteArray wrapper) + `src/surg_rl/editor/__init__.py` (LazyImport discipline).

**Lazy-import / HAS_GUI discipline** — mirror `editor/__init__.py:31-42`:
```python
# editor/__init__.py:31-42  (the discipline new dock_state.py must follow)
from surg_rl.utils.lazy_imports import LazyImport

QtWidgets = LazyImport("PySide6.QtWidgets", "gui")
QtCore = LazyImport("PySide6.QtCore", "gui")
QtGui = LazyImport("PySide6.QtGui", "gui")
HAS_GUI: bool = QtWidgets.available
```

**Imports pattern** — copy from `undo_stack.py:1-25` (the canonical small state-manager module):
```python
# undo_stack.py:17-26 — module-level imports stay cheap; defer SceneDefinition
# (and any heavy Qt symbol) behind `from __future__ import annotations` +
# TYPE_CHECKING. Import Qt symbols from surg_rl.editor, NOT PySide6 directly.
from __future__ import annotations

from typing import TYPE_CHECKING

from surg_rl.editor import QtGui  # noqa: F401  (Qt symbol via LazyImport)

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition
```
For `dock_state.py`, the runtime Qt imports needed are `QtCore.QByteArray` and `QtWidgets.QMainWindow` — import via `from surg_rl.editor import QtCore, QtWidgets` at module top (LazyImport proxies; safe whether or not PySide6 is installed — they only resolve on attribute access). Class bodies may use them in annotations only under `from __future__ import annotations`.

**Class shape pattern** — copy `undo_stack.py:50-77` (a small, single-purpose state-manager class with a private guard):
```python
# undo_stack.py:50-77 — the canonical "small state-manager class" skeleton:
#   - module-level constant for the cap
#   - __init__ sets private state + a guard bool
#   - one public method to push state
#   - one classmethod / helper to retrieve
_MAX_DEPTH: int = 100  # Per D-11.

class SceneUndoStack(QtGui.QUndoStack):
    _active_apply: SceneDefinition | None = None

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self.setUndoLimit(_MAX_DEPTH)

    def push_snapshot(self, before: SceneDefinition, after: SceneDefinition) -> None:
        self.push(_SceneSnapshotCommand(before, after))
    ...
```

**`DockStateManager` skeleton to follow** (per D-01, with the `_captured` guard from Pitfall 5):
```python
# Adapt undo_stack.py's class shape to DockStateManager (D-01):
class DockStateManager:
    def __init__(self) -> None:
        self._factory_state: QtCore.QByteArray | None = None
        self._captured: bool = False          # Pitfall 5 guard

    def capture_factory_default(self, window: QtWidgets.QMainWindow) -> None:
        if self._captured:                    # run once at first showEvent
            return
        self._factory_state = window.saveState()
        self._captured = True

    def reset_to_default(self, window: QtWidgets.QMainWindow) -> bool:
        if self._factory_state is not None and window.restoreState(self._factory_state):
            return True
        self._rebuild_default_layout(window)  # D-01 code-level fallback
        self._factory_state = window.saveState()
        self._captured = True
        return True
```

**Error handling pattern** — `QMainWindow.restoreState()` returns `bool`; treat `False` as "missing/corrupt → invoke the rebuild fallback" (D-01). No exceptions expected from `saveState()`/`restoreState()`. The fallback `_rebuild_default_layout` is the *only* place the current crude re-`addDockWidget` body (see `main_window.py:256-262` below) is preserved — kept as the fallback, NOT the primary path (D-01).

---

### `tests/test_dock_state.py` (NEW — test, offscreen GUI)

**Analogs:** `tests/gui/conftest.py` (offscreen fixtures) + `tests/test_viewport.py` (offscreen + `pytestmark` + `qapp` + tmp_path/isolated HOME pattern) + `tests/test_gui_scaffold.py` (skipif + subprocess pattern).

**Offscreen harness pattern** — copy verbatim from `tests/gui/conftest.py:1-35`:
```python
# tests/gui/conftest.py:1-35 — the canonical offscreen GUI test harness.
from __future__ import annotations

import os
import sys

import pytest

# Force offscreen Qt for all tests in this directory.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False


@pytest.fixture(scope="session")
def qapp():
    if not _HAVE_PYSIDE6:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path
```

**Per-file skipif + qapp pattern** — copy from `tests/test_viewport.py:13-68` (the standalone single-file variant the new test file should mirror, since it may live in `tests/` not `tests/gui/`):
```python
# tests/test_viewport.py:13-67 — module-top offscreen + skipif + qapp fixture
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False

pytestmark_viewport = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)
```
**NOTE:** The new test file must declare `pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")` at module level (D-08). If placed in `tests/`, duplicate the small `qapp` + `isolated_home` fixtures (per RESEARCH.md Wave 0 gaps: "either import it or duplicate the small fixture in the new file"). If placed in `tests/gui/`, the shared `conftest.py` already provides them.

**EditorWindow offscreen construction pattern** — copy from `tests/test_viewport.py:142-153`:
```python
# tests/test_viewport.py:142-153 — build EditorWindow offscreen + monkeypatch HOME
@pytestmark_viewport
class TestViewportInMainWindow:
    def test_main_window_central_widget_is_viewport_panel(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.editor.viewport import ViewportPanel

        w = EditorWindow()
        assert isinstance(w.centralWidget(), ViewportPanel)
        w.close()
```

**closeEvent invocation pattern** — copy from `tests/test_viewport.py:299-316` (the existing closeEvent test the SC#3 mock-slow test will mirror):
```python
# tests/test_viewport.py:299-316 — closeEvent + Mock stop pattern
def test_close_event_stops_viewport(self, qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    from PySide6.QtGui import QCloseEvent

    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    mock_stop = MagicMock()
    w._viewport_panel.stop = mock_stop
    w.closeEvent(QCloseEvent())
    assert mock_stop.call_count >= 1, "closeEvent must call stop() before Qt teardown"
    with contextlib.suppress(Exception):
        w.close()
```

**objectName introspection (SC#4 / D-07) pattern** — copy from RESEARCH.md `Code Examples` §"objectName introspection test" (already verified against `tests/test_viewport.py` harness); use `w.findChildren(QDockWidget)` + assert all names non-empty + unique.

**Mock-slow-parser close-mid-call (SC#3 / D-09b) pattern** — copy from RESEARCH.md `Code Examples` §"Mock-slow-parser close-mid-call test". The `monkeypatch.setattr(tp.TextParser, "parse_sync", slow_parse_sync)` signature targets `text_parser.py:545` `parse_sync(self, input_data: str | Path, **kwargs) -> SceneDefinition`.

---

### `src/surg_rl/editor/main_window.py` (MODIFIED — controller)

**Analog:** the file itself. The methods being changed are excerpted below at their CURRENT on-disk state (so the executor sees real code, not assumptions).

**Imports pattern** (lines 10-20):
```python
# main_window.py:10-20
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor._safe_error import safe_error_message
from surg_rl.editor._settings import EditorSettings

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition
```
**Add:** `from surg_rl.editor.dock_state import DockStateManager` at module top (it's a same-package module; no heavy import — verify in `dock_state.py` that it imports Qt via `surg_rl.editor` LazyImport, not PySide6 directly). The `aboutToClose` signal declaration must be added at class-body top (`aboutToClose = QtCore.Signal()` per RESEARCH.md Pattern 3).

**`_build_dock_widgets` objectName convention** (lines 91-117) — the convention new docks must follow (`dock_<slug>`):
```python
# main_window.py:91-117 — the objectName convention (D-07 / SC#4): dock_<slug>
self._tree_dock = QtWidgets.QDockWidget("Scene Tree", self)
self._tree_dock.setObjectName("dock_scene_tree")     # ← dock_<slug>
self._tree_dock.setWidget(self._tree_view)
self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)

self._properties_dock = QtWidgets.QDockWidget("Properties", self)
self._properties_dock.setObjectName("dock_properties")  # ← dock_<slug>
...
self._llm_dock = QtWidgets.QDockWidget("LLM Prompt-to-JSON", self)
self._llm_dock.setObjectName("dock_llm")                 # ← dock_<slug>
```

**`_action_reset_layout` CURRENT body** (lines 256-262) — the crude re-`addDockWidget` to REPLACE per D-01/D-02:
```python
# main_window.py:256-262 — REPLACE with DockStateManager.reset_to_default(self)
def _action_reset_layout(self) -> None:
    self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)
    self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self._properties_dock)
    self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self._llm_dock)
    self._tree_dock.show()
    self._properties_dock.show()
    self._llm_dock.show()
```
Replace with a one-liner: `self._dock_state.reset_to_default(self)`. The body above is preserved ONLY as the `_rebuild_default_layout` fallback inside `DockStateManager` (D-01).

**`_refresh_viewport_and_tree` CURRENT body** (lines 306-319) — the widget-recreation to REPLACE per D-06:
```python
# main_window.py:306-319 — REPLACE with update_scene() in-place swap (D-06)
def _refresh_viewport_and_tree(self) -> None:
    from surg_rl.editor.tree_view import SceneTreeView
    from surg_rl.editor.viewport import ViewportPanel

    self._tree_view = SceneTreeView(self._scene or _empty_scene_stub())    # ← RECREATES
    self._tree_dock.setWidget(self._tree_view)
    self._tree_view.node_selected.connect(self._on_node_selected)
    old_panel = self._viewport_panel
    self._viewport_panel = ViewportPanel(                                  # ← RECREATES
        scene=self._scene or _empty_scene_stub(),
        on_fps_update=self._update_fps_status,
    )
    self.setCentralWidget(self._viewport_panel)
    old_panel.stop()
```
Replace with:
```python
self._tree_view.update_scene(self._scene or _empty_scene_stub())
self._viewport_panel.update_scene(self._scene or _empty_scene_stub())
```
Keep the `node_selected` connection intact (it's wired once in `_build_dock_widgets`; since the widget is no longer recreated, the connection survives — do NOT re-connect). NOTE: the current recreation re-connects `node_selected` because the widget is new; the refactored version does NOT need to.

**`closeEvent` CURRENT body** (lines 373-382) — the teardown to EXTEND per D-04/D-05:
```python
# main_window.py:373-382 — EXTEND: emit aboutToClose BEFORE super().closeEvent()
def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
    # Stop the viewport render loop BEFORE Qt tears down — prevents
    # dangling QTimer callbacks and MuJoCo Renderer __del__ crashes
    # during interpreter shutdown (UAT Gap 2 fix, plan 33-07).
    try:  # noqa: SIM105 — best-effort cleanup; broad suppress is intentional
        self._viewport_panel.stop()
    except Exception:  # noqa: BLE001
        pass  # best-effort — don't block window close on viewport cleanup
    self._settings.save_window(self.saveGeometry(), self.saveState())
    super().closeEvent(event)
```
Extend per RESEARCH.md Pattern 3 — emit `aboutToClose` (try/except, best-effort) BEFORE the existing `stop()` + `save_window` + `super().closeEvent(event)`. Keep the existing broad-suppress try/except shape (it matches D-05's "log and proceed" / never block quit).

**`__init__` extension points** (lines 51-85) — add to `__init__`:
1. `self._dock_state = DockStateManager()` (alongside `self._settings = EditorSettings()`)
2. `self.aboutToClose = QtCore.Signal()` declared at class body (PySide6 class-level Signal)
3. `self.aboutToClose.connect(self._llm_panel.stop)` after `self._llm_panel = LLMPanel()` in `_build_dock_widgets` (D-04 wiring)

**`showEvent` (NEW override)** — not currently overridden. Add a `showEvent(self, event)` that calls `self._dock_state.capture_factory_default(self)` (D-01; the guard is inside the manager). Per PySide6 naming, decorate with `# noqa: N802`.

**`_restore_geometry` CURRENT body** (lines 364-371) — UNCHANGED per D-03 (the existing restore path is correct; the bug was widget recreation, not restore timing):
```python
# main_window.py:364-371 — KEEP AS-IS per D-03
def _restore_geometry(self) -> None:
    geo, state = self._settings.load_window()
    if geo is not None:
        self.restoreGeometry(geo)
    else:
        self.resize(1280, 800)
    if state is not None:
        self.restoreState(state)
```

**Error handling convention** — every teardown/cleanup block uses `try: ... except Exception:  # noqa: BLE001` with `pass` (best-effort, never block close). New code in `closeEvent` (aboutToClose emit, future panels' stops) follows the same shape.

---

### `src/surg_rl/editor/llm_panel.py` (MODIFIED — component / QThread owner)

**Analog:** the file itself. The `stop()` method (D-05) generalizes the existing `_on_cancel` (lines 127-131).

**`_on_cancel` CURRENT body** (lines 127-131) — the pattern to generalize into `stop()`:
```python
# llm_panel.py:127-131 — the existing cancel pattern (NO wait()) to generalize
def _on_cancel(self) -> None:
    if self._worker is not None:
        self._worker.setProperty("_cancelled", True)
    if self._thread is not None:
        self._thread.quit()
```

**`_on_generate` QThread wiring** (lines 102-125) — the `finished`/`failed` -> `thread.quit` -> `thread.finished` -> `deleteLater` chain. The `stop()` must NOT additionally call `deleteLater` (Pitfall 4):
```python
# llm_panel.py:114-125 — the existing wiring (KEEP; stop() must NOT touch deleteLater)
self._thread = QtCore.QThread()
self._worker = TextParserWorker(provider=provider, api_key=api_key)
self._worker.moveToThread(self._thread)
self._thread.started.connect(lambda: self._worker.run(prompt))
self._worker.finished.connect(self._on_parse_finished)
self._worker.failed.connect(self._on_parse_failed)
self._worker.finished.connect(self._thread.quit)
self._worker.failed.connect(self._thread.quit)
self._thread.finished.connect(self._thread.deleteLater)  # ← already wired; do NOT re-delete in stop()
```

**`stop()` skeleton** — per RESEARCH.md Pattern 2 + D-05:
```python
# Adapt llm_panel.py:127-131 to D-05 semantics:
def stop(self) -> None:
    if self._worker is not None:
        self._worker.setProperty("_cancelled", True)  # existing _on_cancel pattern
    if self._thread is not None:
        self._thread.quit()
        if not self._thread.wait(3000):
            logger.warning("LLMPanel worker thread did not exit within 3s; proceeding with close")
    # Do NOT call deleteLater here — thread.finished -> deleteLater is already wired (Pitfall 4)
```
**Logger import convention** — mirror `viewport.py:21-23`:
```python
# viewport.py:21-23 — the editor module logger convention
from surg_rl.utils.logging import get_logger
logger = get_logger(__name__)
```
Add `from surg_rl.utils.logging import get_logger` + `logger = get_logger(__name__)` at module top. The timeout warning is `logger.warning(...)` (log-only, NOT user-facing — per Security Domain V5, no `safe_error_message` needed for log-only warnings).

**`_on_cancel` disposition** — per RESEARCH.md "Deprecated/outdated": keep `_on_cancel` calling `self.stop()` (or fold its body into `stop()` and have `_on_cancel` delegate). The Cancel button keeps working; `stop()` is the canonical teardown used by `aboutToClose`.

**`TextParserWorker._cancelled` access pattern** — the existing code uses `self._worker.setProperty("_cancelled", True)` (a dynamic Qt property, not a Python attribute). `stop()` must use the same `setProperty` pattern (consistent with how `_on_cancel` already signals cancel; the worker's `run()` polls the property). Do NOT switch to a Python attribute — the worker lives on the QThread and the property is the cross-thread-safe accessor.

---

### `src/surg_rl/editor/viewport.py` (MODIFIED — component / render surface)

**Analog:** the file itself. `update_scene(scene)` (D-06) mirrors the existing `stop()` simulator-close pattern and the `_tick` lazy-load path. NOTE: 1-line uncommitted change on `main` (does not affect this phase; verified `git diff --stat` = 1 insertion, 1 deletion).

**`stop()` simulator-close pattern** (lines 169-180) — the canonical "close old simulator before swapping" pattern `update_scene` must reuse (Pitfall 7):
```python
# viewport.py:169-180 — the simulator-close pattern update_scene reuses (Pitfall 7)
def stop(self) -> None:
    self._running = False
    if self._simulator is not None:
        # MuJoCo Renderer.__del__ can raise AttributeError
        # ('_gl_context') during interpreter shutdown if the GL
        # context is already destroyed. Swallow it — we're tearing
        # down (UAT Gap 2 fix).
        with contextlib.suppress(AttributeError, OSError):
            self._simulator.close()
        self._simulator = None
```

**`_tick` lazy-load path** (lines 189-209) — the path `update_scene` triggers by setting `self._simulator = None`:
```python
# viewport.py:189-209 — _tick reloads the simulator when it is None.
# update_scene() must set _simulator = None so this path reloads the new scene.
def _tick(self) -> None:
    if not self._running:
        return
    if self._simulator is None:
        try:
            self._simulator = self._on_load_simulator(self._scene)
        except Exception as exc:  # noqa: BLE001
            ...
            QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
            return
```

**`__init__` state** (lines 126-163) — the attributes `update_scene` swaps:
```python
# viewport.py:132-158 — the attributes update_scene resets on scene swap
self._scene = scene                                  # ← swap target
self._on_load_simulator = on_load_simulator or _default_load_simulator
self._simulator: BaseSimulator | None = None         # ← set to None to trigger reload
self._running: bool = True                           # ← keep True (don't halt the loop)
...
self._camera_offset: _CameraOffset = {               # ← reset to factory defaults
    "azimuth": 0.0, "elevation": 0.0, "distance": 2.5, "target": (0.0, 0.0, 0.0)
}
```

**`update_scene` skeleton** — per RESEARCH.md Pattern 4 + Pitfall 7 + A3:
```python
# Adapt viewport.py:169-180 + 390-397 to in-place scene swap (D-06):
def update_scene(self, scene: SceneDefinition) -> None:
    """In-place scene swap — NO widget recreation (D-06, bug #3 fix).

    Closes the old simulator (Pitfall 7), swaps the scene, resets the camera
    (A3 — new scene = fresh view), and lets _tick reload the simulator on the
    next tick (simulator set to None). The widget identity (and thus the dock
    geometry keyed on objectName) is preserved.
    """
    with contextlib.suppress(AttributeError, OSError):
        if self._simulator is not None:
            self._simulator.close()
    self._simulator = None          # forces _tick to reload via _on_load_simulator
    self._scene = scene
    self.reset_camera()             # A3 — reuse viewport.py:390-397
```
Do NOT create a new `ViewportPanel`. Do NOT call `setCentralWidget`. Do NOT halt `_running` (the render loop continues across the swap; next `_tick` reloads the simulator for the new scene).

**`reset_camera` body** (lines 390-397) — already exists; `update_scene` calls it rather than re-implementing:
```python
# viewport.py:390-397 — reused by update_scene (A3)
def reset_camera(self) -> None:
    self._camera_offset: _CameraOffset = {
        "azimuth": 0.0, "elevation": 0.0, "distance": 2.5, "target": (0.0, 0.0, 0.0)
    }
```

---

### `src/surg_rl/editor/tree_view.py` (MODIFIED — component / QTreeView)

**Analog:** the file itself. `update_scene(scene)` (D-06) rebuilds the `QStandardItemModel` in place using the existing `_build_tree`.

**`__init__` model + signal wiring** (lines 56-69) — the wiring `update_scene` must preserve (set in `__init__` on `self`, NOT on the model — so rebuilding model rows preserves connections):
```python
# tree_view.py:56-69 — the signal/selectionModel wiring update_scene must NOT break
def __init__(self, scene: SceneDefinition) -> None:
    super().__init__()
    self._scene = scene
    self._model = QtGui.QStandardItemModel()             # ← rebuild rows in place
    self._model.setHorizontalHeaderLabels(["Scene Elements"])
    self.setModel(self._model)
    self.setHeaderHidden(False)
    self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    self.customContextMenuRequested.connect(self._show_context_menu)  # ← on self, preserved
    self.setDragDropMode(...)
    self.setSelectionMode(...)
    self.selectionModel().currentChanged.connect(self._on_selection_changed)  # ← on self, preserved
    self._build_tree()                                   # ← the in-place rebuild target
    self.expandAll()
```

**`_build_tree` pattern** (lines 71-96) — the row-building logic `update_scene` reuses:
```python
# tree_view.py:71-96 — _build_tree appends a root + section rows to self._model.
# update_scene should clear the model then call _build_tree again.
def _build_tree(self) -> None:
    root = QtGui.QStandardItem(
        self._scene.metadata.name if self._scene.metadata else "Untitled"
    )
    root.setData(_ValidationState.UNVALIDATED, _DATA_ROLE_VALIDATION)
    root.setIcon(_icon_for_state(_ValidationState.UNVALIDATED))
    self._model.appendRow(root)
    for label, attr, is_collection in [
        ("Simulator", "simulator", False),
        ("Environment", "environment", False),
        ...
    ]:
        ...
```

**`update_scene` skeleton** — per RESEARCH.md Pattern 4 + A2:
```python
# Adapt tree_view.py:56-96 to in-place model rebuild (D-06, A2):
def update_scene(self, scene: SceneDefinition) -> None:
    """In-place scene swap — rebuild the QStandardItemModel rows (D-06).

    Swaps self._scene, clears the model, and re-runs _build_tree. The
    selectionModel/customContextMenuRequested/node_selected wiring (set on
    self in __init__) is preserved (A2). NO new SceneTreeView, NO setWidget.
    """
    self._scene = scene
    self._model.clear()
    self._model.setHorizontalHeaderLabels(["Scene Elements"])  # clear() drops headers
    self._build_tree()
    self.expandAll()
```
**NOTE:** `QStandardItemModel.clear()` drops the horizontal header labels — re-set them after `clear()` (verified against the `__init__` order which sets headers after `QStandardItemModel()`). The `selectionModel()` is recreated by Qt when the model is reset via `setModel`; since we do NOT call `setModel` again (we reuse `self._model` and only `clear()` + repopulate it), the existing `selectionModel` connection survives (A2 — verify in implementation; if `clear()` resets selectionModel, re-wire `selectionModel().currentChanged.connect(self._on_selection_changed)` after `clear()`).

---

### `src/surg_rl/editor/_settings.py` (MODIFIED — extend only if needed)

**Analog:** the file itself. Per D-03, the existing `save_window`/`load_window` (lines 39-48) is sufficient — extend ONLY if `DockStateManager` needs a persistence key (it does NOT, per D-01: factory default is NOT persisted).

**`save_window`/`load_window` CURRENT body** (lines 39-48) — UNCHANGED this phase:
```python
# _settings.py:39-48 — the existing QSettings plumbing (KEEP per D-03)
def save_window(self, geometry: QByteArray, state: QByteArray) -> None:
    self._q.setValue("window/geometry", geometry)
    self._q.setValue("window/state", state)
    self._q.sync()

def load_window(self) -> tuple[QByteArray | None, QByteArray | None]:
    return (
        self._q.value("window/geometry", type=QByteArray),
        self._q.value("window/state", type=QByteArray),
    )
```
The factory-default `QByteArray` owned by `DockStateManager` is NOT persisted here (D-01 — recomputed each launch from the first `showEvent`). No new keys. No change expected to `_settings.py` this phase (listed as MODIFIED for completeness; if no extension is needed, leave the file untouched).

**No-secrets convention** — the module docstring (`_settings.py:8-9`) states "No API keys are stored here." Any new key added in future phases must honor this; `DockStateManager` adds nothing to QSettings, so the convention is upheld.

---

## Shared Patterns

### Lazy-import / HAS_GUI discipline
**Source:** `src/surg_rl/editor/__init__.py:31-42` + `src/surg_rl/editor/undo_stack.py:17-26`
**Apply to:** `src/surg_rl/editor/dock_state.py` (the only NEW editor module)
```python
# editor/__init__.py:31-42 — the LazyImport sentinel + HAS_GUI guard
from surg_rl.utils.lazy_imports import LazyImport
QtWidgets = LazyImport("PySide6.QtWidgets", "gui")
QtCore = LazyImport("PySide6.QtCore", "gui")
QtGui = LazyImport("PySide6.QtGui", "gui")
HAS_GUI: bool = QtWidgets.available
```
**Rule:** new `dock_state.py` imports Qt symbols via `from surg_rl.editor import QtCore, QtWidgets` (the LazyImport proxies), NOT `from PySide6 import ...` at module top. `from __future__ import annotations` + `TYPE_CHECKING` for any heavy model imports.

### Best-effort teardown (broad suppress)
**Source:** `src/surg_rl/editor/main_window.py:377-380`
**Apply to:** `closeEvent` (aboutToClose emit, each panel's stop() call); `LLMPanel.stop()` timeout; `ViewportPanel.update_scene()` simulator close
```python
# main_window.py:377-380 — the canonical best-effort teardown suppress
try:  # noqa: SIM105 — best-effort cleanup; broad suppress is intentional
    self._viewport_panel.stop()
except Exception:  # noqa: BLE001
    pass  # best-effort — don't block window close
```
**Rule:** close/teardown paths NEVER block quit. `# noqa: BLE001` + `# noqa: SIM105` are the established markers. `LLMPanel.stop()` on `wait()` timeout logs `logger.warning(...)` and proceeds (D-05).

### Logger convention
**Source:** `src/surg_rl/editor/viewport.py:21-23`
**Apply to:** `src/surg_rl/editor/dock_state.py` (if it logs) + `src/surg_rl/editor/llm_panel.py` (for `stop()` timeout warning)
```python
# viewport.py:21-23
from surg_rl.utils.logging import get_logger
logger = get_logger(__name__)
```
**Rule:** use `get_logger(__name__)` at module top; `logger.warning(...)` for the `wait()` timeout (log-only — per Security Domain V5, log-only messages do NOT need `safe_error_message` redaction; only user-facing error strings do).

### User-facing error redaction
**Source:** `src/surg_rl/editor/_safe_error.py` + `src/surg_rl/editor/llm_panel.py:38,144`
**Apply to:** any error string surfaced to the user (status bar, message box) from a teardown path
```python
# llm_panel.py:37-38 — the existing redaction pattern for user-facing errors
except Exception as exc:  # noqa: BLE001
    self.failed.emit(safe_error_message(exc))
```
**Rule:** `safe_error_message(exc)` wraps any error shown to the user. The `LLMPanel.stop()` timeout warning is `logger.warning(...)` (log-only, NOT user-facing) — no redaction needed. If a future phase surfaces the timeout to the status bar, route it through `safe_error_message`.

### objectName convention
**Source:** `src/surg_rl/editor/main_window.py:101-114`
**Apply to:** any future dock added to `EditorWindow` (Phase 42/43/44/45/46/47/48/51)
```python
# main_window.py:101-114 — dock_<slug> convention (SC#4 / D-07 enforces via introspection)
self._tree_dock.setObjectName("dock_scene_tree")     # dock_<slug>
self._properties_dock.setObjectName("dock_properties") # dock_<slug>
self._llm_dock.setObjectName("dock_llm")             # dock_<slug>
```
**Rule:** every `QDockWidget` gets `setObjectName("dock_<slug>")` at construction. The SC#4 introspection test (`tests/test_dock_state.py::TestDockObjectNames`) catches any future dock missing an objectName.

### Signal declaration convention
**Source:** `src/surg_rl/editor/llm_panel.py:22-23,46` + `src/surg_rl/editor/tree_view.py:54`
**Apply to:** `EditorWindow.aboutToClose` (the one new signal this phase)
```python
# llm_panel.py:22-23 — class-level Signal declarations
class TextParserWorker(QtCore.QObject):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

# llm_panel.py:46
class LLMPanel(QtWidgets.QWidget):
    scene_accepted = QtCore.Signal(object)
```
**Rule:** `aboutToClose = QtCore.Signal()` declared at `EditorWindow` class-body top (no payload — it's a pure teardown trigger). Connect in `__init__` after the panel is constructed: `self.aboutToClose.connect(self._llm_panel.stop)`.

### offscreen GUI test harness
**Source:** `tests/gui/conftest.py:1-35` + `tests/test_viewport.py:13-67`
**Apply to:** `tests/test_dock_state.py` (the one new test file)
```python
# tests/gui/conftest.py:10-35 — module-top offscreen + skipif + qapp + isolated_home
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False

@pytest.fixture(scope="session")
def qapp():
    if not _HAVE_PYSIDE6:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)

@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path
```
**Rule:** module-top `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` + `pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")`. `isolated_home` is mandatory for any test that constructs `EditorWindow` (QSettings would otherwise pollute the developer's real `~/Library/Preferences/com.SurgRL.SceneEditor.plist`).

## No Analog Found

None — every new/modified file has a real on-disk analog. The two NEW files (`dock_state.py`, `tests/test_dock_state.py`) have same-package / same-test-tree siblings to mirror; all MODIFIED files are read at their current state above.

## Metadata

**Analog search scope:**
- `src/surg_rl/editor/` — `__init__.py`, `_settings.py`, `undo_stack.py`, `main_window.py`, `llm_panel.py`, `viewport.py`, `tree_view.py`
- `tests/` — `test_gui_scaffold.py`, `test_viewport.py`
- `tests/gui/` — `conftest.py`, `test_editor_smoke.py`

**Files scanned:** 9 source/test files (all read in full; none exceeded 2,000 lines — `test_viewport.py` is the longest at 716 lines)

**Mid-modification verification:** `git diff --stat src/surg_rl/editor/viewport.py` = 1 line changed, 1 deletion (confirmed minor; current on-disk state read in full and reflected above)

**Pattern extraction date:** 2026-07-15