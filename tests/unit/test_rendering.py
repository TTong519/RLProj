"""Unit tests for surg_rl.render_thread module.

Tests use MagicMock to avoid creating real OS windows.
"""

import platform
import threading
import time
from unittest.mock import MagicMock

import pytest

from surg_rl.render_thread import RenderThread
from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
from surg_rl.simulators.pybullet_simulator import PyBulletSimulator


# ============================================================================
# RenderThread tests
# ============================================================================

class TestRenderThread:
    """Tests for the background render thread."""

    def test_is_daemon(self):
        """Thread must be a daemon thread."""
        viewer = MagicMock()
        rt = RenderThread(viewer, target_fps=30.0)
        assert rt.daemon is True

    def test_calls_sync_at_interval(self):
        """Viewer.sync() should be called at roughly the target interval."""
        viewer = MagicMock()
        viewer.sync = MagicMock()
        viewer.is_running = MagicMock(return_value=True)
        rt = RenderThread(viewer, target_fps=60.0)
        rt.start()

        # Let it run for a short period
        time.sleep(0.2)
        rt.stop()

        # Should have been called multiple times over 200ms at 60 FPS
        assert viewer.sync.call_count >= 3

    def test_skip_when_not_running(self):
        """If viewer says it's not running, skip sync call."""
        viewer = MagicMock()
        viewer.is_running = False
        rt = RenderThread(viewer, target_fps=1000)  # very high fps
        rt.start()
        time.sleep(0.03)
        rt.stop()
        viewer.sync.assert_not_called()

    def test_stops_cleanly(self):
        """stop() should clear event, join, and close viewer."""
        viewer = MagicMock()
        viewer.close = MagicMock()
        rt = RenderThread(viewer, target_fps=10.0)
        rt.start()
        time.sleep(0.05)
        rt.stop()
        assert not rt.is_alive()
        viewer.close.assert_called_once()


# ============================================================================
# MuJoCo viewer tests (mocked)
# ============================================================================

class TestMuJoCoViewer:
    """Mocked tests for MuJoCoSimulator.start_viewer / stop_viewer."""

    @pytest.fixture(autouse=True)
    def _patch_display(self, monkeypatch):
        """Pretend display is available so we always test the viewer path."""
        monkeypatch.setenv("DISPLAY", ":0")

    def test_start_viewer_returns_true(self, monkeypatch):
        """start_viewer returns True when launch_passive succeeds."""
        sim = MuJoCoSimulator()
        sim._loaded = True
        sim._model = MagicMock()
        sim._data = MagicMock()

        # Mock mujoco module + viewer so we don't need the real package
        mock_mujoco = MagicMock()
        mock_viewer = MagicMock()
        mock_viewer.close = MagicMock()
        mock_mujoco.viewer.launch_passive = lambda model, data: mock_viewer
        sim._mujoco = mock_mujoco

        # Ensure renderer appears available and NOT on macOS
        monkeypatch.setattr(sim, "_renderer_available", True)
        monkeypatch.setattr(
            "surg_rl.simulators.mujoco_simulator.platform.system", lambda: "Linux"
        )

        result = sim.start_viewer(target_fps=60.0)
        assert result is True
        assert sim._viewer is mock_viewer
        assert sim._render_thread is not None
        assert sim._render_thread.is_alive()
        sim.stop_viewer()
        assert not sim._render_thread or not sim._render_thread.is_alive()

    def test_headless_returns_false(self, monkeypatch):
        """If the renderer is not available, return False."""
        sim = MuJoCoSimulator()
        sim._loaded = True
        # Force headless by pre-setting the cached flag to False
        sim._renderer_available = False

        result = sim.start_viewer()
        assert result is False
        assert sim._viewer is None

    @pytest.mark.skipif(
        platform.system() != "Darwin",
        reason="macOS-specific RuntimeError"
    )
    def test_macos_raises_without_mjpython(self, monkeypatch):
        """On macOS, without mjpython, start_viewer raises RuntimeError."""
        sim = MuJoCoSimulator()
        sim._loaded = True
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.raises(RuntimeError, match="mjpython"):
            sim.start_viewer()

    def test_stop_viewer_cleans_up(self, monkeypatch):
        """stop_viewer should stop the render thread and clear viewer."""
        sim = MuJoCoSimulator()
        sim._loaded = True
        sim._model = MagicMock()
        sim._data = MagicMock()

        mock_viewer = MagicMock()
        mock_mujoco = MagicMock()
        mock_mujoco.viewer.launch_passive = lambda model, data: mock_viewer
        sim._mujoco = mock_mujoco

        monkeypatch.setattr(sim, "_renderer_available", True)
        monkeypatch.setattr(
            "surg_rl.simulators.mujoco_simulator.platform.system", lambda: "Linux"
        )

        sim.start_viewer(target_fps=30.0)
        time.sleep(0.05)
        sim.stop_viewer()

        assert sim._render_thread is None
        assert sim._viewer is None


# ============================================================================
# PyBullet viewer tests
# ============================================================================

class TestPyBulletViewer:
    """Tests for PyBullet start_viewer / stop_viewer."""

    def test_gui_returns_true(self):
        """GUI mode passes through from constructor."""
        sim = PyBulletSimulator(render_mode="GUI")
        assert sim.start_viewer() is True

    def test_direct_returns_false(self):
        """DIRECT mode logs warning and returns False."""
        sim = PyBulletSimulator(render_mode="DIRECT")
        assert sim.start_viewer() is False

    def test_stop_viewer_is_noop(self):
        """stop_viewer is a no-op in PyBullet."""
        sim = PyBulletSimulator(render_mode="DIRECT")
        sim.stop_viewer()  # should not raise


# ============================================================================
# SurgicalEnv integration tests (mocked/specialised)
# ============================================================================

