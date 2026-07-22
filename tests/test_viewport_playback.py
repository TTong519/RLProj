"""Phase 42 Plan 02 — Viewport playback integration tests (RED scaffold, Task 1).

Covers the integration half of GUI-11 (EditorWindow + ViewportPanel wiring of
the Plan 01 SimStepWorker + RenderPollLoop):

  - TestPlaybackToolbar (D-06/D-09): a QToolBar objectName="toolbar_playback"
    is docked at the top with a Play/Pause toggle QAction, a Step-one QAction,
    and a QComboBox objectName="combo_playback_speed" with exactly the 5 items
    "0.25x","0.5x","1x","2x","4x" (default currentText "1x" per D-10).
  - TestPlaybackStatus (D-08): a 5th permanent QLabel _status_playback reflects
    "▶ playing {speed}x" / "⏸ paused" / "⏸ paused (static scene — no dynamics)".
  - TestLoadPaused (D-11): after update_scene(scene), sim_worker._paused == True,
    the Play button is unchecked, and the status bar shows "⏸ paused".
  - TestStaticSceneHint (D-12): _scene_has_dynamics predicate (pure-function
    assertions GREEN in Task 1) + the status-bar hint integration (GREEN once
    Task 2 + 3 wire update_scene + _update_playback_status).
  - TestCloseMidStepCleanExit (D-04): closing the editor mid-step fires
    aboutToClose -> _stop_sim_worker -> thread.quit + thread.wait(3000) — the
    SimStepWorker thread is no longer running; no segfault / RuntimeError.

Offscreen harness mirrors tests/test_dock_state.py:19-55 (standalone single-file
variant): QT_QPA_PLATFORM=offscreen module-top, _HAVE_PYSIDE6 try/except,
pytestmark skipif, qapp session fixture, isolated_home fixture.

RED baseline on Task 1: the EditorWindow wiring (QThread/SimStepWorker/
RenderPollLoop/toolbar/status-bar/_stop_sim_worker) does not exist yet (Task 3
GREEN), so the integration assertions surface honest AttributeErrors. The
pure-function assertions in TestStaticSceneHint on ``_scene_has_dynamics`` are
GREEN from Task 1 (the predicate ships in viewport.py in this same task).
"""

from __future__ import annotations

import contextlib
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
# Module-under-test imports.
# ---------------------------------------------------------------------------
# The predicate ships in viewport.py in Task 1 (GREEN part of this task); the
# EditorWindow integration wiring (Task 3) is what turns the integration
# assertions GREEN.
from surg_rl.editor.viewport import _scene_has_dynamics  # noqa: E402
from surg_rl.simulators.base_simulator import (  # noqa: E402
    Observation,
    State,
    StepResult,
)


# ---------------------------------------------------------------------------
# MockSimulator — mirrors the shape verified in 42-RESEARCH.md §Code Examples
# (see tests/test_sim_step_worker.py for the full docstring). CPU-only, no GL
# context — render() returns a zero ndarray so ViewportPanel/RenderPollLoop can
# run offscreen without a real backend. Used by the integration tests via
# monkeypatch.setattr(viewport, "_default_load_simulator", lambda scene: mock).
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


@pytest.fixture
def mock_loader(monkeypatch):
    """Replace _default_load_simulator with a MockSimulator factory.

    Returns a list of the MockSimulator instances created so a test can inspect
    step/render counts on the live simulator. The factory returns a fresh mock
    per call (update_scene loads a new simulator each swap).
    """
    instances: list[MockSimulator] = []

    def _factory(scene):  # noqa: ANN001
        mock = MockSimulator()
        instances.append(mock)
        return mock

    import surg_rl.editor.viewport as vp_module

    monkeypatch.setattr(vp_module, "_default_load_simulator", _factory)
    return instances


# ---------------------------------------------------------------------------
# Scene builders for the D-12 predicate + integration assertions.
#
# The predicate is a STRUCTURAL schema-level check (D-12) — it only reads
# whether ``scene.robots`` / ``scene.tissues`` / ``scene.fluid`` are non-empty
# / non-None. We build the scenes with ``SceneDefinition.model_construct(...)``
# (Pydantic's documented validation-bypass per CLAUDE.md) and sentinel objects
# so the predicate tests stay focused on the structural contract, not on
# assembling fully-valid robot/tissue/fluid configs (which require urdf_path /
# geometry / bounds validators that are out of scope for the D-12 check). The
# integration tests (TestLoadPaused, TestStaticSceneHint integration assertion)
# also use these builders — ViewportPanel.update_scene only stores the scene
# and reads these same structural fields, never validates the nested configs.
# ---------------------------------------------------------------------------
def _empty_scene():
    from surg_rl.scene_definition import SceneDefinition

    return SceneDefinition()


