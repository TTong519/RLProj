# Phase 9: ROS2 Bridge for Real Hardware — Research

**Researched:** 2026-05-02
**Domain:** ROS2 integration for Python surgical-robotics RL simulator
**Confidence:** MEDIUM-HIGH (well-established patterns; some version/availability details are distro-specific)

## Summary

Phase 9 bridges the `surg-rl` simulation to ROS2 for real-hardware validation. The established pattern is a **lightweight ROS2 node** (via `rclpy`) that runs alongside the simulator, publishing `JointState` messages at the simulation step frequency and subscribing to command topics that override the RL agent's actions. This is the same pattern used by `pybullet_ros`, `mujoco_menagerie`, and NVIDIA Isaac Sim's ROS2 bridge.

Key findings:
1. **`rclpy` is the standard Python client library**, but it is **not on PyPI**. It must be installed via the ROS2 apt repository (`ros-humble-rclpy` or `ros-jazzy-rclpy`). The `[ros2]` extra in `pyproject.toml` should document this and use conditional imports.
2. **macOS is unsupported** by official ROS2 distros after Foxy. The bridge code must detect macOS, emit a warning, and skip ROS2 initialization gracefully.
3. **Trajectory replay** is best implemented as a standalone `ros2 launch` node (or a CLI sub-command) that loads SB3 checkpoints, samples actions, and publishes them to the same command topic at reduced frequency.
4. **Real/sim mode switching** is a runtime flag on `SimulationController` (or a thin wrapper) that changes whether `step()` sources actions from the RL policy or from the ROS2 subscriber queue.
5. **Do NOT hand-roll message serialization** — use `sensor_msgs.msg.JointState`, `geometry_msgs.msg.Pose`, and `std_msgs.msg.Float64MultiArray` from the ROS2 message packages. These are also apt-only, but their Python bindings are auto-generated and stable.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ROS2 node lifecycle (init, spin, shutdown) | `ros2/` bridge module | — | `rclpy` owns this; we wrap it in a context manager |
| JointState publisher | `ros2/` bridge module | `simulators/` (state extraction) | Publisher lives in bridge; state comes from `BaseSimulator.get_state()` |
| Command subscriber | `ros2/` bridge module | `rl/` (action injection) | Subscriber writes to a thread-safe queue; `SurgicalEnv.step()` reads from queue when in real-robot mode |
| Trajectory replay | `ros2/` replay module | `rl/` (checkpoint loading) | Replay logic is independent of the bridge; reuses the same command topic |
| Real/sim mode switch | `dynamics/` controller | `ros2/` bridge module | `SimulationController` owns the mode flag; bridge only feeds external data |
| CLI `ros2-bridge` command | `cli.py` | `ros2/` entrypoint | Typer command delegates to `ros2_bridge_node()` |
| `[ros2]` extra / packaging | `pyproject.toml` | docs | No pip-installable `rclpy`; extra documents apt deps |

## Standard Stack

### Core
| Library / Package | Version / Source | Purpose | Why Standard |
|-------------------|------------------|---------|--------------|
| `rclpy` | `ros-humble-rclpy` or `ros-jazzy-rclpy` (apt) | ROS2 Python client library | Official, maintained by Open Robotics; no PyPI equivalent |
| `sensor_msgs` | `ros-humble-sensor-msgs` (apt) | `JointState`, `Image` message types | ROS2 standard message package; Python bindings auto-generated |
| `geometry_msgs` | `ros-humble-geometry-msgs` (apt) | `Pose`, `Twist`, `Transform` | ROS2 standard for spatial data |
| `std_msgs` | `ros-humble-std-msgs` (apt) | `Float64MultiArray`, `Header` | Base message primitives |
| `rosidl_runtime_py` | bundled with `rclpy` | Message serialization utilities | Converts between ROS2 msg objects and plain Python dicts/lists |
| `PyYAML` | `>=6.0` (PyPI) | `ros2_bridge.yaml` config parsing | Already in project deps; zero friction |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `launch_ros` | apt (`ros-humble-launch-ros`) | Launch-file support for multi-node startup | If we provide `.launch.py` files for publisher + subscriber + replay |
| `ament_index_python` | apt | Package resource lookup (e.g., finding mesh paths) | Only if we need to resolve ROS2 package paths at runtime |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `rclpy` pub/sub | `ros2_control` + `hardware_interface` | `ros2_control` is the SOTA for real robot hardware, but it adds significant complexity (URDF ros2_control tags, hardware components, controller managers). For a research simulator bridge, raw pub/sub is simpler and sufficient. |
| `sensor_msgs/JointState` | Custom `surg_rl/msg/JointState` | Custom messages require building a ROS2 package with `colcon`, which breaks the pip-install-only workflow. `sensor_msgs/JointState` is universal and already understood by RViz, MoveIt, etc. |
| apt-only `rclpy` | `roslibpy` (WebSocket bridge to rosbridge) | `roslibpy` avoids apt deps, but requires a running `rosbridge_server` (extra process). Adds latency and operational complexity. Not worth it for a local bridge. |

