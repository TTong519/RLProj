"""Trajectory replay — loads SB3 checkpoints and publishes actions to ROS2.

Provides TrajectoryReplay — a self-contained replay tool that loads a trained
SB3 model checkpoint, creates its own SurgicalEnv, runs a predict loop, and
publishes actions to a ROS2 command topic at configurable reduced speed.

Independent of the main bridge process per Phase 9 decision D-08.
"""

import sys

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# ── Detect ROS2 availability (mirrors __init__.py guard) ──────────────
# We duplicate the check here to avoid a circular import with
# surg_rl.ros2.__init__ which imports TrajectoryReplay from this module.

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

# ── Dummy implementation (no rclpy available) ─────────────────────────

if not _HAS_ROS2:

    class TrajectoryReplay:
        """Dummy trajectory replay — ROS2 is not available on this platform.

        On macOS or systems without ROS2, constructing this class raises
        RuntimeError with clear installation instructions.
        """

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "ROS2 is not available. Install rclpy via apt: "
                "sudo apt install ros-humble-rclpy ros-humble-std-msgs"
            )

        def run_replay(self, max_steps: int = 1000) -> dict:
            """Replay trajectory (no-op in dummy mode)."""
            raise RuntimeError(
                "ROS2 is not available. Install rclpy via apt: "
                "sudo apt install ros-humble-rclpy ros-humble-std-msgs"
            )

        def terminate(self) -> None:
            """Clean shutdown (no-op in dummy mode)."""
            raise RuntimeError(
                "ROS2 is not available. Install rclpy via apt: "
                "sudo apt install ros-humble-rclpy ros-humble-std-msgs"
            )


# ── Real implementation (rclpy available) ─────────────────────────────

else:
    import rclpy  # noqa: F811
    from std_msgs.msg import Float64MultiArray  # noqa: F811

    class TrajectoryReplay:
        """Self-contained SB3 trajectory replay publishing to a ROS2 command topic.

        Loads a trained SB3 checkpoint via PPO.load(), creates its own
        SurgicalEnv, and runs a predict loop that publishes predicted
        actions to the configured ROS2 command topic.

        Per D-07: dedicated, self-contained — no IPC with the bridge.
        Per D-08: loads SB3 checkpoint, runs predict loop.
        Per D-09: sleep-based speed throttling via sleep((1.0/speed - 1.0) * dt).

        Speed throttling:
            - speed=1.0 → no sleep (full speed)
            - speed=0.1 → sleep 9*dt between steps (10% speed)
            - speed=0.01 → sleep 99*dt between steps (1% speed)

        Example:
            >>> replay = TrajectoryReplay(
            ...     model_path="models/ppo_suturing.zip",
            ...     scene_path="scenes/suturing_demo.json",
            ...     speed=0.1,
            ... )
            >>> stats = replay.run_replay(max_steps=500)
            >>> replay.terminate()
        """

        def __init__(
            self,
            model_path: str,
            scene_path: str,
            command_topic: str = "/surg_rl/commands",
            speed: float = 0.1,
            simulator_type: str = "mujoco",
            max_episode_steps: int = 1000,
            deterministic: bool = True,
        ):
            """Initialize trajectory replay.

            Args:
                model_path: Path to SB3 zip checkpoint.
                scene_path: Path to scene JSON/YAML definition.
                command_topic: ROS2 topic to publish actions to.
                speed: Replay speed multiplier (0.01 = 1%, 0.1 = 10%, 1.0 = full).
                simulator_type: "mujoco" or "pybullet".
                max_episode_steps: Max steps per episode.
                deterministic: Use deterministic actions (True) or stochastic (False).

            Raises:
                ValueError: If speed is not in (0.0, 1.0].
            """
            if speed <= 0 or speed > 1.0:
                raise ValueError(f"Speed must be in (0.0, 1.0], got {speed}")

            rclpy.init()
            self._node = rclpy.create_node("trajectory_replay")
            self._pub = self._node.create_publisher(Float64MultiArray, command_topic, 10)

            # Load model per D-08
            from stable_baselines3 import PPO

            self._model = PPO.load(model_path)
            from surg_rl.rl.environment import make_env

            self._env = make_env(
                scene_path=scene_path,
                simulator_type=simulator_type,
                max_episode_steps=max_episode_steps,
            )
            self._speed = speed
            self._deterministic = deterministic
            self._dt = self._env.config.timestep * self._env.config.frame_skip
            self._obs, _ = self._env.reset()
            self._step_count = 0

            logger.info(
                "TrajectoryReplay created: model=%s, scene=%s, " "speed=%.2f, dt=%.4f, topic=%s",
                model_path,
                scene_path,
                speed,
                self._dt,
                command_topic,
            )

        def run_replay(self, max_steps: int = 1000) -> dict:
            """Run replay loop for max_steps.

            Each step: predict action from SB3 model → publish to ROS2
            command topic → step the environment → apply speed throttle.

            Args:
                max_steps: Maximum number of steps to run.

            Returns:
                Dict with: steps_executed, total_wall_time, avg_step_time.
            """
            import time as time_mod

            start_time = time_mod.perf_counter()
            steps = 0
            terminated = False
            truncated = False

            for _ in range(max_steps):
                # Predict action per D-08
                action, _ = self._model.predict(self._obs, deterministic=self._deterministic)

                # Publish to ROS2 command topic
                msg = Float64MultiArray()
                msg.data = action.tolist()
                self._pub.publish(msg)

                # Step environment
                self._obs, reward, terminated, truncated, info = self._env.step(action)
                self._step_count += 1
                steps += 1

                if terminated or truncated:
                    self._obs, _ = self._env.reset()

                # Speed throttling per D-09
                if self._speed < 1.0:
                    throttle_time = (1.0 / self._speed - 1.0) * self._dt
                    time_mod.sleep(throttle_time)

            elapsed = time_mod.perf_counter() - start_time
            result = {
                "steps_executed": steps,
                "total_wall_time": elapsed,
                "avg_step_time": elapsed / steps if steps > 0 else 0,
            }
            logger.info(
                "Replay complete: %d steps in %.2fs (avg %.4fs/step)",
                steps,
                elapsed,
                result["avg_step_time"],
            )
            return result

        def terminate(self) -> None:
            """Clean shutdown: close env, destroy node, shutdown rclpy.

            Must be called after run_replay() completes to free resources
            and avoid dangling ROS2 nodes.
            """
            self._env.close()
            self._node.destroy_node()
            rclpy.shutdown()
            logger.info("TrajectoryReplay terminated.")
