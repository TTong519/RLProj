"""Regression tests for the Phase 33 viewport + mjpython refactor."""
from __future__ import annotations

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
        assert ("running_under_mjpython =" not in src), (
            "mujoco_simulator.py still has the inline 3-signal mjpython check; "
            "refactor to use _is_running_under_mjpython()"
        )
        assert ("_is_running_under_mjpython" in src), (
            "mujoco_simulator.py must call _is_running_under_mjpython()"
        )


class TestAppMojocoReexec:
    def test_app_main_includes_mjpython_reexec_block(self) -> None:
        src = Path("src/surg_rl/editor/app.py").read_text()
        assert "os.execvp" in src and "mjpython" in src, (
            "app.main() must re-exec under mjpython on macOS"
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

pytestmark_viewport = pytest.mark.skipif(
    not _HAVE_PYSIDE6, reason="PySide6 not installed"
)


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
        from surg_rl.editor.viewport import ViewportPanel
        from PySide6.QtWidgets import QLabel
        scene = _fake_scene()
        panel = ViewportPanel(scene)
        assert isinstance(panel._canvas, QLabel)
        panel.stop()

    def test_display_array_sets_pixmap(self, qapp) -> None:
        from surg_rl.editor.viewport import ViewportPanel
        import numpy as np
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
        from surg_rl.editor.viewport import ViewportPanel
        from surg_rl.editor import QtCore
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
    def test_main_window_central_widget_is_viewport_panel(self, qapp, tmp_path, monkeypatch) -> None:
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
            assert mock.call_count == 0, (
                "_tick must not reschedule QTimer.singleShot after stop()"
            )

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
            assert "(simulator unavailable)" in panel._canvas.text(), (
                "canvas must show simulator-unavailable text"
            )
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
            assert "Render error" in panel._canvas.text(), (
                "canvas must show render error text"
            )
            assert mock.call_count >= 1, (
                "_tick must reschedule after a render exception"
            )
        panel.stop()