def _scene_with_robot():
    from surg_rl.scene_definition import SceneDefinition

    return SceneDefinition.model_construct(robots=[object()])


def _scene_with_tissue():
    from surg_rl.scene_definition import SceneDefinition

    return SceneDefinition.model_construct(tissues=[object()])


def _scene_with_fluid():
    # D-12 CORRECTED field path: fluid is a DIRECT field on SceneDefinition
    # (schema.py:1442), NOT on EnvironmentConfig.
    from surg_rl.scene_definition import SceneDefinition

    return SceneDefinition.model_construct(fluid=object())


def _scene_with_instruments_only():
    from surg_rl.scene_definition import SceneDefinition

    return SceneDefinition.model_construct(instruments=[object()])


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------
@pytestmark
class TestPlaybackToolbar:
    """D-06/D-09: playback QToolBar + Play/Pause toggle + Step-one + speed combo.

    RED on Task 1: the toolbar is built in Task 3's ``_build_playback_toolbar``;
    findChildren(QToolBar) is empty until then.
    """

    def test_playback_toolbar_has_required_widgets(self, qapp, isolated_home, mock_loader) -> None:
        from PySide6.QtWidgets import QComboBox, QToolBar

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        try:
            tbs = w.findChildren(QToolBar)
            names = [t.objectName() for t in tbs]
            assert tbs, "EditorWindow should construct at least one QToolBar"
            assert "toolbar_playback" in names, f"toolbar_playback objectName missing; got {names}"
            # Speed combo with the 5 D-09 items + D-10 default 1x.
            combos = w.findChildren(QComboBox)
            speed = next((c for c in combos if c.objectName() == "combo_playback_speed"), None)
            assert speed is not None, "combo_playback_speed QComboBox missing"
            items = [speed.itemText(i) for i in range(speed.count())]
            assert items == [
                "0.25x",
                "0.5x",
                "1x",
                "2x",
                "4x",
            ], f"speed combo items must be exactly the 5 D-09 values; got {items}"
            assert (
                speed.currentText() == "1x"
            ), f"speed combo default must be '1x' (D-10); got {speed.currentText()!r}"
            # Play/Pause toggle + Step-one actions exist on the toolbar.
            tb = next(t for t in tbs if t.objectName() == "toolbar_playback")
            actions = tb.actions()
            assert any(
                a.isCheckable() for a in actions
            ), "Play/Pause QAction must be checkable (D-06)"
            assert (
                len(actions) >= 2
            ), f"toolbar must have Play/Pause + Step-one QActions; got {len(actions)}"
        finally:
            with contextlib.suppress(Exception):
                w.close()


@pytestmark
class TestPlaybackStatus:
    """D-08: 5th permanent QLabel _status_playback reflects play/pause/static.

    RED on Task 1: the label + _update_playback_status helper ship in Task 3.
    """

    def test_status_bar_has_playback_label_and_toggles(
        self, qapp, isolated_home, mock_loader
    ) -> None:
        from PySide6.QtWidgets import QLabel

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        try:
            labels = w.findChildren(QLabel)
            playback = next((lbl for lbl in labels if lbl.objectName() == "status_playback"), None)
            assert playback is not None, "status_playback QLabel missing on status bar"
            # Initial state on construction: paused.
            assert (
                "⏸" in playback.text()
            ), f"initial playback status must be paused; got {playback.text()!r}"
            # Toggle to playing via the toolbar action.
            w._act_play_pause.setChecked(True)
            qapp.processEvents()
            assert (
                "▶" in playback.text() and "1x" in playback.text()
            ), f"playback status must show '▶ playing 1x'; got {playback.text()!r}"
            # Toggle back to paused.
            w._act_play_pause.setChecked(False)
            qapp.processEvents()
            assert (
                "⏸" in playback.text()
            ), f"playback status must show paused; got {playback.text()!r}"
        finally:
            with contextlib.suppress(Exception):
                w.close()


@pytestmark
class TestLoadPaused:
    """D-11: after update_scene, sim_worker._paused == True and Play is unchecked.

    RED on Task 1: ``w._sim_worker`` is wired in Task 3; ``update_scene`` is
    extended to re-bind + load-paused in Task 2.
    """

    def test_update_scene_loads_paused(self, qapp, isolated_home, mock_loader) -> None:
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        try:
            scene = _scene_with_robot()
            w._viewport_panel.update_scene(scene)
            qapp.processEvents()
            # D-11 — load paused: worker._paused == True, Play unchecked, status paused.
            assert (
                w._sim_worker._paused is True
            ), "SimStepWorker must be paused after update_scene (D-11)"
            assert (
                w._act_play_pause.isChecked() is False
            ), "Play/Pause QAction must be unchecked after update_scene (D-11)"
            assert "⏸" in w._status_playback.text(), (
                f"status bar must show paused after update_scene; got "
                f"{w._status_playback.text()!r}"
            )
        finally:
            with contextlib.suppress(Exception):
                w.close()


