"""RenderPollLoop — UI-thread render loop driving the render half of GUI-11.

Per 42-CONTEXT.md D-01, D-02, D-05, D-12:

  - D-01: runs on the UI thread at ~30 Hz (``_FRAME_INTERVAL_MS=33``) via a
    self-rescheduling ``QTimer.singleShot``. It renders the LATEST published
    snapshot and yields to the event loop between frames (prevents frame
    pile-up). It NEVER calls ``simulator.step()`` (D-02) and NEVER blocks on
    physics — it only reads the latest snapshot and calls ``render()``.
  - D-02: there is ONE render timer on the UI thread (this loop) + ONE sim
    loop on the QThread worker (``SimStepWorker``). The render-poll is the
    only ``singleShot`` chain in the editor package.
  - D-05: camera orbit/pan/zoom (``_editor_camera_*``) is ephemeral,
    panel-local state pushed into the simulator on the render side only —
    NOT written to ``SceneDefinition`` / ``SceneUndoStack``.
  - D-12: the render-poll stays alive while the worker is paused so camera
    orbit/zoom still works and a step-one snapshot gets rendered on the next
    poll (Pitfall 6 — pause only stops the worker's accumulator QTimer).

Pitfalls addressed:
  - Pitfall 2: ``render()`` is ONLY called on the UI thread (GL/software
    renderer contexts are thread-affine). The worker never renders.
  - Pitfall 8: ``_tick`` checks ``_running`` at the TOP (early-return on
    already-queued callbacks after stop()) AND before rescheduling.

The render-poll delegates the ndarray display to ``canvas.set_image(arr)`` —
the canvas (or a Plan 02 adapter wrapping ``ViewportCanvas``) owns the
ndarray->QPixmap conversion (the ``_display_array`` path stays in the
viewport layer). This keeps ``RenderPollLoop`` focused on the loop strategy
(cadence, skip-when-no-new, running guard, camera push, fps) and swappable
without touching widget code.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from surg_rl.editor import QtCore
from surg_rl.editor._safe_error import safe_error_message
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# --- Module constants ---
# ~30 Hz render poll (replaces the old _tick's 50 ms / 20 Hz). Self-rescheduling
# QTimer.singleShot cadence — yields to the event loop between frames.
_FRAME_INTERVAL_MS: int = 33


class RenderPollLoop(QtCore.QObject):
    """UI-thread render loop: renders the latest published snapshot at ~30 Hz.

    The loop is pure UI-thread: it reads ``_latest_snapshot`` (set by
    ``on_snapshot``, connected queued to ``SimStepWorker.snapshot_ready``),
    pushes the ephemeral camera offset into the simulator, calls
    ``simulator.render()``, and hands the ndarray to ``canvas.set_image``.
    Skip-when-no-new (``frame_id == _last_rendered_id``) saves CPU when the
    sim has not published a fresh snapshot.
    """

    def __init__(
        self,
        simulator_ref: Callable[[], object],
        canvas: Any,
        camera_offset_ref: Callable[[], dict],
        on_fps_update: Callable[[float], None] | None = None,
        width: int = 640,
        height: int = 480,
        camera_name: str | None = None,
        sim_lock: threading.RLock | None = None,
    ) -> None:
        super().__init__()
        # A callable returning the CURRENT shared simulator — the live
        # simulator is swapped in-place by ViewportPanel.update_scene, so the
        # loop always reads the latest (Plan 02).
        self._simulator_ref = simulator_ref
        self._canvas = canvas
        self._camera_offset_ref = camera_offset_ref
        self._on_fps_update = on_fps_update
        self._width = width
        self._height = height
        self._camera_name = camera_name
        # Cross-thread simulator-access lock shared with SimStepWorker +
        # ViewportPanel (PyBullet is not thread-safe — see sim_step_worker.py).
        # The controller passes ONE instance to all three; ``render()`` is the
        # only simulator-touching op on this side and is guarded in ``_render``.
        self._sim_lock: threading.RLock = sim_lock if sim_lock is not None else threading.RLock()
        # _running guard (Pitfall 8): stop() sets False so already-queued
        # singleShot callbacks early-return instead of rescheduling.
        self._running: bool = True
        self._latest_snapshot: Any = None
        # Sentinel id semantics:
        #   -1 = no frame rendered yet (initial static frame still pending)
        #   -2 = initial static frame rendered (only re-render on new frame_id)
        #    0+ = last rendered SimStepWorker frame_id
        self._last_rendered_id: int = -1
        # fps counter (mirrors viewport.py:137-138, 292-304).
        self._frame_count: int = 0
        self._last_fps_check: float = 0.0
        self._fps: float = 0.0
        # Tick instrumentation — counts every _tick invocation (before the
        # skip-when-no-new check) so the SC#2 proxy cadence test can verify
        # the QTimer.singleShot fires at >=30 Hz independent of whether a new
        # snapshot rendered. Skip-when-no-new is correct behavior, but it
        # means ``canvas.set_image_count`` only rises on new frame_ids; the
        # timer cadence is the truer offscreen proxy (real-fps is backstop).
        self._tick_count: int = 0

    # --- Snapshot ingestion (the thread boundary, D-03) ---
    def on_snapshot(self, snapshot) -> None:
        """Store the latest published snapshot (connected queued to the worker)."""
        self._latest_snapshot = snapshot

    def bind_simulator(self, simulator) -> None:
        """Re-bind the loop to a new simulator on scene swap (Plan 02).

        ``ViewportPanel.update_scene`` calls this so the loop reads the new
        simulator via the ref callable (kept as-is) and resets the render
        state so the new scene's initial frame renders fresh.
        """
        self._latest_snapshot = None
        self._last_rendered_id = -1
        self._frame_count = 0
        self._last_fps_check = 0.0

    # --- Loop control ---
    def start(self) -> None:
        """Arm the self-rescheduling render-poll chain."""
        self._running = True
        QtCore.QTimer.singleShot(0, self._tick)

    def stop(self) -> None:
        """Halt the render-poll — already-queued callbacks early-return in _tick.

        Does NOT close the simulator: ``ViewportPanel.stop()`` / ``update_scene``
        closes the shared simulator AFTER pausing the worker (Pitfall 3
        ordering — never close while the worker may still be mid-step).
        """
        self._running = False

    # --- Self-rescheduling tick (runs on the UI thread) ---
    def _tick(self) -> None:
        # Tick instrumentation — increment before the running guard so the
        # SC#2 proxy cadence test can count singleShot callbacks regardless of
        # whether the tick early-returns (post-stop) or skips render.
        self._tick_count += 1
        # Top guard (Pitfall 8): stop() may have been called between the
        # singleShot being queued and this callback firing.
        if not self._running:
            return
        sim = self._simulator_ref()
        snap = self._latest_snapshot

        if sim is None:
            # No simulator bound yet — reschedule and wait.
            pass
        elif snap is None and self._last_rendered_id == -1:
            # Initial static frame: render once on a paused load (D-11) so the
            # user sees the scene immediately, then only re-render on a new
            # frame_id (Pitfall 6 — the poll stays alive while paused).
            self._render(sim)
            self._last_rendered_id = -2
        elif snap is not None and snap.frame_id != self._last_rendered_id:
            # New snapshot — render it.
            self._render(sim)
            self._last_rendered_id = snap.frame_id
            self._frame_count += 1
            self._maybe_update_fps()
        # else: snap is None (initial already rendered, -2) OR
        #       snap.frame_id == _last_rendered_id -> skip render (no new
        #       snapshot; saves CPU). Camera orbit still works because the
        #       next render of a new frame_id will pick up the latest offset.

        # Bottom guard (Pitfall 8): only reschedule if still running.
        if self._running:
            QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)

    def _render(self, sim) -> None:
        """Push the ephemeral camera offset into sim and render one frame."""
        # D-05 ephemeral camera (VERBATIM viewport.py:220-236 block) — kept on
        # the render side; NOT written to SceneDefinition / SceneUndoStack.
        try:
            offset = self._camera_offset_ref()
            object.__setattr__(sim, "_editor_camera_target", offset["target"])
            object.__setattr__(sim, "_editor_camera_distance", offset["distance"])
            object.__setattr__(sim, "_editor_camera_azimuth", offset["azimuth"])
            object.__setattr__(sim, "_editor_camera_elevation", offset["elevation"])
        except Exception:  # noqa: BLE001
            pass
        try:
            # Serialize render() with the worker's step()/get_state()/bind_scene
            # (and ViewportPanel.close on scene swap) via _sim_lock — PyBullet's
            # C API is not thread-safe; concurrent getCameraImage + stepSimulation
            # (or GC of a stale simulator's pybullet buffers during bind_scene)
            # corrupts the heap and segfaults. The lock is released before the
            # ndarray->QPixmap conversion in canvas.set_image (no sim access).
            with self._sim_lock:
                arr = sim.render(
                    mode="rgb_array",
                    width=self._width,
                    height=self._height,
                    camera_name=self._camera_name,
                )
        except Exception as exc:  # noqa: BLE001
            # Route any render error to the canvas via the redactor (D-19 /
            # GUI-09 — never leak raw secrets to the status bar). The
            # framebuffer-size retry (viewport.py:243-274) is a MuJoCo-specific
            # concern that belongs in the canvas/viewport adapter layer (Plan
            # 02), not the render-poll loop — kept out of scope here.
            self._canvas.set_text(f"Render error: {safe_error_message(exc)}")
            return
        if arr is not None:
            self._canvas.set_image(arr)
        else:
            # GL context unavailable (e.g. macOS offscreen) — show a stable
            # diagnostic instead of leaving a stale frame up.
            self._canvas.set_text("(preview render unavailable — no GL context)")

    def _maybe_update_fps(self) -> None:
        """1 s window fps counter (mirrors viewport.py:292-304)."""
        now = time.monotonic()
        if self._last_fps_check == 0.0:
            self._last_fps_check = now
            return
        elapsed = now - self._last_fps_check
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_check = now
            if self._on_fps_update is not None:
                self._on_fps_update(self._fps)
