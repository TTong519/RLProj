"""ROS2 bridge package for surg-rl.

Provides a bridge between the surg-rl simulation and ROS2 for real-hardware
validation. ROS2 dependencies (rclpy, sensor_msgs, std_msgs) are optional —
the package degrades gracefully on platforms without them.

Exports:
    HAS_ROS2: bool indicating whether rclpy is available.
    Ros2BridgeConfig: Pydantic v2 dataclass for bridge configuration.
    Ros2BridgeNode: Bridge node for state publishing / command subscribing.
    TrajectoryReplay: Self-contained SB3 checkpoint replay to ROS2.
"""

import logging
import sys

logger = logging.getLogger(__name__)

# ── HAS_ROS2 flag ──────────────────────────────────────────────────────
# Import guard: attempt to import rclpy (Linux-only, apt-installed).
# On macOS or missing deps, degrade gracefully with a warning.

if sys.platform == "darwin":
    HAS_ROS2 = False
    logger.warning(
        "ROS2 not supported on macOS. Use a Docker Linux container. "
        "Bridge features disabled."
    )
else:
    try:
        import rclpy  # noqa: F401
        from rclpy.node import Node  # noqa: F401
        from sensor_msgs.msg import JointState  # noqa: F401
        from std_msgs.msg import Float64MultiArray  # noqa: F401

        HAS_ROS2 = True
    except ImportError:
        HAS_ROS2 = False
        logger.warning(
            "ROS2 not available — rclpy must be installed via apt. "
            "Bridge features disabled."
        )

# ── Public API ─────────────────────────────────────────────────────────
from surg_rl.ros2.config import Ros2BridgeConfig  # noqa: E402, F401
from surg_rl.ros2.bridge_node import Ros2BridgeNode  # noqa: E402, F401
from surg_rl.ros2.replay import TrajectoryReplay  # noqa: E402, F401

__all__ = [
    "HAS_ROS2",
    "Ros2BridgeConfig",
    "Ros2BridgeNode",
    "TrajectoryReplay",
]
