"""Phase 42 Plan 01 — RenderPollLoop offscreen tests (RED scaffold, Task 1).

Covers the render-side half of GUI-11's render/sim decoupling:
  - TestRenderPollCadence (SC#2 proxy): with an instant-render MockSimulator,
    RenderPollLoop fires >=30 Hz (QTimer.singleShot cadence _FRAME_INTERVAL_MS=33).
  - TestStepOneRendersWhilePaused (Pitfall 6): the render-poll stays alive
    while the worker is paused; a step-one snapshot (new frame_id) renders on
    the next poll.
  - TestSkipNoNewSnapshot: render() NOT called when snapshot.frame_id ==
    _last_rendered_id (skip-when-no-new saves CPU).
  - TestRunningGuard: after stop(), _tick early-returns and does NOT
    reschedule (already-queued singleShot callbacks become no-ops).

Offscreen harness mirrors tests/test_dock_state.py:19-55 (standalone single-file
variant): QT_QPA_PLATFORM=offscreen module-top, _HAVE_PYSIDE6 try/except,
pytestmark skipif, qapp session fixture, isolated_home fixture.

RED on this task: ``RenderPollLoop`` is not yet implemented (Task 3 GREEN), so
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
# Module-under-test import (RED — Task 1; GREEN in Task 3).
# ---------------------------------------------------------------------------
# Imported at module top so collection surfaces the honest ImportError baseline
# before Task 3 creates the module. Do NOT wrap in try/except or pytest.skip.
from surg_rl.editor.render_poll_loop import RenderPollLoop  # noqa: E402
from surg_rl.simulators.base_simulator import (  # noqa: E402
    Observation,
    State,
    StepResult,
)


# ---------------------------------------------------------------------------
# _Snapshot stub — local dataclass for the test only. The real _Snapshot lives
# in sim_step_worker.py (Task 2); RenderPollLoop reads snapshot.frame_id
# (duck-typed), so a local stub is sufficient and keeps this test file
# independent of Task 2's module for the RED baseline.
# ---------------------------------------------------------------------------
@dataclass
class _Snapshot:
    state: Any
    frame_id: int


# ---------------------------------------------------------------------------
# MockSimulator — mirrors the shape verified in 42-RESEARCH.md §Code Examples
# (see test_sim_step_worker.py for the full docstring). render() is the ONLY
# call RenderPollLoop makes (D-02 — the render-poll never calls step()).
# ---------------------------------------------------------------------------
@dataclass
class MockSimulator:
    render_delay: float = 0.0
    step_count: int = 0
    render_count: int = 0
    timestep: float = 0.02
    frame_skip: int = 1
    _loaded: bool = True
    _editor_camera_target: Any = field(default_factory=lambda: (0.0, 0.0, 0.0))
    _editor_camera_distance: float = 2.5
    _editor_camera_azimuth: float = 0.0
    _editor_camera_elevation: float = 0.0

    def step(self, action: Any | None) -> StepResult:
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
# Spy canvas — records set_image / set_text calls so tests can assert what the
# render-poll actually pushed to the display surface.
# ---------------------------------------------------------------------------
@dataclass
class _SpyCanvas:
    set_image_count: int = 0
    set_text_count: int = 0
    last_image: Any = None
    last_text: str = ""

    def set_image(self, arr) -> None:
        self.set_image_count += 1
        self.last_image = arr

    def set_text(self, text: str) -> None:
        self.set_text_count += 1
        self.last_text = text

    def width(self) -> int:
        return 640

    def height(self) -> int:
        return 480


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
# Helpers — construct a RenderPollLoop wired to a MockSimulator + spy canvas.
# ---------------------------------------------------------------------------
def _make_loop(mock: MockSimulator, canvas: _SpyCanvas | None = None, on_fps_update=None):
    if canvas is None:
        canvas = _SpyCanvas()
    camera_offset_ref = lambda: {  # noqa: E731
        "target": (0.0, 0.0, 0.0),
        "distance": 2.5,
        "azimuth": 0.0,
        "elevation": 0.0,
    }
    return RenderPollLoop(
        simulator_ref=lambda: mock,  # noqa: E731
        canvas=canvas,
        camera_offset_ref=camera_offset_ref,
        on_fps_update=on_fps_update,
        width=640,
        height=480,
        camera_name=None,
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------
@pytestmark
class TestRenderPollCadence:
    """SC#2 proxy: RenderPollLoop fires >=30 Hz with an instant-render mock."""

    def test_render_poll_fires_at_least_30hz(self, qapp, isolated_home) -> None:
        from PySide6.QtTest import QTest

        mock = MockSimulator()  # instant render (render_delay=0)
        canvas = _SpyCanvas()
        loop = _make_loop(mock, canvas)
        try:
            loop.start()
            # Pump the UI event loop for ~100 ms. At _FRAME_INTERVAL_MS=33,
            # singleShot fires at ~0, 33, 66, 99 ms -> ~4 ticks; assert >=3.
            # We count _tick invocations (loop._tick_count), not renders:
            # skip-when-no-new means canvas.set_image only rises on a new
            # frame_id, so the timer cadence is the truer offscreen proxy.
            QTest.qWait(100)
            qapp.processEvents()
            assert loop._tick_count >= 3, (
                f"render-poll cadence too low: {loop._tick_count} ticks "
                f"in 100ms (>=3 expected at 30Hz)"
            )
        finally:
            loop.stop()


