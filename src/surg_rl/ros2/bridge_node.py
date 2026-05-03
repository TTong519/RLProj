"""ROS2 bridge node — publishes joint states and subscribes to commands.

Provides Ros2BridgeNode which bridges the surg-rl simulation to ROS2 DDS.
On platforms without rclpy (macOS, missing deps), defines a dummy class
with no-op methods and warning logs.

Architecture:
    - Publisher: sensor_msgs/JointState at sim step frequency.
    - Subscriber: std_msgs/Float64MultiArray with keep-latest queue (maxsize=1).
    - Error validation: NaN/Inf detection, dimension mismatch handling.
"""

import multiprocessing
import queue
import sys
from typing import Optional

import numpy as np

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# ── Detect ROS2 availability (mirrors __init__.py guard) ──────────────
# We duplicate the check here to avoid a circular import with
# surg_rl.ros2.__init__ which imports Ros2BridgeNode from this module.

if sys.platform == "darwin":
    _HAS_ROS2 = False
else:
    try:
        import rclpy  # noqa: F401
        from rclpy.node import Node  # noqa: F401
        from sensor_msgs.msg import JointState  # noqa: F401
        from std_msgs.msg import Float64MultiArray  # noqa: F401

        _HAS_ROS2 = True
    except ImportError:
        _HAS_ROS2 = False

# ── Dummy implementation (no rclpy available) ─────────────────────────

if not _HAS_ROS2:
    class Ros2BridgeNode:
        """Dummy bridge node — ROS2 is not available on this platform.

        All methods are no-ops that log warnings and return safe defaults.
        This class exists so imports never crash, even on macOS or systems
        without ROS2 installed.
        """

        def __init__(
            self,
            joint_names: Optional[list[str]] = None,
            publisher_topic: str = "/surg_rl/joint_states",
            command_topic: str = "/surg_rl/commands",
            command_queue: "multiprocessing.Queue | None" = None,
            frame_id: str = "world",
            qos_profile: str = "sensor_data",
            on_nan_inf: str = "raise",
            on_dimension_mismatch: str = "zero",
        ):
            self._joint_names = joint_names or []
            self._publisher_topic = publisher_topic
            self._command_topic = command_topic
            self._frame_id = frame_id
            self._qos_profile = qos_profile
            self._on_nan_inf = on_nan_inf
            self._on_dimension_mismatch = on_dimension_mismatch
            self._command_queue = command_queue or multiprocessing.Queue(maxsize=1)
            logger.debug(
                "Dummy Ros2BridgeNode created (ROS2 not available). "
                "Publisher: %s, Subscriber: %s",
                publisher_topic,
                command_topic,
            )

        def setup_joint_names(self, joint_names: list[str]) -> None:
            """Update the list of joint names (no-op in dummy mode)."""
            self._joint_names = joint_names
            logger.debug(
                "Dummy node: joint_names updated to %s (ROS2 not active)",
                joint_names,
            )

        def publish_state(
            self,
            qpos: np.ndarray,
            qvel: np.ndarray,
            joint_names: Optional[list[str]] = None,
        ) -> None:
            """Publish joint state (no-op in dummy mode)."""
            logger.debug(
                "Dummy node: publish_state called with shapes "
                "qpos=%s, qvel=%s (ROS2 not active)",
                qpos.shape,
                qvel.shape,
            )

        def get_latest_command(self) -> Optional[np.ndarray]:
            """Return latest command from the queue (works even in dummy mode).

            The command queue uses only Python's queue module, which is always
            available regardless of rclpy. This method functions identically
            in both dummy and real mode.
            """
            try:
                return self._command_queue.get_nowait()
            except queue.Empty:
                return None

        def _on_command(self, msg) -> None:
            """Subscriber callback (no-op in dummy mode)."""
            pass

        def __repr__(self) -> str:
            return (
                f"Ros2BridgeNode(Dummy)("
                f"pub={self._publisher_topic}, "
                f"sub={self._command_topic})"
            )

# ── Real implementation (rclpy available) ─────────────────────────────

