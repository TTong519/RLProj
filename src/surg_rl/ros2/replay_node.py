"""ROS2 replay node — standalone ros node for trajectory replay.

Provides a standalone ROS2 node entry point that loads an SB3 checkpoint,
runs a predict loop, and publishes actions to a ROS2 command topic.
Used by ``launch/replay.launch.py`` as executable ``replay_node``.
"""

from __future__ import annotations

import sys

if sys.platform == "darwin":
    _HAS_ROS2 = False
else:
    try:
        import rclpy  # noqa: F401
        from rclpy.node import Node  # noqa: F401
        from std_msgs.msg import Float64MultiArray  # noqa: F401

        _HAS_ROS2 = True
    except ImportError:
        _HAS_ROS2 = False

if not _HAS_ROS2:

    class DummyReplayNode:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError(
                "ROS2 is not available. Install rclpy via apt: "
                "sudo apt install ros-humble-rclpy ros-humble-std-msgs"
            )

    def main() -> None:
        raise RuntimeError(
            "ROS2 is not available. Install rclpy via apt: "
            "sudo apt install ros-humble-rclpy ros-humble-std-msgs"
        )

else:
    from typing import Any

    import rclpy  # type: ignore[import-not-found]  # noqa: F811
    from rclpy.node import Node  # type: ignore[import-not-found]  # noqa: F811
    from std_msgs.msg import Float64MultiArray  # type: ignore[import-not-found]  # noqa: F811

    _node: Node | None = None
    _pub: Any = None

    def main() -> None:
        """Entry point for ros2 launch — loads model and starts replay predict loop.

        Expects params: model_path, control_freq, use_sim_time
        (declared in launch/replay.launch.py).
        """
        global _node, _pub

        rclpy.init()
        _node = Node("surg_rl_replay")
        _pub = _node.create_publisher(Float64MultiArray, "/surg_rl/commands", 10)

        from surg_rl.ros2.replay import TrajectoryReplay

        replay = TrajectoryReplay(
            model_path="/app/checkpoints/model.zip",
            scene_path="/etc/surg-rl/scene.json",
            speed=0.1,
        )
        try:
            replay.run_replay(max_steps=10000)
        except KeyboardInterrupt:
            pass
        finally:
            replay.terminate()
            _node.destroy_node()
            rclpy.shutdown()
