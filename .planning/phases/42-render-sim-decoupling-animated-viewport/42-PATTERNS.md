# Phase 42: Render/Sim Decoupling & Animated Viewport - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 7 (4 new + 3 modified) plus 1 extended test file
**Analogs found:** 8 / 8 (every new/modified file has a real on-disk analog; all modifications read the file itself; both new editor modules have same-package siblings to mirror; all new test files have the Phase 41 offscreen test harness to mirror)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/surg_rl/editor/sim_step_worker.py` (NEW) | service / QThread worker-object | event-driven (QTimer accumulator ~50 Hz) + pub-sub (queued `snapshot_ready` ~30 Hz cap) | `src/surg_rl/editor/llm_panel.py` (`TextParserWorker` QThread worker-object + `LLMPanel.stop()` cooperative teardown) | exact (only existing `QThread` worker-object in the editor — `moveToThread` + `finished`/`failed` + `stop()` template) |
| `src/surg_rl/editor/render_poll_loop.py` (NEW) | component / UI-thread render loop | event-driven (self-rescheduling `QTimer.singleShot` ~30 Hz) + transform (snapshot → pixmap) | `src/surg_rl/editor/viewport.py` `_tick` (lines 189–290) + `stop()` (169–180) | exact (the monolithic loop being split along this seam; reuse the `_running` guard, self-rescheduling discipline, `_display_array`, `_editor_camera_*` push, `_maybe_update_fps`) |
| `src/surg_rl/editor/viewport.py` (MODIFIED) | component / render surface | event-driven (split `_tick`) + in-place state swap | the file itself (`_tick`, `stop()`, `update_scene()`, `_display_array`, `_maybe_update_fps`) | exact (read current method bodies below) |
| `src/surg_rl/editor/main_window.py` (MODIFIED) | controller / QMainWindow | event-driven (close, shortcuts, playback) + request-response (`update_scene`) | the file itself + Phase 41 `aboutToClose` wiring | exact |
| `tests/test_sim_step_worker.py` (NEW) | test | offscreen unit/integration (MockSimulator + controllable clock) | `tests/test_dock_state.py` (`TestCloseMidCallMockSlow` + `qapp`/`isolated_home` fixtures + `pytestmark skipif`) | exact (offscreen GUI test pattern) |
| `tests/test_render_poll_loop.py` (NEW) | test | offscreen unit/integration (MockSimulator + snapshot injection) | `tests/test_dock_state.py` + `tests/test_viewport.py` (offscreen harness) | exact |
| `tests/test_viewport_playback.py` (NEW) | test | offscreen integration (toolbar/shortcuts/status-bar/load-paused/teardown) | `tests/test_dock_state.py` (`TestDockObjectNames`, `TestAboutToClose`, `TestCloseMidCallMockSlow`) | exact |
| `tests/test_dock_state.py` (EXTENDED — `TestDockObjectNames`) | test | offscreen GUI introspection | the file itself (extend to also collect `QToolBar` children) | exact |
| `src/surg_rl/simulators/base_simulator.py` (UNCHANGED — reused primitives) | model / ABC | request-response (`step`/`render`/`get_state`/`close`) | the file itself | N/A (no change; `step:219`, `render:231`, `get_state:252`, `close:270` are the reused primitives) |

## Pattern Assignments

### `src/surg_rl/editor/sim_step_worker.py` (NEW — service / QThread worker-object)

**Analogs:** `src/surg_rl/editor/llm_panel.py` (the only existing `QThread` worker-object pattern in the editor) + `src/surg_rl/editor/viewport.py` (`stop()`/`_running` guard for the accumulator timer halt) + `src/surg_rl/editor/__init__.py` (LazyImport discipline).

**Lazy-import / HAS_GUI discipline** — mirror `editor/__init__.py:31-42` (new `sim_step_worker.py` imports Qt via the LazyImport proxies, NOT `from PySide6 import ...`):
```python
# editor/__init__.py:31-42 — the discipline new editor modules follow
from surg_rl.utils.lazy_imports import LazyImport
QtWidgets = LazyImport("PySide6.QtWidgets", "gui")
QtCore = LazyImport("PySide6.QtCore", "gui")
QtGui = LazyImport("PySide6.QtGui", "gui")
HAS_GUI: bool = QtWidgets.available
```

**Imports pattern** — copy the shape of `llm_panel.py:1-14` (module-top `from __future__ import annotations` + `TYPE_CHECKING`, Qt via `from surg_rl.editor import QtCore`, `get_logger(__name__)`):
```python
# llm_panel.py:1-14 — the canonical small-editor-module imports
from __future__ import annotations

from typing import TYPE_CHECKING

from surg_rl.editor import QtCore
from surg_rl.utils.logging import get_logger

if TYPE_CHECKING:
    from surg_rl.simulators.base_simulator import BaseSimulator

logger = get_logger(__name__)
```

**QObject worker + Signal declaration pattern** — copy `llm_panel.py:17-26` (class-level `Signal` declarations, `super().__init__()`, private state attrs):
```python
# llm_panel.py:17-26 — TextParserWorker(QObject) class shape
class TextParserWorker(QtCore.QObject):
    """QObject worker that calls TextParser.parse_sync() on a QThread (per D-13)."""
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, provider: str | None, api_key: str | None) -> None:
        super().__init__()
        self._provider = provider
        self._api_key = api_key
