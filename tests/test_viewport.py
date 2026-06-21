"""Regression tests for the Phase 33 viewport + mjpython refactor."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# File-content tests (no PySide6 required) — verify the mjpython refactor
class TestViewportMojocoRefactor:
    """Lock that mujoco_simulator.py's inline mjpython block is gone."""

    def test_mujoco_simulator_uses_shared_helper(self) -> None:
        src = Path("src/surg_rl/simulators/mujoco_simulator.py").read_text()
        assert "running_under_mjpython =" not in src, (
            "mujoco_simulator.py still has the inline 3-signal mjpython check; "
            "refactor to use _is_running_under_mjpython()"
        )
        assert (
            "_is_running_under_mjpython" in src
        ), "mujoco_simulator.py must call _is_running_under_mjpython()"


class TestAppMjpythonNoReexec:
    def test_app_main_does_not_reexec_under_mjpython(self) -> None:
        src = Path("src/surg_rl/editor/app.py").read_text()
        assert "os.execvp" not in src, (
            "app.main() must NOT re-exec under mjpython on macOS — "
            "mjpython runs Python on a secondary thread and breaks PySide6"
        )

    def test_app_main_no_longer_exits_on_mjpython_warn(self) -> None:
        src = Path("src/surg_rl/editor/app.py").read_text()
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "_ensure_mjpython_or_warn" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("#"):
                    continue
                assert next_line != "sys.exit(1)", (
                    f"app.main() still has sys.exit(1) after "
                    f"_ensure_mjpython_or_warn() at line {i+1}"
                )


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
    scene.environment.cameras = [MagicMock()]
    scene.environment.cameras[0].name = "main"
    scene.simulator.value = "mujoco"
    return scene


@pytestmark_viewport
class TestViewportFrame:
    def test_canvas_is_qlabel_with_pixmap(self, qapp) -> None:
        from PySide6.QtWidgets import QLabel

        from surg_rl.editor.viewport import ViewportPanel

        scene = _fake_scene()
        panel = ViewportPanel(scene)
        assert isinstance(panel._canvas, QLabel)
        panel.stop()

    def test_display_array_sets_pixmap(self, qapp) -> None:
        import numpy as np

        from surg_rl.editor.viewport import ViewportPanel

        scene = _fake_scene()
        panel = ViewportPanel(scene)
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        arr[:, :, 0] = 255
        panel._display_array(arr)
        assert panel._canvas.pixmap() is not None
        assert not panel._canvas.pixmap().isNull()
        panel.stop()


@pytestmark_viewport
class TestViewportTimer:
    def test_tick_schedules_another_tick(self, qapp) -> None:
        from surg_rl.editor import QtCore
        from surg_rl.editor.viewport import ViewportPanel

        with patch.object(QtCore.QTimer, "singleShot") as mock:
            scene = _fake_scene()
            panel = ViewportPanel(scene)
            qapp.processEvents()
            mock.assert_called()
            panel.stop()


@pytestmark_viewport
class TestViewportCameraReset:
    def test_reset_camera_zeros_offsets(self, qapp) -> None:
        from surg_rl.editor.viewport import ViewportPanel

        scene = _fake_scene()
        panel = ViewportPanel(scene)
        panel._camera_offset["azimuth"] = 1.5
        panel._camera_offset["distance"] = 0.3
        panel.reset_camera()
        assert panel._camera_offset["azimuth"] == 0.0
        assert panel._camera_offset["distance"] == 1.0
        panel.stop()


@pytestmark_viewport
class TestViewportRenderRate:
    def test_frame_interval_is_50ms(self) -> None:
        from surg_rl.editor import viewport

        assert viewport._FRAME_INTERVAL_MS == 50


