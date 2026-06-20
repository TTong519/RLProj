"""FieldRenderer — dispatches FieldSpec -> Qt widget via registry pattern.

Per GUI-05 + D-06: registry dict keyed by FieldSpec.widget_hint maps to
widget factory. Unknown types fall back to QLineEdit (per D-06).
"""
from __future__ import annotations

from typing import Any, Callable

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor.schema_walker import FieldSpec


def _make_vec3_spinbox(spec: FieldSpec) -> QtWidgets.QWidget:
    """3 QDoubleSpinBox side-by-side (x, y, z) inside a QWidget container."""
    container = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    defaults = spec.default_value if isinstance(spec.default_value, dict) else {}
    for axis in ("x", "y", "z"):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName(axis)
        spin.setDecimals(4)
        spin.setRange(-1e6, 1e6)
        spin.setValue(float(defaults.get(axis, 0.0)))
        layout.addWidget(spin)
    return container


def _make_enum_combobox(spec: FieldSpec) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox()
    for v in spec.enum_values:
        combo.addItem(str(v))
    if spec.default_value is not None and str(spec.default_value) in [str(v) for v in spec.enum_values]:
        combo.setCurrentText(str(spec.default_value))
    return combo


def _make_file_picker(spec: FieldSpec) -> QtWidgets.QWidget:
    container = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    line = QtWidgets.QLineEdit(str(spec.default_value or ""))
    btn = QtWidgets.QPushButton("Browse...")

    def _on_browse() -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            container, f"Select {spec.field_name}", line.text()
        )
        if path:
            line.setText(path)

    btn.clicked.connect(_on_browse)
    layout.addWidget(line, 1)
    layout.addWidget(btn)
    return container


def _make_color_picker(spec: FieldSpec) -> QtWidgets.QPushButton:
    btn = QtWidgets.QPushButton(str(spec.default_value or "#ffffff"))
    btn.setProperty("color_hex", str(spec.default_value or "#ffffff"))

    def _on_pick() -> None:
        initial = QtGui.QColor(str(spec.default_value or "#ffffff"))
        chosen = QtWidgets.QColorDialog.getColor(initial, btn)
        if chosen.isValid():
            btn.setText(chosen.name())
            btn.setProperty("color_hex", chosen.name())

    btn.clicked.connect(_on_pick)
    return btn


def _make_range_slider(spec: FieldSpec) -> QtWidgets.QSlider:
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    lo = float(spec.constraints.get("minimum", 0.0))
    hi = float(spec.constraints.get("maximum", 1.0))
    val = float(spec.default_value if spec.default_value is not None else lo)
    if hi > lo:
        slider.setValue(int(round((val - lo) / (hi - lo) * 100)))
    return slider


def _make_text(spec: FieldSpec) -> QtWidgets.QLineEdit:
    return QtWidgets.QLineEdit(str(spec.default_value) if spec.default_value is not None else "")


class FieldRenderer:
    """Widget factory registry keyed by FieldSpec.widget_hint.

    Public attributes:
        - registry: dict[str, Callable[[FieldSpec], QtWidgets.QWidget]]
    Public methods:
        - render(spec) -> QtWidgets.QWidget: dispatches via registry; fallback to text.
    """

    def __init__(self) -> None:
        self.registry: dict[str, Callable[[FieldSpec], QtWidgets.QWidget]] = {
            "vec3-spinbox": _make_vec3_spinbox,
            "enum-combobox": _make_enum_combobox,
            "file-picker": _make_file_picker,
            "color-picker": _make_color_picker,
            "range-slider": _make_range_slider,
            "text": _make_text,
        }

    def render(self, spec: FieldSpec) -> QtWidgets.QWidget:
        factory = self.registry.get(spec.widget_hint, _make_text)
        return factory(spec)
