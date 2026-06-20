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


def _empty_scene_stub() -> "SceneDefinition":
    """Create a minimal valid SceneDefinition for when the editor opens with no scene."""
    from surg_rl.scene_definition import SceneDefinition, SimulatorType
    return SceneDefinition(simulator=SimulatorType.MUJOCO)


class EditorWindow(QtWidgets.QMainWindow):
    """Phase 33 PySide6 scene editor main window."""

    def __init__(self, scene_path: str | Path | None = None) -> None:
        super().__init__()
        self.setObjectName("EditorWindow")
        self.setWindowTitle("Surg-RL Scene Editor")
        self._settings = EditorSettings()
        self._current_path: Path | None = None
        self._scene: "SceneDefinition | None" = None

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
        self._set_status("Untitled", "—", "—", "—")

        if scene_path is not None:
            self._open_scene(Path(scene_path))

    def _build_central_viewport(self) -> None:
        # Replaced in __init__ by ViewportPanel (Phase 33-03).
        pass

    def _build_dock_widgets(self) -> None:
        self._tree_dock = self._make_dock(
            "Scene Tree", QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            _PLACEHOLDER_TEXT.format(plan="33-04 — Tree View"),
        )
        self._properties_dock = self._make_dock(
            "Properties", QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
            _PLACEHOLDER_TEXT.format(plan="33-04 — Property Form"),
        )
        self._llm_dock = self._make_dock(
            "LLM Prompt-to-JSON", QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
            _PLACEHOLDER_TEXT.format(plan="33-05 — LLM Panel"),
        )

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
        file_menu.addAction("Save &As...", self._action_save_as, QtGui.QKeySequence.StandardKey.SaveAs)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, QtGui.QKeySequence.StandardKey.Quit)
        self._edit_menu = mb.addMenu("&Edit")
        self._undo_action = self._edit_menu.addAction("&Undo", lambda: None, QtGui.QKeySequence.StandardKey.Undo)
        self._redo_action = self._edit_menu.addAction("&Redo", lambda: None, QtGui.QKeySequence.StandardKey.Redo)
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
        sim_label = self._scene.simulator.value if self._scene and hasattr(self._scene.simulator, "value") else "—"
        self._set_status(path_label, sim_label, f"{fps:.1f}", "—")

    def _action_new(self) -> None: pass
    def _action_open(self) -> None: pass
    def _action_save(self) -> None: pass
    def _action_save_as(self) -> None: pass
    def _action_reset_layout(self) -> None: pass
    def _action_about(self) -> None: None
    def _open_scene(self, path: Path) -> None: pass
    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        for p in self._settings.recent_files():
            self._recent_menu.addAction(p, lambda checked=False, path=p: self._open_scene(Path(path)))

    def _restore_geometry(self) -> None:
        geo, state = self._settings.load_window()
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1280, 800)
        if state is not None:
            self.restoreState(state)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self._settings.save_window(self.saveGeometry(), self.saveState())
        super().closeEvent(event)
