"""Phase 42 Plan 01 — SimStepWorker offscreen tests (RED scaffold, Task 1).

Covers the sim-side half of GUI-11's render/sim decoupling:
  - TestSimStepWorkerAccumulator (SC#1): physics advances at ~50 Hz via the
    fixed-step accumulator; snapshot_ready is emitted.
  - TestPauseResumeStepOne (SC#3): pause stops stepping; step_one() advances
    exactly one physics step and publishes exactly one snapshot; resume
    restarts the accumulator.
  - TestDecouplingAndPublishCap (SC#4): a slow render on the UI thread does
    NOT slow physics (worker is on its own QThread); the ~30 Hz publish cap
    limits snapshot_ready emissions.
  - TestSpeedScaling (D-09): 2x ~= 2x steps; 0.5x ~= half (within jitter).

Offscreen harness mirrors tests/test_dock_state.py:19-55 (standalone single-file
variant): QT_QPA_PLATFORM=offscreen module-top, _HAVE_PYSIDE6 try/except,
pytestmark skipif, qapp session fixture, isolated_home fixture.

RED on this task: ``SimStepWorker`` is not yet implemented (Task 2 GREEN), so
the module-level import surfaces an honest ImportError collection error.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

# Force offscreen Qt for all tests in this file (must run before any
# QApplication is constructed).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")


# ---------------------------------------------------------------------------
# Module-under-test import (RED — Task 1; GREEN in Task 2).
# ---------------------------------------------------------------------------
# Imported at module top so collection surfaces the honest ImportError baseline
# before Task 2 creates the module. Do NOT wrap in try/except or pytest.skip.
from surg_rl.editor.sim_step_worker import SimStepWorker  # noqa: E402
from surg_rl.simulators.base_simulator import (  # noqa: E402
    Observation,
    State,
    StepResult,
)


# ---------------------------------------------------------------------------
# MockSimulator — mirrors the shape verified in 42-RESEARCH.md §Code Examples
# against base_simulator.py (State :90-111, StepResult :114-135, step :219,
# get_state :252, render :231). CPU-only, no GL context, safe off-UI-thread
# (only step() + get_state() are called from the worker thread).
# ---------------------------------------------------------------------------
@dataclass
class MockSimulator:
    step_delay: float = 0.0
    render_delay: float = 0.0
    step_count: int = 0
    render_count: int = 0
    timestep: float = 0.02
    frame_skip: int = 1
    _loaded: bool = True
    # Attribute hooks the RenderPollLoop / viewport push for camera orbit; the
    # mock accepts them silently so render() can read them if it wants.
    _editor_camera_target: Any = field(default_factory=lambda: (0.0, 0.0, 0.0))
    _editor_camera_distance: float = 2.5
    _editor_camera_azimuth: float = 0.0
    _editor_camera_elevation: float = 0.0

    def step(self, action: Any | None) -> StepResult:
        if self.step_delay > 0.0:
            time.sleep(self.step_delay)
        self.step_count += 1
        return StepResult(
            observation=Observation(),
            reward=0.0,
            terminated=False,
            truncated=False,
        )

    def get_state(self) -> State:
        return State(time=float(self.step_count))

    def render(
        self,
        mode: str = "rgb_array",
        width: int | None = None,
        height: int | None = None,
        camera_name: str | None = None,
    ) -> np.ndarray:
        if self.render_delay > 0.0:
            time.sleep(self.render_delay)
        self.render_count += 1
        h = height or 480
        w = width or 640
        return np.zeros((h, w, 3), dtype=np.uint8)

    def close(self) -> None:  # noqa: D401
        """No-op close (mock holds no real resources)."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def qapp():
    if not _HAVE_PYSIDE6:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME + XDG_CONFIG_HOME to tmp_path so QSettings stays isolated."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path


# ---------------------------------------------------------------------------
# Cross-thread slot invocation helper.
# ---------------------------------------------------------------------------
# PySide6 has no Q_ARG macro (that's PyQt). The idiomatic PySide6 way to
# invoke a slot cross-thread with QueuedConnection is to emit a signal that
# is connected to the slot — Qt auto-selects QueuedConnection when the
# emitter (UI thread) and receiver (worker QThread) live on different
# threads. ``_make_emitter`` wraps the four worker-driving signals so tests
# can drive ``SimStepWorker`` exactly the way EditorWindow will in Plan 02.
def _make_emitter(worker):
    """Create a UI-thread emitter and connect its signals to the worker slots.

    Connection type is AutoConnection — Qt upgrades to QueuedConnection because
    ``worker`` lives on the worker QThread and the emitter lives on the UI
    thread. Returns the emitter so the test can ``.bind.emit(mock)`` etc.
    """
    from PySide6.QtCore import QObject, Signal

    class _E(QObject):
        bind = Signal(object)
        pause = Signal(bool)
        speed = Signal(float)
        step = Signal()

    e = _E()
    e.bind.connect(worker.bind_scene)
    e.pause.connect(worker.set_paused)
    e.speed.connect(worker.set_speed)
    e.step.connect(worker.step_one)
    return e