@pytestmark_viewport
class TestViewportInMainWindow:
    def test_main_window_central_widget_is_viewport_panel(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.editor.viewport import ViewportPanel

        w = EditorWindow()
        assert isinstance(w.centralWidget(), ViewportPanel)
        w.close()

    def test_main_window_reset_shortcut_connected(self, qapp, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        from PySide6.QtGui import QShortcut

        shortcuts = w.findChildren(QShortcut)
        assert any("R" in s.key().toString() for s in shortcuts)
        w.close()


@pytestmark_viewport
class TestViewportRenderLoopGuard:
    """UAT Gap 2: viewport render-loop hardening (33-07 task 1)."""

    def test_stop_halts_render_loop(self, qapp) -> None:
        from surg_rl.editor import QtCore
        from surg_rl.editor.viewport import ViewportPanel

        scene = _fake_scene()
        panel = ViewportPanel(scene, on_load_simulator=lambda s: None)
        qapp.processEvents()
        panel.stop()
        assert panel._running is False, "stop() must set _running=False"
        # After stop(), a queued _tick callback must NOT reschedule.
        with patch.object(QtCore.QTimer, "singleShot") as mock:
            panel._tick()
            assert mock.call_count == 0, "_tick must not reschedule QTimer.singleShot after stop()"

    def test_tick_recovers_from_simulator_none(self, qapp) -> None:
        from surg_rl.editor import QtCore
        from surg_rl.editor.viewport import ViewportPanel

        scene = _fake_scene()
        # Force simulator unavailable.
        panel = ViewportPanel(scene, on_load_simulator=lambda s: None)
        panel.stop()  # halt any auto-started loop first
        panel._running = True  # re-enable for the manual _tick under test
        panel._simulator = None
        with patch.object(QtCore.QTimer, "singleShot") as mock:
            panel._tick()
            assert (
                "(simulator unavailable)" in panel._canvas.text()
            ), "canvas must show simulator-unavailable text"
            assert mock.call_count >= 1, (
                "_tick must reschedule when simulator is unavailable "
                "(original bug: silent render-loop death)"
            )
        panel.stop()

    def test_del_guarded_against_attribute_error(self, qapp) -> None:
        from surg_rl.editor.viewport import ViewportPanel

        class _BadCloseSimulator:
            def close(self) -> None:
                raise AttributeError("_gl_context")

            def render(self, **kwargs):
                return None

        scene = _fake_scene()
        panel = ViewportPanel(scene, on_load_simulator=lambda s: _BadCloseSimulator())
        qapp.processEvents()
        # stop() must swallow the AttributeError from simulator.close().
        try:
            panel.stop()
        except AttributeError as exc:  # noqa: PT017
            pytest.fail(f"stop() must not raise AttributeError: {exc}")
        # __del__ must also be guarded — no AttributeError propagates.
        try:
            panel.__del__()
        except AttributeError as exc:  # noqa: PT017
            pytest.fail(f"__del__ must not raise AttributeError: {exc}")

    def test_render_error_reschedules(self, qapp) -> None:
        from surg_rl.editor import QtCore
        from surg_rl.editor.viewport import ViewportPanel

        class _RenderFailSimulator:
            def close(self) -> None:
                pass

            def render(self, **kwargs):
                raise RuntimeError("GL fail")

        scene = _fake_scene()
        panel = ViewportPanel(scene, on_load_simulator=lambda s: _RenderFailSimulator())
        panel.stop()  # halt auto-started loop
        panel._running = True  # re-enable for the manual _tick under test
        panel._simulator = _RenderFailSimulator()
        with patch.object(QtCore.QTimer, "singleShot") as mock:
            panel._tick()
            assert "Render error" in panel._canvas.text(), "canvas must show render error text"
            assert mock.call_count >= 1, "_tick must reschedule after a render exception"
        panel.stop()


@pytestmark_viewport
class TestEditorLaunchGuard:
    """UAT Gap 2: EditorWindow closeEvent + launch smoke test (33-07 task 2)."""

    def test_close_event_stops_viewport(self, qapp, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        from PySide6.QtGui import QCloseEvent

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        # Replace the viewport's stop() with a Mock to observe the call.
        mock_stop = MagicMock()
        w._viewport_panel.stop = mock_stop
        w.closeEvent(QCloseEvent())
        assert (
            mock_stop.call_count >= 1
        ), "closeEvent must call self._viewport_panel.stop() before Qt teardown"
        # Best-effort: close the window cleanly.
        with contextlib.suppress(Exception):
            w.close()

    def test_editor_launches_without_freeze(self, qapp, tmp_path, monkeypatch) -> None:
        """Launch smoke test — verifies the window shows and the event loop runs.

        UAT Gap 2 truth: 'window opens and remains responsive'. If the
        editor freezes on launch (the original bug), QTest.qWait(500) never
        returns and this test times out / hangs.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        from PySide6.QtTest import QTest

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        # Process events for 500ms — if the app froze, this blocks.
        QTest.qWait(500)
        assert w.isVisible(), (
            "Window must be visible after show() + 500ms event processing " "(no freeze on launch)"
        )
        w.close()
        QTest.qWait(100)
        # If we reach here, the launch did not freeze — test passes.


# File-content test — no PySide6 required. Guards the
# gui-no-render-under-mjpython fix: `surg_rl.rl.__init__` must NOT eagerly
# import heavy third-party deps (stable_baselines3/torch/tensorflow), so
# that `from surg_rl.rl.difficulty import DifficultyLevel` (the leaf
# enum used by `scene_definition.schema`) stays cheap and the GUI does
# not freeze on launch.
class TestRlPackageLazyImport:
    """Regression for the gui-no-render-under-mjpython launch freeze.

    Root cause: `scene_definition.schema` did
    `from surg_rl.rl.difficulty import DifficultyLevel`, which triggered
    `surg_rl.rl.__init__` to eagerly import `surg_rl.rl.callbacks` ->
    `stable_baselines3` -> `torch` -> `tensorflow` (~9-11s). The whole
    chain ran synchronously inside `EditorWindow.__init__`, blocking
    the QApplication event loop before `window.show()` and producing
    macOS "Application Not Responding" with no visible window.

    Fix: `surg_rl.rl.__init__` defers heavy re-exports behind PEP 562
    `__getattr__`. Only the lightweight `difficulty` and `task_results`
    submodules are imported eagerly.
    """

    def test_rl_init_does_not_eagerly_import_stable_baselines3(self) -> None:
        src = Path("src/surg_rl/rl/__init__.py").read_text()
        # The heavy submodule re-exports must be deferred (lazy).
        assert "from .callbacks import" not in src, (
            "surg_rl.rl.__init__ must NOT eagerly import .callbacks "
            "(triggers stable_baselines3 -> torch -> tensorflow, ~9-11s). "
            "Use PEP 562 __getattr__ to defer it. "
            "(debug: gui-no-render-under-mjpython)"
        )
        assert "from .environment import" not in src, (
            "surg_rl.rl.__init__ must NOT eagerly import .environment "
            "(triggers simulator backends + heavy deps). "
            "Use PEP 562 __getattr__ to defer it."
        )
        assert "from .training import" not in src, (
            "surg_rl.rl.__init__ must NOT eagerly import .training "
            "(triggers stable_baselines3). "
            "Use PEP 562 __getattr__ to defer it."
        )
        assert "from .observation import" not in src, (
            "surg_rl.rl.__init__ must NOT eagerly import .observation. "
            "Use PEP 562 __getattr__ to defer it."
        )
        assert "from .action import" not in src, (
            "surg_rl.rl.__init__ must NOT eagerly import .action. "
            "Use PEP 562 __getattr__ to defer it."
        )
        assert "from .rewards import" not in src, (
            "surg_rl.rl.__init__ must NOT eagerly import .rewards. "
            "Use PEP 562 __getattr__ to defer it."
        )

    def test_rl_init_eagerly_imports_lightweight_submodules(self) -> None:
        """The leaf submodules (no heavy deps) stay eager for direct access."""
        src = Path("src/surg_rl/rl/__init__.py").read_text()
        assert "from .difficulty import DifficultyLevel" in src, (
            "surg_rl.rl.__init__ must still eagerly import .difficulty "
            "(the leaf enum) so `from surg_rl.rl import DifficultyLevel` "
            "works without triggering __getattr__."
        )
        assert "from .task_results import" in src, (
            "surg_rl.rl.__init__ must still eagerly import .task_results "
            "(lightweight, only pydantic)."
        )

    def test_rl_init_defines_pep562_getattr(self) -> None:
        src = Path("src/surg_rl/rl/__init__.py").read_text()
        assert "def __getattr__(name: str)" in src, (
            "surg_rl.rl.__init__ must define PEP 562 __getattr__ to defer "
            "heavy re-exports. (debug: gui-no-render-under-mjpython)"
        )


@pytestmark_viewport
class TestEditorLaunchImportCost:
    """Runtime regression for gui-no-render-under-mjpython.

    Asserts that constructing EditorWindow (which transitively imports
    scene_definition -> surg_rl.rl.difficulty) does NOT pull
    stable_baselines3 / torch / tensorflow into sys.modules. Before the
    fix, this took ~11s and froze the macOS app.
    """

    def test_editor_window_construction_does_not_load_heavy_rl_deps(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        # Ensure a fresh interpreter state for this test: confirm the
        # heavy deps are NOT already loaded before we construct the window.
        # (They may be loaded by other tests in the same session, so we
        # record the pre-state and assert no NEW heavy import is required
        # by EditorWindow construction — verified by importing
        # scene_definition alone not loading them.)
        import importlib

        # Force a fresh import of scene_definition in an isolated module
        # namespace is not trivial; instead assert the source-level guard:
        # importing surg_rl.scene_definition must not load stable_baselines3.
        # We clear the heavy modules from sys.modules if present (best
        # effort) and re-import scene_definition to see if they come back.
        for heavy in ("stable_baselines3", "torch", "tensorflow"):
            monkeypatch.delitem(sys.modules, heavy, raising=False)
        # Also clear surg_rl.rl so the lazy __init__ re-runs.
        for mod in list(sys.modules):
            if mod.startswith("surg_rl.rl") or mod.startswith("surg_rl.scene_definition"):
                monkeypatch.delitem(sys.modules, mod, raising=False)

        importlib.import_module("surg_rl.scene_definition")
        assert "stable_baselines3" not in sys.modules, (
            "Importing surg_rl.scene_definition must NOT eagerly load "
            "stable_baselines3 (causes ~9-11s GUI launch freeze). "
            "(debug: gui-no-render-under-mjpython)"
        )
        assert (
            "torch" not in sys.modules
        ), "Importing surg_rl.scene_definition must NOT eagerly load torch."