```
For `SimStepWorker` declare `snapshot_ready = QtCore.Signal(object)` (payload = `State` or a `_Snapshot` wrapper with `frame_id`; implementer's discretion per CONTEXT, but a wrapper with a monotonic `frame_id` is required by the render-poll's "new snapshot?" check).

**QThread wiring pattern** — copy `llm_panel.py:117-128` (the `moveToThread` + `started`→work + `finished`/`failed`→`thread.quit` + `thread.finished`→`deleteLater` chain). The controller (`EditorWindow`) owns this wiring; `SimStepWorker` itself does NOT call `moveToThread`:
```python
# llm_panel.py:117-128 — the QThread worker-object wiring SimStepWorker mirrors
self._thread = QtCore.QThread()
self._worker = TextParserWorker(provider=provider, api_key=api_key)
self._worker.moveToThread(self._thread)
self._thread.started.connect(lambda: self._worker.run(prompt))
self._worker.finished.connect(self._on_parse_finished)
self._worker.failed.connect(self._on_parse_failed)
self._worker.finished.connect(self._thread.quit)
self._worker.failed.connect(self._thread.quit
self._thread.finished.connect(self._thread.deleteLater)  # deleteLater ONLY here
self._thread.start()
```
**For `SimStepWorker`** the wiring is: `moveToThread` + `thread.started.connect(worker.start)` (the `start` slot creates the accumulator `QTimer` so its affinity is the worker thread) + `snapshot_ready.connect(render_loop.on_snapshot, Qt.QueuedConnection)` + `thread.finished.connect(thread.deleteLater)`. Do NOT call `deleteLater` from `stop()` (Pitfall 4).

**`stop()` cooperative-teardown pattern** — copy `llm_panel.py:130-158` VERBATIM in shape (cancel flag + `thread.quit()` + `thread.wait(3000)` + log-on-timeout + NEVER `terminate()` + NEVER `deleteLater`). `SimStepWorker.stop()` sets the cancel flag + stops the accumulator `QTimer`; the controller (`EditorWindow`) calls `thread.quit()`+`thread.wait(3000)` (mirroring `LLMPanel.stop()` which owns the thread):
```python
# llm_panel.py:130-158 — the D-05 cooperative teardown template
def stop(self) -> None:
    if self._worker is not None:
        # Cross-thread cancel flag (dynamic Qt property — the worker polls it;
        # do NOT switch to a Python attribute, the worker lives on the QThread
        # and the property is the thread-safe accessor).
        self._worker.setProperty("_cancelled", True)
    if self._thread is not None:
        self._thread.quit()
        if not self._thread.wait(3000):
            logger.warning(
                "LLMPanel worker thread did not exit within 3s; "
                "proceeding with close"
            )
    # Do NOT call deleteLater here — thread.finished -> deleteLater is
    # already wired in _on_generate (Pitfall 4).
```
**Adaptation for `SimStepWorker`:** the worker itself sets `self._cancelled = True` + `self._timer.stop()`; the `QThread`/`quit()`/`wait(3000)` lives on the controller that owns the `QThread` (mirror `LLMPanel` which owns both `_worker` and `_thread`). See `main_window.py` assignment for the controller-side wiring. The `aboutToClose.connect(self._sim_worker.stop)` mirror at `main_window.py:139` is the trigger.

**Worker `@Slot` pattern** — `TextParserWorker.run` uses `@QtCore.Slot(str)` (`llm_panel.py:36-43`); `SimStepWorker` uses `@QtCore.Slot()` / `@QtCore.Slot(bool)` / `@QtCore.Slot(float)` / `@QtCore.Slot(object)` for `start`/`set_paused`/`set_speed`/`step_one`/`bind_scene`. The try/except inside `run` (`llm_panel.py:38-42`) emits `failed` with `safe_error_message(exc)` — `SimStepWorker` is a long-running loop, so its `_tick` should NOT emit failed on every transient error; instead log + continue (or skip the tick). See RESEARCH.md Pattern 1 for the accumulator skeleton.

**`simulator.step(None)` — the physics-only advance** — VERIFIED in RESEARCH.md against `mujoco_simulator.py:220-221` and `pybullet_simulator.py:946-947` (both guard `if action is not None: self._apply_action(action)`). The worker calls `self._simulator.step(None)` — no zero-vector synthesis, no `get_num_controls()` probe, no RL policy. Backend-agnostic.

**`_running` guard for the accumulator timer** — mirror `viewport.py:142,190-191,289-290` (set `_running=False`/`_cancelled=True` at the top of `stop()` so already-queued `QTimer` callbacks early-return):
```python
# viewport.py:189-191 + 289-290 — the guard pattern RenderPollLoop + the
# SimStepWorker accumulator tick must both check at the top.
def _tick(self) -> None:
    if not self._running:
        return  # stop() was called — halt the render loop
    ...
    if self._running:
        QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
```

---

### `src/surg_rl/editor/render_poll_loop.py` (NEW — component / UI-thread render loop)

**Analog:** `src/surg_rl/editor/viewport.py` `_tick` (lines 189–290) — the monolithic self-rescheduling `QTimer.singleShot` loop being split along this seam. The render half (camera push + `render()` + `_display_array` + `_maybe_update_fps` + self-reschedule with `_running` guard) moves here. The (currently absent) `step()` responsibility moves onto `SimStepWorker`.

**Imports pattern** — mirror `viewport.py:10-23` (Qt via `from surg_rl.editor import QtCore, QtGui, QtWidgets`, `get_logger(__name__)`, `TYPE_CHECKING` for `SceneDefinition`/`BaseSimulator`):
```python
# viewport.py:10-23 — the editor render-module imports
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, TypedDict

import numpy as np

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition
    from surg_rl.simulators.base_simulator import BaseSimulator
```

**Self-rescheduling `QTimer.singleShot` + `_running` guard pattern** — copy `viewport.py:165-180, 189-191, 287-290` (the entire render loop skeleton; `RenderPollLoop._tick` inherits this verbatim, only changing the body to read the latest snapshot instead of calling `render()` synchronously off the same loop as `step()`):
```python
# viewport.py:165-180 — _start + stop() with the _running guard
def _start(self) -> None:
    self._running = True
    QtCore.QTimer.singleShot(0, self._tick)

def stop(self) -> None:
    # Halt the render loop — _tick checks _running at the top and before
    # rescheduling, so already-queued QTimer callbacks become no-ops.
    self._running = False
    if self._simulator is not None:
        with contextlib.suppress(AttributeError, OSError):
            self._simulator.close()
        self._simulator = None
```
```python
# viewport.py:189-191 + 287-290 — the guard at both ends of _tick
def _tick(self) -> None:
    if not self._running:
        return  # stop() was called — halt the render loop
    ...
    # Only reschedule if still running — stop() may have been called
    # during render (UAT Gap 2 fix: prevents dangling QTimer callbacks).
    if self._running:
        QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
```
**Adaptation:** `RenderPollLoop.stop()` does NOT close the simulator (the `ViewportPanel.stop()` / `update_scene` path closes the shared simulator after pausing the worker — see the `viewport.py` assignment). `RenderPollLoop.stop()` only sets `_running=False`. The new `_FRAME_INTERVAL_MS = 33` (~30 Hz, replacing the old 50 ms / 20 Hz).

**Camera-offset push-into-simulator pattern** — copy `viewport.py:220-236` VERBATIM (this block stays on the render side per D-05; `render()` is called on the UI thread only, and the camera offsets are panel-local/ephemeral):
```python
# viewport.py:220-236 — push _editor_camera_* into the simulator before render
try:
    object.__setattr__(
        self._simulator, "_editor_camera_target", self._camera_offset["target"]
    )
    object.__setattr__(
        self._simulator, "_editor_camera_distance", self._camera_offset["distance"]
    )
    object.__setattr__(
        self._simulator, "_editor_camera_azimuth", self._camera_offset["azimuth"]
    )
    object.__setattr__(
        self._simulator, "_editor_camera_elevation", self._camera_offset["elevation"]
    )
except Exception:  # noqa: BLE001
    pass
```

**`render()` call + framebuffer retry pattern** — copy `viewport.py:237-274` (the `render(mode="rgb_array", width, height, camera_name)` call + the high-DPI `framebuffer`/`offwidth` retry at 640×480). `RenderPollLoop` reuses this whole block. `camera_name` is read from `scene.environment.cameras[0].name` (`viewport.py:212-217`).

**`_display_array` + `_maybe_update_fps` pattern** — copy `viewport.py:292-353` VERBATIM (these are pure render-side helpers; relocate them onto `RenderPollLoop` or have `RenderPollLoop` call into `ViewportPanel` for them — implementer's discretion per CONTEXT "Claude's Discretion" bullet 2). `_maybe_update_fps` uses `time.monotonic()` with a 1 s window (`viewport.py:293-304`) — the fps-counter state (`_frame_count`, `_last_fps_check`) moves with it.

**Skip-when-no-new-snapshot pattern** — NEW (no existing analog; the render-poll reads `self._latest_snapshot.frame_id` and skips `render()` when it equals `_last_rendered_id`). See RESEARCH.md Pattern 2 for the recommended shape. The initial-static-frame case (snapshot is `None` while paused on load) renders once so the user sees the scene, then only re-renders on new `frame_id`s.

**Error handling pattern** — `viewport.py:243-274` wraps `render()` in `try/except Exception: # noqa: BLE001` and routes user-facing strings through `safe_error_message` (`from surg_rl.editor._safe_error import safe_error_message`). `RenderPollLoop` reuses this. On error it sets `self._canvas.set_text(...)` + reschedules (does NOT halt the loop).

---

### `src/surg_rl/editor/viewport.py` (MODIFIED — component / render surface)

**Analog:** the file itself. The methods being changed are excerpted below at their CURRENT on-disk state.

**`_tick` CURRENT body** (lines 189–290) — SPLIT per D-01: the render half (212–285 + camera push 220–236 + framebuffer retry 243–274 + `_display_array` + `_maybe_update_fps` + reschedule 289–290) moves into `RenderPollLoop`; the (currently absent) `step()` responsibility moves onto `SimStepWorker`. `ViewportPanel._tick` is REMOVED (replaced by delegating to `self._render_loop`). The lazy-load path (193–209) stays on the UI thread — the simulator is loaded + GL-probed on the UI thread by `_default_load_simulator` (`render()` is thread-affine), then handed to the worker via `bind_scene` (queued). See the `sim_step_worker.py` assignment for the `QThread` wiring.
```python
# viewport.py:189-290 — the monolithic loop being split (excerpt: the structure)
def _tick(self) -> None:
    if not self._running:
        return
    if self._simulator is None:                              # lazy-load — STAYS on UI thread
        try:
            self._simulator = self._on_load_simulator(self._scene)
        except Exception as exc:  # noqa: BLE001
            ...
            QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
            return
    try:
        # camera push 220-236 — MOVES to RenderPollLoop (ephemeral, D-05)
        # sim.render(...) 237-242 — MOVES to RenderPollLoop (UI thread only)
    except Exception as exc:  # noqa: BLE001
        # framebuffer retry 243-274 — MOVES to RenderPollLoop
    if arr is not None:
        self._display_array(arr)                             # MOVES to RenderPollLoop
    self._frame_count += 1
    self._maybe_update_fps()                                 # MOVES to RenderPollLoop
    if self._running:
        QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)  # MOVES to RenderPollLoop
```

**`stop()` CURRENT body** (lines 169–180) — GENERALIZE to also stop the render-loop + pause the worker BEFORE closing the shared simulator (Pitfall 3 — closing the simulator while the worker is mid-step). Keep the `contextlib.suppress(AttributeError, OSError)` simulator-close pattern VERBATIM:
```python
# viewport.py:169-180 — the simulator-close pattern (KEEP the suppress shape)
def stop(self) -> None:
    self._running = False
    if self._simulator is not None:
        # MuJoCo Renderer.__del__ can raise AttributeError during shutdown.
        with contextlib.suppress(AttributeError, OSError):
            self._simulator.close()
        self._simulator = None
```
**Generalized `stop()` (D-04 + Pitfall 3):** call `self._render_loop.stop()` (sets `_running=False`) + `self._sim_worker.set_paused(True)` (queued; OR use `QMetaObject.invokeMethod(..., BlockingQueuedInvocation)` per RESEARCH Pitfall 3 to synchronously halt the accumulator before close) BEFORE the `contextlib.suppress(...)` `simulator.close()` block. The `aboutToClose` signal already fires before `viewport.stop()` in `closeEvent` (`main_window.py:400` then `:407`), so the worker is already cancelled; `viewport.stop()` is the belt-and-braces pause-before-close for the `update_scene` swap path.

**`update_scene()` CURRENT body** (lines 399–415) — EXTEND per D-11 + Pattern 4 (re-binds worker + render-loop to the new scene through the in-place swap; loads paused). KEEP the in-place swap (NO widget recreation — Phase 41 D-06); add the worker re-bind + load-paused steps. The order MUST be: pause worker → close old sim → swap scene + reset camera → load new sim on UI thread → `render_loop.bind_simulator(new_sim)` → `sim_worker.bind_scene.emit(new_sim)` (queued) → set paused (D-11):
```python
# viewport.py:399-415 — the existing in-place swap (KEEP, EXTEND with re-bind + paused)
def update_scene(self, scene: SceneDefinition) -> None:
    with contextlib.suppress(AttributeError, OSError):
        if self._simulator is not None:
            self._simulator.close()
    self._simulator = None  # forces _tick to reload via _on_load_simulator
    self._scene = scene
    self.reset_camera()  # A3 — new scene = fresh view
```
See RESEARCH.md Pattern 4 for the full extended skeleton (steps 1–5). Load paused per D-11: `self._sim_worker.set_paused(True)` after `bind_scene`; the toolbar/status reflect it via the playback-state callback.

**`reset_camera` body** (lines 390–397) — UNCHANGED; `update_scene` calls it.

**`_default_load_simulator` body** (lines 418–482) — UNCHANGED; the worker reuses whatever simulator the loader returns. The loader probes GL on the UI thread (`sim.render(...)` at 467–472) — keep loading + probing on the UI thread, hand the live simulator to the worker.

---

### `src/surg_rl/editor/main_window.py` (MODIFIED — controller / QMainWindow)

**Analog:** the file itself. The methods being changed are excerpted below at their CURRENT on-disk state.

**Imports pattern** (lines 10-20) — add `SimStepWorker` import:
```python
# main_window.py:10-20 — CURRENT imports
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor._safe_error import safe_error_message
from surg_rl.editor._settings import EditorSettings
from surg_rl.editor.dock_state import DockStateManager

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition
```
**Add:** `from surg_rl.editor.sim_step_worker import SimStepWorker` (same-package; verify it imports Qt via `surg_rl.editor` LazyImport, not PySide6 directly).

**`aboutToClose` declaration** (line 59) — ALREADY DECLARED in Phase 41:
```python
# main_window.py:59 — the milestone-wide teardown contract SimStepWorker plugs into
aboutToClose = QtCore.Signal()  # noqa: N815 — Qt Signal naming convention
```

**`_viewport_panel` creation** (lines 80–84) — EXTEND in `__init__` to also create the `QThread` + `SimStepWorker` + `RenderPollLoop`:
```python
# main_window.py:80-84 — CURRENT ViewportPanel creation
self._viewport_panel = ViewportPanel(
    scene=self._scene or _empty_scene_stub(),
    on_fps_update=self._update_fps_status,
)
self.setCentralWidget(self._viewport_panel)
```
**Add (per RESEARCH.md System Architecture Diagram):**
```python
# Mirror llm_panel.py:117-128 for the QThread wiring:
self._sim_thread = QtCore.QThread()
self._sim_worker = SimStepWorker()
self._sim_worker.moveToThread(self._sim_thread)
self._sim_thread.started.connect(self._sim_worker.start)
self._sim_thread.finished.connect(self._sim_thread.deleteLater)  # ONLY here
# RenderPollLoop lives on the UI thread (constructed here, NOT moveToThread).
# Connect snapshot_ready (queued) -> render_loop.on_snapshot.
self._sim_thread.start()
```
The `RenderPollLoop` is constructed with refs to `self._viewport_panel` (canvas + camera_offset + simulator ref + `on_fps_update` callback) — implementer's discretion per CONTEXT on whether `RenderPollLoop` owns `_display_array`/`_maybe_update_fps` or delegates back to `ViewportPanel`.

**`aboutToClose.connect(self._llm_panel.stop)` pattern** (line 139) — MIRROR for `SimStepWorker.stop()`:
```python
# main_window.py:136-139 — the D-04 wiring pattern to mirror
# D-04 wiring: register LLMPanel.stop() on aboutToClose so closeEvent
# tears down the LLM worker thread before Qt deletes the panel (SC#3).
# Future workers connect their stop() here too — no closeEvent edit.
self.aboutToClose.connect(self._llm_panel.stop)
```
**Add immediately after:** `self.aboutToClose.connect(self._sim_worker.stop)`. The `stop()` method on the controller side (NOT `SimStepWorker.stop()` which only flags cancel + stops the timer) — implementer's discretion on whether `EditorWindow` owns the `thread.quit()`+`wait(3000)` (mirror `LLMPanel.stop()` which owns both `_worker` and `_thread`) or `SimStepWorker.stop()` does. RESEARCH.md Pattern 1 note says: "the controller's job (`EditorWindow` owns the `QThread` and calls `quit()`+`wait(3000)`, mirroring `LLMPanel.stop()`)." Pick that: `EditorWindow._on_about_to_close` (or a dedicated `self._stop_sim_worker`) calls `self._sim_worker.stop()` (flags cancel + stops accumulator) then `self._sim_thread.quit()` + `self._sim_thread.wait(3000)` + log-on-timeout (copy `llm_panel.py:150-156` shape). Keep ONE teardown path.

**`_wire_shortcuts` CURRENT body** (lines 180-183) — EXTEND with `Space` (play/pause) and `.` (step-one) `QShortcut`s. `Ctrl+R` (camera reset) stays unchanged. Per Phase 33 D-12, shortcuts on the main window, not per-widget:
```python
# main_window.py:180-183 — CURRENT shortcuts
def _wire_shortcuts(self) -> None:
    # Cmd+R / Ctrl+R for camera reset (D-04).
    reset_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self)
    reset_shortcut.activated.connect(self._viewport_panel.reset_camera)
```
**Add (per RESEARCH.md Pattern 3):**
```python
QtGui.QShortcut(QtGui.QKeySequence("Space"), self).activated.connect(self._toggle_play_pause)
QtGui.QShortcut(QtGui.QKeySequence("."), self).activated.connect(self._on_step_one)
```

**`_build_status_bar` CURRENT body** (lines 204-213) — EXTEND with a 5th permanent `QLabel` `_status_playback` (D-08). KEEP the `Panel`/`Sunken` frame shape for visual consistency:
```python
# main_window.py:204-213 — the 4-permanent-label row to extend
def _build_status_bar(self) -> None:
    bar = self.statusBar()
    self._status_path = QtWidgets.QLabel("Untitled")
    self._status_sim = QtWidgets.QLabel("—")
    self._status_fps = QtWidgets.QLabel("—")
    self._status_validation = QtWidgets.QLabel("—")
    for w in (self._status_path, self._status_sim, self._status_fps, self._status_validation):
        w.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        bar.addPermanentWidget(w)
```
**Add:** `self._status_playback = QtWidgets.QLabel("⏸ paused")` to the tuple + `addPermanentWidget`. Add a `_update_playback_status(playing, speed, static=False)` helper (RESEARCH.md Pattern 3) that routes any user-facing string through `safe_error_message` if it includes scene content (keep the static-scene hint generic — "static scene — no dynamics" — no redaction needed for the generic string per Security Domain V5).

**`_update_fps_status` CURRENT body** (lines 221-228) — UNCHANGED; the playback segment is updated by a separate `_update_playback_status` callback, not by `_update_fps_status`:
```python
# main_window.py:221-228 — the fps label stays as-is
def _update_fps_status(self, fps: float) -> None:
    path_label = self._current_path.name if self._current_path else "Untitled"
    sim_label = (
        self._scene.simulator.value
        if self._scene and hasattr(self._scene.simulator, "value")
        else "—"
    )
    self._set_status(path_label, sim_label, f"{fps:.1f}", "—")
```

**Playback toolbar pattern (D-06/D-09)** — NEW method `_build_playback_toolbar` (no existing `QToolBar` in the editor; mirror the `objectName` discipline from `_build_dock_widgets` at `main_window.py:119-132`):
```python
# main_window.py:119-132 — the objectName discipline (dock_<slug>) the toolbar
# follows (extend to toolbar_<slug> per CONTEXT "Claude's Discretion")
self._tree_dock = QtWidgets.QDockWidget("Scene Tree", self)
self._tree_dock.setObjectName("dock_scene_tree")     # ← dock_<slug>
self._tree_dock.setWidget(self._tree_view)
self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)
```
**Toolbar skeleton (per RESEARCH.md Pattern 3):** `QToolBar("Playback")` + `setObjectName("toolbar_playback")` BEFORE `addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, tb)` (Pitfall 7 — `saveState()` identifies toolbars by `objectName`). Play/Pause `QAction` (toggle, `setCheckable(True)`), Step-one `QAction`, speed `QComboBox` with items `["0.25x", "0.5x", "1x", "2x", "4x"]`, `setCurrentText("1x")` (D-10 default 1x, session-only), `setObjectName("combo_playback_speed")` on the combo. Connect `toggled`/`triggered`/`currentTextChanged` to handlers that emit queued signals to the worker's `set_paused`/`step_one`/`set_speed` slots.

**`_refresh_viewport_and_tree` CURRENT body** (lines 323-332) — UNCHANGED; `update_scene` (the extended one above) handles load-paused. `update_scene` call at `:332` is the D-11 entry point:
```python
# main_window.py:323-332 — the in-place swap entry point (D-11 loads paused
# inside ViewportPanel.update_scene, NOT here)
def _refresh_viewport_and_tree(self) -> None:
    self._tree_view.update_scene(self._scene or _empty_scene_stub())
    self._viewport_panel.update_scene(self._scene or _empty_scene_stub())
```

**`closeEvent` CURRENT body** (lines 394-411) — UNCHANGED. `aboutToClose.emit()` at `:400` already triggers `_sim_worker.stop()` (wired in `__init__`); `viewport.stop()` at `:407` closes the shared simulator AFTER the worker is cancelled. The ordering `aboutToClose` → `viewport.stop()` is the Pitfall 3 guarantee — preserve it:
```python
# main_window.py:394-411 — UNCHANGED. aboutToClose (line 400) fires BEFORE
# viewport.stop() (line 407) — SimStepWorker.stop() is wired via aboutToClose
# so the worker is cancelled BEFORE the shared simulator is closed.
def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
    try:  # noqa: SIM105 — best-effort teardown; broad suppress is intentional
        self.aboutToClose.emit()
    except Exception:  # noqa: BLE001
        pass
    try:  # noqa: SIM105 — best-effort cleanup; broad suppress is intentional
        self._viewport_panel.stop()
    except Exception:  # noqa: BLE001
        pass
    self._settings.save_window(self.saveGeometry(), self.saveState())
    super().closeEvent(event)
```

**Error handling convention** — every teardown/cleanup block uses `try: ... except Exception:  # noqa: BLE001` with `pass` (best-effort, never block close). New `stop()` / `set_paused` / `bind_scene` paths follow the same shape. The `wait()` timeout is `logger.warning(...)` (log-only, NOT user-facing — no `safe_error_message` redaction needed).

---

### `tests/test_sim_step_worker.py`, `tests/test_render_poll_loop.py`, `tests/test_viewport_playback.py` (NEW — offscreen GUI tests)

**Analog:** `tests/test_dock_state.py` (the Phase 41 offscreen test harness the new test files mirror).

**Offscreen harness pattern** — copy `tests/test_dock_state.py:19-55` VERBATIM (module-top offscreen + skipif + `qapp` + `isolated_home`):
```python
# tests/test_dock_state.py:19-55 — the canonical offscreen harness
from __future__ import annotations

import contextlib
import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")


@pytest.fixture(scope="session")
def qapp():
    if not _HAVE_PYSIDE6:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME + XDG_CONFIG_HOME to tmp_path so QSettings stays isolated."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path
```
**Rule:** `isolated_home` is MANDATORY for any test constructing `EditorWindow` (QSettings isolation — otherwise pollutes the developer's real `~/Library/Preferences/com.SurgRL.SceneEditor.plist`). Duplicate the small fixture in each new test file (per RESEARCH.md Wave 0 gaps) OR place the new files in `tests/gui/` to reuse `tests/gui/conftest.py`.

**Class-based test grouping pattern** — copy `tests/test_dock_state.py:58-65, 88-96` (the `@pytestmark` class decorator + descriptive class docstring + one test per `def test_*`):
```python
# tests/test_dock_state.py:58-65 — class-based grouping with pytestmark
@pytestmark
class TestDockObjectNames:
    """SC#4 / D-07: every QDockWidget has a non-empty, unique objectName."""
    def test_every_dock_has_unique_nonempty_objectname(self, qapp, isolated_home) -> None:
        ...
```
For Phase 42 the classes are: `TestSimStepWorkerAccumulator`, `TestPauseResumeStepOne`, `TestDecouplingAndPublishCap`, `TestSpeedScaling`, `TestRenderPollCadence`, `TestStepOneRendersWhilePaused`, `TestPlaybackToolbar`, `TestPlaybackStatus`, `TestLoadPaused`, `TestStaticSceneHint`, `TestCloseMidStepCleanExit` (per RESEARCH.md Validation Architecture → Test Map).

**`TestCloseMidCallMockSlow` pattern** — copy `tests/test_dock_state.py:277-329` (the `monkeypatch.setattr` + `time.sleep` + `w.close()` + `assert not thread.isRunning()` shape). `TestCloseMidStepCleanExit` mirrors this for `SimStepWorker`:
```python
# tests/test_dock_state.py:277-329 — the mock-slow close-mid-call pattern
@pytestmark
class TestCloseMidCallMockSlow:
    def test_close_mid_llm_call_clean_exit_mock_slow(
        self, qapp, isolated_home, monkeypatch
    ) -> None:
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.scene_definition import SceneDefinition
        from surg_rl.scene_generation import text_parser as tp

        def slow_parse_sync(self, input_data, **kwargs):  # noqa: ANN001
            time.sleep(2)
            return SceneDefinition()

        monkeypatch.setattr(tp.TextParser, "parse_sync", slow_parse_sync)

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        w._llm_panel._prompt.setPlainText("a test prompt")
        w._llm_panel._on_generate()
        qapp.processEvents()
        try:
            w._llm_panel.stop()
            qapp.processEvents()
            thread = w._llm_panel._thread
            if thread is not None:
                assert not thread.isRunning(), (
                    "LLM worker thread still running after stop() — "
                    "close mid-LLM-call must exit cleanly (SC#3 / D-05)"
                )
        finally:
            with contextlib.suppress(Exception):
                w.close()
```
**Adaptation:** `monkeypatch.setattr(vp, "_default_load_simulator", lambda scene: MockSimulator())` (per RESEARCH.md Code Examples) replaces the simulator loader with a `MockSimulator` (no GL/physics). Start the worker (`w._sim_worker.set_paused(False)`), `time.sleep(0.05)`, then `w.close()` (the full `closeEvent` path: `aboutToClose` → `_sim_worker.stop()` → `viewport.stop()`). Assert `not w._sim_thread.isRunning()`.

**`TestAboutToClose` Mock-stop pattern** — copy `tests/test_dock_state.py:376-405` for a wiring guard (Mock `_sim_worker.stop` and assert `closeEvent` calls it via `aboutToClose`):
```python
# tests/test_dock_state.py:384-405 — Mock stop + closeEvent wiring guard
def test_close_event_emits_aboutto_close_before_super(
    self, qapp, isolated_home
) -> None:
    from unittest.mock import MagicMock
    from PySide6.QtGui import QCloseEvent
    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    mock_llm_stop = MagicMock()
    w._llm_panel.stop = mock_llm_stop
    w.closeEvent(QCloseEvent())
    try:
        assert mock_llm_stop.call_count >= 1, "closeEvent must emit aboutToClose..."
    finally:
        with contextlib.suppress(Exception):
            w.close()
```
**Adaptation:** also Mock `w._sim_worker.stop` and assert BOTH `mock_llm_stop.call_count >= 1` AND `mock_sim_stop.call_count >= 1`.

**`TestDockObjectNames` extension pattern** — copy `tests/test_dock_state.py:58-85` and EXTEND to also collect `QToolBar` children (Pitfall 7 / Phase 41 D-07 extension). Add a second test (or extend the existing one) that asserts `w.findChildren(QToolBar)` are non-empty + each has a non-empty unique `objectName` (specifically `toolbar_playback`):
```python
# tests/test_dock_state.py:66-85 — the existing QDockWidget introspection to EXTEND
def test_every_dock_has_unique_nonempty_objectname(self, qapp, isolated_home) -> None:
    from PySide6.QtWidgets import QDockWidget
    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    w.show()
    qapp.processEvents()
    try:
        docks = w.findChildren(QDockWidget)
        names = [d.objectName() for d in docks]
        assert docks, "EditorWindow should construct at least one QDockWidget"
        assert all(names), f"Every QDockWidget must have a non-empty objectName; got {names}"
        assert len(names) == len(set(names)), f"QDockWidget objectNames must be unique; got {names}"
    finally:
        w.close()
```
**Extension (add to the same class or a new `TestToolbarObjectNames`):** mirror with `from PySide6.QtWidgets import QToolBar` + `tbs = w.findChildren(QToolBar)` + assert `tbs` non-empty + all `objectName`s non-empty + unique + `"toolbar_playback" in names`.

**MockSimulator pattern** — RESEARCH.md Code Examples provides the shape (copy verbatim):
```python
# Source: [VERIFIED: base_simulator.py:90-111 State + 114-135 StepResult shapes]
import time
from dataclasses import dataclass, field
import numpy as np
from surg_rl.simulators.base_simulator import State, StepResult, Observation

class MockSimulator:
    def __init__(self, step_delay: float = 0.0) -> None:
        self.step_delay = step_delay
        self.step_count = 0
        self._loaded = True
        self.timestep = 0.02
        self.frame_skip = 1
    def step(self, action):
        if self.step_delay:
            time.sleep(self.step_delay)
        self.step_count += 1
        return StepResult(observation=Observation(), reward=0.0,
                          terminated=False, truncated=False)
    def get_state(self):
        return State(time=float(self.step_count))
    def render(self, mode="rgb_array", width=None, height=None, camera_name=None):
        return np.zeros((height or 480, width or 640, 3), dtype=np.uint8)
    def close(self): pass
```
Place this in a shared helper (e.g. `tests/gui/_mock_sim.py` or duplicate in each new test file). With this mock + a real `QThread`, the test asserts: after 100 ms wall, `step_count` is ~5 (50 Hz); `snapshot_ready` fired at most ~3 times (~30 Hz cap); `step_one()` while paused increments `step_count` by exactly 1; `stop()` → `thread.wait(3000)` → `isRunning()==False`.

---

### `tests/test_dock_state.py` (EXTENDED — `TestDockObjectNames`)

**Analog:** the file itself. See the test assignment above for the extension pattern (also collect `QToolBar` children + assert `toolbar_playback` has a non-empty unique `objectName`). The extension is a 1-class addition to the existing `TestDockObjectNames` (or a new sibling class `TestToolbarObjectNames`); the existing dock test stays intact (regression guard for Phase 41 SC#4).

---

## Shared Patterns

### Lazy-import / HAS_GUI discipline
**Source:** `src/surg_rl/editor/__init__.py:31-42`
**Apply to:** `src/surg_rl/editor/sim_step_worker.py` + `src/surg_rl/editor/render_poll_loop.py` (the two NEW editor modules)
```python
# editor/__init__.py:31-42 — the LazyImport sentinel + HAS_GUI guard
from surg_rl.utils.lazy_imports import LazyImport
QtWidgets = LazyImport("PySide6.QtWidgets", "gui")
QtCore = LazyImport("PySide6.QtCore", "gui")
QtGui = LazyImport("PySide6.QtGui", "gui")
HAS_GUI: bool = QtWidgets.available
```
**Rule:** new editor modules import Qt symbols via `from surg_rl.editor import QtCore, QtWidgets, QtGui` (the LazyImport proxies), NOT `from PySide6 import ...` at module top. `from __future__ import annotations` + `TYPE_CHECKING` for any heavy model imports (`SceneDefinition`, `BaseSimulator`).

### QThread worker-object lifecycle (cooperative teardown)
**Source:** `src/surg_rl/editor/llm_panel.py:117-128` (wiring) + `:130-158` (`stop()` template)
**Apply to:** `src/surg_rl/editor/sim_step_worker.py` (the worker's `stop()` flags cancel + stops accumulator) + `src/surg_rl/editor/main_window.py` (the controller's `aboutToClose`-wired teardown that owns `thread.quit()`+`wait(3000)`)
```python
# llm_panel.py:117-128 — the wiring (moveToThread + started->run + finished->quit + finished->deleteLater)
self._thread = QtCore.QThread()
self._worker = TextParserWorker(provider=provider, api_key=api_key)
self._worker.moveToThread(self._thread)
self._thread.started.connect(lambda: self._worker.run(prompt))
self._worker.finished.connect(self._thread.quit)
self._worker.failed.connect(self._thread.quit
self._thread.finished.connect(self._thread.deleteLater)  # ONLY here
self._thread.start()
```
```python
# llm_panel.py:130-158 — the D-05 stop() template (cancel + quit + wait + log)
def stop(self) -> None:
    if self._worker is not None:
        self._worker.setProperty("_cancelled", True)
    if self._thread is not None:
        self._thread.quit()
        if not self._thread.wait(3000):
            logger.warning("LLMPanel worker thread did not exit within 3s; proceeding with close")
    # Do NOT call deleteLater here — thread.finished -> deleteLater is already wired (Pitfall 4)
```
**Rule:** `moveToThread` + `@Slot`s on the worker; `thread.quit()`+`wait(3000)`+log-on-timeout; NEVER `thread.terminate()` (D-04/D-05); NEVER `thread.deleteLater()` before `wait()` (Pitfall 4 — "Deleting a running QThread will result in a program crash"); the `thread.finished -> thread.deleteLater` wiring handles deletion. `aboutToClose` is the trigger (mirror `main_window.py:139`).

### `aboutToClose` registry-signal teardown contract
**Source:** `src/surg_rl/editor/main_window.py:59, 136-139, 394-411`
**Apply to:** `EditorWindow.__init__` — add `self.aboutToClose.connect(self._sim_worker.stop)` (the controller-side `stop()` that calls `thread.quit()`+`wait(3000)`)
```python
# main_window.py:59 + 136-139 — the contract SimStepWorker plugs into (NO closeEvent edit)
aboutToClose = QtCore.Signal()  # noqa: N815
...
self.aboutToClose.connect(self._llm_panel.stop)   # existing
# Add:
self.aboutToClose.connect(self._sim_worker.stop)  # NEW — mirror line 139
```
**Rule:** `closeEvent` (lines 394-411) is UNCHANGED. `aboutToClose.emit()` at `:400` fires BEFORE `viewport.stop()` at `:407` — the worker is cancelled BEFORE the shared simulator is closed (Pitfall 3 guarantee). Future workers (Phase 46 recorder, 48 autosave, 51 VLM) plug in the same way.

### Self-rescheduling `QTimer.singleShot` + `_running` guard
**Source:** `src/surg_rl/editor/viewport.py:165-180, 189-191, 287-290`
**Apply to:** `src/surg_rl/editor/render_poll_loop.py` (the UI-thread render loop) + `src/surg_rl/editor/sim_step_worker.py` (the accumulator `QTimer` halt path)
```python
# viewport.py:189-191 + 287-290 — the guard at both ends of _tick
def _tick(self) -> None:
    if not self._running:
        return  # stop() was called — halt the loop
    ...
    if self._running:
        QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
```
**Rule:** every self-rescheduling `singleShot` (or `QTimer.timeout`) callback checks `_running` at the top AND before reschedule. `stop()` sets `_running=False` first so already-queued callbacks early-return. Prevents dangling QTimer callbacks after window close (UAT Gap 2 fix).

### `objectName` discipline (Phase 41 D-07)
**Source:** `src/surg_rl/editor/main_window.py:119-132` (dock_<slug>) + `tests/test_dock_state.py:58-85` (introspection test)
**Apply to:** the new playback `QToolBar` (`toolbar_playback`) + the speed `QComboBox` (`combo_playback_speed`) — set `objectName` BEFORE `addToolBar`/`addWidget` so `saveState()`/`restoreState()` round-trip correctly
```python
# main_window.py:119-132 — the objectName convention (extend dock_<slug> to toolbar_<slug>)
self._tree_dock = QtWidgets.QDockWidget("Scene Tree", self)
self._tree_dock.setObjectName("dock_scene_tree")     # dock_<slug>
self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)
```
**Rule:** every `QDockWidget` AND `QToolBar` gets a non-empty unique `objectName` at construction. The SC#4 introspection test (`tests/test_dock_state.py::TestDockObjectNames`) is EXTENDED this phase to also collect `QToolBar` children and assert non-empty unique `objectName` (Pitfall 7).

### Best-effort teardown (broad suppress)
**Source:** `src/surg_rl/editor/main_window.py:399-409` + `src/surg_rl/editor/viewport.py:178, 410-412`
**Apply to:** `SimStepWorker.stop()` / `ViewportPanel.update_scene()` simulator close / `EditorWindow.closeEvent` paths
```python
# main_window.py:399-409 — the canonical best-effort teardown suppress
try:  # noqa: SIM105 — best-effort teardown; broad suppress is intentional
    self.aboutToClose.emit()
except Exception:  # noqa: BLE001
    pass  # best-effort — don't block window close
try:  # noqa: SIM105 — best-effort cleanup; broad suppress is intentional
    self._viewport_panel.stop()
except Exception:  # noqa: BLE001
    pass
```
```python
# viewport.py:178 — the simulator-close suppress (reused in update_scene + stop())
with contextlib.suppress(AttributeError, OSError):
    self._simulator.close()
```
**Rule:** close/teardown paths NEVER block quit. `# noqa: BLE001` + `# noqa: SIM105` are the established markers. `wait()` timeout is `logger.warning(...)` (log-only, proceeds).

### Logger convention
**Source:** `src/surg_rl/editor/viewport.py:21-23` + `src/surg_rl/editor/llm_panel.py:9-14`
**Apply to:** `src/surg_rl/editor/sim_step_worker.py` + `src/surg_rl/editor/render_poll_loop.py`
```python
# viewport.py:21-23 / llm_panel.py:9-14 — the editor module logger convention
from surg_rl.utils.logging import get_logger
logger = get_logger(__name__)
```
**Rule:** `get_logger(__name__)` at module top. `logger.warning(...)` for the `wait()` timeout (log-only, NOT user-facing — no `safe_error_message` redaction per Security Domain V5). `logger.debug(...)`/`logger.info(...)` for the macOS PyBullet fallback (mirror `viewport.py:456, 474`).

### User-facing error/hint redaction
**Source:** `src/surg_rl/editor/_safe_error.py:34-43` + `src/surg_rl/editor/viewport.py:199, 266, 272`
**Apply to:** the static-scene hint (D-12) + any teardown-timeout string surfaced to the status bar + any `update_scene`/`bind_scene` error surfaced to the canvas
```python
# _safe_error.py:34-43 — the redactor
def safe_error_message(error: BaseException | str) -> str:
    text = str(error) if isinstance(error, BaseException) else error
    for pattern in _REDACTION_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text
```
```python
# viewport.py:199, 272 — the existing usage pattern in the render loop
from surg_rl.editor._safe_error import safe_error_message
self._canvas.set_text(f"Simulator load error: {safe_error_message(exc)}")
```
**Rule:** any error/hint string that reaches the status bar / canvas / message box passes through `safe_error_message()`. Log-only messages (`logger.warning`) do NOT need redaction. The static-scene hint "static scene — no dynamics" is generic (no scene content) — no redaction strictly needed, but routing it through `safe_error_message` is the defensive default if the hint ever includes scene detail.

### Signal declaration convention
**Source:** `src/surg_rl/editor/llm_panel.py:22-26, 49` + `src/surg_rl/editor/main_window.py:59`
**Apply to:** `SimStepWorker.snapshot_ready` (the one new signal this phase — the decoupling boundary D-03)
```python
# llm_panel.py:22-26 — class-level Signal declarations
class TextParserWorker(QtCore.QObject):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
```
**Rule:** `snapshot_ready = QtCore.Signal(object)` declared at `SimStepWorker` class-body top (payload = `State` or a `_Snapshot` wrapper with `frame_id`; the latter enables the render-poll's "new snapshot?" check). Connect to `render_loop.on_snapshot` with `Qt.ConnectionType.QueuedConnection` (the signal crosses the worker→UI thread boundary — the queued connection is the thread-safe path; `State` is pure data, safe to pass across threads per RESEARCH A3).

### Static-scene predicate (D-12 — schema-level, NOT a runtime heuristic)
**Source:** `src/surg_rl/scene_definition/schema.py:1382-1442` (the `SceneDefinition` field definitions — VERIFIED this session)
**Apply to:** `_scene_has_dynamics(scene)` pure function called once in `update_scene` (RESEARCH.md "Resolving D-12")
**VERIFIED schema fields** (RESEARCH.md A4 flagged this for confirmation — now confirmed):
```python
# schema.py:1397-1442 — the SceneDefinition fields the predicate reads
environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig, ...)  # :1397
robots: list[RobotConfig] = Field(default_factory=list, ...)                    # :1402
tissues: list[TissueConfig] = Field(default_factory=..., ...)                   # :1403
instruments: list[InstrumentConfig] = Field(default_factory=..., ...)           # :1406
task: TaskConfig | None = Field(default=None, ...)                              # :1411
fluid: FluidConfig | None = Field(default=None, ...)                            # :1442  ← on SceneDefinition, NOT on EnvironmentConfig
```
**CORRECTION to RESEARCH.md Pattern (D-12):** the RESEARCH's `_scene_has_dynamics` read `env.fluid` — that is WRONG. `fluid` is a direct field on `SceneDefinition` (`schema.py:1442`), NOT on `EnvironmentConfig`. `EnvironmentConfig` has `lights`, `cameras`, `ground_plane` (`schema.py:996-1009`) — no `fluid`. The correct predicate:
```python
def _scene_has_dynamics(scene: SceneDefinition) -> bool:
    # Structural check — NOT a runtime step-delta heuristic (D-12).
    # Verified field names against schema.py:1397-1442.
    if getattr(scene, "robots", None):           # :1402 — any robot with joints -> dynamics
        return True
    if getattr(scene, "tissues", None):          # :1403 — tissues (soft-body) -> dynamics
        return True
    if getattr(scene, "fluid", None) is not None:  # :1442 — fluid config -> dynamics
        return True
    return False
```
**Open question for the planner (RESEARCH A4):** whether a scene with ONLY `instruments` (no robots/tissues/fluid) has dynamics. `instruments` is a non-empty list in many scenes; instruments without robots have no actuated joints, so the predicate above treats instruments-only as static (returns `False`). The planner/implementer should confirm this is the desired UX (a scene with instruments but no robots — does the user expect the "static scene" hint? If yes, the predicate is correct; if no, add `or getattr(scene, "instruments", None)`). The hint is informational only (D-12), so the risk is LOW either way.

## No Analog Found

None — every new/modified file has a real on-disk analog:
- The two NEW editor modules (`sim_step_worker.py`, `render_poll_loop.py`) have same-package siblings: `llm_panel.py` (the only existing `QThread` worker-object) and `viewport.py` (`_tick` — the monolithic loop being split).
- The three NEW test files have `tests/test_dock_state.py` (the Phase 41 offscreen harness + `TestCloseMidCallMockSlow` + `TestAboutToClose` + `TestDockObjectNames`).
- All MODIFIED files are read at their current state above.
- `base_simulator.py` is UNCHANGED (reused primitives only).

The one genuinely NEW pattern (no exact on-disk analog) is the **accumulator + ~30 Hz publish cap** in `SimStepWorker._tick` — there is no existing fixed-step accumulator in the codebase. RESEARCH.md Pattern 1 provides the recommended shape (implementer's discretion per CONTEXT); the planner should reference RESEARCH.md Pattern 1 directly for that one piece. The `RenderPollLoop` skip-when-no-new-snapshot pattern is also NEW but trivially derived from the existing `_tick` + a `frame_id` comparison (RESEARCH.md Pattern 2).

## Metadata

**Analog search scope:**
- `src/surg_rl/editor/` — `__init__.py`, `_safe_error.py`, `_settings.py`, `dock_state.py`, `llm_panel.py`, `main_window.py`, `viewport.py` (all read in full; none exceeded 2,000 lines — `main_window.py` is the longest at 412 lines)
- `src/surg_rl/simulators/` — `base_simulator.py` (signatures only, per RESEARCH.md verification — `step:219`, `render:231`, `get_state:252`, `close:270`)
- `src/surg_rl/scene_definition/` — `schema.py` (field-name verification for the D-12 predicate — `SceneDefinition:1382-1442`, `EnvironmentConfig:990-1009`)
- `tests/` — `test_dock_state.py` (the Phase 41 offscreen test pattern — read in full, 406 lines)

**Files scanned:** 8 source/test files (all read in full)

**Mid-mapping verification:** `git log -1` HEAD = `6935e38 docs(41): complete phase execution` (per RESEARCH.md — source unchanged on `main`); all CONTEXT.md/RESEARCH.md line-number citations re-verified this session against the live source — all confirmed. One correction found: RESEARCH.md's `_scene_has_dynamics` predicate read `env.fluid`; the actual schema has `fluid` on `SceneDefinition` directly (`schema.py:1442`), NOT on `EnvironmentConfig` — corrected in the Static-scene predicate shared pattern above.

**Pattern extraction date:** 2026-07-16