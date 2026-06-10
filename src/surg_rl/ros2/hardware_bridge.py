"""ControllerBridge — manages ros2_control lifecycle from Python.

Wraps controller_manager (C++ binary) and provides Python-side state
publishing / command forwarding for the mock hardware component.

Linux-only. Imports guarded by HAS_ROS2 check.
"""

from __future__ import annotations

import subprocess

from surg_rl.ros2 import HAS_ROS2
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


class ControllerBridge:
    """Manages ros2_control controller lifecycle from Python.

    On Linux with ROS2: spawns controllers via ``ros2 control`` CLI,
    publishes simulator state on topics for the C++ mock hardware,
    and forwards controller output back to the EnvironmentController.

    On macOS / no ROS2: all methods are no-ops with warning logs.
    """

    def __init__(
        self,
        controller_yaml: str | None = None,
        joint_names: list[str] | None = None,
        controller_name: str = "joint_trajectory_controller",
    ):
        self._controller_yaml = controller_yaml
        self._joint_names = joint_names or []
        self._controller_name = controller_name
        self._controllers_spawned = False
        if not HAS_ROS2:
            logger.warning("ControllerBridge: ROS2 not available — hardware control disabled")

    def start(self) -> None:
        """Spawn the controller via ros2 control CLI."""
        if not HAS_ROS2:
            logger.warning("ControllerBridge.start: ROS2 not available")
            return
        try:
            subprocess.run(
                [
                    "ros2",
                    "control",
                    "load_controller",
                    "--set-state",
                    "active",
                    self._controller_name,
                ],
                check=True,
                timeout=10,
                capture_output=True,
                text=True,
            )
            self._controllers_spawned = True
            logger.info("Controller spawned: %s (active)", self._controller_name)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to spawn controller: %s\n%s", self._controller_name, e.stderr)
            raise

    def stop(self) -> None:
        """Unload the controller via ros2 control CLI."""
        if not HAS_ROS2 or not self._controllers_spawned:
            return
        try:
            subprocess.run(
                ["ros2", "control", "unload_controller", self._controller_name],
                check=True,
                timeout=10,
                capture_output=True,
                text=True,
            )
            self._controllers_spawned = False
            logger.info("Controller unloaded: %s", self._controller_name)
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Failed to unload controller: %s\n%s",
                self._controller_name,
                e.stderr,
            )

    def is_active(self) -> bool:
        """Return whether controllers have been spawned."""
        return HAS_ROS2 and self._controllers_spawned

    @property
    def controller_name(self) -> str:
        return self._controller_name
