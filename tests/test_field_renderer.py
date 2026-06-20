"""TDD regression for FieldRenderer - covers GUI-05's widget factory registry."""
from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Skip the entire module if PySide6 is not installed
pytest.importorskip("PySide6", reason="PySide6 not installed")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


class TestFieldRendererRegistry:
    def test_registry_has_five_widget_factories(self, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        r = FieldRenderer()
        assert "vec3-spinbox" in r.registry
        assert "enum-combobox" in r.registry
        assert "file-picker" in r.registry
        assert "color-picker" in r.registry
        assert "range-slider" in r.registry

    def test_unknown_widget_hint_falls_back_to_text(self, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        r = FieldRenderer()
        spec = FieldSpec(json_path="x", field_name="x", type="string", widget_hint="bogus-type")
        widget = r.render(spec)
        from PySide6.QtWidgets import QLineEdit
        assert isinstance(widget, QLineEdit)


class TestFieldRendererWidgetDispatch:
    def test_vec3_spinbox_renders_three_number_inputs(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QWidget, QDoubleSpinBox
        r = FieldRenderer()
        spec = FieldSpec(json_path="position", field_name="position", type="object",
                         widget_hint="vec3-spinbox", default_value={"x": 0.0, "y": 0.0, "z": 0.0})
        widget = r.render(spec)
        assert isinstance(widget, QWidget)
        spinboxes = widget.findChildren(QDoubleSpinBox)
        assert len(spinboxes) == 3
        assert [s.objectName() for s in spinboxes] == ["x", "y", "z"]

    def test_enum_combobox_renders_with_enum_values(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QComboBox
        r = FieldRenderer()
        spec = FieldSpec(json_path="color", field_name="color", type="string",
                         widget_hint="enum-combobox", enum_values=["red", "green", "blue"],
                         default_value="red")
        widget = r.render(spec)
        assert isinstance(widget, QComboBox)
        assert [widget.itemText(i) for i in range(widget.count())] == ["red", "green", "blue"]
        assert widget.currentText() == "red"

    def test_file_picker_renders_line_edit_plus_button(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QWidget, QLineEdit, QPushButton
        r = FieldRenderer()
        spec = FieldSpec(json_path="mesh", field_name="mesh", type="string", format="uri",
                         widget_hint="file-picker", default_value="")
        widget = r.render(spec)
        assert isinstance(widget, QWidget)
        assert widget.findChild(QLineEdit) is not None
        assert widget.findChild(QPushButton) is not None

    def test_color_picker_renders_button(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QPushButton
        r = FieldRenderer()
        spec = FieldSpec(json_path="color", field_name="color", type="string",
                         widget_hint="color-picker", default_value="#ff0000")
        widget = r.render(spec)
        assert isinstance(widget, QPushButton)

    def test_range_slider_renders_slider_with_constraints(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QSlider
        r = FieldRenderer()
        spec = FieldSpec(json_path="opacity", field_name="opacity", type="number",
                         widget_hint="range-slider", default_value=0.5,
                         constraints={"minimum": 0.0, "maximum": 1.0})
        widget = r.render(spec)
        assert isinstance(widget, QSlider)
        assert widget.minimum() == 0
        assert widget.maximum() == 100


class TestFieldRendererDefaults:
    def test_widget_displays_default_value(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QLineEdit
        r = FieldRenderer()
        spec = FieldSpec(json_path="name", field_name="name", type="string",
                         widget_hint="text", default_value="hello")
        widget = r.render(spec)
        assert isinstance(widget, QLineEdit)
        assert widget.text() == "hello"

    def test_widget_omits_none_for_optional_fields(self, skip_no_pyside6, qapp) -> None:
        from surg_rl.editor.field_renderer import FieldRenderer
        from surg_rl.editor.schema_walker import FieldSpec
        from PySide6.QtWidgets import QLineEdit
        r = FieldRenderer()
        spec = FieldSpec(json_path="description", field_name="description", type="string",
                         widget_hint="text", default_value=None, required=False)
        widget = r.render(spec)
        assert isinstance(widget, QLineEdit)
        assert widget.text() == ""
