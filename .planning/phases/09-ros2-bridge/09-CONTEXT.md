# Phase 9: ROS2 Bridge for Real Hardware - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

## Phase Boundary

Bridge the `surg-rl` simulation to ROS2: publish joint states at simulation frequency, subscribe to command topics, replay trained trajectories at reduced speed, and switch between simulation-powered and externally-driven action sources. All ROS2 code lives behind an optional `[ros2]` extra — core install stays lightweight.

## Implementation Decisions

### Bridge Topology
- **D-01:** Bridge runs as a **separate multiprocessing Process** (not a daemon thread). `SurgicalEnv.__init__` spawns it, `env.close()` terminates it.
- **D-02:** IPC via **multiprocessing.Queue** (state → bridge) and **multiprocessing.Queue** (commands ← bridge). Keep-latest semantics: `maxsize=1` for the command queue.

### Topics & Message Types
- **D-03:** State publisher uses `sensor_msgs/JointState`. Command subscriber uses `std_msgs/Float64MultiArray`.
- **D-04:** Topic names are **config-driven via `ros2_bridge.yaml`**, not hardcoded. Defaults: `/surg_rl/joint_states` (state) and `/surg_rl/commands` (commands).
- **D-05:** Frame ID is **configurable in `ros2_bridge.yaml`**. Default: `"world"`.
- **D-06:** Joint state publisher uses **`qos_profile_sensor_data`** (RELIABLE, KEEP_LAST(5)). Command subscriber uses default.

### Trajectory Replay
- **D-07:** Replay is a **dedicated CLI command**: `surg-rl ros2-replay --checkpoint model.zip --scene scene.json --speed 0.1`.
- **D-08:** Replay creates its **own SurgicalEnv, loads the SB3 checkpoint, and runs a predict loop**. Self-contained — no IPC with a running bridge.
- **D-09:** Speed throttling is **sleep-based**: `time.sleep((1.0/speed - 1.0) * dt)` between steps. Default speed = 0.1 (10%).

### Real/Sim Mode Switch
- **D-10:** Mode flag (`_mode: Literal["sim", "real_robot"]`) and external action queue live in **EnvironmentController** (the class ROADMAP refers to as `SimulationController`).
- **D-11:** Action injection via **`EnvironmentController.get_action(policy_action) → np.ndarray`** override method. `SurgicalEnv.step()` calls it before passing to the simulator.
- **D-12:** Mode switch API: **`controller.set_real_robot_mode(True/False)`**.

### macOS Handling
- **D-13:** On macOS: **import logs a WARNING and sets `HAS_ROS2 = False`**. Module-level functions return `None` or early-exit.
- **D-14:** Calling ROS2 bridge functions on macOS logs a **warning and returns `None`**. No crash.
- **D-15:** CLI `surg-rl ros2-bridge` on macOS prints a **clear message + exits 0**.
- **D-16:** ROS2 bridge tests use **mocked `rclpy` imports** — tests run on macOS without actual ROS2 apt deps.
- **D-17:** macOS limitation **documented with Docker workaround** (Linux container with ROS2, shared volume for scenes).

### Backend Support
- **D-18:** Bridge supports **both MuJoCo and PyBullet** from day one via `BaseSimulator.get_state()` / `apply_action()`.

### Publishing Frequency & Batching
- **D-19:** Joint states are published at **every `SurgicalEnv.step()` call**.
- **D-20:** Batching is **configurable in `ros2_bridge.yaml`** (`batch_size`). Default: 1 (no batching).

### Config File
- **D-21:** Config path is **user-specified via `--config` CLI flag**. No fixed default location.
- **D-22:** Config schema is a **Pydantic v2 dataclass** (`Ros2BridgeConfig`) with fields: `state_topic`, `command_topic`, `frame_id`, `batch_size`, `qos_profile`, `on_missing_topic`, `on_nan_inf`, `on_dimension_mismatch`.

### Error Handling & Action Validation
- **D-23:** **Wrong-dimension commands** → apply zero action (robot returns to home).
- **D-24:** **Missing counterpart topic** at startup → fatal error (default: `"error"`). Configurable to `"warn"` for partial operation.
- **D-25:** **NaN/Inf in commands or states** → raise `ValueError` (default: `"raise"`). Configurable to `"sanitize"` (replace NaN→0.0, Inf→limit).
- **D-26:** All three error strategies are **configurable in `ros2_bridge.yaml`** via `on_dimension_mismatch`, `on_missing_topic`, `on_nan_inf`.