**Installation (documented, not automated):**
```bash
# Ubuntu 22.04 (Humble) or 24.04 (Jazzy)
sudo apt update && sudo apt install -y ros-humble-rclpy ros-humble-sensor-msgs ros-humble-geometry-msgs ros-humble-std-msgs
source /opt/ros/humble/setup.bash

# Then install the Python extra (which currently only documents deps)
pip install "surg-rl[ros2]"
```

**Version verification:**
- ROS2 Humble Hawksbill: LTS until May 2027; supports Ubuntu 22.04; Python 3.10.
- ROS2 Jazzy Jalisco: LTS until May 2029; supports Ubuntu 24.04; Python 3.12.
- `rclpy` API is **stable** across Humble → Jazzy; minor breaking changes in `Node` constructor arguments are unlikely.

## Architecture Patterns

### Pattern 1: Bridge Node (Publisher + Subscriber)

```
+-------------------+     +-------------------+     +-------------------+
|   SurgicalEnv     |     |   Ros2BridgeNode  |     |   External ROS2   |
|   (Gymnasium)     |<--->|   (rclpy.Node)    |<--->|   Nodes (RViz,    |
|                   |     |                   |     |   real robot,     |
|  step()           |     |  publisher:       |     |   MoveIt, etc.)   |
|  get_state()      |     |    /surg_rl/joint_states              |
|  render()         |     |  subscriber:      |     |                   |
|                   |     |    /surg_rl/commands                  |
+-------------------+     +-------------------+     +-------------------+
         ^
         | (when mode == "sim")
+-------------------+
|   RL Policy       |
|   (SB3 / RLlib)   |
+-------------------+
```

- `Ros2BridgeNode` inherits from `rclpy.node.Node`.
- Publisher sends `sensor_msgs.msg.JointState` at the simulation frequency (typically 30–240 Hz).
- Subscriber receives `sensor_msgs.msg.JointState` (or `std_msgs.msg.Float64MultiArray`) and writes actions to a `threading.Queue`.
- `SurgicalEnv.step()` checks `controller.mode`. If `real_robot`, it pops from the queue instead of taking the RL policy's action.

### Pattern 2: Trajectory Replay Node

```
+-------------------+     +-------------------+     +-------------------+
|  CheckpointLoader |     |  TrajectoryReplay |     |  Ros2BridgeNode  |
|  (SB3 zip)        |---->|  (rclpy.Node)     |---->|  (subscriber      |
|                   |     |                   |     |   forwards to    |
|  model.predict()  |     |  throttled @ 10%  |     |   SimulationController)
|                   |     |  (sleep 10x step) |     |                   |
+-------------------+     +-------------------+     +-------------------+
```

- Replay is a **separate node** so it can run independently of the bridge.
- It loads the SB3 model, enters a loop: `action, _ = model.predict(obs)`, publish to `/surg_rl/commands`, sleep.
- Throttling is achieved by a simple `time.sleep(9 * dt)` after each step (10% speed = 10x wall-clock time per step).

### Pattern 3: Real/Sim Mode Switch

```python
class SimulationController:
    def __init__(self, ...):
        self.mode: Literal["sim", "real_robot"] = "sim"
        self._external_action_queue: queue.Queue = queue.Queue(maxsize=1)

    def set_real_robot_mode(self, enabled: bool) -> None:
        self.mode = "real_robot" if enabled else "sim"

    def get_action(self, policy_action: np.ndarray) -> np.ndarray:
        if self.mode == "real_robot":
            try:
                return self._external_action_queue.get_nowait()
            except queue.Empty:
                # Hold last action or zero; configurable
                return self._last_action
        return policy_action
```

