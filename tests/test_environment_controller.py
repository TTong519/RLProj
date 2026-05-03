"""Tests for EnvironmentController real/sim mode and external action queue.

Covers TDD task 0 of plan 09-02:
  - Mode flag (_mode = "sim"/"real_robot")
  - External action queue with keep-latest semantics (maxsize=1)
  - get_action() override with real/sim routing
  - set_real_robot_mode() API
  - inject_external_action() with queue management
  - Regression: existing reset(), step_update(), episode_end() still work
"""

import numpy as np
import pytest

from surg_rl.dynamics.environment_controller import (
    EnvironmentController,
    EnvironmentControllerConfig,
)


class TestRealRobotMode:
    """Tests for the real/sim mode flag and external action queue."""

    def test_default_mode_is_sim(self):
        """Test 1: controller.mode == 'sim' by default."""
        controller = EnvironmentController()
        assert controller.mode == "sim"

    def test_external_action_queue_exists_empty(self):
        """Test 1: _external_action_queue exists and is empty."""
        controller = EnvironmentController()
        assert controller._external_action_queue is not None
        assert controller._external_action_queue.empty()

    def test_set_real_robot_mode_true(self):
        """Test 2: set_real_robot_mode(True) switches to 'real_robot'."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        assert controller.mode == "real_robot"

    def test_set_real_robot_mode_false(self):
        """Test 2: set_real_robot_mode(False) switches back to 'sim'."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        controller.set_real_robot_mode(False)
        assert controller.mode == "sim"

    def test_get_action_passthrough_in_sim_mode(self):
        """Test 3: get_action returns policy_action unchanged in sim mode."""
        controller = EnvironmentController()
        pa = np.array([1.0, 2.0, 3.0])
        result = controller.get_action(pa)
        assert np.array_equal(result, pa)

    def test_get_action_returns_external_when_available(self):
        """Test 4: In real_robot mode, get_action returns external action from queue if available."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        external = np.array([4.0, 5.0, 6.0])
        controller.inject_external_action(external)
        pa = np.array([1.0, 2.0, 3.0])
        result = controller.get_action(pa)
        assert np.array_equal(result, external)

    def test_get_action_hold_last_when_queue_empty(self):
        """Test 5: In real_robot mode, if queue empty, get_action returns _last_action."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        # Inject one action, then consume it, then call again
        external = np.array([4.0, 5.0, 6.0])
        controller.inject_external_action(external)
        first = controller.get_action(np.array([1.0, 2.0, 3.0]))
        assert np.array_equal(first, external)
        # Queue now empty — should return hold-last (the previous external action)
        second = controller.get_action(np.array([1.0, 2.0, 3.0]))
        assert np.array_equal(second, external)

    def test_queue_maxsize_one_keep_latest(self):
        """Test 6: Queue respects maxsize=1 — third put overwrites second."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        a1 = np.array([1.0, 1.0, 1.0])
        a2 = np.array([2.0, 2.0, 2.0])
        a3 = np.array([3.0, 3.0, 3.0])
        controller.inject_external_action(a1)
        controller.inject_external_action(a2)
        controller.inject_external_action(a3)  # should overwrite a2
        result = controller.get_action(np.array([0.0, 0.0, 0.0]))
        # Should be a3 (latest), a1 was already evicted by a2's overwrite
        assert np.array_equal(result, a3)

    def test_nan_validation_in_get_action(self):
        """Test D-25: NaN/Inf in external action raises ValueError."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        nan_action = np.array([1.0, np.nan, 3.0])
        controller.inject_external_action(nan_action)
        with pytest.raises(ValueError, match="NaN or Inf"):
            controller.get_action(np.array([0.0, 0.0, 0.0]))

    def test_inf_validation_in_get_action(self):
        """Test D-25: Inf in external action raises ValueError."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        inf_action = np.array([1.0, np.inf, 3.0])
        controller.inject_external_action(inf_action)
        with pytest.raises(ValueError, match="NaN or Inf"):
            controller.get_action(np.array([0.0, 0.0, 0.0]))


class TestRegressionExistingMethods:
    """Ensure existing controller methods still work after modification."""

    def test_reset_still_works(self):
        """Test 7: reset() still returns a ParameterSnapshot."""
        controller = EnvironmentController()
        result = controller.reset()
        assert result is not None
        assert hasattr(result, "physics")

    def test_step_update_still_works(self):
        """Test 7: step_update() still returns a ParameterSnapshot with mock sim."""
        from unittest.mock import MagicMock

        controller = EnvironmentController()
        controller.reset()
        mock_sim = MagicMock()
        result = controller.step_update(mock_sim)
        assert result is not None

    def test_episode_end_still_works(self):
        """Test 7: episode_end() still returns a dict with episode key."""
        from unittest.mock import MagicMock

        controller = EnvironmentController()
        controller.reset()
        mock_sim = MagicMock()
        result = controller.episode_end({"reward": 10.0}, mock_sim)
        assert isinstance(result, dict)
        assert "episode" in result

    def test_get_status_includes_mode(self):
        """get_status() includes 'mode' key."""
        controller = EnvironmentController()
        status = controller.get_status()
        assert "mode" in status
        assert status["mode"] == "sim"
        controller.set_real_robot_mode(True)
        status = controller.get_status()
        assert status["mode"] == "real_robot"
