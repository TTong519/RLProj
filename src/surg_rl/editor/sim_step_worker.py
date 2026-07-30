"""SimStepWorker — QThread worker-object driving the sim half of GUI-11.

Per 42-CONTEXT.md D-01, D-03, D-04, D-07, D-09, D-11:

  - D-01: fixed-step accumulator at ~50 Hz (``_SIM_HZ``), decoupled from the
    render rate. The accumulator runs on a ``QThread``; the render-poll runs
    on the UI thread. ONE sim loop + ONE render timer (D-02 forbids naive
    fixes).
  - D-03: snapshots are derived from ``BaseSimulator.get_state() -> State`` and
    published via the queued ``snapshot_ready`` signal — the decoupling seam.
    ``State`` is pure-data (numpy + dicts, no Qt/GL handles), safe across
    threads (Assumption A3).
  - D-04: cooperative ``stop()`` = cancel flag + ``timer.stop()``. The
    controller (EditorWindow, Plan 02) owns ``thread.quit()``/``wait(3000)``.
    NEVER ``thread.terminate()``; NEVER ``deleteLater()`` here (Pitfall 4 —
    ``thread.finished -> thread.deleteLater`` is the only delete path).
  - D-07: ``step_one()`` runs exactly one ``step(None)`` while paused and
    publishes one snapshot (does NOT resume the timer).
  - D-09: ``set_speed()`` scales ``wall_dt`` (``accum += wall_dt * speed``),
    NOT ``sim_dt`` (Pitfall 5). ``sim_dt`` stays fixed at 1/50.
  - D-11: the worker LOADS PAUSED — ``start()`` creates the accumulator
    ``QTimer`` but does NOT start it when ``_paused`` is True; the user must
    press Play (or ``set_paused(False)``) to begin animation.

Pitfalls addressed:
  - Pitfall 4: spiral-of-death cap ``_MAX_STEPS_PER_TICK=8`` — when hit,
    ``_accum`` is reset to 0.0 to discard backed-up debt.
  - Pitfall 5: speed scales ``wall_dt``, NOT ``sim_dt``.
  - Pitfall 8: ``_tick`` guards on ``_cancelled`` and ``_simulator is None``.

The worker only calls ``simulator.step(None)`` + ``simulator.get_state()`` (both
CPU-only). It NEVER calls ``render()`` (Pitfall 2 — GL contexts are
thread-affine; render lives on the UI thread in ``RenderPollLoop``).
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from surg_rl.editor import QtCore
from surg_rl.utils.logging import get_logger

if TYPE_CHECKING:
    from surg_rl.simulators.base_simulator import BaseSimulator

logger = get_logger(__name__)

# --- Module constants (the FLAGGED ASSUMPTION thresholds — resolved here) ---
# Fixed-step sim rate (sim_dt = 1/_SIM_HZ = 0.02 s). INCLUSIVE accumulator
# boundary: ``while accum >= sim_dt``.
_SIM_HZ: float = 50.0
# Publish cap for snapshot_ready (30 Hz). INCLUSIVE boundary:
# ``if now - last_publish >= 1.0 / _PUBLISH_HZ``.
_PUBLISH_HZ: float = 30.0
# Spiral-of-death cap: never run more than this many steps in one _tick, even
# if the accumulator has backed up (e.g. after a UI-thread stall). When hit,
# discard the remaining debt by resetting _accum to 0.0 (Pitfall 4).
_MAX_STEPS_PER_TICK: int = 8


# --- Module-level registry of live editor sim runtimes ----------------------
# EditorWindow.__init__ starts a SimStepWorker QThread + a RenderPollLoop
# self-rescheduling singleShot chain. Tests that construct EditorWindow
# WITHOUT calling close() leak both: the singleShot chain holds the loop →
# the loop's ``simulator_ref`` lambda holds the EditorWindow, so the window
# is NEVER unreachable while the render-poll runs → a per-window
# ``weakref.finalize`` safety net never fires. The leaked thread + render-poll
# then run until interpreter shutdown → ``QThread: Destroyed while thread is
# still running`` (SIGABRT) or a pybullet C-state segfault during teardown.
#
# This registry + ``reap_all_sim_runtimes`` is the reliable fix: an autouse
# fixture in tests/conftest.py calls ``reap_all_sim_runtimes`` after every
# test, stopping each leaked render-poll (kills the singleShot chain) +
# cancelling + joining each leaked QThread, so no sim runtime outlives a
# test (no cross-test leak → no shutdown crash). The registry holds STRONG
# refs so a leaked QThread is never destroyed while still running even
# before the reaper runs.
_ACTIVE_SIM_RUNTIMES: list[tuple[object, SimStepWorker, object, object]] = []
_ACTIVE_LOCK = threading.Lock()


def register_sim_runtime(
    window: object, thread: object, worker: SimStepWorker, render_loop: object
) -> None:
    """Record a live (window, thread, worker, render_loop) runtime. Holds a
    strong ref so a leaked QThread is not destroyed while running (the reaper
    joins it) and a leaked EditorWindow is torn down by the reaper's close()."""
    with _ACTIVE_LOCK:
        _ACTIVE_SIM_RUNTIMES.append((window, thread, worker, render_loop))