- The mode switch is **non-destructive** — the simulation keeps running, but the action source changes.
- `Ros2BridgeNode` writes to `_external_action_queue` in its subscriber callback.
- `SurgicalEnv.step(action)` calls `controller.get_action(action)` before passing to the simulator.

## Don't Hand-Roll

- **Message definitions:** Always use `sensor_msgs.msg.JointState`, `geometry_msgs.msg.PoseStamped`, etc. Never define custom message classes by hand.
- **DDS discovery / QoS:** Let `rclpy` handle QoS profiles. Use `qos_profile_sensor_data` for high-frequency topics, `qos_profile_default` for commands.
- **Node lifecycle:** Use `rclpy.init()`, `node = Ros2BridgeNode()`, `rclpy.spin(node)` in a dedicated thread. Never implement a custom event loop.
- **Time stamps:** Use `node.get_clock().now().to_msg()` for `std_msgs.msg.Header.stamp`. Do not use `time.time()`.
- **JSON/YAML config parsing:** Use `yaml.safe_load()` (already in project) for bridge config files. Do not write a custom parser.

## Common Pitfalls

| Pitfall | Symptom | Mitigation |
|---------|---------|------------|
| `rclpy.spin()` blocks the training loop | Training hangs at first `step()` | Run `rclpy.spin(node)` in a **daemon thread**; main thread stays free for RL. Use `executor = MultiThreadedExecutor()` if callbacks need concurrency. |
| GIL contention between spin thread and main thread | High CPU, jerky simulation | Keep callback work minimal (just `queue.put`). Heavy work (state serialization) stays in main thread. |
| Message type mismatch | Subscriber callback never fires; `ros2 topic echo` shows data but node doesn't | Use `ros2 topic info /topic` to verify type. Ensure publisher and subscriber use **exactly** the same message class. |
| `rclpy` not initialized before node creation | `RuntimeError: rclpy.init() must be called before rclpy.create_node()` | Always call `rclpy.init()` in the bridge constructor or a context manager. |
| Forgetting to `destroy_node()` + `rclpy.shutdown()` | Zombie ROS2 nodes visible in `ros2 node list` after process exit | Use `try/finally` or context manager. Register `atexit` handler as backup. |
| macOS users try to `pip install rclpy` | `pip` fails with "No matching distribution" | Detect platform at import time: `if sys.platform == "darwin": warnings.warn("ROS2 not supported on macOS...")`. Skip ROS2 init. |
| apt-only deps break `pip install "surg-rl[ros2]"` | `pyproject.toml` optional-extra fails because packages aren't on PyPI | The `[ros2]` extra should contain **only PyPI-installable** packages (e.g., `PyYAML`). Document apt deps separately in README. Do NOT list `rclpy` in `extras_require`. |
| Queue overflow at high sim frequency | Subscriber callback blocks; DDS drops messages | Use `queue.Queue(maxsize=1)` and overwrite (keep-latest semantics for commands). For state publishing, use a non-blocking `publish()` — it's okay to drop old states. |
| Frame ID mismatch | RViz shows robot in wrong place or not at all | Always set `header.frame_id = "world"` (or the simulator's world frame name) in published messages. |

## Code Examples

### Minimal Bridge Node

```python
import threading
import queue
from typing import Optional

import numpy as np

# Lazy import — ROS2 is optional
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Float64MultiArray
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    Node = object  # type: ignore


class Ros2BridgeNode(Node):
    """ROS2 node that publishes sim state and receives commands."""

    def __init__(
        self,
        joint_names: list[str],
        publisher_topic: str = "/surg_rl/joint_states",
        command_topic: str = "/surg_rl/commands",
    ):
        super().__init__("surg_rl_bridge")
        self._joint_names = joint_names
        self._command_queue: queue.Queue = queue.Queue(maxsize=1)

        self._pub = self.create_publisher(JointState, publisher_topic, 10)
        self._sub = self.create_subscription(
            Float64MultiArray,
            command_topic,
            self._on_command,
            10,
        )

    def _on_command(self, msg: Float64MultiArray) -> None:
        # Keep-latest semantics: overwrite old command
        if self._command_queue.full():
            try:
                self._command_queue.get_nowait()
            except queue.Empty:
                pass
        self._command_queue.put_nowait(np.array(msg.data, dtype=np.float64))

    def publish_state(self, qpos: np.ndarray, qvel: np.ndarray) -> None:
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "world"
        msg.name = self._joint_names
        msg.position = qpos.tolist()
        msg.velocity = qvel.tolist()
        self._pub.publish(msg)

    def get_latest_command(self) -> Optional[np.ndarray]:
        try:
            return self._command_queue.get_nowait()
        except queue.Empty:
            return None


class Ros2Bridge:
    """Context manager for bridge lifecycle."""

    def __init__(self, node: Ros2BridgeNode):
        if not HAS_ROS2:
            raise RuntimeError("ROS2 is not installed. Install rclpy via apt.")
        self._node = node
        self._spin_thread: Optional[threading.Thread] = None

    def __enter__(self):
        rclpy.init()
        executor = rclpy.executors.MultiThreadedExecutor()
        executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=executor.spin, daemon=True)
        self._spin_thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._node.destroy_node()
        rclpy.shutdown()
        return False
```

### Mode Switch in SurgicalEnv

```python
# In SurgicalEnv.step()
def step(self, action):
    if self._bridge is not None and self._controller.mode == "real_robot":
        external = self._bridge.node.get_latest_command()
        if external is not None:
            action = external
    # ... continue with normal step logic
```

### Trajectory Replay Node

```python
class TrajectoryReplayNode(Node):
    def __init__(self, model_path: str, scene_path: str, speed: float = 0.1):
        super().__init__("trajectory_replay")
        self._pub = self.create_publisher(Float64MultiArray, "/surg_rl/commands", 10)
        # Load SB3 model (lazy import stable_baselines3)
        from stable_baselines3 import PPO
        self._model = PPO.load(model_path)
        self._env = make_surgical_env({"scene_path": scene_path})
        self._speed = speed
        self._timer = self.create_timer(1.0 / (self._env.metadata.get("render_fps", 30) / self._speed), self._tick)

    def _tick(self):
        obs = self._env._get_obs()  # or proper reset if needed
        action, _ = self._model.predict(obs, deterministic=True)
        msg = Float64MultiArray()
        msg.data = action.tolist()
        self._pub.publish(msg)
```

## Alternatives Considered

1. **`ros2_control` instead of raw pub/sub:**
   - **Pros:** Standard for real robots; hardware_interface abstraction; works with MoveIt.
   - **Cons:** Requires URDF `ros2_control` tags, controller manager, and `hardware_interface::SystemInterface` implementation in C++ or Python. Far too heavy for a research simulator bridge.
   - **Verdict:** Document `ros2_control` as a future integration path, but implement raw pub/sub for Phase 9.

2. **WebSocket bridge (`roslibpy`) instead of native `rclpy`:**
   - **Pros:** `roslibpy` is on PyPI; no apt deps; works on any platform with a browser.
   - **Cons:** Requires `rosbridge_server` (extra ROS2 node); adds 10–50 ms latency per message; not suitable for real-time joint control at >30 Hz.
   - **Verdict:** Rejected. Native `rclpy` is the right choice for a local machine bridge.

3. **Custom pip-installable message packages:**
   - Some projects (e.g., `px4_msgs`, `arduplane_msgs`) publish generated message Python bindings to PyPI.
   - **Pros:** `pip install "surg-rl[ros2]"` would actually work without apt.
   - **Cons:** Maintaining generated message packages is a full-time job; they drift with ROS2 distro releases; users still need `rclpy` from apt anyway.
   - **Verdict:** Rejected. Document apt deps clearly instead.

4. **Docker-based bridge for macOS:**
   - Run the ROS2 node inside a Linux container with host-network mode.
   - **Pros:** macOS users can participate.
   - **Cons:** Host networking does not work on macOS Docker Desktop (Linux-only feature); DDS discovery across containers is painful.
   - **Verdict:** Document as a known limitation. macOS users can use the simulator without ROS2, or run the bridge on a remote Linux machine.

## Recommendation

**Use Pattern 1 (Bridge Node) with daemon-thread `rclpy.spin()`, `sensor_msgs/JointState` for state, and `std_msgs/Float64MultiArray` for commands.** This is the minimal viable ROS2 bridge that satisfies all 6 requirements without architectural over-engineering.

---
*Research complete. Ready for `/gsd-plan-phase 9`.*
