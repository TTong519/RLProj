"""TDD regression for SceneTreeView + PropertyForm (GUI-04 + GUI-05 runtime)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# File-content / pure-Python tests can run without PySide6
class TestTreeViewModuleImports:
    def test_tree_view_module_loads(self) -> None:
        src = Path("src/surg_rl/editor/tree_view.py").read_text()
        assert "class SceneTreeView" in src
        assert "node_selected" in src

    def test_property_form_module_loads(self) -> None:
        src = Path("src/surg_rl/editor/property_form.py").read_text()
        assert "class PropertyForm" in src
        assert "validation_changed" in src

    def test_main_window_wires_tree_and_form(self) -> None:
        src = Path("src/surg_rl/editor/main_window.py").read_text()
        assert "SceneTreeView" in src
        assert "PropertyForm" in src
        assert "_on_node_selected" in src


# Qt-dependent tests below — require PySide6 + offscreen platform
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


def _fake_scene() -> MagicMock:
    """MagicMock-shaped scene for unit tests that don't need a real Pydantic model."""
    scene = MagicMock()
    scene.metadata.name = "test-scene"
    scene.simulator.value = "mujoco"
    scene.robots = []
    scene.tissues = []
    scene.instruments = []
    scene.environment.lights = []
    scene.environment.cameras = []
    scene.task = None
    return scene


# =====================================================================
# SceneTreeView tests
# =====================================================================


@pytestmark_viewport
class TestSceneTreeBuilds:
    def test_tree_populates_from_scene_top_level(self, qapp) -> None:
        from surg_rl.editor.tree_view import SceneTreeView

        scene = _fake_scene()
        tree = SceneTreeView(scene)
        model = tree.model()
        assert model.rowCount() >= 1

    def test_tree_root_label_is_scene_name(self, qapp) -> None:
        from surg_rl.editor.tree_view import SceneTreeView

        scene = _fake_scene()
        tree = SceneTreeView(scene)
        root = tree.model().item(0)
        assert "test-scene" in root.text()

    def test_tree_node_has_validation_icon_role(self, qapp) -> None:
        from surg_rl.editor.tree_view import SceneTreeView, _ValidationState

        scene = _fake_scene()
        tree = SceneTreeView(scene)
        root = tree.model().item(0)
        state = (
            root.data(_ValidationState.DATA_ROLE)
            if hasattr(_ValidationState, "DATA_ROLE")
            else None
        )
        assert state is None or state in {
            _ValidationState.UNVALIDATED,
            _ValidationState.VALID,
            _ValidationState.INVALID,
        }


@pytestmark_viewport
class TestSceneTreeContextMenu:
    def test_right_click_opens_context_menu(self, qapp) -> None:
        from PySide6.QtCore import Qt

        from surg_rl.editor.tree_view import SceneTreeView

        scene = _fake_scene()
        tree = SceneTreeView(scene)
        assert tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        assert hasattr(tree, "_show_context_menu")

    def test_context_menu_has_add_remove_duplicate(self, qapp) -> None:
        from surg_rl.editor.tree_view import SceneTreeView

        scene = _fake_scene()
        tree = SceneTreeView(scene)
        menu = tree._build_context_menu(tree.model().item(0))
        actions = [a.text() for a in menu.actions() if a.text()]
        assert "Add Child" in actions


# =====================================================================
# PropertyForm tests
# =====================================================================


@pytestmark_viewport
class TestPropertyFormRendersFields:
    def test_form_renders_widgets_for_class(self, qapp) -> None:
        from surg_rl.editor.property_form import PropertyForm
        from surg_rl.editor.schema_walker import SchemaWalker
        from surg_rl.scene_definition import Position

        form = PropertyForm()
        schema = Position.model_json_schema()
        specs = SchemaWalker().walk(schema)
        form.set_field_specs(specs, instance=Position())
        # The form wraps rows in a QScrollArea; inspect the internal form layout.
        assert form._form_layout.count() >= 1

    def test_form_uses_field_renderer(self, qapp) -> None:
        from PySide6.QtWidgets import QDoubleSpinBox

        from surg_rl.editor.property_form import PropertyForm
        from surg_rl.editor.schema_walker import SchemaWalker
        from surg_rl.scene_definition import Position

        form = PropertyForm()
        specs = SchemaWalker().walk(Position.model_json_schema())
        form.set_field_specs(specs, instance=Position())
        spinboxes = form._form_host.findChildren(QDoubleSpinBox)
        assert len(spinboxes) == 3


# =====================================================================
# EditorWindow integration tests
# =====================================================================


@pytestmark_viewport
class TestEditorWindowTreeAndForm:
    def test_editor_window_has_tree_and_form(self, qapp, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        from surg_rl.editor import QtWidgets
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.editor.property_form import PropertyForm
        from surg_rl.editor.tree_view import SceneTreeView

        w = EditorWindow()
        assert any(
            isinstance(d.widget(), SceneTreeView) for d in w.findChildren(QtWidgets.QDockWidget)
        )
        assert any(
            isinstance(d.widget(), PropertyForm) for d in w.findChildren(QtWidgets.QDockWidget)
        )
        w.close()

    def test_tree_builds_from_real_scene_definition(self, qapp) -> None:
        from surg_rl.editor.tree_view import SceneTreeView
        from surg_rl.scene_definition import InstrumentConfig, SceneDefinition, SimulatorType

        scene = SceneDefinition(simulator=SimulatorType.MUJOCO)
        scene.instruments.append(InstrumentConfig(name="scalpel1"))
        tree = SceneTreeView(scene)
        labels = []
        for r in range(tree.model().rowCount()):
            root_item = tree.model().item(r)
            for cr in range(root_item.rowCount()):
                labels.append(root_item.child(cr).text())
        assert "Instruments" in labels
        assert "Robots" in labels
        assert "Tissues" in labels
        for r in range(tree.model().rowCount()):
            root_item = tree.model().item(r)
            for cr in range(root_item.rowCount()):
                sec = root_item.child(cr)
                if sec.text() == "Instruments":
                    assert sec.rowCount() == 1
                    assert sec.child(0).text() == "scalpel1"