def unregister_sim_runtime(thread: object) -> None:
    """Drop a runtime that was torn down via the close() path (so the reaper
    does not double-stop it). No-op if already reaped/unregistered."""
    with _ACTIVE_LOCK:
        _ACTIVE_SIM_RUNTIMES[:] = [r for r in _ACTIVE_SIM_RUNTIMES if r[1] is not thread]


def reap_all_sim_runtimes(timeout_ms: int = 3000) -> None:
    """Tear down every leaked editor runtime by calling its EditorWindow.close()
    (the FULL proper teardown: aboutToClose → stop+join the SimStepWorker
    QThread, stop the RenderPollLoop, close the simulator), then null the
    render-loop's window refs so the window is collectable.

    Called by the autouse fixture in tests/conftest.py after each test. Tests
    that construct EditorWindow WITHOUT calling close() leak a window whose
    QObject graph (EditorWindow ↔ ViewportPanel via the _scene_bound signal;
    EditorWindow → SimStepWorker → RenderPollLoop via the snapshot_ready
    signal) forms a reference cycle only breakable by cyclic GC, AND whose
    render-poll's 33 ms singleShot holds the last external ref to the loop.
    A later mock-driven cyclic GC (test_rendering::test_stops_cleanly) then
    collects the cycle and traverses a stale shiboken6 QObject wrapper →
    segfault (Phase 42 regression; baseline has no QThread and is clean).

    Calling close() here runs the SAME teardown slots closeEvent runs, so the
    graph is in a clean state (thread joined, sim closed) when the fixture
    later spins the event loop (QTest.qWait) to fire the 33 ms singleShot and
    gc.collect()s the now-unreachable graph — in this controlled context
    shiboken deletion is safe, so no stale wrapper lingers for a later test.

    Safe to call when empty; safe to call repeatedly. The close() path
    unregisters via ``unregister_sim_runtime`` so this never double-closes a
    window already closed by the test.
    """
    with _ACTIVE_LOCK:
        items = list(_ACTIVE_SIM_RUNTIMES)
        _ACTIVE_SIM_RUNTIMES.clear()
    for window, thread, worker, render_loop in items:
        # Full teardown via close() (mirrors closeEvent). Best-effort; never
        # raise — this is a GC-safety reaper, not the primary close path.
        if window is not None:
            with contextlib.suppress(Exception):  # noqa: BLE001
                window.close()
        # Belt-and-braces in case close() did not run (e.g. window already
        # partially destroyed): stop the render-poll + join the QThread +
        # close the leaked simulator + null the worker's sim ref.
        with contextlib.suppress(Exception):  # noqa: BLE001
            render_loop.stop()
        with contextlib.suppress(Exception):  # noqa: BLE001
            worker._cancelled = True
        if thread is not None:
            thread.quit()
            with contextlib.suppress(Exception):  # noqa: BLE001
                thread.wait(timeout_ms)
        with contextlib.suppress(Exception), worker._sim_lock:  # noqa: BLE001
            sim = worker._simulator
            worker._simulator = None
            if sim is not None:
                sim.close()
        # Release the render-loop's holds on the EditorWindow (its
        # simulator_ref/camera_offset_ref lambdas + on_fps_update bound method
        # + canvas ref capture the window/viewport).
        with contextlib.suppress(Exception):  # noqa: BLE001
            render_loop._simulator_ref = None
            render_loop._canvas = None
            render_loop._camera_offset_ref = None
            render_loop._on_fps_update = None


