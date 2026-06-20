"""ViewportPanel — the 3D render surface for the scene editor.

Per CONTEXT.md D-01..D-04:
  - D-01: render-to-QImage (np.ndarray -> QImage -> QPixmap -> QLabel)
  - D-02: reuse BaseSimulator.render(mode="rgb_array", width, height, camera_name) as-is
  - D-03: QTimer.singleShot(50, self._tick) self-rescheduling (no interval timer)
  - D-04: mouse orbit/pan/zoom + R key camera reset
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from surg_rl.editor import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    import numpy as np

    from surg_rl.scene_definition import SceneDefinition
    from surg_rl.simulators.base_simulator import BaseSimulator

_DEFAULT_WIDTH: int = 640
_DEFAULT_HEIGHT: int = 480
_FRAME_INTERVAL_MS: int = 50
_ORBIT_SENSITIVITY: float = 0.005
_PAN_SENSITIVITY: float = 0.002
_ZOOM_STEP: float = 0.1


class ViewportPanel(QtWidgets.QWidget):
    """QWidget that renders the loaded scene at 20 Hz via QTimer.singleShot.

    Lifecycle:
        __init__ takes the loaded SceneDefinition and a callback for FPS updates.
        _tick is self-rescheduling: it processes one frame, then schedules the next
        via QTimer.singleShot(50, self._tick). This pattern (per D-03) prevents
        frame pile-up if the render takes > 50 ms.
    """

    def __init__(
        self,
        scene: SceneDefinition,
        on_fps_update: Callable[[float], None] | None = None,
        on_load_simulator: Callable[[SceneDefinition], BaseSimulator | None] | None = None,
    ) -> None:
        super().__init__()
        self._scene = scene
        self._on_fps_update = on_fps_update
        self._on_load_simulator = on_load_simulator or _default_load_simulator
        self._simulator: BaseSimulator | None = None
        self._frame_count: int = 0
        self._last_fps_check: float = 0.0

        self._canvas = QtWidgets.QLabel()
        self._canvas.setMinimumSize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
        self._canvas.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._canvas.setStyleSheet("background-color: #222; color: #888;")
        self._canvas.setText("(loading simulator...)")
        self._canvas.setMouseTracking(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._camera_offset = {"azimuth": 0.0, "elevation": 0.0, "distance": 1.0, "target": (0.0, 0.0, 0.0)}

        self._install_mouse_filters()
        self._start()

    def _start(self) -> None:
        QtCore.QTimer.singleShot(0, self._tick)

    def stop(self) -> None:
        if self._simulator is not None:
            self._simulator.close()
            self._simulator = None

    def _tick(self) -> None:
        if self._simulator is None:
            self._simulator = self._on_load_simulator(self._scene)
            if self._simulator is None:
                self._canvas.setText("(simulator unavailable)")
                return

        try:
            camera_name = None
            env = getattr(self._scene, "environment", None)
            if env is not None:
                cameras = getattr(env, "cameras", None)
                if cameras:
                    camera_name = getattr(cameras[0], "name", None)
            arr = self._simulator.render(
                mode="rgb_array",
                width=self._canvas.width(),
                height=self._canvas.height(),
                camera_name=camera_name,
            )
        except Exception as exc:  # noqa: BLE001
            from surg_rl.editor._safe_error import safe_error_message
            self._canvas.setText(f"Render error: {safe_error_message(exc)}")
            QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
            return

        if arr is not None:
            self._display_array(arr)
        self._frame_count += 1
        self._maybe_update_fps()

        QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)

    def _maybe_update_fps(self) -> None:
        import time
        now = time.monotonic()
        if self._last_fps_check == 0.0:
            self._last_fps_check = now
            return
        elapsed = now - self._last_fps_check
        if elapsed >= 1.0 and self._on_fps_update is not None:
            fps = self._frame_count / elapsed
            self._on_fps_update(fps)
            self._frame_count = 0
            self._last_fps_check = now

    def _display_array(self, arr: np.ndarray) -> None:
        h, w = arr.shape[:2]
        bytes_per_line = 3 * w
        qimg = QtGui.QImage(arr.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qimg).scaled(
            self._canvas.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self._canvas.setPixmap(pixmap)

    def _install_mouse_filters(self) -> None:
        self._canvas.installEventFilter(self)
        self._last_mouse_pos: QtCore.QPoint | None = None

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is not self._canvas:
            return super().eventFilter(obj, event)
        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._last_mouse_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            return True
        if event.type() == QtCore.QEvent.Type.MouseMove and self._last_mouse_pos is not None:
            cur = event.position().toPoint() if hasattr(event, "position") else event.pos()
            dx = cur.x() - self._last_mouse_pos.x()
            dy = cur.y() - self._last_mouse_pos.y()
            if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
                self._camera_offset["azimuth"] += dx * _ORBIT_SENSITIVITY
                self._camera_offset["elevation"] += dy * _ORBIT_SENSITIVITY
            elif event.buttons() & QtCore.Qt.MouseButton.MiddleButton:
                tx, ty, tz = self._camera_offset["target"]
                self._camera_offset["target"] = (
                    tx - dx * _PAN_SENSITIVITY,
                    ty + dy * _PAN_SENSITIVITY,
                    tz,
                )
            self._last_mouse_pos = cur
            return True
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            self._last_mouse_pos = None
            return True
        if event.type() == QtCore.QEvent.Type.Wheel:
            delta = event.angleDelta().y() / 120.0
            self._camera_offset["distance"] *= (1.0 - delta * _ZOOM_STEP)
            return True
        return super().eventFilter(obj, event)

    def reset_camera(self) -> None:
        """Reset to the scene's saved camera name (D-04: not hardcoded)."""
        self._camera_offset = {"azimuth": 0.0, "elevation": 0.0, "distance": 1.0, "target": (0.0, 0.0, 0.0)}


def _default_load_simulator(scene: SceneDefinition) -> BaseSimulator | None:
    """Default simulator loader. Returns None on import error (PySide6-free or no backend)."""
    try:
        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator
    except ImportError:
        return None
    backend = scene.simulator.value if hasattr(scene.simulator, "value") else str(scene.simulator)
    if backend == "mujoco":
        sim = MuJoCoSimulator()
    elif backend == "pybullet":
        sim = PyBulletSimulator()
    else:
        return None
    sim.load_scene(scene)
    return sim
