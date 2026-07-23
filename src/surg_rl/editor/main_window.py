"""EditorWindow — Phase 33 main window shell.

Plans 33-02..05 fill in the panes:
  - 33-02: SchemaWalker + FieldRenderer (properties pane)
  - 33-03: Viewport with 3D render
  - 33-04: Tree view + validation icons
  - 33-05: LLM panel + undo/redo
"""

from __future__ import annotations

import contextlib
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor._safe_error import safe_error_message
from surg_rl.editor._settings import EditorSettings
from surg_rl.editor.dock_state import DockStateManager
from surg_rl.editor.render_poll_loop import RenderPollLoop
from surg_rl.editor.sim_step_worker import SimStepWorker

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

_PLACEHOLDER_TEXT = "(populated by Phase 33 plan {plan})"


def _finalize_sim_thread(thread: QtCore.QThread, worker: SimStepWorker) -> None:
    """Best-effort SimStepWorker thread teardown at EditorWindow GC time.

    Pre-Phase-42 EditorWindow tests (``test_gui_foundation.py``) construct
    ``EditorWindow`` without calling ``close()``, which was safe when the
    window owned no QThreads. Phase 42 Task 3 starts a SimStepWorker QThread
    in ``__init__``; if those pre-existing tests never call ``close()``, the
    thread is still running when the QThread is destroyed →
    ``QThread: Destroyed while thread is still running`` + segfault during
    GC. This finalizer is the safety net: it runs when the EditorWindow
    Python wrapper is garbage-collected, sets the cancel flag + quits +
    waits (mirrors ``_stop_sim_worker``). It holds refs to the thread +
    worker ONLY (not to self) so it does not keep the EditorWindow alive
    (Rule 1 fix for the thread-leak regression in pre-existing tests).
    """
    with contextlib.suppress(Exception):
        worker._cancelled = True
    if thread is not None:
        thread.quit()
        with contextlib.suppress(Exception):
            thread.wait(3000)


def _empty_scene_stub() -> SceneDefinition:
    """Create a minimal valid SceneDefinition for when the editor opens with no scene."""
    from surg_rl.scene_definition import SceneDefinition, SimulatorType

    return SceneDefinition(simulator=SimulatorType.MUJOCO)


def _find_instance(scene: SceneDefinition | None, cls: type):
    """Recursively find the first instance of `cls` in the scene tree."""
    if scene is None:
        return None
    if hasattr(scene, "environment") and isinstance(getattr(scene, "environment", None), cls):
        return scene.environment
    if hasattr(scene, "task") and isinstance(getattr(scene, "task", None), cls):
        return scene.task
    for attr in ("robots", "tissues", "instruments"):
        lst = getattr(scene, attr, None) or []
        for inst in lst:
            if isinstance(inst, cls):
                return inst
    return None


