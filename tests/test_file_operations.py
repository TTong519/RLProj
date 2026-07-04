"""TDD regression for Phase 33 file operations + undo/redo + LLM panel (GUI-01/02/06/07)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# Pure-Python tests (no PySide6 required)
class TestFileOperationsPurePython:
    def test_undo_stack_module_loads(self) -> None:
        src = Path("src/surg_rl/editor/undo_stack.py").read_text()
        assert "class SceneUndoStack" in src
        assert "_MAX_DEPTH" in src

    def test_llm_panel_module_loads(self) -> None:
        src = Path("src/surg_rl/editor/llm_panel.py").read_text()
        assert "class LLMPanel" in src
        assert "class TextParserWorker" in src

    def test_main_window_wires_file_ops(self) -> None:
        src = Path("src/surg_rl/editor/main_window.py").read_text()
        assert "_save_scene_to" in src
        assert "_open_scene" in src
        assert "_undo_stack" in src
        assert "_on_llm_scene_accepted" in src

    def test_difficulty_level_enum_survives_round_trip(self, tmp_path) -> None:
        """Lock GUI-02: Pydantic v2 round-trip preserves _FloatMixin DifficultyLevel."""
        from surg_rl.rl.difficulty import DifficultyLevel
        from surg_rl.scene_definition import (
            SceneDefinition,
            SimulatorType,
            TaskConfig,
            load_scene,
            save_scene,
        )

        task = TaskConfig(name="x", description="y", difficulty_level=DifficultyLevel.HARD)
        scene = SceneDefinition(simulator=SimulatorType.MUJOCO, task=task)
        target = tmp_path / "out.json"
        save_scene(scene, target)
        reloaded = load_scene(target, validate=True)
        assert float(reloaded.task.difficulty_level) == 1.0
        assert reloaded.task.difficulty_level == DifficultyLevel.HARD


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


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path


def _minimal_scene() -> dict:
    return {
        "simulator": "mujoco",
        "environment": {
            "name": "main",
            "cameras": [],
            "lights": [],
        },
    }


@pytestmark_viewport
class TestSaveScene:
    def test_save_writes_valid_json(self, qapp, tmp_path) -> None:
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.scene_definition import SceneDefinition, SimulatorType

        w = EditorWindow()
        w._scene = SceneDefinition(simulator=SimulatorType.MUJOCO)
        target = tmp_path / "out.json"
        w._save_scene_to(target)
        try:
            assert target.exists()
            loaded = json.loads(target.read_text())
            assert "simulator" in loaded
        finally:
            w.close()


@pytestmark_viewport
class TestOpenScene:
    def test_open_loads_scene(self, tmp_path, isolated_home) -> None:
        scene_path = tmp_path / "test.json"
        scene_path.write_text(json.dumps(_minimal_scene()))
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow(scene_path=scene_path)
        assert w._scene is not None
        assert w._current_path == scene_path


@pytestmark_viewport
class TestUndoStack:
    def test_push_snapshot_then_undo_restores_before(self, qapp) -> None:
        from surg_rl.editor.undo_stack import SceneUndoStack
        from surg_rl.scene_definition import SceneDefinition, SimulatorType

        before = SceneDefinition(simulator=SimulatorType.MUJOCO)
        after = SceneDefinition(simulator=SimulatorType.PYBULLET)
        stack = SceneUndoStack()
        stack.push_snapshot(before, after)
        stack.undo()
        snap = SceneUndoStack.take_active_apply()
        assert snap is not None
        assert snap.simulator == SimulatorType.MUJOCO

    def test_redo_after_undo_restores_after(self, qapp) -> None:
        from surg_rl.editor.undo_stack import SceneUndoStack
        from surg_rl.scene_definition import SceneDefinition, SimulatorType

        before = SceneDefinition(simulator=SimulatorType.MUJOCO)
        after = SceneDefinition(simulator=SimulatorType.PYBULLET)
        stack = SceneUndoStack()
        stack.push_snapshot(before, after)
        stack.undo()
        SceneUndoStack.take_active_apply()
        stack.redo()
        snap = SceneUndoStack.take_active_apply()
        assert snap is not None
        assert snap.simulator == SimulatorType.PYBULLET


@pytestmark_viewport
class TestUndoStackCap:
    def test_stack_caps_at_100(self, qapp) -> None:
        from surg_rl.editor.undo_stack import SceneUndoStack
        from surg_rl.scene_definition import SceneDefinition, SimulatorType

        stack = SceneUndoStack()
        for _ in range(150):
            stack.push_snapshot(
                SceneDefinition(), SceneDefinition(simulator=SimulatorType.PYBULLET)
            )
        undo_count = 0
        while stack.canUndo():
            stack.undo()
            undo_count += 1
        assert undo_count == 100
