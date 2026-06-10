"""Tests for ros2_control ControllerBridge and URDF tag injection."""

from __future__ import annotations

import sys

from surg_rl.ros2.hardware_bridge import ControllerBridge


class TestControllerBridge:
    """R2CTL-01, R2CTL-03: Controller lifecycle management."""

    def test_create_controller_bridge(self):
        cb = ControllerBridge(joint_names=["j1", "j2"])
        assert not cb.is_active()
        assert cb.controller_name == "joint_trajectory_controller"

    def test_controller_bridge_macos_noop(self):
        cb = ControllerBridge()
        if sys.platform == "darwin":
            cb.start()
            assert not cb.is_active()
            cb.stop()
            assert not cb.is_active()

    def test_controller_bridge_stop_before_start(self):
        cb = ControllerBridge()
        cb.stop()
        assert not cb.is_active()

    def test_controller_bridge_custom_name(self):
        cb = ControllerBridge(controller_name="position_controllers")
        assert cb.controller_name == "position_controllers"


class TestURDFTagInjection:
    """R2CTL-02: ros2_control XML tag injection in URDF."""

    def test_inject_ros2_control_tags(self):
        from surg_rl.simulators.scene_builder import SceneBuilder

        urdf = '<robot name="test"><joint name="j1" type="revolute"/></robot>'
        result = SceneBuilder._inject_ros2_control_tags(urdf, ["j1"])
        assert "ros2_control" in result
        assert "mock_components/GenericSystem" in result
        assert "command_interface" in result
        assert "state_interface" in result
        assert 'name="position"' in result
        assert 'name="velocity"' in result

    def test_inject_multiple_joints(self):
        from surg_rl.simulators.scene_builder import SceneBuilder

        urdf = '<robot name="test"><joint name="j1"/><joint name="j2"/></robot>'
        result = SceneBuilder._inject_ros2_control_tags(urdf, ["j1", "j2"])
        assert result.count("state_interface") == 4


class TestCLIIntegration:
    """R2CTL-04: CLI ros2-control command."""

    def test_cli_help_includes_ros2_control(self):
        import subprocess

        r = subprocess.run(
            [sys.executable, "-m", "surg_rl.cli", "ros2-control", "--help"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": "src"},
        )
        assert r.returncode == 0
        assert "ros2-control" in r.stdout or "Usage" in r.stdout
