"""ViewportPanel — the 3D render surface for the scene editor.

Per CONTEXT.md D-01..D-04:
  - D-01: render-to-QImage (np.ndarray -> QImage -> QPixmap -> QLabel)
  - D-02: reuse BaseSimulator.render(mode="rgb_array", width, height, camera_name) as-is
  - D-03: QTimer.singleShot(50, self._tick) self-rescheduling (no interval timer)
  - D-04: mouse orbit/pan/zoom + R key camera reset
"""

from __future__ import annotations

import contextlib
import platform
from collections.abc import Callable
from typing import TYPE_CHECKING, TypedDict

import numpy as np

from surg_rl.editor import QtCore, QtGui, QtWidgets
from surg_rl.editor._platform_guard import _is_running_under_mjpython
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition
    from surg_rl.simulators.base_simulator import BaseSimulator

_DEFAULT_WIDTH: int = 640
_DEFAULT_HEIGHT: int = 480
_FRAME_INTERVAL_MS: int = 50
_ORBIT_SENSITIVITY: float = 0.005
_PAN_SENSITIVITY: float = 0.002
_ZOOM_STEP: float = 0.15


class _CameraOffset(TypedDict):
    azimuth: float
    elevation: float
    distance: float
    target: tuple[float, float, float]


class ViewportCanvas(QtWidgets.QWidget):
    """Custom render surface that receives mouse/wheel events directly.

    A QLabel with a pixmap often fails to deliver wheel events and can be
    flaky for mouse tracking on macOS. A plain QWidget with overridden
    event handlers is the reliable Qt idiom for an interactive canvas.
    """

    def __init__(self, panel: ViewportPanel, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._pixmap: QtGui.QPixmap | None = None
        self._text: str = "(loading simulator...)"
        self.setMinimumSize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setStyleSheet("background-color: #222; color: #888;")

    def set_image(self, pixmap: QtGui.QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def set_text(self, text: str) -> None:
        self._pixmap = None
        self._text = text
        self.update()

    def pixmap(self) -> QtGui.QPixmap | None:
        """Return the currently displayed pixmap (QLabel-compatible helper)."""
        return self._pixmap

    def text(self) -> str:
        """Return the current fallback text (QLabel-compatible helper)."""
        return self._text

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#222222"))
        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QtGui.QColor("#888888"))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self.setFocus()
        self._panel._on_mouse_press(event.position().toPoint(), event.button())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self._panel._on_mouse_move(
            event.position().toPoint(),
            event.buttons(),
        )

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self._panel._on_mouse_release()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y() / 120.0
        self._panel._on_wheel(delta)


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
        # Render-loop guard (UAT Gap 2 fix): stop() sets this False so that
        # already-queued QTimer.singleShot callbacks early-return instead of
        # rescheduling indefinitely after window close.
        self._running: bool = True

        self._canvas = ViewportCanvas(self)
        self._canvas.setMinimumSize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._camera_offset: _CameraOffset = {
            "azimuth": 0.0,
            "elevation": 0.0,
            "distance": 2.5,
            "target": (0.0, 0.0, 0.0),
        }
        self._last_render_width: int = _DEFAULT_WIDTH
        self._last_render_height: int = _DEFAULT_HEIGHT

        self._canvas.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._canvas.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover)
        self._last_mouse_pos: QtCore.QPoint | None = None
        self._start()

    def _start(self) -> None:
        self._running = True
        QtCore.QTimer.singleShot(0, self._tick)

    def stop(self) -> None:
        # Halt the render loop — _tick checks _running at the top and before
        # rescheduling, so already-queued QTimer callbacks become no-ops.
        self._running = False
        if self._simulator is not None:
            # MuJoCo Renderer.__del__ can raise AttributeError
            # ('_gl_context') during interpreter shutdown if the GL
            # context is already destroyed. Swallow it — we're tearing
            # down (UAT Gap 2 fix).
            with contextlib.suppress(AttributeError, OSError):
                self._simulator.close()
            self._simulator = None

    def __del__(self) -> None:
        # Best-effort cleanup during interpreter shutdown. Guard against
        # MuJoCo Renderer.__del__ AttributeError when the GL context is
        # already garbage-collected (UAT Gap 2 fix).
        with contextlib.suppress(Exception):
            self.stop()

    def _tick(self) -> None:
        if not self._running:
            return  # stop() was called — halt the render loop

        if self._simulator is None:
            try:
                self._simulator = self._on_load_simulator(self._scene)
            except Exception as exc:  # noqa: BLE001
                from surg_rl.editor._safe_error import safe_error_message

                self._canvas.set_text(f"Simulator load error: {safe_error_message(exc)}")
                QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
                return

            if self._simulator is None:
                self._canvas.set_text("(simulator unavailable)")
                # FIX (UAT Gap 2): reschedule instead of returning — the
                # original code killed the render loop silently when the
                # simulator was unavailable.
                QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
                return

        try:
            camera_name = None
            env = getattr(self._scene, "environment", None)
            if env is not None:
                cameras = getattr(env, "cameras", None)
                if cameras:
                    camera_name = getattr(cameras[0], "name", None)
            self._last_render_width = max(1, self._canvas.width())
            self._last_render_height = max(1, self._canvas.height())
            # Push current camera offsets into the simulator so PyBullet preview
            # orbit/pan/zoom respond to user input. MuJoCo ignores these attrs.
            try:
                object.__setattr__(
                    self._simulator, "_editor_camera_target", self._camera_offset["target"]
                )
                object.__setattr__(
                    self._simulator, "_editor_camera_distance", self._camera_offset["distance"]
                )
                object.__setattr__(
                    self._simulator, "_editor_camera_azimuth", self._camera_offset["azimuth"]
                )
                object.__setattr__(
                    self._simulator, "_editor_camera_elevation", self._camera_offset["elevation"]
                )
            except Exception:  # noqa: BLE001
                pass
            arr = self._simulator.render(
                mode="rgb_array",
                width=self._last_render_width,
                height=self._last_render_height,
                camera_name=camera_name,
            )
        except Exception as exc:  # noqa: BLE001
            err_msg = str(exc)
            # MuJoCo's default offscreen framebuffer is 640x480. If the
            # viewport canvas is larger, the renderer raises a framebuffer
            # size error. Retry at the default framebuffer size so the preview
            # still works on high-DPI / large windows.
            if "framebuffer" in err_msg.lower() or "offwidth" in err_msg.lower():
                logger.debug(
                    "Viewport render too large for MuJoCo framebuffer (%s); retrying at 640x480",
                    err_msg,
                )
                self._last_render_width = 640
                self._last_render_height = 480
                try:
                    arr = self._simulator.render(
                        mode="rgb_array",
                        width=self._last_render_width,
                        height=self._last_render_height,
                        camera_name=camera_name,
                    )
                except Exception as exc2:  # noqa: BLE001
                    from surg_rl.editor._safe_error import safe_error_message

                    self._canvas.set_text(f"Render error: {safe_error_message(exc2)}")
                    QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
                    return
            else:
                from surg_rl.editor._safe_error import safe_error_message

                self._canvas.set_text(f"Render error: {safe_error_message(exc)}")
                QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
                return

        if arr is not None:
            self._display_array(arr)
        else:
            # MuJoCo's CGL/EGL renderer can return None when no GL context is
            # available (e.g. macOS offscreen Qt). Show a stable diagnostic
            # message instead of leaving the initial "loading simulator..."
            # text up forever.
            self._canvas.set_text("(preview render unavailable — no GL context)")
        self._frame_count += 1
        self._maybe_update_fps()

        # Only reschedule if still running — stop() may have been called
        # during render (UAT Gap 2 fix: prevents dangling QTimer callbacks).
        if self._running:
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
        # QImage wrapping arr.data requires a contiguous RGB buffer; copy if
        # the array is sliced/transposed or has a non-standard dtype.
        arr = np.ascontiguousarray(arr)

        # Flattened RGB(A) buffer: try common (H*W*3/4,) layouts first.
        if arr.ndim == 1:
            size = arr.size
            canvas_w = max(1, self._canvas.width())
            canvas_h = max(1, self._canvas.height())
            # Best guess: if the size matches the canvas area, reshape as RGB.
            if size == canvas_w * canvas_h * 3:
                arr = arr.reshape((canvas_h, canvas_w, 3))
            elif size == canvas_w * canvas_h * 4:
                arr = arr.reshape((canvas_h, canvas_w, 4))
            elif size == self._last_render_width * self._last_render_height * 3:
                arr = arr.reshape((self._last_render_height, self._last_render_width, 3))
            elif size == self._last_render_width * self._last_render_height * 4:
                arr = arr.reshape((self._last_render_height, self._last_render_width, 4))
            else:
                raise ValueError(f"Unsupported image shape for preview: {arr.shape}")

        # Cast after reshaping so we do not lose float data prematurely.
        arr = np.ascontiguousarray(arr, dtype=np.uint8)
        if arr.ndim == 2:
            # Grayscale: tile to RGB.
            arr = np.stack([arr] * 3, axis=-1)
            arr = np.ascontiguousarray(arr, dtype=np.uint8)
        elif arr.ndim != 3:
            raise ValueError(f"Unsupported image shape for preview: {arr.shape}")

        h, w = arr.shape[:2]
        if arr.shape[2] == 4:
            fmt = QtGui.QImage.Format.Format_ARGB32
            bytes_per_line = 4 * w
        elif arr.shape[2] == 3:
            fmt = QtGui.QImage.Format.Format_RGB888
            bytes_per_line = 3 * w
        else:
            # Drop extra channels so we never leave the canvas stuck.
            arr = arr[:, :, :3]
            arr = np.ascontiguousarray(arr, dtype=np.uint8)
            fmt = QtGui.QImage.Format.Format_RGB888
            bytes_per_line = 3 * w

        qimg = QtGui.QImage(arr.data, w, h, bytes_per_line, fmt)
        pixmap = QtGui.QPixmap.fromImage(qimg)
        self._canvas.set_image(pixmap)

    def _on_mouse_press(self, pos: QtCore.QPoint, button: QtCore.Qt.MouseButton) -> None:
        self._last_mouse_pos = pos
        self._drag_button = button

    def _on_mouse_move(
        self,
        pos: QtCore.QPoint,
        buttons: QtCore.Qt.MouseButton,
    ) -> None:
        if self._last_mouse_pos is None:
            return
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        if buttons & QtCore.Qt.MouseButton.LeftButton:
            self._camera_offset["azimuth"] += dx * _ORBIT_SENSITIVITY
            self._camera_offset["elevation"] += dy * _ORBIT_SENSITIVITY
        elif buttons & QtCore.Qt.MouseButton.MiddleButton:
            tx, ty, tz = self._camera_offset["target"]
            self._camera_offset["target"] = (
                tx - dx * _PAN_SENSITIVITY,
                ty + dy * _PAN_SENSITIVITY,
                tz,
            )
        self._last_mouse_pos = pos

    def _on_mouse_release(self) -> None:
        self._last_mouse_pos = None
        self._drag_button = QtCore.Qt.MouseButton.NoButton

    def _on_wheel(self, delta: float) -> None:
        self._camera_offset["distance"] *= 1.0 - delta * _ZOOM_STEP
        # Clamp to a sensible range so the user cannot zoom through or behind
        # the scene and lose the view.
        self._camera_offset["distance"] = max(0.1, min(50.0, self._camera_offset["distance"]))

    def reset_camera(self) -> None:
        """Reset to the scene's saved camera name (D-04: not hardcoded)."""
        self._camera_offset: _CameraOffset = {
            "azimuth": 0.0,
            "elevation": 0.0,
            "distance": 2.5,
            "target": (0.0, 0.0, 0.0),
        }


