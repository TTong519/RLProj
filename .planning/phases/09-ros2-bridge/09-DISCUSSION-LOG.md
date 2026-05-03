# Phase 9: ROS2 Bridge - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 09-ros2-bridge
**Areas discussed:** Bridge topology, Topic naming & message types, Trajectory replay architecture, Real/sim mode switch location, macOS handling, Backend priority, Publishing frequency & batching, Config file schema & location, Error handling & action validation

---

## Bridge Topology

| Option | Description | Selected |
|--------|-------------|----------|
| Thread inside SurgicalEnv | Ros2BridgeNode inside env, context manager | |
| Separate process | Bridge runs as standalone multiprocessing Process | ✓ |
| CLI-only external node | Bridge is CLI concern only, connects via RPC | |

**User's choice:** Separate process
**Notes:** multiprocessing Queue/Pipe for IPC; SurgicalEnv owns bridge process lifecycle (spawn in __init__, terminate in close())

---

## Topic Naming & Message Types

| Option | Description | Selected |
|--------|-------------|----------|
| sensor_msgs/JointState | Full JointState for commands | |
| std_msgs/Float64MultiArray | Raw action values, compact | |
| Custom message | surg_rl_msgs, needs colcon | |
| Mixed: JointState + Float64Array | JointState for state, Float64Array for commands | ✓ |

**User's choice:** Mixed — JointState state publisher + Float64MultiArray command subscriber
**Notes:** Topic names config-driven in ros2_bridge.yaml (defaults: /surg_rl/joint_states, /surg_rl/commands); frame_id configurable in YAML; QoS = qos_profile_sensor_data

---

## Trajectory Replay Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated CLI command | surg-rl ros2-replay, separate from bridge | ✓ |
| Bridge mode flag | --replay on bridge itself | |
| Standalone script/node | External ROS2 node, not in surg-rl CLI | |

**User's choice:** Dedicated CLI command (surg-rl ros2-replay)
**Notes:** Own SurgicalEnv + predict loop (self-contained); sleep-based throttling (sleep 9*dt for 10% speed)

---

## Real/Sim Mode Switch Location

| Option | Description | Selected |
|--------|-------------|----------|
| EnvironmentController | Mode flag + queue in controller | ✓ |
| SurgicalEnv directly | Mode flag in env, reads multiprocessing Queue | |
| New Ros2BridgeController | Separate class for bridge delegation | |

**User's choice:** EnvironmentController
**Notes:** get_action(policy_action) override method; set_real_robot_mode() API

---

## macOS Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Warn + disable | Import logs WARNING, HAS_ROS2=False | ✓ |
| Raise ImportError | Hard failure on import | |
| Silent no-op | No warning, no error | |

**User's choice:** Warn + disable at import
**Notes:** On call: warn + return None; CLI: warn + exit 0; tests: mock rclpy; docs: Docker workaround

---

## Backend Priority

| Option | Description | Selected |
|--------|-------------|----------|
| Both backends at once | MuJoCo + PyBullet from day one | ✓ |
| MuJoCo first | Start with MuJoCo, PyBullet later | |

**User's choice:** Both backends at once via BaseSimulator.get_state()/apply_action()

---

## Publishing Frequency & Batching

| Option | Description | Selected |
|--------|-------------|----------|
| Every step | Publish joint_states at each env.step() | ✓ |
| Fixed timer rate | ROS2 Timer at fixed Hz | |
| Configurable in YAML | publish_rate_hz in ros2_bridge.yaml | |

**User's choice:** Every step
**Notes:** Batching configurable in YAML (batch_size, default 1)

---

## Config File Schema & Location

| Option | Description | Selected |
|--------|-------------|----------|
| User-specified --config | Full path passed via CLI | ✓ |
| Fixed default configs/ | configs/ros2_bridge.yaml | |
| CLI flags only | No YAML file | |

**User's choice:** User-specified --config path
**Notes:** Pydantic v2 Ros2BridgeConfig dataclass for validation

---

## Error Handling & Action Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Hold last valid action | Skip bad command, use last action | |
| Apply zero action | Return to home position | ✓ |
| Silently discard | Drop bad message | |

**User's choice:** Wrong dimensions → apply zero action
**Notes:** Missing topics → fatal error (safest default, configurable); NaN/Inf → raise ValueError (safest default, configurable); all three strategies configurable in ros2_bridge.yaml

---

## Claude's Discretion

- Exact multiprocessing.Process spawn timing (at __init__ vs first reset())
- Ros2BridgeNode internal implementation details
- Warning wording for macOS / headless / missing-topic cases
- YAML schema design for error strategy fields (string enum vs nested object)
- Whether ros2_bridge.yaml supports separate pub/sub sections with different QoS/rate

## Deferred Ideas

- ros2_control integration — future phase
- ROS2 launch file support (.launch.py) — v0.3.0
- Custom surg_rl_msgs package — defer indefinitely
- WebSocket bridge (roslibpy) — rejected in research
