"""EditorWindow — Phase 33 main window shell.

Plans 33-02..05 fill in the panes:
  - 33-02: SchemaWalker + FieldRenderer (properties pane)
  - 33-03: Viewport with 3D render
  - 33-04: Tree view + validation icons
  - 33-05: LLM panel + undo/redo
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor._safe_error import safe_error_message
from surg_rl.editor._settings import EditorSettings

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition

_PLACEHOLDER_TEXT = "(populated by Phase 33 plan {plan})"


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

    def __init__(self, scene_path: str | Path | None = None) -> None:
        super().__init__()
        self.setObjectName("EditorWindow")
        self.setWindowTitle("Surg-RL Scene Editor")
        self._settings = EditorSettings()
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

        self._build_dock_widgets()
        self._build_menu_bar()
        self._build_status_bar()
        self._wire_drag_drop()
        self._wire_shortcuts()
        self._restore_geometry()
        self._update_undo_actions()
        self._set_status("Untitled", "—", "—", "—")

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
        for w in (self._status_path, self._status_sim, self._status_fps, self._status_validation):
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
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self._properties_dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self._llm_dock)
        self._tree_dock.show()
        self._properties_dock.show()
        self._llm_dock.show()

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
        from surg_rl.editor.tree_view import SceneTreeView
        from surg_rl.editor.viewport import ViewportPanel

        self._tree_view = SceneTreeView(self._scene or _empty_scene_stub())
        self._tree_dock.setWidget(self._tree_view)
        self._tree_view.node_selected.connect(self._on_node_selected)
        old_panel = self._viewport_panel
        self._viewport_panel = ViewportPanel(
            scene=self._scene or _empty_scene_stub(),
            on_fps_update=self._update_fps_status,
        )
        self.setCentralWidget(self._viewport_panel)
        old_panel.stop()

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