@pytestmark
class TestStepOneRendersWhilePaused:
    """Pitfall 6: render-poll stays alive while paused; new frame_id renders."""

    def test_new_snapshot_renders_on_next_poll(self, qapp, isolated_home) -> None:
        from PySide6.QtTest import QTest

        mock = MockSimulator()
        canvas = _SpyCanvas()
        loop = _make_loop(mock, canvas)
        try:
            loop.start()
            QTest.qWait(30)
            qapp.processEvents()
            renders_before = canvas.set_image_count

            # Inject a snapshot with frame_id=1 (as if the worker's step_one
            # published it while paused).
            loop.on_snapshot(_Snapshot(state=mock.get_state(), frame_id=1))
            QTest.qWait(60)
            qapp.processEvents()
            assert canvas.set_image_count >= renders_before + 1, (
                f"new frame_id=1 should render; renders before={renders_before}, "
                f"after={canvas.set_image_count}"
            )

            renders_after_1 = canvas.set_image_count
            # Inject frame_id=2 -> renders exactly once more for the new id.
            loop.on_snapshot(_Snapshot(state=mock.get_state(), frame_id=2))
            QTest.qWait(60)
            qapp.processEvents()
            assert canvas.set_image_count >= renders_after_1 + 1, (
                f"new frame_id=2 should render; renders before={renders_after_1}, "
                f"after={canvas.set_image_count}"
            )
        finally:
            loop.stop()


@pytestmark
class TestSkipNoNewSnapshot:
    """Skip-when-no-new: render() NOT called when frame_id is unchanged."""

    def test_duplicate_frame_id_skips_render(self, qapp, isolated_home) -> None:
        from PySide6.QtTest import QTest

        mock = MockSimulator()
        canvas = _SpyCanvas()
        loop = _make_loop(mock, canvas)
        try:
            loop.start()
            QTest.qWait(30)
            qapp.processEvents()
            # Inject frame_id=1 and let it render.
            loop.on_snapshot(_Snapshot(state=mock.get_state(), frame_id=1))
            QTest.qWait(60)
            qapp.processEvents()
            render_count_after_first = mock.render_count

            # Re-inject the SAME frame_id -> skip render.
            loop.on_snapshot(_Snapshot(state=mock.get_state(), frame_id=1))
            QTest.qWait(60)
            qapp.processEvents()
            assert mock.render_count == render_count_after_first, (
                f"render() should NOT be called for duplicate frame_id; "
                f"render_count incremented from {render_count_after_first} "
                f"to {mock.render_count}"
            )
        finally:
            loop.stop()


@pytestmark
class TestRunningGuard:
    """After stop(), _tick early-returns and does NOT reschedule."""

    def test_stop_halts_render_poll(self, qapp, isolated_home) -> None:
        from PySide6.QtTest import QTest

        mock = MockSimulator()
        canvas = _SpyCanvas()
        loop = _make_loop(mock, canvas)
        loop.start()
        QTest.qWait(50)
        qapp.processEvents()
        renders_at_stop = canvas.set_image_count
        loop.stop()
        # Pump the event loop for another interval; already-queued singleShot
        # callbacks must early-return on `not _running` and NOT render.
        QTest.qWait(100)
        qapp.processEvents()
        assert canvas.set_image_count == renders_at_stop, (
            f"render-poll should not render after stop(); "
            f"renders_at_stop={renders_at_stop}, after_wait={canvas.set_image_count}"
        )