@pytestmark
class TestStaticSceneHint:
    """D-12: _scene_has_dynamics predicate + status-bar hint.

    The pure-function assertions (GREEN in Task 1 — the predicate ships in
    viewport.py in this same task):
      - empty scene -> False
      - robots non-empty -> True
      - tissues non-empty -> True
      - fluid is not None -> True (DIRECT field on SceneDefinition, NOT on
        EnvironmentConfig)
      - instruments-only -> False (instruments without robots have no actuated
        joints — flagged in 42-PATTERNS.md Open Question, LOW risk either way)

    The integration assertion (status-bar hint text after loading a static
    scene) is RED until Task 2 + 3 wire update_scene + _update_playback_status.
    """

    def test_predicate_empty_scene_is_static(self) -> None:
        assert _scene_has_dynamics(_empty_scene()) is False

    def test_predicate_robots_nonempty_has_dynamics(self) -> None:
        assert _scene_has_dynamics(_scene_with_robot()) is True

    def test_predicate_tissues_nonempty_has_dynamics(self) -> None:
        assert _scene_has_dynamics(_scene_with_tissue()) is True

    def test_predicate_fluid_nonnone_has_dynamics(self) -> None:
        # D-12 CORRECTED field path: scene.fluid is a DIRECT field on
        # SceneDefinition (schema.py:1442), NOT scene.environment.fluid.
        assert _scene_has_dynamics(_scene_with_fluid()) is True

    def test_predicate_instruments_only_is_static(self) -> None:
        # instruments without robots have no actuated joints (42-PATTERNS.md
        # Open Question resolution — informational hint only, LOW risk).
        assert _scene_has_dynamics(_scene_with_instruments_only()) is False

    def test_predicate_reads_direct_fluid_not_environment_fluid(self) -> None:
        # Guard against the RESEARCH.md typo (env.fluid is WRONG). Build a
        # scene whose environment has no fluid attribute but whose direct
        # fluid field is set — the predicate MUST return True.
        scene = _scene_with_fluid()
        env = getattr(scene, "environment", None)
        assert env is not None
        assert not hasattr(env, "fluid"), (
            "EnvironmentConfig must NOT have a `fluid` attribute (schema.py:990-1009); "
            "the predicate reads scene.fluid directly (schema.py:1442)"
        )
        assert _scene_has_dynamics(scene) is True

    def test_static_scene_hint_shown_in_status_bar(self, qapp, isolated_home, mock_loader) -> None:
        # Integration assertion — RED until Task 2 + 3.
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        try:
            static_scene = _scene_with_instruments_only()
            w._viewport_panel.update_scene(static_scene)
            qapp.processEvents()
            assert "static scene" in w._status_playback.text(), (
                f"static-scene hint must appear in status bar; got "
                f"{w._status_playback.text()!r}"
            )
            # A scene with a robot does NOT show the static hint.
            dynamic_scene = _scene_with_robot()
            w._viewport_panel.update_scene(dynamic_scene)
            qapp.processEvents()
            assert "static scene" not in w._status_playback.text(), (
                f"dynamic scene must NOT show the static-scene hint; got "
                f"{w._status_playback.text()!r}"
            )
        finally:
            with contextlib.suppress(Exception):
                w.close()


@pytestmark
class TestCloseMidStepCleanExit:
    """D-04: closing mid-step exits cleanly — sim_thread not running after close.

    RED on Task 1: ``w._sim_thread`` + ``w._sim_worker`` are wired in Task 3.

    Mirrors tests/test_dock_state.py:277-329 TestCloseMidCallMockSlow — the
    mock-slow close-mid-call pattern adapted for SimStepWorker.
    """

    def test_close_mid_step_clean_exit(self, qapp, isolated_home, mock_loader) -> None:
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        # Start the worker stepping (resume from the default paused load).
        w._sim_worker.set_paused.emit(False)
        time.sleep(0.05)  # let the accumulator tick a few times
        qapp.processEvents()
        try:
            # Full closeEvent path: aboutToClose -> _stop_sim_worker
            # (sim_worker.stop + thread.quit + thread.wait(3000)) -> viewport.stop.
            w.close()
            qapp.processEvents()
            assert not w._sim_thread.isRunning(), (
                "SimStepWorker thread still running after close — "
                "close mid-step must exit cleanly (D-04)"
            )
        except Exception:
            # Best-effort: still assert the thread state, then re-raise.
            with contextlib.suppress(Exception):
                assert not w._sim_thread.isRunning()
            raise
        finally:
            with contextlib.suppress(Exception):
                w.close()
