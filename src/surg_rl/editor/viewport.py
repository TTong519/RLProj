"""ViewportPanel — the 3D render surface for the scene editor.

Per CONTEXT.md D-01..D-04 (Phase 42 render/sim decoupling):
  - D-01: render-to-QImage (np.ndarray -> QImage -> QPixmap -> canvas)
  - D-02: reuse BaseSimulator.render(mode="rgb_array", width, height, camera_name) as-is
  - D-03: the render loop is delegated to RenderPollLoop (UI thread, ~30 Hz);
          the step responsibility is delegated to SimStepWorker (QThread,
          ~50 Hz). ViewportPanel owns the canvas + camera offset + the
          ndarray->QPixmap adapter (set_image) and the scene-swap (update_scene).
  - D-04: mouse orbit/pan/zoom + R key camera reset
"""

from __future__ import annotations

import contextlib
import platform
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypedDict

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


def _scene_has_dynamics(scene: SceneDefinition) -> bool:
    """D-12 static-scene predicate — a STRUCTURAL schema-level check (NOT a
    runtime step-delta heuristic and NOT an auto-pause).

    Returns True when the scene has any actuated/animated entity:
      - ``scene.robots`` (schema.py:1402) non-empty — any robot with joints
        has actuated dynamics.
      - ``scene.tissues`` (schema.py:1403) non-empty — tissues are soft-body
        and deform under contact.
      - ``scene.fluid`` (schema.py:1442) is not None — ``fluid`` is a DIRECT
        field on ``SceneDefinition`` (NOT on ``EnvironmentConfig`` — the
        EnvironmentConfig has lights/cameras/ground_plane only, schema.py
        :990-1009).

    Instruments-only (no robots/tissues/fluid) returns False — instruments
    without robots have no actuated joints, so the scene is structurally
    static. The hint is informational only (D-12 — the worker keeps stepping
    harmlessly if the user hits Play on a static scene; the render-poll stays
    alive so camera orbit/zoom still work).
    """
    if getattr(scene, "robots", None):
        return True
    if getattr(scene, "tissues", None):
        return True
    return getattr(scene, "fluid", None) is not None


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
    """QWidget hosting the 3D render surface for the loaded scene.

    Phase 42 render/sim decoupling (Plan 42-02):
        The render half of the old monolithic ``_tick`` is delegated to a
        ``RenderPollLoop`` (UI thread, ~30 Hz self-rescheduling); the step
        responsibility is delegated to a ``SimStepWorker`` (QThread, ~50 Hz
        fixed-step accumulator). ``EditorWindow`` constructs both and hands
        them in via ``set_playback`` after ``__init__``. ``ViewportPanel``
        owns the canvas, the ephemeral camera offset (D-05), the
        ndarray->QPixmap adapter (``set_image``), and the in-place scene
        swap (``update_scene`` — Phase 41 D-06: no widget recreation).
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
        # already-queued render-poll callbacks early-return instead of
        # rescheduling indefinitely after window close.
        self._running: bool = True

        # Phase 42 D-01/D-02 — the render half of the old monolithic _tick is
        # delegated to a RenderPollLoop (UI thread, ~30 Hz), and the step
        # responsibility is on a SimStepWorker (QThread, ~50 Hz). The
        # EditorWindow constructs both and hands them in via set_playback()
        # AFTER __init__ so the worker/loop have the right thread affinity.
        # Until set_playback() is called, _sim_worker/_render_loop are None
        # and stop()/update_scene() guard the missing refs (backward-compat
        # for tests that construct ViewportPanel in isolation).
        self._sim_worker: Any = None
        self._render_loop: Any = None
        # D-12 static-scene hint flag — set by update_scene/set_playback from
        # _scene_has_dynamics; read by the EditorWindow status-bar callback
        # (Task 3). Panel-local/ephemeral (D-05 — NOT written to the schema).
        self._static_scene: bool = not _scene_has_dynamics(scene)

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
        # Phase 42 D-02 — NO auto-start render chain on the UI thread here.
        # The RenderPollLoop (constructed by EditorWindow) owns the ONLY
        # render chain and is started by the controller after set_playback().
        # The old self._start() path is removed (D-02 forbids a second render
        # chain on the UI thread).

    def set_playback(
        self,
        sim_worker: Any,
        render_loop: Any,
    ) -> None:
        """Receive the SimStepWorker + RenderPollLoop refs from EditorWindow.

        Performs the INITIAL bind: loads the scene's simulator on the UI
        thread (GL-probe-safe per D-01 — ``_default_load_simulator`` calls
        ``sim.render()`` which is thread-affine), hands the live simulator to
        the render loop (``bind_simulator``) and to the worker (queued
        ``bind_scene.emit``), and sets the worker paused (D-11 — load paused;
        the user must press Play to begin animation). Also evaluates the
        D-12 static-scene hint for the initial scene.

        Idempotent: safe to call once. Subsequent scene swaps go through
        ``update_scene`` (the in-place re-bind path).
        """
        self._sim_worker = sim_worker
        self._render_loop = render_loop
        self._bind_loaded_simulator(initial=True)

    def _bind_loaded_simulator(self, initial: bool = False) -> None:
        """Load the current scene's simulator on the UI thread and bind it to
        the worker + render loop. Shared by ``set_playback`` (initial) and
        ``update_scene`` (swap).

        Order (Pitfall 3): the caller (``update_scene``) pauses the worker +
        closes the old simulator BEFORE this runs. Here we load the new sim
        (UI thread), bind the render loop, then queue ``bind_scene`` to the
        worker (the worker binds on its own thread after any in-flight
        ``_tick``), then reaffirm paused (D-11 belt-and-braces) and evaluate
        the D-12 hint.
        """
        if self._render_loop is not None:
            self._render_loop.bind_simulator(None)  # reset render state eagerly
        try:
            new_sim = self._on_load_simulator(self._scene)
        except Exception as exc:  # noqa: BLE001
            from surg_rl.editor._safe_error import safe_error_message

            self._canvas.set_text(f"Simulator load error: {safe_error_message(exc)}")
            new_sim = None
        self._simulator = new_sim
        if new_sim is None:
            self._canvas.set_text("(simulator unavailable)")
        else:
            self._canvas.set_text("(loading simulator...)")
        if self._render_loop is not None and new_sim is not None:
            self._render_loop.bind_simulator(new_sim)
        if self._sim_worker is not None:
            if new_sim is not None:
                self._sim_worker.bind_scene.emit(new_sim)  # queued — worker thread
            # D-11 — load paused: the worker must NOT start stepping until the
            # user presses Play (or Space). Belt-and-braces after bind_scene.
            self._sim_worker.set_paused.emit(True)
        # D-12 static-scene hint (panel-local; the EditorWindow status-bar
        # callback reads this in Task 3).
        self._static_scene = not _scene_has_dynamics(self._scene)

    def stop(self) -> None:
        """Halt the render loop + pause the worker BEFORE closing the shared
        simulator (Pitfall 3 — the worker is never mid-step() while
        ``simulator.close()`` runs on the UI thread).

        The ``aboutToClose`` signal (EditorWindow.closeEvent) already fired
        and already triggered ``_stop_sim_worker`` (controller-side
        ``sim_worker.stop`` + ``thread.quit`` + ``wait(3000)``); this method
        is the belt-and-braces for the ``update_scene`` swap path and for
        tests that call ``viewport.stop()`` directly.
        """
        # _running guard kept for backward compat with tests that assert
        # ``stop() sets _running=False`` (the render-poll has its own _running
        # guard inside RenderPollLoop).
        self._running = False
        # Pitfall 3 — pause the worker BEFORE closing the shared simulator.
        if self._render_loop is not None:
            with contextlib.suppress(Exception):
                self._render_loop.stop()
        if self._sim_worker is not None:
            with contextlib.suppress(Exception):
                self._sim_worker.set_paused.emit(True)
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

    def _tick(self) -> None:  # noqa: D401
        """No-op retained for backward compat with tests that call ``_tick``
        directly. The render half of the old monolithic ``_tick`` is delegated
        to ``RenderPollLoop._tick`` (Plan 01) and the step responsibility is
        on ``SimStepWorker._tick`` (Plan 01). The ``_running`` guard is kept
        so post-stop calls early-return (``test_stop_halts_render_loop``).
        """
        if not self._running:
            return  # stop() was called — halt
        # Render + step are owned by RenderPollLoop + SimStepWorker (D-01/D-02).
        # No reschedule here — the render-poll owns the only render chain
        # (D-02 forbids a second render chain on the UI thread).

    # --- RenderPollLoop canvas adapter (D-03 — the loop calls these) ---
    def set_image(self, arr) -> None:
        """Canvas adapter for RenderPollLoop — converts the rendered ndarray
        to a QPixmap via ``_display_array`` (the ndarray→QPixmap path stays
        in the viewport layer per 42-01-SUMMARY "Render-error handling scoped
        out"). ``RenderPollLoop._render`` calls this with the ``sim.render()``
        result.
        """
        self._display_array(arr)

    def set_text(self, text: str) -> None:
        """Canvas adapter for RenderPollLoop — delegates to the ViewportCanvas
        fallback text (used when render() raises or returns None)."""
        self._canvas.set_text(text)

    def width(self) -> int:  # noqa: D401
        """Canvas width for RenderPollLoop's render-size selection."""
        return self._canvas.width()

    def height(self) -> int:  # noqa: D401
        """Canvas height for RenderPollLoop's render-size selection."""
        return self._canvas.height()

    def camera_name(self) -> str | None:
        """Read the scene's first camera name for ``sim.render()`` (mirrors
        the old _tick :212-217 block — kept on the render side)."""
        env = getattr(self._scene, "environment", None)
        if env is not None:
            cameras = getattr(env, "cameras", None)
            if cameras:
                return getattr(cameras[0], "name", None)
        return None

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

    def update_scene(self, scene: SceneDefinition) -> None:
        """In-place scene swap + worker/loop re-bind — NO widget recreation
        (Phase 41 D-06, bug #3 fix). Loads PAUSED (D-11) so opening a scene
        never surprises the user with CPU/GPU load.

        Order (Pitfall 3 + 42-RESEARCH.md Pattern 4):
          (a) pause the worker (``set_paused.emit(True)``) BEFORE closing the
              old simulator — the worker must never be mid-step() while
              ``simulator.close()`` runs on the UI thread;
          (b) close the old simulator via ``contextlib.suppress`` (the
              existing close pattern);
          (c) ``_simulator = None``;
          (d) swap ``_scene``;
          (e) ``reset_camera()`` (A3 — new scene = fresh view);
          (f) load the new simulator on the UI thread + bind the render loop
              + queue ``bind_scene.emit(new_sim)`` to the worker + reaffirm
              paused (D-11) + evaluate the D-12 static-scene hint — shared
              with ``set_playback`` via ``_bind_loaded_simulator``.

        The widget identity (and thus the dock geometry keyed on
        objectName) is preserved — no central-widget swap, no new
        ``ViewportPanel``. ``_running`` stays True so the render loop
        continues across the swap (the render-poll reads the new simulator
        via ``bind_simulator``).
        """
        # (a) Pitfall 3 — pause worker BEFORE closing the old sim.
        if self._sim_worker is not None:
            with contextlib.suppress(Exception):
                self._sim_worker.set_paused.emit(True)
        # (b) close the old simulator (the existing suppress pattern).
        with contextlib.suppress(AttributeError, OSError):
            if self._simulator is not None:
                self._simulator.close()
        # (c) drop the old ref.
        self._simulator = None
        # (d) swap the scene.
        self._scene = scene
        # (e) fresh view.
        self.reset_camera()
        # (f) load + bind (UI-thread load, queued bind_scene, paused D-11,
        # D-12 hint) — shared with set_playback. If set_playback has not
        # been called yet (no worker/loop), this still loads the simulator
        # and evaluates the hint so the canvas shows the new scene.
        self._bind_loaded_simulator()


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