class EditorWindow(QtWidgets.QMainWindow):
    """Phase 33 PySide6 scene editor main window."""

    # D-04: milestone-wide teardown contract. closeEvent emits aboutToClose
    # BEFORE super().closeEvent() so every long-running panel's stop() runs
    # before Qt tears down children. Future workers (Phase 42 SimStepWorker,
    # 46 recorder, 48 autosave, 51 VLM) just declare stop() + connect to
    # aboutToClose — no closeEvent edit needed. Plain Signal (no payload —
    # pure teardown trigger); a registry mixin is deferred until the
    # per-panel wiring count grows past ~3-4 panels.
    aboutToClose = QtCore.Signal()  # noqa: N815 — Qt Signal naming convention

    # Phase 42 — proxy signals connected to the SimStepWorker @Slots with a
    # queued connection (the worker lives on a QThread; its @Slot methods are
    # NOT signals and cannot be .emit()-ed directly). The EditorWindow
    # controller owns these so the toolbar/shortcut handlers can request
    # pause/speed/step-one on the worker thread without touching the worker's
    # thread-affine QTimer state from the UI thread.
    _play_pause_request = QtCore.Signal(bool)  # paused: bool
    _speed_request = QtCore.Signal(float)
    _step_one_request = QtCore.Signal()

    def __init__(self, scene_path: str | Path | None = None) -> None:
        super().__init__()
        self.setObjectName("EditorWindow")
        self.setWindowTitle("Surg-RL Scene Editor")
        self._settings = EditorSettings()
        self._dock_state = DockStateManager()
        self._current_path: Path | None = None
        self._scene: SceneDefinition | None = None

        # Phase 33-05: undo/redo stack (per-scene, capped, cleared on save)
        from surg_rl.editor.undo_stack import SceneUndoStack

        self._undo_stack = SceneUndoStack(self)
        self._undo_stack.canUndoChanged.connect(self._update_undo_actions)
        self._undo_stack.canRedoChanged.connect(self._update_undo_actions)

        # Phase 33-03 wires the 3D viewport as the central widget.
        from surg_rl.editor.viewport import ViewportPanel

        self._viewport_panel = ViewportPanel(
            scene=self._scene or _empty_scene_stub(),
            on_fps_update=self._update_fps_status,
        )
        self.setCentralWidget(self._viewport_panel)

        # Phase 42 D-01/D-02/D-03 — render/sim decoupling. The SimStepWorker
        # owns the ~50 Hz fixed-step accumulator on a QThread; the RenderPollLoop
        # owns the ~30 Hz render of the latest published snapshot on the UI
        # thread. The queued snapshot_ready -> on_snapshot connection is the
        # decoupling seam (D-03 — State is pure-data, safe across threads).
        self._sim_thread = QtCore.QThread()
        self._sim_thread.setObjectName("sim_step_worker_thread")
        self._sim_worker = SimStepWorker()
        self._sim_worker.moveToThread(self._sim_thread)
        # thread.started -> worker.start creates the accumulator QTimer on the
        # worker thread (affinity = worker thread; Qt timers must be created on
        # the thread they run on).
        self._sim_thread.started.connect(self._sim_worker.start)
        # The ONLY delete path (Pitfall 4 — never call deleteLater from stop()).
        self._sim_thread.finished.connect(self._sim_thread.deleteLater)
        # RenderPollLoop lives on the UI thread (NOT moveToThread — render() is
        # thread-affine). It reads the live simulator via a ref callable so
        # in-place scene swaps (update_scene) are picked up without re-wiring.
        self._render_loop = RenderPollLoop(
            simulator_ref=lambda: self._viewport_panel._simulator,
            canvas=self._viewport_panel,
            camera_offset_ref=lambda: self._viewport_panel._camera_offset,
            on_fps_update=self._update_fps_status,
            width=max(1, self._viewport_panel.width()),
            height=max(1, self._viewport_panel.height()),
            camera_name=self._viewport_panel.camera_name(),
        )
        # D-03 decoupling seam — queued because it crosses the worker→UI thread
        # boundary; the snapshot payload is pure-data (no Qt/GL handles).
        self._sim_worker.snapshot_ready.connect(
            self._render_loop.on_snapshot, QtCore.Qt.ConnectionType.QueuedConnection
        )
        # Connect the proxy request signals to the worker @Slots (queued — the
        # worker lives on a QThread; the @Slot methods touch thread-affine QTimer
        # state and must run on the worker thread). The ViewportPanel proxy
        # signals (_pause_requested / _bind_scene_requested) route the
        # update_scene/stop pause+bind requests the same way.
        self._play_pause_request.connect(
            self._sim_worker.set_paused, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._speed_request.connect(
            self._sim_worker.set_speed, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._step_one_request.connect(
            self._sim_worker.step_one, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._viewport_panel._pause_requested.connect(
            self._sim_worker.set_paused, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._viewport_panel._bind_scene_requested.connect(
            self._sim_worker.bind_scene, QtCore.Qt.ConnectionType.QueuedConnection
        )
        # Refresh the playback status-bar segment when a new scene is bound
        # (D-12 — the static/dynamic hint is re-evaluated in _bind_loaded_
        # simulator and the controller mirrors it in _status_playback). Queued
        # so the initial emit during set_playback (before the toolbar/status
        # bar are built later in __init__) defers until after __init__ returns.
        self._viewport_panel._scene_bound.connect(
            self._refresh_playback_status, QtCore.Qt.ConnectionType.QueuedConnection
        )
        # Hand the worker + loop refs to ViewportPanel — does the INITIAL bind
        # (load the scene's simulator on the UI thread + bind_scene queued +
        # set_paused True D-11 + D-12 hint).
        self._viewport_panel.set_playback(self._sim_worker, self._render_loop)
        # Start the worker thread (runs the worker's event loop — NOT a
        # blocking run()) and the UI-thread render-poll chain.
        self._sim_thread.start()
        self._render_loop.start()
        # Rule 1 safety net — pre-Phase-42 EditorWindow tests construct the
        # window without calling close() (safe before because the window owned
        # no QThreads). Now that __init__ starts a SimStepWorker QThread, those
        # tests leak a running thread → "QThread: Destroyed while thread is
        # still running" + segfault during GC. The finalizer stops the thread
        # at GC time; it holds refs to the thread + worker ONLY (not self) so
        # it does not keep the EditorWindow alive.
        self._sim_finalizer = weakref.finalize(
            self, _finalize_sim_thread, self._sim_thread, self._sim_worker
        )

        self._build_dock_widgets()
        # Phase 42 D-06 — playback toolbar (Play/Pause + Step-one + speed
        # combo). Built AFTER _build_dock_widgets so the dock-state factory
        # snapshot (captured next) includes both docks + the toolbar. The
        # toolbar objectName is set BEFORE addToolBar (Pitfall 7) so
        # saveState()/restoreState() round-trip it.
        self._build_playback_toolbar()
        # CR-01: capture the factory-default snapshot from the CODE-BUILT layout
        # BEFORE _restore_geometry re-applies the user's saved QSettings layout,
        # so Reset Layout restores the factory arrangement, not the user's
        # last-saved (e.g. tabified) layout. saveState() is valid pre-show because
        # the dock widgets are already added; the one-shot _captured guard makes
        # the later showEvent capture a defensive no-op (D-01).
        self._dock_state.capture_factory_default(self)
        self._build_menu_bar()
        self._build_status_bar()
        self._wire_drag_drop()
        self._wire_shortcuts()
        self._restore_geometry()
        self._update_undo_actions()
        self._set_status("Untitled", "—", "—", "—")
        # Reflect the initial paused load (D-11) + D-12 static-scene hint in the
        # playback status-bar segment (set_playback already evaluated the hint).
        self._update_playback_status(
            playing=False,
            speed=self._current_speed(),
            static=self._viewport_panel._static_scene,
        )

        if scene_path is not None:
            self._open_scene(Path(scene_path))

    def _build_central_viewport(self) -> None:
        # Replaced in __init__ by ViewportPanel (Phase 33-03).
        pass

    def _build_dock_widgets(self) -> None:
        # Plan 33-04 wires the tree and property form into the docks.
        from surg_rl.editor.llm_panel import LLMPanel
        from surg_rl.editor.property_form import PropertyForm
        from surg_rl.editor.tree_view import SceneTreeView

        self._tree_view = SceneTreeView(self._scene or _empty_scene_stub())
        self._property_form = PropertyForm()
        self._llm_panel = LLMPanel()

        self._tree_dock = QtWidgets.QDockWidget("Scene Tree", self)
        self._tree_dock.setObjectName("dock_scene_tree")
        self._tree_dock.setWidget(self._tree_view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)

        self._properties_dock = QtWidgets.QDockWidget("Properties", self)
        self._properties_dock.setObjectName("dock_properties")
        self._properties_dock.setWidget(self._property_form)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self._properties_dock)

        self._llm_dock = QtWidgets.QDockWidget("LLM Prompt-to-JSON", self)
        self._llm_dock.setObjectName("dock_llm")
        self._llm_dock.setWidget(self._llm_panel)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self._llm_dock)

        self._tree_view.node_selected.connect(self._on_node_selected)
        self._llm_panel.scene_accepted.connect(self._on_llm_scene_accepted)
        # D-04 wiring: register LLMPanel.stop() on aboutToClose so closeEvent
        # tears down the LLM worker thread before Qt deletes the panel (SC#3).
        # Future workers connect their stop() here too — no closeEvent edit.
        self.aboutToClose.connect(self._llm_panel.stop)
        # Phase 42 D-04 — mirror line 139 for the SimStepWorker. The controller
        # side (_stop_sim_worker) owns thread.quit() + thread.wait(3000) +
        # log-on-timeout (mirrors llm_panel.py:130-158). aboutToClose fires at
        # closeEvent :400 BEFORE viewport.stop() at :407 — the worker is
        # cancelled BEFORE the shared simulator is closed (Pitfall 3 ordering).
        self.aboutToClose.connect(self._stop_sim_worker)

    def _stop_sim_worker(self) -> None:
        """Controller-side teardown for the SimStepWorker QThread (D-04).

        Mirrors ``LLMPanel.stop()`` (Phase 41 D-05): set the cross-thread
        cancel flag (a plain Python bool — thread-safe under the GIL; the
        worker's ``_tick`` polls it at the top), then the controller owns
        ``thread.quit()`` + ``thread.wait(3000)`` + log-on-timeout. The
        worker's accumulator QTimer stops naturally when the thread's event
        loop exits (``thread.quit()``); we do NOT call ``sim_worker.stop()``
        from the UI thread because that would touch the worker-thread-affine
        QTimer (``QObject::killTimer: Timers cannot be stopped from another
        thread``). NEVER ``thread.terminate()`` (D-04 — risks leaving simulator
        physics state inconsistent); NEVER ``thread.deleteLater()`` here
        (Pitfall 4 — the ``thread.finished -> thread.deleteLater`` wiring in
        __init__ is the only delete path).

        Best-effort — never blocks close on timeout (log and proceed).
        """
        # Detach the GC finalizer — close() is the explicit teardown path, so
        # the finalizer would be redundant (and double-stop the thread).
        finalizer = getattr(self, "_sim_finalizer", None)
        if finalizer is not None:
            finalizer.detach()
        # Cross-thread cancel flag — the worker's _tick polls _cancelled
        # at the top and returns; thread.quit() exits the event loop (and
        # stops the accumulator QTimer naturally).
        with contextlib.suppress(Exception):
            self._sim_worker._cancelled = True
        if self._sim_thread is not None:
            self._sim_thread.quit()
            if not self._sim_thread.wait(3000):
                logger.warning("SimStepWorker thread did not exit within 3s; proceeding with close")
        # Do NOT call deleteLater here — thread.finished -> deleteLater is
        # already wired in __init__ (Pitfall 4).

    def _build_playback_toolbar(self) -> None:
        """Phase 42 D-06/D-09 — playback QToolBar docked at the top.

        Play/Pause toggle QAction (setCheckable) + Step-one QAction + speed
        QComboBox with the 5 D-09 multipliers (default ``1x`` per D-10,
        session-only — NOT persisted to QSettings, D-05). ``objectName`` is set
        BEFORE ``addToolBar`` (Pitfall 7) so ``saveState()``/``restoreState()``
        round-trip the toolbar (Phase 41 D-07 extension).
        """
        tb = QtWidgets.QToolBar("Playback")
        tb.setObjectName("toolbar_playback")
        # Pitfall 7 — setObjectName BEFORE addToolBar (saveState identifies
        # toolbars by objectName).
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, tb)
        # Play/Pause toggle (D-06). Checked = playing; unchecked = paused.
        self._act_play_pause = tb.addAction("▶ Play")
        self._act_play_pause.setCheckable(True)
        self._act_play_pause.setObjectName("act_play_pause")
        # Step-one (D-06/D-07 — exactly one step() while paused).
        self._act_step_one = tb.addAction("⏭ Step")
        self._act_step_one.setObjectName("act_step_one")
        tb.addSeparator()
        speed_label = QtWidgets.QLabel("Speed:")
        speed_label.setObjectName("lbl_playback_speed")
        tb.addWidget(speed_label)
        self._speed_combo = QtWidgets.QComboBox()
        self._speed_combo.setObjectName("combo_playback_speed")
        for s in ("0.25x", "0.5x", "1x", "2x", "4x"):
            self._speed_combo.addItem(s)
        self._speed_combo.setCurrentText("1x")  # D-10 default 1x (session-only)
        tb.addWidget(self._speed_combo)
        # Wire the handlers — emit queued signals to the worker's slots.
        self._act_play_pause.toggled.connect(self._on_play_pause_toggled)
        self._act_step_one.triggered.connect(self._on_step_one)
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)

    def _make_dock(
        self, title: str, area: QtCore.Qt.DockWidgetArea, placeholder: str
    ) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(title, self)
        dock.setObjectName(f"dock_{title.replace(' ', '_').lower()}")
        body = QtWidgets.QLabel(placeholder)
        body.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        dock.setWidget(body)
        self.addDockWidget(area, dock)
        return dock

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()
        file_menu = mb.addMenu("&File")
        file_menu.addAction("&New", self._action_new, QtGui.QKeySequence.StandardKey.New)
        file_menu.addAction("&Open...", self._action_open, QtGui.QKeySequence.StandardKey.Open)
        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._refresh_recent_menu()
        file_menu.addAction("&Save", self._action_save, QtGui.QKeySequence.StandardKey.Save)
        file_menu.addAction(
            "Save &As...", self._action_save_as, QtGui.QKeySequence.StandardKey.SaveAs
        )
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, QtGui.QKeySequence.StandardKey.Quit)
        self._edit_menu = mb.addMenu("&Edit")
        self._undo_action = self._edit_menu.addAction(
            "&Undo", self._on_undo, QtGui.QKeySequence.StandardKey.Undo
        )
        self._redo_action = self._edit_menu.addAction(
            "&Redo", self._on_redo, QtGui.QKeySequence.StandardKey.Redo
        )
        self._undo_action.setEnabled(False)
        self._redo_action.setEnabled(False)
        view_menu = mb.addMenu("&View")
        view_menu.addAction("&Reset Layout", self._action_reset_layout)
        help_menu = mb.addMenu("&Help")
        help_menu.addAction("&About", self._action_about)

    def _wire_shortcuts(self) -> None:
        # Cmd+R / Ctrl+R for camera reset (D-04).
        reset_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self)
        reset_shortcut.activated.connect(self._viewport_panel.reset_camera)
        # Phase 42 D-06 — playback shortcuts on the main window (per Phase 33
        # D-12: shortcuts live on the main window, not per-widget). Space =
        # play/pause toggle; "." = step-one (exactly one step() while paused,
        # D-07). The render-poll stays alive while paused (Pitfall 6) so a
        # step-one snapshot renders on the next poll.
        play_pause_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Space"), self)
        play_pause_shortcut.activated.connect(self._toggle_play_pause)
        step_one_shortcut = QtGui.QShortcut(QtGui.QKeySequence("."), self)
        step_one_shortcut.activated.connect(self._on_step_one)

    # --- Phase 42 playback handlers (D-06/D-07/D-08/D-09/D-12) ---
    def _toggle_play_pause(self) -> None:
        """Space shortcut — toggle the Play/Pause action (routes through the
        toggled signal so the status-bar + worker stay in sync)."""
        self._act_play_pause.setChecked(not self._act_play_pause.isChecked())

    def _on_play_pause_toggled(self, checked: bool) -> None:
        """Play/Pause toolbar action toggled. ``checked`` = playing."""
        # checked = playing -> paused = not checked; the worker resumes its
        # accumulator when paused=False. Emitted via the proxy signal so the
        # @Slot runs queued on the worker thread (NOT the UI thread).
        self._play_pause_request.emit(not checked)
        self._update_playback_status(
            playing=checked,
            speed=self._current_speed(),
            static=self._viewport_panel._static_scene,
        )

    def _on_step_one(self) -> None:
        """Step-one toolbar action / "." shortcut (D-07). Runs exactly one
        ``step(None)`` on the worker while paused (does NOT resume the
        accumulator). The render-poll picks up the new snapshot on its next
        ~30 Hz tick (Pitfall 6)."""
        self._step_one_request.emit()

    def _on_speed_changed(self, text: str) -> None:
        """Speed QComboBox currentTextChanged (D-09). Scales wall_dt on the
        worker (NOT sim_dt — Pitfall 5). Session-only (D-05 — NOT persisted
        to QSettings; resets to 1x on launch per D-10)."""
        try:
            speed = float(text.rstrip("x"))
        except ValueError:
            speed = 1.0
        self._speed_request.emit(speed)
        self._update_playback_status(
            playing=self._act_play_pause.isChecked(),
            speed=speed,
            static=self._viewport_panel._static_scene,
        )

    def _current_speed(self) -> float:
        """Parse the speed combo's current text to a float multiplier."""
        try:
            return float(self._speed_combo.currentText().rstrip("x"))
        except ValueError:
            return 1.0

    def _update_playback_status(self, playing: bool, speed: float, static: bool = False) -> None:
        """D-08 — reflect play/pause/static in the 5th status-bar segment.

        Routes through ``safe_error_message`` if scene detail ever leaks in
        (defensive default per Security Domain V5); the generic static-scene
        hint has no scene content, so no redaction is strictly needed.
        """
        if static and not playing:
            self._status_playback.setText("⏸ paused (static scene — no dynamics)")
        elif playing:
            # :g strips the trailing ".0" so 1.0 renders as "1" (matches the
            # speed combo text "1x", "2x", "0.5x", etc. — D-09/D-10).
            self._status_playback.setText(f"▶ playing {speed:g}x")
        else:
            self._status_playback.setText("⏸ paused")

    def _refresh_playback_status(self) -> None:
        """Slot for ``ViewportPanel._scene_bound`` — re-read the panel-local
        D-12 hint + the current toolbar state and refresh the status-bar
        playback segment after a scene swap (the hint + paused state may
        change across scenes). Called queued so the initial emit during
        ``set_playback`` (before the toolbar/status exist) defers safely."""
        # Guard the very first emit during __init__ (queued connection means
        # this normally runs after __init__, but be defensive against any
        # re-entrancy).
        if not hasattr(self, "_status_playback") or not hasattr(self, "_act_play_pause"):
            return
        self._update_playback_status(
            playing=self._act_play_pause.isChecked(),
            speed=self._current_speed(),
            static=self._viewport_panel._static_scene,
        )

    def _wire_drag_drop(self) -> None:
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and self._is_json_url(event.mimeData().urls()[0]):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls and self._is_json_url(urls[0]):
            self._open_scene(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    @staticmethod
    def _is_json_url(url: QtCore.QUrl) -> bool:
        return url.toLocalFile().lower().endswith(".json")

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self._status_path = QtWidgets.QLabel("Untitled")
        self._status_sim = QtWidgets.QLabel("—")
        self._status_fps = QtWidgets.QLabel("—")
        self._status_validation = QtWidgets.QLabel("—")
        # Phase 42 D-08 — 5th permanent QLabel for the playback state segment
        # ("▶ playing {speed}x" / "⏸ paused" / "⏸ paused (static scene — no
        # dynamics)" per D-12). Same Panel/Sunken frame as the existing 4
        # labels for visual consistency.
        self._status_playback = QtWidgets.QLabel("⏸ paused")
        self._status_playback.setObjectName("status_playback")
        for w in (
            self._status_path,
            self._status_sim,
            self._status_fps,
            self._status_validation,
            self._status_playback,
        ):
            w.setFrameShape(QtWidgets.QFrame.Shape.Panel)
            w.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
            bar.addPermanentWidget(w)

    def _set_status(self, path: str, sim: str, fps: str, validation: str) -> None:
        self._status_path.setText(path)
        self._status_sim.setText(f"sim: {sim}")
        self._status_fps.setText(f"fps: {fps}")
        self._status_validation.setText(f"validate: {validation}")

    def _update_fps_status(self, fps: float) -> None:
        path_label = self._current_path.name if self._current_path else "Untitled"
        sim_label = (
            self._scene.simulator.value
            if self._scene and hasattr(self._scene.simulator, "value")
            else "—"
        )
        self._set_status(path_label, sim_label, f"{fps:.1f}", "—")

    def _on_node_selected(self, cls: type) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        instance = _find_instance(self._scene, cls)
        if instance is None:
            return
        specs = SchemaWalker().walk(cls.model_json_schema())
        self._property_form.set_field_specs(specs, instance)

    def _action_new(self) -> None:
        from surg_rl.scene_definition import SceneDefinition

        self._scene = SceneDefinition()
        self._current_path = None
        self._refresh_viewport_and_tree()
        self._set_status("Untitled", "—", "—", "—")
        self._undo_stack.clear()

    def _action_open(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open scene", str(Path.cwd()), "Scene JSON (*.json)"
        )
        if path:
            self._open_scene(Path(path))

    def _action_save(self) -> None:
        if self._current_path is None:
            self._action_save_as()
        else:
            self._save_scene_to(self._current_path)

    def _action_save_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save scene as",
            str(self._current_path or Path.cwd() / "scene.json"),
            "Scene JSON (*.json)",
        )
        if path:
            self._save_scene_to(Path(path))

    def _action_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            "About Surg-RL Scene Editor",
            "Surg-RL Scene Editor\nv0.5.0\nPhase 33 - PySide6 scene editor",
        )

    def _action_reset_layout(self) -> None:
        self._dock_state.reset_to_default(self)

    def _open_scene(self, path: Path) -> None:
        from surg_rl.scene_definition import load_scene

        try:
            self._scene = load_scene(path)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Open failed", safe_error_message(exc))
            return
        self._current_path = path
        self._settings.add_recent_file(path)
        self._refresh_viewport_and_tree()
        self._refresh_recent_menu()
        self._undo_stack.clear()
        sim = (
            self._scene.simulator.value
            if hasattr(self._scene.simulator, "value")
            else str(self._scene.simulator)
        )
        self._set_status(path.name, sim, "—", "valid")

    def _save_scene_to(self, path: Path) -> None:
        from pydantic import ValidationError

        from surg_rl.scene_definition import SceneDefinition, save_scene

        if self._scene is None:
            return
        try:
            SceneDefinition.model_validate(self._scene.model_dump())
        except ValidationError as exc:
            QtWidgets.QMessageBox.critical(self, "Validation failed", safe_error_message(exc))
            raise
        save_scene(self._scene, path)
        self._current_path = path
        self._undo_stack.clear_on_save()
        sim = (
            self._scene.simulator.value
            if hasattr(self._scene.simulator, "value")
            else str(self._scene.simulator)
        )
        self._set_status(path.name, sim, "—", "valid")

    def _refresh_viewport_and_tree(self) -> None:
        # D-06: in-place update_scene swap — NO widget recreation (bug #3 fix).
        # The widget identity (ViewportPanel / SceneTreeView) survives, so the
        # dock geometry keyed on objectName survives scene loads. The
        # node_selected connection wired in _build_dock_widgets survives too
        # (no re-connect needed). The old simulator is closed inside
        # ViewportPanel.update_scene (Pitfall 7), and _tick reloads the new
        # scene's simulator on the next tick via _on_load_simulator.
        self._tree_view.update_scene(self._scene or _empty_scene_stub())
        self._viewport_panel.update_scene(self._scene or _empty_scene_stub())

    def _on_undo(self) -> None:
        from surg_rl.editor.undo_stack import SceneUndoStack

        self._undo_stack.undo()
        snap = SceneUndoStack.take_active_apply()
        if snap is not None:
            self._scene = snap
            self._refresh_viewport_and_tree()

    def _on_redo(self) -> None:
        from surg_rl.editor.undo_stack import SceneUndoStack

        self._undo_stack.redo()
        snap = SceneUndoStack.take_active_apply()
        if snap is not None:
            self._scene = snap
            self._refresh_viewport_and_tree()

    def _update_undo_actions(self) -> None:
        self._undo_action.setEnabled(self._undo_stack.canUndo())
        self._redo_action.setEnabled(self._undo_stack.canRedo())

    def _on_llm_scene_accepted(self, scene: SceneDefinition) -> None:
        from surg_rl.scene_definition import SceneDefinition

        before = self._scene.model_copy(deep=True) if self._scene is not None else SceneDefinition()
        self._undo_stack.push_snapshot(before, scene)
        self._scene = scene
        self._refresh_viewport_and_tree()
        self._set_status("Untitled (LLM draft)", "—", "—", "unvalidated")

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        for p in self._settings.recent_files():
            self._recent_menu.addAction(
                p, lambda checked=False, path=p: self._open_scene(Path(path))
            )
        self._recent_menu.clear()
        for p in self._settings.recent_files():
            self._recent_menu.addAction(
                p, lambda checked=False, path=p: self._open_scene(Path(path))
            )

    def _restore_geometry(self) -> None:
        geo, state = self._settings.load_window()
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1280, 800)
        if state is not None:
            self.restoreState(state)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        # Capture the factory-default dock layout at first show (D-01). The
        # one-shot guard lives inside DockStateManager (Pitfall 5) so
        # subsequent showEvents (minimize/restore) do NOT overwrite the
        # factory snapshot with the user's rearranged layout.
        self._dock_state.capture_factory_default(self)
        super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        # D-04: emit aboutToClose BEFORE super().closeEvent() so every
        # registered panel.stop() (LLMPanel.stop, future workers) runs before
        # Qt tears down children (SC#3 — mid-LLM-call clean exit). Best-effort;
        # never block quit (D-05 — log and proceed on any error).
        try:  # noqa: SIM105 — best-effort teardown; broad suppress is intentional
            self.aboutToClose.emit()
        except Exception:  # noqa: BLE001
            pass  # best-effort — don't block window close on panel teardown
        # Stop the viewport render loop BEFORE Qt tears down — prevents
        # dangling QTimer callbacks and MuJoCo Renderer __del__ crashes
        # during interpreter shutdown (UAT Gap 2 fix, plan 33-07).
        try:  # noqa: SIM105 — best-effort cleanup; broad suppress is intentional
            self._viewport_panel.stop()
        except Exception:  # noqa: BLE001
            pass  # best-effort — don't block window close on viewport cleanup
        self._settings.save_window(self.saveGeometry(), self.saveState())
        super().closeEvent(event)
