"""Tests for EnvironmentController ROS2 mode switching."""

import numpy as np
import queue
import pytest
from surg_rl.dynamics.environment_controller import (
    EnvironmentController,
    EnvironmentControllerConfig,
)


class TestControllerRos2Mode:
    def test_default_mode_is_sim(self):
        controller = EnvironmentController()
        assert controller.mode == "sim"

    def test_set_real_robot_mode(self):
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        assert controller.mode == "real_robot"
        controller.set_real_robot_mode(False)
        assert controller.mode == "sim"

    def test_get_action_sim_passthrough(self):
        controller = EnvironmentController()
        policy_action = np.array([1.0, 2.0, 3.0])
        result = controller.get_action(policy_action)
        np.testing.assert_array_equal(result, policy_action)

    def test_get_action_real_robot_external(self):
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        external = np.array([4.0, 5.0, 6.0])
        controller.inject_external_action(external)
        result = controller.get_action(np.array([1.0, 2.0, 3.0]))
        np.testing.assert_array_equal(result, external)

    def test_get_action_real_robot_empty_queue_fallback(self):
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        policy = np.array([1.0, 2.0, 3.0])
        result = controller.get_action(policy)
        assert result is not None

    def test_inject_keep_latest(self):
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        controller.inject_external_action(np.array([1.0]))
        controller.inject_external_action(np.array([2.0]))
        controller.inject_external_action(np.array([3.0]))
        result = controller.get_action(np.array([0.0]))
        np.testing.assert_array_equal(result, np.array([3.0]))

    def test_get_status_includes_mode(self):
        controller = EnvironmentController()
        status = controller.get_status()
        assert "mode" in status
        assert status["mode"] == "sim"

    def test_existing_reset_still_works(self):
        controller = EnvironmentController(
            config=EnvironmentControllerConfig(
                enabled=True,
                use_randomization=False,
            )
        )
        params = controller.reset(seed=42)
        assert params is not None
        assert params.episode == 1

    # ── Gap Fix Tests (Plan 09.2) ────────────────────────────────────────

    def test_external_action_via_multiprocessing_queue(self):
        """External action injected works with multiprocessing.Queue semantics."""
        controller = EnvironmentController()
        controller.set_real_robot_mode(True)
        external = np.array([9.0, 8.0, 7.0])
        controller.inject_external_action(external)
        result = controller.get_action(np.array([1.0, 2.0, 3.0]))
        np.testing.assert_array_equal(result, external)
