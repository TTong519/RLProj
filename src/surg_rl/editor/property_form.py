"""PropertyForm - right-dock property form for the selected tree node.

Per GUI-05 + CONTEXT.md D-06..D-08:
  - QFormLayout populated by FieldRenderer.render(spec) for each FieldSpec
  - Debounced (150 ms) re-validation per D-08
  - Inline error labels below invalid fields
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from surg_rl.editor import QtCore, QtWidgets
from surg_rl.editor._safe_error import safe_error_message
from surg_rl.editor.field_renderer import FieldRenderer
from surg_rl.editor.schema_walker import FieldSpec

if TYPE_CHECKING:
    pass

_VALIDATION_DEBOUNCE_MS: int = 150


class PropertyForm(QtWidgets.QWidget):
    """QFormLayout-based property editor for the selected tree node's class."""

    validation_changed = QtCore.Signal(bool, str)

    def __init__(self) -> None:
        super().__init__()
        self._renderer = FieldRenderer()
        self._specs: list[FieldSpec] = []
        self._instance: BaseModel | None = None
        self._widgets: dict[str, QtWidgets.QWidget] = {}
        self._error_labels: dict[str, QtWidgets.QLabel] = {}
        self._validation_timer = QtCore.QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.setInterval(_VALIDATION_DEBOUNCE_MS)
        self._validation_timer.timeout.connect(self._run_validation)
        self._last_validation_ok: bool = True
        self._last_validation_error: str = ""

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._form_host = QtWidgets.QWidget()
        self._form_layout = QtWidgets.QFormLayout(self._form_host)
        self._form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._scroll.setWidget(self._form_host)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

    def set_field_specs(self, specs: list[FieldSpec], instance: BaseModel) -> None:
        self._clear_form()
        self._specs = specs
        self._instance = instance
        for spec in specs:
            widget = self._renderer.render(spec)
            label = QtWidgets.QLabel(spec.field_name)
            self._form_layout.addRow(label, widget)
            self._widgets[spec.json_path] = widget
            self._connect_widget_value_changed(widget, spec)
            error_label = QtWidgets.QLabel("")
            error_label.setStyleSheet("color: #cc2222; font-size: 10px;")
            error_label.setWordWrap(True)
            self._form_layout.addRow("", error_label)
            self._error_labels[spec.json_path] = error_label

    def _clear_form(self) -> None:
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._widgets.clear()
        self._error_labels.clear()

    def _connect_widget_value_changed(self, widget: QtWidgets.QWidget, spec: FieldSpec) -> None:
        if hasattr(widget, "valueChanged"):
            widget.valueChanged.connect(self._schedule_validation)
        elif hasattr(widget, "textChanged"):
            widget.textChanged.connect(self._schedule_validation)
        elif hasattr(widget, "currentTextChanged"):
            widget.currentTextChanged.connect(self._schedule_validation)
        else:
            for child in widget.findChildren(QtWidgets.QWidget):
                if hasattr(child, "valueChanged"):
                    child.valueChanged.connect(self._schedule_validation)
                elif hasattr(child, "textChanged"):
                    child.textChanged.connect(self._schedule_validation)
                elif hasattr(child, "currentTextChanged"):
                    child.currentTextChanged.connect(self._schedule_validation)
                elif hasattr(child, "clicked"):
                    child.clicked.connect(self._schedule_validation)

    def _schedule_validation(self, *_: Any) -> None:
        self._validation_timer.start()

    def _run_validation(self) -> None:
        if self._instance is None:
            return
        try:
            BaseModel.model_validate(type(self._instance), self._instance.model_dump())
        except ValidationError as exc:
            self._last_validation_ok = False
            self._last_validation_error = str(exc)
            self._show_field_errors(exc)
        except Exception as exc:  # noqa: BLE001
            self._last_validation_ok = False
            self._last_validation_error = safe_error_message(exc)
        else:
            self._last_validation_ok = True
            self._last_validation_error = ""
            self._clear_field_errors()
        self.validation_changed.emit(self._last_validation_ok, self._last_validation_error)

    def _show_field_errors(self, exc: ValidationError) -> None:
        self._clear_field_errors()
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            if loc in self._error_labels:
                self._error_labels[loc].setText(safe_error_message(err["msg"]))

    def _clear_field_errors(self) -> None:
        for label in self._error_labels.values():
            label.setText("")

    def is_valid(self) -> bool:
        return self._last_validation_ok