### Claude's Discretion
- Exact `multiprocessing.Process` spawn timing (at `__init__` vs first `reset()`)
- `Ros2BridgeNode` internal implementation details (exact threading, exception handling in spin loop)
- Warning wording for macOS / headless / missing-topic cases
- Whether `ros2_bridge.yaml` supports separate pub/sub sections with different QoS/rate per direction
- YAML schema design for error strategy fields (string enum or nested object)

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 9 — success criteria (ROS2-01 through ROS2-06)
- `.planning/REQUIREMENTS.md` § ROS2 Bridge — ROS2-01 through ROS2-06 requirements

### Research
- `.planning/phases/09-ros2-bridge/09-RESEARCH.md` — full research with stack patterns, pitfalls, code examples

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — system layers, inheritance hierarchies, data flow
- `.planning/codebase/STACK.md` — core frameworks and optional dependency groups
- `.planning/codebase/INTEGRATIONS.md` — external services and existing integration patterns

### Prior Phase Context
- `.planning/phases/07-real-time-rendering/07-real-time-rendering-CONTEXT.md` — D-02 (simulator thread ownership), D-03 (headless fallback), D-05 (SIGINT/cleanup)
- `.planning/phases/06-hardware-acceleration/06-hardware-acceleration-CONTEXT.md` — graceful degradation pattern, optional extras structure, test strategy

### Key Source Files
- `src/surg_rl/rl/environment.py` — `SurgicalEnv`, `SurgicalEnvConfig`
- `src/surg_rl/rl/training.py` — `TrainingConfig`, `TrainingManager`, checkpoint loading
- `src/surg_rl/dynamics/environment_controller.py` — `EnvironmentController`, `EnvironmentControllerConfig`
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator` ABC (`get_state()`, `apply_action()`, `close()`)
- `src/surg_rl/simulators/mujoco_simulator.py` — MuJoCo backend
- `src/surg_rl/simulators/pybullet_simulator.py` — PyBullet backend
- `src/surg_rl/cli.py` — Typer CLI entrypoint
- `pyproject.toml` — optional dependency groups pattern

## Existing Code Insights

### Reusable Assets
- `EnvironmentController` dataclass pattern — add `_mode`, `_external_action_queue`, `get_action()`, `set_real_robot_mode()` fields/methods
- `SurgicalEnvConfig` dataclass — add `ros2_bridge_config: Ros2BridgeConfig | None = None` field
- `SurgicalEnv.__init__` — spawn bridge Process after `load_scene()` (analogous to D-01 from Phase 7: start_viewer after load_scene)
- `SurgicalEnv.close()` — terminate bridge Process + join (analogous to D-05 from Phase 7)
- `TrainingManager` checkpoint loading — reuse for replay command's `model.load()` call
- `pyproject.toml` `[distributed]` extra pattern — mirror for `[ros2]` extra

### Established Patterns
- Optional dependency groups (`[distributed]`, `[ros2]`, `[llm]`, `[vision]`) in `pyproject.toml` — Phase 5 pattern
- Graceful degradation: warn + fallback, never crash — Phase 6 pattern
- Simulator owns threads/processes — Phase 7 pattern (simulator owns RenderThread → env owns bridge Process)
- Typer CLI flags: `--config` for file paths, boolean flags for toggles
- Pydantic v2 dataclasses for all config objects
- `PYTHONPATH=src` for all direct script invocations

### Integration Points
- `SurgicalEnv.step()` — insert `action = self._controller.get_action(action)` before `simulator.step(action)`
- `SurgicalEnv.close()` — ensure bridge Process is terminated before simulator cleanup
- `cli.py` — add `ros2-bridge` and `ros2-replay` Typer commands
- `EnvironmentController` — add mode flag, queue, and `get_action()` method
- `pyproject.toml` — document `[ros2]` extra (apt deps only, no pip-installable packages)

## Specific Ideas

- Bridge Process should use `try/finally` to call `rclpy.shutdown()` and `node.destroy_node()` on exit
- Replay should accept `--speed 1.0` for full-speed and `--speed 0.01` for 1% debugging speed
- `ros2_bridge.yaml` should support optional `publisher` and `subscriber` sub-sections for directional overrides
- Error strategy fields should use `Literal["error", "warn", "raise", "sanitize", "zero"]` or similar string enum

## Deferred Ideas

- **`ros2_control` integration** — hardware_interface abstraction, MoveIt compatibility. Future phase.
- **ROS2 launch file support** (`ros2 launch surg_rl bridge.launch.py`) — requires colcon build, breaks pip-only workflow. Defer to v0.3.0.
- **Custom `surg_rl_msgs` package** with typed action/task messages — maintenance burden, defer indefinitely.
- **WebSocket bridge (`roslibpy`)** — adds latency, requires rosbridge_server. Rejected in research.

---

*Phase: 09-ros2-bridge*
*Context gathered: 2026-05-02*