@dataclass
class _Snapshot:
    """Published snapshot — the cross-thread decoupling payload (D-03).

    ``frame_id`` is a monotonic int counter (no float precision loss) so the
    render-poll can cheaply detect "new snapshot?" via ``frame_id !=
    last_rendered_id``.
    """

    state: object  # State — typed as object so the dataclass stays PySide6-free
    frame_id: int


class SimStepWorker(QtCore.QObject):
    """QThread worker-object: fixed-step ~50 Hz accumulator + ~30 Hz publish.

    Lives on a ``QThread`` (moveToThread by the controller). The accumulator
    ``QTimer`` is created in ``start()`` so its thread affinity is the worker
    thread (Qt timers must be created on the thread they run on).

    Slots are invoked cross-thread via ``QMetaObject.invokeMethod(...,
    QueuedConnection)`` (or connected signals) — direct Python calls from the
    UI thread would run the slot on the wrong thread and break timer affinity.
    """

    snapshot_ready = QtCore.Signal(object)

    def __init__(self, sim_lock: threading.RLock | None = None) -> None:
        super().__init__()
        self._simulator: BaseSimulator | None = None
        # Cross-thread simulator-access lock (PyBullet is NOT thread-safe — its
        # C API shares global state, so concurrent step()/get_state() on the
        # worker thread + render() on the UI thread, or the GC of a stale
        # simulator's pybullet-allocated buffers during bind_scene while the UI
        # thread is mid-getCameraImage, corrupts the heap and segfaults). The
        # controller (EditorWindow) creates ONE shared RLock and passes the same
        # instance to the worker + RenderPollLoop + ViewportPanel so every
        # simulator-touching op serializes. Uncontended acquire is ~1us, so the
        # ~50 Hz accumulator + ~30 Hz render pay only on real contention (a slow
        # pybullet render blocks step — unavoidable for a non-thread-safe
        # backend; the accumulator's spiral cap discards the backed-up debt).
        self._sim_lock: threading.RLock = sim_lock if sim_lock is not None else threading.RLock()
        self._timer: QtCore.QTimer | None = None
        # D-11 — load paused. start() creates the timer but does NOT start it
        # while paused; the user must press Play to begin animation.
        self._paused: bool = True
        # D-09 — default 1x (real-time). Valid multipliers: 0.25 / 0.5 / 1 / 2 / 4.
        self._speed: float = 1.0
        self._accum: float = 0.0
        self._last_wall: float = 0.0
        self._last_publish: float = 0.0
        # Monotonic int counter — no float precision loss across the seam.
        self._frame_id: int = 0
        self._cancelled: bool = False

    # --- Slots (driven cross-thread by the controller) ---
    @QtCore.Slot()
    def start(self) -> None:
        """Create the accumulator QTimer on the worker thread and arm it.

        Per D-11, the timer is created here (affinity = worker thread) but is
        only started if the worker is NOT paused. A paused load leaves the
        timer idle until ``set_paused(False)`` resumes it.
        """
        self._timer = QtCore.QTimer()
        self._timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._last_wall = time.monotonic()
        if not self._paused:
            self._timer.start(int(1000 / _SIM_HZ))

    @QtCore.Slot(object)
    def bind_scene(self, simulator) -> None:
        """Bind (or re-bind) the worker to a simulator instance.

        Called queued from ``ViewportPanel.update_scene`` on the UI thread;
        runs on the worker thread after any in-flight ``_tick``. Resets the
        accumulator + publish clock so the new scene starts fresh.

        The assignment is guarded by ``_sim_lock``: dropping the previous
        simulator reference can trigger GC of its pybullet-allocated numpy
        buffers, which is unsafe while the UI thread's ``RenderPollLoop`` is
        mid-``getCameraImage`` (PyBullet is not thread-safe). Serializing with
        render guarantees the GC lands between frames, never during one.
        """
        with self._sim_lock:
            self._simulator = simulator
            self._accum = 0.0
            self._last_wall = time.monotonic()
            self._last_publish = self._last_wall
            self._frame_id = 0

    @QtCore.Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """Pause/resume the accumulator timer.

        On resume, ``_last_wall`` is reset so ``wall_dt`` does not spike across
        the pause interval (which would otherwise dump a huge debt into the
        accumulator and trip the spiral cap).
        """
        self._paused = paused
        if self._timer is None:
            # start() has not run yet (e.g. bind_scene arrived before
            # thread.started). The _paused flag is recorded; start() will
            # respect it.
            return
        if paused:
            self._timer.stop()
        else:
            self._last_wall = time.monotonic()
            self._timer.start(int(1000 / _SIM_HZ))

    @QtCore.Slot(float)
    def set_speed(self, speed: float) -> None:
        """Set the playback speed multiplier (scales wall_dt, NOT sim_dt)."""
        self._speed = speed

    @QtCore.Slot()
    def step_one(self) -> None:
        """Advance exactly one physics timestep while paused (D-07).

        Runs a single ``step(None)`` and publishes one snapshot. Does NOT
        resume the accumulator timer — the user is still in paused/scrub
        mode. The render-poll (alive at ~30 Hz while paused, Pitfall 6) picks
        up the new snapshot on its next tick.
        """
        if self._simulator is None:
            return
        with self._sim_lock:
            self._simulator.step(None)
            self._frame_id += 1
            self.snapshot_ready.emit(self._publish())

    # --- Internal accumulator tick (runs on the worker thread) ---
    def _tick(self) -> None:
        # Pitfall 8 + D-11: bail if cancelled, unbound, or paused. set_paused
        # stops the timer, but a timeout posted on the worker thread just
        # before the stop landed may still be delivered once — the _paused
        # check here catches that transition tick so pause takes effect the
        # instant the flag is set, without waiting for the next dequeue.
        if self._cancelled or self._simulator is None or self._paused:
            return
        now = time.monotonic()
        # Recompute wall_dt each tick from time.monotonic() so wall-clock skew
        # does NOT compound (FLAGGED ASSUMPTION precision contract).
        wall_dt = now - self._last_wall
        self._last_wall = now
        # Pitfall 5 — scale wall_dt (the accumulator INPUT), NOT sim_dt.
        self._accum += wall_dt * self._speed
        sim_dt = 1.0 / _SIM_HZ  # = 0.02, fixed
        steps = 0
        # Serialize the step loop + publish with the UI-thread render (and with
        # ViewportPanel.close on scene swap) via _sim_lock — PyBullet is not
        # thread-safe. The accumulator math above is lock-free (no sim access).
        with self._sim_lock:
            # INCLUSIVE boundary: ``accum >= sim_dt`` (one step at exactly accum == sim_dt).
            while self._accum >= sim_dt and steps < _MAX_STEPS_PER_TICK:
                self._simulator.step(None)
                self._accum -= sim_dt
                steps += 1
            if steps == _MAX_STEPS_PER_TICK:
                # Spiral-of-death cap (Pitfall 4): discard backed-up debt so a
                # stall does not cascade into an ever-growing catch-up load.
                self._accum = 0.0
            # INCLUSIVE publish boundary: ``>= 1.0 / _PUBLISH_HZ`` (30 Hz cap).
            if now - self._last_publish >= 1.0 / _PUBLISH_HZ:
                self._frame_id += 1
                self.snapshot_ready.emit(self._publish())
                self._last_publish = now

    def _publish(self) -> _Snapshot:
        return _Snapshot(state=self._simulator.get_state(), frame_id=self._frame_id)

    # --- Cooperative teardown (D-04; controller owns thread.quit/wait) ---
    def stop(self) -> None:
        """Cooperative cancel: set the cancel flag + stop the accumulator timer.

        Mirrors ``LLMPanel.stop()`` (Phase 41 D-05): the worker only flags
        cancellation and stops its own timer; the controller (EditorWindow)
        owns ``thread.quit()`` + ``thread.wait(3000)`` + log-on-timeout, and
        ``thread.finished -> thread.deleteLater`` (Pitfall 4) is wired by the
        controller. NEVER ``thread.terminate()`` (D-04 — risks leaving simulator
        physics state inconsistent). NEVER ``deleteLater()`` here.
        """
        self._cancelled = True
        if self._timer is not None:
            self._timer.stop()
