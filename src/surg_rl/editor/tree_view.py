"""SceneTreeView - left-dock QTreeView showing scene structure with validation.

Per GUI-04 + CONTEXT.md D-05, D-08, D-17:
  - QStandardItemModel populated from SceneDefinition's nested structure
  - Right-click context menu: Add Child, Remove, Duplicate
  - Drag-reorder within a parent
  - Validation icon per node: red dot (invalid), green check (valid), gray dot (unvalidated)
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor._safe_error import safe_error_message

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition


class _ValidationState(Enum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"


_DATA_ROLE_VALIDATION = QtCore.Qt.ItemDataRole.UserRole + 1
_DATA_ROLE_CLASS = QtCore.Qt.ItemDataRole.UserRole + 2
_DATA_ROLE_INSTANCE = QtCore.Qt.ItemDataRole.UserRole + 3
_DATA_ROLE_COLLECTION = QtCore.Qt.ItemDataRole.UserRole + 4


def _icon_for_state(state: _ValidationState) -> QtGui.QIcon:
    pixmap = QtGui.QPixmap(12, 12)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    color = {
        _ValidationState.UNVALIDATED: QtGui.QColor("#888888"),
        _ValidationState.VALID: QtGui.QColor("#22cc22"),
        _ValidationState.INVALID: QtGui.QColor("#cc2222"),
    }[state]
    painter.setBrush(color)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 8, 8)
    painter.end()
    return QtGui.QIcon(pixmap)


class SceneTreeView(QtWidgets.QTreeView):
    """QTreeView showing the SceneDefinition's structure with validation icons."""

    node_selected = QtCore.Signal(type)

    def __init__(self, scene: SceneDefinition) -> None:
        super().__init__()
        self._scene = scene
        self._model = QtGui.QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Scene Elements"])
        self.setModel(self._model)
        self.setHeaderHidden(False)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._build_tree()
        self.expandAll()

    def _build_tree(self) -> None:
        root = QtGui.QStandardItem(self._scene.metadata.name if self._scene.metadata else "Untitled")
        root.setData(_ValidationState.UNVALIDATED, _DATA_ROLE_VALIDATION)
        root.setIcon(_icon_for_state(_ValidationState.UNVALIDATED))
        self._model.appendRow(root)

        for label, attr, is_collection in [
            ("Simulator", "simulator", False),
            ("Environment", "environment", False),
            ("Robots", "robots", True),
            ("Tissues", "tissues", True),
            ("Instruments", "instruments", True),
            ("Task", "task", False),
        ]:
            value = getattr(self._scene, attr, None)
            if value is None and not is_collection:
                continue
            section_item = self._make_node(label, value, is_collection=is_collection)
            root.appendRow(section_item)
            if is_collection:
                for i, child in enumerate(value or []):
                    child_label = getattr(child, "name", None) or f"{label[:-1]} {i}"
                    child_item = self._make_node(child_label, child, is_collection=False)
                    section_item.appendRow(child_item)

    def _make_node(self, label: str, value: Any, is_collection: bool) -> QtGui.QStandardItem:
        item = QtGui.QStandardItem(label)
        item.setData(_ValidationState.UNVALIDATED, _DATA_ROLE_VALIDATION)
        item.setIcon(_icon_for_state(_ValidationState.UNVALIDATED))
        if value is not None:
            item.setData(type(value), _DATA_ROLE_CLASS)
            item.setData(value, _DATA_ROLE_INSTANCE)
        item.setData(is_collection, _DATA_ROLE_COLLECTION)
        return item

    def _on_selection_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        if not current.isValid():
            return
        item = self._model.itemFromIndex(current)
        cls = item.data(_DATA_ROLE_CLASS)
        if cls is not None:
            self.node_selected.emit(cls)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        index = self.indexAt(pos)
        if not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        menu = self._build_context_menu(item)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _build_context_menu(self, item: QtGui.QStandardItem) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)
        is_collection = item.data(_DATA_ROLE_COLLECTION) or False
        menu.addAction("Add Child", lambda: self._add_child(item))
        if item.parent() is not None:
            menu.addAction("Remove", lambda: self._remove_node(item))
        if not is_collection and item.parent() is not None:
            menu.addAction("Duplicate", lambda: self._duplicate_node(item))
        return menu

    def _add_child(self, item: QtGui.QStandardItem) -> None:
        try:
            from surg_rl.scene_definition import InstrumentConfig
        except ImportError:
            return
        new_item = self._make_node(f"New {item.text()}", InstrumentConfig(), is_collection=False)
        item.appendRow(new_item)

    def _remove_node(self, item: QtGui.QStandardItem) -> None:
        parent = item.parent()
        if parent is None:
            return
        parent.removeRow(item.row())

    def _duplicate_node(self, item: QtGui.QStandardItem) -> None:
        parent = item.parent()
        if parent is None:
            return
        original = item.data(_DATA_ROLE_INSTANCE)
        if original is None:
            return
        try:
            duplicate = original.model_copy(deep=True)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Duplicate failed", safe_error_message(exc)
            )
            return
        new_item = self._make_node(item.text() + " (copy)", duplicate, is_collection=False)
        parent.appendRow(new_item)

    def mark_validation(self, index: QtCore.QModelIndex, state: _ValidationState) -> None:
        if not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        item.setData(state, _DATA_ROLE_VALIDATION)
        item.setIcon(_icon_for_state(state))