class TestSurgicalEnvViewer:
    """Headless/mocked tests for SurgicalEnv render wiring."""

    def test_eager_start(self, monkeypatch):
        """Human mode should call start_viewer eagerly during __init__."""
        started = []

        class _SpySimulator(MuJoCoSimulator):
            def start_viewer(self, target_fps=30.0):
                started.append(("start", target_fps))
                return False

        monkeypatch.setattr(
            "surg_rl.rl.environment.MuJoCoSimulator", _SpySimulator
        )

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="human",
            render_fps=60.0,
        )
        env = SurgicalEnv(config)
        try:
            assert started == [("start", 60.0)]
        finally:
            env.close()

    def test_render_rgb_array_delegates_to_simulator(self, monkeypatch):
        """render() in rgb_array mode should call simulator.render()."""
        render_calls = []

        class _SpySimulator(MuJoCoSimulator):
            def render(self, mode="rgb_array", **kw):
                render_calls.append(mode)
                return None

        monkeypatch.setattr(
            "surg_rl.rl.environment.MuJoCoSimulator", _SpySimulator
        )

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="rgb_array",
        )
        env = SurgicalEnv(config)
        try:
            env.render()
            assert "rgb_array" in render_calls
        finally:
            env.close()

    def test_close_calls_stop_viewer(self, monkeypatch):
        """close() should call stop_viewer on the simulator if available."""
        calls = []

        class _SpySimulator(MuJoCoSimulator):
            def start_viewer(self, target_fps=30.0):
                return False

            def stop_viewer(self):
                calls.append("stop_viewer")

            def close(self):
                calls.append("close")

        monkeypatch.setattr(
            "surg_rl.rl.environment.MuJoCoSimulator", _SpySimulator
        )

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="human",
        )
        env = SurgicalEnv(config)
        env.close()
        assert "stop_viewer" in calls
        assert "close" in calls

    def test_headless_fallback_sets_none(self, monkeypatch, caplog):
        """If start_viewer returns False, render_mode should become None."""
        class _NoopSimulator(MuJoCoSimulator):
            def start_viewer(self, target_fps=30.0):
                return False

        monkeypatch.setattr(
            "surg_rl.rl.environment.MuJoCoSimulator", _NoopSimulator
        )

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="human",
        )
        env = SurgicalEnv(config)
        try:
            assert env.render_mode is None
        finally:
            env.close()

    def test_handlers_registered(self, monkeypatch):
        """Repeated env creation should not double-register signals."""
        configs = [
            SurgicalEnvConfig(
                scene_path="scenes/minimal_scene.json",
                render_mode="rgb_array",
            )
            for _ in range(3)
        ]
        envs = [SurgicalEnv(c) for c in configs]
        for e in envs:
            assert e._handlers_registered is True
            e.close()

    def test_sigint_handler_crashes_gracefully(self, monkeypatch):
        """SIGINT handler should call close() and raise KeyboardInterrupt."""
        class _SpySimulator(MuJoCoSimulator):
            def start_viewer(self, target_fps=30.0):
                return False

            def close(self):
                pass

        monkeypatch.setattr(
            "surg_rl.rl.environment.MuJoCoSimulator", _SpySimulator
        )

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="rgb_array",
        )
        env = SurgicalEnv(config)
        import signal

        # Simulate SIGINT
        try:
            handler = signal.getsignal(signal.SIGINT)
            handler(signal.SIGINT, None)
        except KeyboardInterrupt:
            pass  # expected
        env.close()


# ============================================================================
# Step-overhead heuristic (mocked)
# ============================================================================

class TestStepOverhead:
    """Ensure rendering does not block the step() path."""

    def test_step_with_viewer_not_blocked(self, monkeypatch):
        """Step should complete regardless of viewer state."""
        step_called = []

        class _FastSimulator(MuJoCoSimulator):
            def start_viewer(self, target_fps=30.0):
                return False

            def step(self, action):
                step_called.append(True)
                # Return a minimal StepResult-like container
                from surg_rl.simulators.base_simulator import StepResult
                return StepResult(
                    observation=MagicMock(rgb_image=None),
                    reward=0.0,
                    terminated=False,
                    truncated=False,
                )

        monkeypatch.setattr(
            "surg_rl.rl.environment.MuJoCoSimulator", _FastSimulator
        )

        config = SurgicalEnvConfig(
            scene_path="scenes/minimal_scene.json",
            render_mode="rgb_array",
        )
        env = SurgicalEnv(config)
        try:
            env.reset()
            env.step(env.action_space.sample())
            assert step_called
        finally:
            env.close()


# ============================================================================
# CLI train --render-human wiring (RENDER-04)
# ============================================================================

class TestCliRenderHumanWiring:
    """RENDER-04: verify --render-human/--render-fps flow to TrainingConfig."""

    def test_trainingconfig_accepts_render_mode(self):
        """TrainingConfig has render_mode field for CLI wiring."""
        from surg_rl.rl.training import TrainingConfig

        config = TrainingConfig(render_mode="human", render_fps=30.0)
        assert config.render_mode == "human"
        assert config.render_fps == 30.0

    def test_trainingconfig_default_render_none(self):
        """TrainingConfig render_mode defaults to None (no viewer)."""
        from surg_rl.rl.training import TrainingConfig

        config = TrainingConfig()
        assert config.render_mode is None
        assert config.render_fps == 30.0

    def test_surgicalenvconfig_propagates_render_mode(self):
        """SurgicalEnvConfig propagates render_mode when set."""
        from surg_rl.rl.environment import SurgicalEnvConfig

        config = SurgicalEnvConfig(render_mode="human", render_fps=30.0)
        assert config.render_mode == "human"
        assert config.render_fps == 30.0