def _settle(qapp, seconds: float) -> None:
    """Sleep then flush UI-thread deliveries — lets the worker QThread run.

    ``QTest.qWait`` holds the Python GIL during its internal msleep, which
    starves the worker QThread (its ``_tick`` slot is Python and needs the
    GIL). A plain ``time.sleep`` releases the GIL so the worker thread runs
    freely at ~50 Hz; the trailing ``processEvents`` flushes any queued
    ``snapshot_ready`` deliveries to the UI thread.
    """
    time.sleep(seconds)
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------
@pytestmark
class TestSimStepWorkerAccumulator:
    """SC#1: physics advances at ~50 Hz via the fixed-step accumulator."""

    def test_accumulator_advances_physics(self, qapp, isolated_home) -> None:
        from PySide6.QtCore import QThread

        worker = SimStepWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        mock = MockSimulator()
        emitter = _make_emitter(worker)
        try:
            thread.start()
            emitter.bind.emit(mock)  # queued -> worker thread
            emitter.pause.emit(False)  # queued -> unpause (D-11 load paused)
            # Settle: time.sleep releases the GIL so the worker QThread runs
            # freely at ~50 Hz; processEvents flushes UI-thread deliveries.
            _settle(qapp, 0.1)
            # 50 Hz * 100 ms ~= 5 steps; allow jitter down to 3.
            assert mock.step_count >= 3, (
                f"expected >=3 steps in 100ms at 50Hz, got {mock.step_count}"
            )
        finally:
            worker.stop()
            thread.quit()
            assert thread.wait(3000), "worker thread did not exit within 3s"


@pytestmark
class TestPauseResumeStepOne:
    """SC#3: pause stops stepping; step_one advances exactly 1; resume restarts."""

    def test_step_one_advances_exactly_one_while_paused(self, qapp, isolated_home) -> None:
        from PySide6.QtCore import QThread

        worker = SimStepWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        mock = MockSimulator()
        emitter = _make_emitter(worker)
        snapshots: list = []
        worker.snapshot_ready.connect(
            lambda snap: snapshots.append(snap),
            __import__("PySide6").QtCore.Qt.ConnectionType.QueuedConnection,
        )
        try:
            thread.start()
            emitter.bind.emit(mock)
            # Worker stays paused (D-11 default). Let the bind land.
            _settle(qapp, 0.03)
            assert mock.step_count == 0, "no steps should fire while paused"

            # step_one -> exactly one physics step + one snapshot.
            emitter.step.emit()
            _settle(qapp, 0.03)
            assert mock.step_count == 1, (
                f"step_one should advance exactly 1, got {mock.step_count}"
            )
            assert len(snapshots) == 1, (
                f"step_one should publish exactly 1 snapshot, got {len(snapshots)}"
            )
        finally:
            worker.stop()
            thread.quit()
            thread.wait(3000)

    def test_pause_then_resume_advances_then_holds(self, qapp, isolated_home) -> None:
        from PySide6.QtCore import QThread

        worker = SimStepWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        mock = MockSimulator()
        emitter = _make_emitter(worker)
        try:
            thread.start()
            emitter.bind.emit(mock)
            _settle(qapp, 0.02)
            # Unpause for 100 ms -> steps advance.
            emitter.pause.emit(False)
            _settle(qapp, 0.1)
            count_after_run = mock.step_count
            assert count_after_run >= 3, (
                f"expected >=3 steps after resume, got {count_after_run}"
            )

            # Pause -> steps must NOT advance further.
            emitter.pause.emit(True)
            _settle(qapp, 0.1)
            assert mock.step_count == count_after_run, (
                "step_count must not advance while paused"
            )
        finally:
            worker.stop()
            thread.quit()
            thread.wait(3000)