else:
    import rclpy  # noqa: F811
    from rclpy.node import Node  # noqa: F811
    from sensor_msgs.msg import JointState  # noqa: F811
    from std_msgs.msg import Float64MultiArray  # noqa: F811

    class Ros2BridgeNode(Node):
        """ROS2 node bridging simulation to ROS2 DDS.

        Publishes sensor_msgs/JointState at simulation step frequency
        and subscribes to std_msgs/Float64MultiArray for external commands.

        Thread safety:
            - publish_state() is called from the main (sim) thread.
            - _on_command() runs in the rclpy spin thread.
            - _command_queue is a thread-safe queue.Queue with maxsize=1.

        Error handling (threat model mitigations):
            - T-09-01: Command dimension mismatch → zero action (D-23).
            - T-09-02: NaN/Inf validation in publish_state (D-25).
            - T-09-04: queue.Queue(maxsize=1) keep-latest (DoS protection).

        Example:
            >>> node = Ros2BridgeNode(
            ...     joint_names=["joint1", "joint2"],
            ...     publisher_topic="/surg_rl/joint_states",
            ...     command_topic="/surg_rl/commands",
            ... )
            >>> node.publish_state(
            ...     qpos=np.array([0.1, 0.2]),
            ...     qvel=np.array([0.0, 0.0]),
            ... )
            >>> cmd = node.get_latest_command()
        """

        def __init__(
            self,
            joint_names: list[str],
            publisher_topic: str = "/surg_rl/joint_states",
            command_topic: str = "/surg_rl/commands",
            command_queue: "multiprocessing.Queue | None" = None,
            frame_id: str = "world",
            qos_profile: str = "sensor_data",
            on_nan_inf: str = "raise",
            on_dimension_mismatch: str = "zero",
        ):
            super().__init__("surg_rl_bridge")
            self._joint_names = list(joint_names)
            self._publisher_topic = publisher_topic
            self._command_topic = command_topic
            self._frame_id = frame_id
            self._qos_profile = qos_profile
            self._on_nan_inf = on_nan_inf
            self._on_dimension_mismatch = on_dimension_mismatch
            self._command_queue = command_queue or multiprocessing.Queue(maxsize=1)

            from rclpy.qos import qos_profile_sensor_data

            qos = qos_profile_sensor_data if self._qos_profile == "sensor_data" else 10
            self._pub = self.create_publisher(
                JointState, publisher_topic, qos
            )
            self._sub = self.create_subscription(
                Float64MultiArray,
                command_topic,
                self._on_command,
                10,
            )

            logger.info(
                "Ros2BridgeNode created. Publisher: %s, Subscriber: %s, "
                "Joints: %s",
                publisher_topic,
                command_topic,
                joint_names,
            )

        # ── Public API ────────────────────────────────────────────────

        def setup_joint_names(self, joint_names: list[str]) -> None:
            """Update the list of joint names.

            Args:
                joint_names: New list of joint names.
            """
            self._joint_names = list(joint_names)
            logger.debug("Joint names updated to %s", joint_names)

        def publish_state(
            self,
            qpos: np.ndarray,
            qvel: np.ndarray,
            joint_names: Optional[list[str]] = None,
        ) -> None:
            """Publish a JointState message on the configured topic.

            Per D-25: validates no NaN/Inf in qpos/qvel before publishing.
            Raises ValueError if non-finite values detected.

            Per RESEARCH.md: uses node.get_clock().now().to_msg() for
            timestamps (not time.time()).

            Args:
                qpos: Joint position array (shape: [n_joints]).
                qvel: Joint velocity array (shape: [n_joints]).
                joint_names: Optional override for message joint names.

            Raises:
                ValueError: If qpos or qvel contains NaN or Inf values.
            """
            # Validate no NaN/Inf (T-09-02 mitigation)
            if not np.all(np.isfinite(qpos)) or not np.all(np.isfinite(qvel)):
                if self._on_nan_inf == "raise":
                    raise ValueError(
                        f"NaN/Inf in state data: qpos min={np.min(qpos)}, "
                        f"max={np.max(qpos)}, qvel min={np.min(qvel)}, "
                        f"max={np.max(qvel)}"
                    )
                elif self._on_nan_inf == "sanitize":
                    qpos = np.nan_to_num(qpos, nan=0.0, posinf=1e6, neginf=-1e6)
                    qvel = np.nan_to_num(qvel, nan=0.0, posinf=1e6, neginf=-1e6)

            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self._frame_id
            msg.name = joint_names if joint_names else self._joint_names
            msg.position = qpos.tolist()
            msg.velocity = qvel.tolist()
            self._pub.publish(msg)

        def get_latest_command(self) -> Optional[np.ndarray]:
            """Return the latest command from the subscriber queue.

            Non-blocking: returns None immediately if no command available.

            Returns:
                np.ndarray of action values, or None if queue is empty.
            """
            try:
                return self._command_queue.get_nowait()
            except queue.Empty:
                return None

        # ── Internal ──────────────────────────────────────────────────

        def _on_command(self, msg: Float64MultiArray) -> None:
            """Subscriber callback for incoming commands.

            Per D-23 (dimension mismatch): if message dimension doesn't
            match len(self._joint_names), apply zero action.

            Per D-02 (keep-latest): uses queue.Queue(maxsize=1) —
            if queue is full, discard the old command and overwrite.

            Per T-09-01 (threat mitigation): validates dimension at entry.

            Args:
                msg: Incoming Float64MultiArray message.
            """
            # Convert to numpy array
            data = np.array(msg.data, dtype=np.float64)

            # Dimension mismatch → configurable behavior (D-23, T-09-01)
            if len(data) != len(self._joint_names):
                if self._on_dimension_mismatch == "zero":
                    logger.warning(
                        "Command dimension mismatch: got %d values, "
                        "expected %d joints. Applying zero action.",
                        len(data),
                        len(self._joint_names),
                    )
                    data = np.zeros(len(self._joint_names), dtype=np.float64)
                elif self._on_dimension_mismatch == "warn":
                    logger.warning(
                        "Command dimension mismatch: got %d values, "
                        "expected %d joints. Passing through as-is.",
                        len(data),
                        len(self._joint_names),
                    )

            # Keep-latest semantics: overwrite old command (D-02, T-09-04)
            if self._command_queue.full():
                try:
                    self._command_queue.get_nowait()
                except queue.Empty:
                    pass
            self._command_queue.put_nowait(data)

        def __repr__(self) -> str:
            return (
                f"Ros2BridgeNode("
                f"pub={self._publisher_topic}, "
                f"sub={self._command_topic})"
            )