def _default_load_simulator(scene: SceneDefinition) -> BaseSimulator | None:
    """Default simulator loader. Returns None on import error (PySide6-free or no backend).

    On macOS (and other environments where MuJoCo's offscreen CGL/EGL renderer
    cannot acquire a GL context), the editor preview falls back to PyBullet
    DIRECT mode so the user still sees a rendered scene instead of a perpetual
    loading screen.
    """
    try:
        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator
    except ImportError:
        return None
    backend = scene.simulator.value if hasattr(scene.simulator, "value") else str(scene.simulator)
    sim: BaseSimulator | None
    if backend == "mujoco":
        sim = MuJoCoSimulator()
    elif backend == "pybullet":
        sim = PyBulletSimulator(render_mode="DIRECT")
    else:
        return None

    try:
        sim.load_scene(scene)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preview simulator load failed for backend=%s: %s", backend, exc)
        with contextlib.suppress(Exception):
            sim.close()
        sim = None

    # If MuJoCo scene loaded but offscreen rendering is unavailable, try
    # PyBullet DIRECT mode as a software-rendered preview fallback.
    if sim is not None and backend == "mujoco":
        # On macOS without mjpython, MuJoCo's CGL context is missing, but a
        # small probe may still succeed. Always use PyBullet for the editor
        # preview in that configuration so the user sees a rendered scene
        # instead of a perpetual "no GL context" placeholder.
        if platform.system() == "Darwin" and not _is_running_under_mjpython():
            logger.info("macOS stock Python: using PyBullet software renderer for editor preview")
            with contextlib.suppress(Exception):
                sim.close()
            sim = PyBulletSimulator(render_mode="DIRECT")
            sim.load_scene(scene)
            object.__setattr__(sim, "_editor_preview_fallback", "pybullet")
            return sim

        # For other platforms (or macOS under mjpython), probe at the
        # default MuJoCo framebuffer size. Catch None returns and exceptions.
        probe_ok = False
        try:
            probe = sim.render(mode="rgb_array", width=640, height=480)
            probe_ok = probe is not None
        except Exception as exc:  # noqa: BLE001
            logger.debug("MuJoCo probe render failed: %s", exc)
            probe_ok = False
        if not probe_ok:
            logger.info("MuJoCo offscreen renderer unavailable; using PyBullet for editor preview")
            with contextlib.suppress(Exception):
                sim.close()
            sim = PyBulletSimulator(render_mode="DIRECT")
            sim.load_scene(scene)
            # Tag the simulator so the viewport can show a one-time status note.
            object.__setattr__(sim, "_editor_preview_fallback", "pybullet")

    return sim