@pytestmark
class TestDecouplingAndPublishCap:
    """SC#4: render/sim decoupled + ~30 Hz publish cap."""

    def test_publish_cap_limits_snapshot_ready_to_30hz(self, qapp, isolated_home) -> None:
        from PySide6.QtCore import QThread

        worker = SimStepWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        mock = MockSimulator(step_delay=0.0)
        emitter = _make_emitter(worker)
        snapshots: list = []
        worker.snapshot_ready.connect(
            lambda snap: snapshots.append(snap),
            __import__("PySide6").QtCore.Qt.ConnectionType.QueuedConnection,
        )
        try:
            thread.start()
            emitter.bind.emit(mock)
            emitter.pause.emit(False)
            _settle(qapp, 0.1)
            # 50 Hz sim steps.
            assert mock.step_count >= 3
            # 30 Hz publish cap -> ~3 publishes in 100 ms; allow 4 for jitter.
            assert len(snapshots) <= 4, (
                f"publish cap failed: {len(snapshots)} snapshots in 100ms (<=4 expected)"
            )
            assert len(snapshots) >= 1, "expected at least one published snapshot"
        finally:
            worker.stop()
            thread.quit()
            thread.wait(3000)

    def test_slow_ui_thread_does_not_slow_physics(self, qapp, isolated_home) -> None:
        """A slow render on the UI thread must NOT slow the worker's physics.

        Simulates a slow render by blocking the UI thread with time.sleep(0.08)
        in a loop while the worker steps on its own QThread. The worker's
        step_count still advances at ~50 Hz because step() runs on the worker
        thread, decoupled from the UI thread.
        """
        from PySide6.QtCore import QThread

        worker = SimStepWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        mock = MockSimulator(step_delay=0.0)
        emitter = _make_emitter(worker)
        try:
            thread.start()
            emitter.bind.emit(mock)
            emitter.pause.emit(False)
            # Block the UI thread in ~80 ms slices for ~200 ms (slow render
            # simulation). The worker thread keeps stepping independently.
            end = time.monotonic() + 0.2
            while time.monotonic() < end:
                time.sleep(0.08)  # simulate an 80 ms synchronous render
                qapp.processEvents()
            assert mock.step_count >= 5, (
                f"worker physics should keep advancing while UI is blocked; "
                f"got {mock.step_count} steps in ~200ms (expected >=5)"
            )
        finally:
            worker.stop()
            thread.quit()
            thread.wait(3000)


@pytestmark
class TestSpeedScaling:
    """D-09: speed scales wall_dt (NOT sim_dt); 2x ~= 2x, 0.5x ~= half."""

    def test_speed_2x_doubles_step_count(self, qapp, isolated_home) -> None:
        from PySide6.QtCore import QThread

        worker_1x, thread_1x, mock_1x, em_1x = self._make_worker()
        worker_2x, thread_2x, mock_2x, em_2x = self._make_worker()
        try:
            thread_1x.start()
            thread_2x.start()
            em_1x.bind.emit(mock_1x)
            em_2x.bind.emit(mock_2x)
            em_1x.pause.emit(False)
            em_2x.speed.emit(2.0)
            em_2x.pause.emit(False)
            _settle(qapp, 0.12)
            c1 = mock_1x.step_count
            c2 = mock_2x.step_count
            # 2x should be roughly double 1x; generous jitter bounds (1.5x..2.5x).
            if c1 >= 2:
                ratio = c2 / c1
                assert 1.5 <= ratio <= 2.5, (
                    f"2x speed ratio out of bounds: 1x={c1}, 2x={c2}, ratio={ratio:.2f}"
                )
            else:
                pytest.skip("1x baseline too small for a meaningful ratio")
        finally:
            worker_1x.stop()
            worker_2x.stop()
            thread_1x.quit()
            thread_2x.quit()
            thread_1x.wait(3000)
            thread_2x.wait(3000)

    def test_speed_0_5x_halves_step_count(self, qapp, isolated_home) -> None:
        from PySide6.QtCore import QThread

        worker_1x, thread_1x, mock_1x, em_1x = self._make_worker()
        worker_half, thread_half, mock_half, em_half = self._make_worker()
        try:
            thread_1x.start()
            thread_half.start()
            em_1x.bind.emit(mock_1x)
            em_half.bind.emit(mock_half)
            em_1x.pause.emit(False)
            em_half.speed.emit(0.5)
            em_half.pause.emit(False)
            _settle(qapp, 0.15)
            c1 = mock_1x.step_count
            ch = mock_half.step_count
            # 0.5x should be roughly half of 1x; generous jitter (0.3x..0.7x).
            if c1 >= 4:
                ratio = ch / c1
                assert 0.3 <= ratio <= 0.7, (
                    f"0.5x speed ratio out of bounds: 1x={c1}, 0.5x={ch}, ratio={ratio:.2f}"
                )
            else:
                pytest.skip("1x baseline too small for a meaningful ratio")
        finally:
            worker_1x.stop()
            worker_half.stop()
            thread_1x.quit()
            thread_half.quit()
            thread_1x.wait(3000)
            thread_half.wait(3000)

    @staticmethod
    def _make_worker():
        from PySide6.QtCore import QThread

        worker = SimStepWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        mock = MockSimulator()
        emitter = _make_emitter(worker)
        return worker, thread, mock, emitter