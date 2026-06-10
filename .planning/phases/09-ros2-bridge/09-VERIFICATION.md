---
phase: 09-ros2-bridge
verified: 2026-05-03T00:00:00Z
status: gaps_found
score: 12/15 must-haves verified (implementation-level)
overrides_applied: 0
gaps:
  - truth: "Ros2BridgeNode subscriber injects external commands (ROS2-02 / Roadmap SC#2)"
    status: failed
    reason: "CR-01: queue.Queue is not process-safe — child process writes to its own copy; main process reads from a disconnected copy. External ROS2 commands never reach the action pipeline."
    artifacts:
      - path: "src/surg_rl/ros2/bridge_node.py"
        issue: "_command_queue is queue.Queue (thread-safe only, not process-safe). When the node object is passed to multiprocessing.Process via Ros2Bridge.start(), the queue is pickled/copied. The child's subscriber callback writes to the child copy; main's get_latest_command() reads from main copy. No data crosses the boundary."
      - path: "src/surg_rl/rl/environment.py"
        issue: "_setup_bridge() creates Ros2BridgeNode with queue.Queue internally, then passes node to Ros2Bridge.start() which spawns a multiprocessing.Process. The shared-memory break is structural — the node and its queue must be redesigned for cross-process IPC."
    missing:
      - "Replace queue.Queue with multiprocessing.Queue in Ros2BridgeNode.__init__"
      - "Create the multiprocessing.Queue in _setup_bridge() and inject it into both Ros2BridgeNode.__init__ (optional param) and _run_bridge"
      - "Verify with test: inject command in child subscriber callback → main get_latest_command() sees it"

  - truth: "Ros2BridgeConfig.frame_id is wired into published messages (D-05, WR-01)"
    status: failed
    reason: "frame_id is hardcoded to 'world' in bridge_node.py line 226. The config field exists and validates, but is never passed to Ros2BridgeNode."
    artifacts:
      - path: "src/surg_rl/ros2/bridge_node.py"
        issue: "Line 226: msg.header.frame_id = 'world' — hardcoded, ignores config value"
      - path: "src/surg_rl/rl/environment.py"
        issue: "_setup_bridge() passes joint_names, publisher_topic, command_topic to Ros2BridgeNode but not frame_id"
    missing:
      - "Add frame_id parameter to Ros2BridgeNode.__init__"
      - "Wire bridge_cfg.frame_id from _setup_bridge()"
      - "Replace hardcoded 'world' with self._frame_id in publish_state()"

  - truth: "Ros2BridgeConfig.qos_profile applies qos_profile_sensor_data (D-06, WR-02)"
    status: failed
    reason: "qos_profile config field defaults to 'sensor_data' but create_publisher() uses default QoS (depth=10 only)"
    artifacts:
      - path: "src/surg_rl/ros2/bridge_node.py"
        issue: "Line 161-162: self.create_publisher(JointState, publisher_topic, 10) — no QoS profile applied"
    missing:
      - "Import rclpy.qos profiles (qos_profile_sensor_data)"
      - "Map config.qos_profile string to actual QoSProfile object at publisher creation"

  - truth: "Ros2BridgeConfig error strategies (on_nan_inf, on_dimension_mismatch) are configurable at runtime (D-25, D-26, WR-04)"
    status: failed
    reason: "Error strategies are hardcoded: NaN→always ValueError, dimension→always zero. The config fields exist but are never read at runtime."
    artifacts:
      - path: "src/surg_rl/ros2/bridge_node.py"
        issue: "publish_state() always raises ValueError on NaN/Inf (line 213-222) regardless of on_nan_inf config. _on_command() always applies zero action (line 265-272) regardless of on_dimension_mismatch config."
    missing:
      - "Pass Ros2BridgeConfig error strategy fields into Ros2BridgeNode"
      - "Branch in publish_state(): 'raise' → ValueError, 'sanitize' → replace NaN→0.0/Inf→limits"
      - "Branch in _on_command(): 'zero' → zero action, 'warn' → log + passthrough"

  - truth: "Ros2BridgeConfig.on_missing_topic detects missing counterpart topics (D-24, WR-05)"
    status: failed
    reason: "on_missing_topic field exists but no startup topic liveness check is implemented. Bridge silently proceeds without counterpart."
    artifacts:
      - path: "src/surg_rl/ros2/bridge_node.py"
        issue: "No code for on_missing_topic check exists"
    missing:
      - "Add startup check in Ros2Bridge.start() or _setup_bridge()"
      - "Query existing topics via rclpy, compare with configured state_topic/command_topic"
      - "Branch: 'error' → RuntimeError, 'warn' → logger.warning"

deferred: []
human_verification:
  - test: "Verify publisher works — run surg-rl ros2-bridge on Linux with ROS2, then ros2 topic list"
    expected: "/surg_rl/joint_states should appear in topic list"
    why_human: "Requires ROS2 installation (rclpy apt deps) and Linux platform"
  - test: "Verify subscriber works after CR-01 fix — publish Float64MultiArray to /surg_rl/commands, observe robot joints move in simulation"
    expected: "Robot joints respond to published commands in real_robot mode"
    why_human: "End-to-end integration test requiring ROS2 + MuJoCo/PyBullet"
  - test: "Run trajectory replay — surg-rl ros2-replay --checkpoint model.zip --scene scene.json --speed 0.1"
    expected: "Replay completes without crashes, publishes actions to command topic"
    why_human: "Requires trained SB3 checkpoint + ROS2 environment"
---

# Phase 9: ROS2 Bridge — Verification Report

**Phase Goal:** Publish simulation state to ROS2 and accept external commands for real-robot validation.
**Verified:** 2026-05-03
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Ros2BridgeConfig Pydantic v2 dataclass validates 8 fields and loads from YAML | ✓ VERIFIED | `config.py` has @dataclass with 8 fields, `from_yaml()` classmethod |
| 2 | HAS_ROS2 flag correctly detects rclpy availability on any platform | ✓ VERIFIED | `__init__.py` has platform-aware detection (darwin→False, else try ImportError) |
| 3 | Ros2BridgeNode publishes JointState and has subscriber structure | ⚠️ PARTIAL | Publisher code exists (line 161-163, 190-230) and works. Subscriber structure exists (line 164-169, 247-280) but IPC is broken (CR-01) |
| 4 | macOS import sets HAS_ROS2=False with WARNING, no crash | ✓ VERIFIED | `__init__.py` line 23-28: darwin guard with logger.warning |
| 5 | EnvironmentController has _mode flag with set_real_robot_mode() API | ✓ VERIFIED | `environment_controller.py` lines 147, 193-203 |
| 6 | EnvironmentController.get_action() routes sim/real_robot correctly | ✓ VERIFIED | Code lines 221-258: sim→passthrough, real_robot→queue→hold-last. Logic sound, but queue never fills from bridge (CR-01) |
| 7 | SurgicalEnv spawns bridge Process when ros2_bridge_config is set | ✓ VERIFIED | `_setup_bridge()` lines 363-410, `Ros2Bridge.start()` line 866-875 |
| 8 | SurgicalEnv.step() calls get_action() and publish_joint_state() | ✓ VERIFIED | step() lines 485 (get_action), 559-561 (publish) |
| 9 | Bridge terminates cleanly in close() before simulator cleanup | ✓ VERIFIED | `close()` lines 587-589 terminates bridge before `_simulator.close()` |
| 10 | TrajectoryReplay loads SB3 checkpoint and creates own SurgicalEnv | ✓ VERIFIED | `replay.py` lines 134-148: PPO.load() + make_env() |
| 11 | run_replay() runs predict loop publishing Float64MultiArray | ✓ VERIFIED | Lines 162-219: predict→publish→step→throttle loop |
| 12 | Speed throttling via sleep((1.0/speed - 1.0) * dt) | ✓ VERIFIED | Lines 203-205: formula matches D-09 exactly |
| 13 | terminate() calls env.close() + rclpy.shutdown() | ✓ VERIFIED | Lines 221-229: correct cleanup order |
| 14 | ros2-bridge CLI command with --config and --scene | ✓ VERIFIED | `cli.py` lines 633-722: Typer command with all flags |
| 15 | ros2-replay CLI command with --checkpoint and --speed | ✓ VERIFIED | `cli.py` lines 726-802 |
| 16 | macOS: both CLI commands print info + exit 0 | ✓ VERIFIED | Lines 663-670, 762-770: Darwin guards with Exit(0) |
| 17 | Missing rclpy: commands print apt instructions + exit 1 | ✓ VERIFIED | Lines 672-678, 782-788 |
| 18 | pyproject.toml has [ros2] extra with PyYAML + apt docs | ✓ VERIFIED | `pyproject.toml` lines 102-107 |

**Score:** 18/18 truths structurally exist. Functionally, truths #3 and #6 are PARTIAL due to CR-01 (subscriber IPC broken), and truths related to config wiring (WR-01 through WR-05) are structural gaps documented below.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/surg_rl/ros2/__init__.py` | HAS_ROS2 flag, rclpy import guard, exports | ✓ VERIFIED | 54 lines, correct darwin guard, exports all 3 classes |
| `src/surg_rl/ros2/config.py` | Ros2BridgeConfig with 8 fields, from_yaml() | ✓ VERIFIED | 105 lines, Pydantic v2 @dataclass, YAML loader |
| `src/surg_rl/ros2/bridge_node.py` | Ros2BridgeNode pub/sub, dummy class | ✓ VERIFIED | 287 lines, real + dummy implementations |
| `src/surg_rl/ros2/replay.py` | TrajectoryReplay with predict loop + throttle | ✓ VERIFIED | 230 lines, self-contained replay |
| `src/surg_rl/dynamics/environment_controller.py` | _mode, queue, get_action(), inject_external_action() | ✓ VERIFIED | Mode switch + queue added, no regression |
| `src/surg_rl/rl/environment.py` | ros2_bridge_config, _setup_bridge, Ros2Bridge, step/close wiring | ✓ VERIFIED | Bridge lifecycle fully integrated |
| `src/surg_rl/cli.py` | ros2_bridge and ros2_replay commands | ✓ VERIFIED | Both commands with guards + error handling |
| `pyproject.toml` | [ros2] extra with apt docs | ✓ VERIFIED | PyYAML entry + comment documenting apt deps |
| `tests/test_ros2_bridge.py` | Config + node tests | ✓ VERIFIED | 20 tests pass |
| `tests/test_ros2_controller.py` | Controller mode tests | ✓ VERIFIED | 8 tests pass |
| `tests/test_ros2_replay.py` | Replay validation tests | ✓ VERIFIED | 17 pass, 2 skipped (valid skip) |
| `tests/test_ros2_cli.py` | CLI command tests | ✓ VERIFIED | 6 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Config.from_yaml() | YAML file | yaml.safe_load() → Pydantic v2 | ✓ WIRED | Pattern `yaml\.safe_load` confirmed |
| BridgeNode.publish_state() | JointState publisher | create_publisher + publish() | ✓ WIRED | Pattern `create_publisher.*JointState` confirmed |
| SurgicalEnv.step() → controller.get_action() | Action routing | mode switch | ✓ WIRED | Line 485: get_action() called before randomization |
| SurgicalEnv.step() → bridge | State publish | publish_joint_state() | ✓ WIRED | Lines 559-561: publishes every step |
| ros2-bridge CLI → config | Config loading | from_yaml() | ✓ WIRED | Line 686: Ros2BridgeConfig.from_yaml(config) |
| ros2-replay CLI → replay | Replay init | TrajectoryReplay() | ✓ WIRED | Line 775: TrajectoryReplay instantiation |
| Bridge subscriber → controller queue | Command injection | _command_queue → _external_action_queue | ✗ NOT_WIRED | **CR-01**: queue.Queue is process-local; child writes to own copy |
| Speed throttling | sleep formula | sleep((1.0/speed - 1.0) * dt) | ✓ WIRED | Lines 203-205: matches D-09 formula |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| BridgeNode.publish_state() | qpos, qvel → JointState | SurgicalEnv.step() → get_state() | ✓ (sim state is real) | ✓ FLOWING |
| BridgeNode._on_command() | msg.data → _command_queue | ROS2 subscriber callback | ✓ (ROS2 messages are real) | ✗ DISCONNECTED — queue is process-local, main never sees data |
| Controller.get_action() | _external_action_queue → external action | EnvironmentController._external_action_queue | ✗ (queue never populated) | ✗ DISCONNECTED — bridge queue copy != controller queue |
| TrajectoryReplay.run_replay() | model.predict(obs) → _pub.publish() | SB3 checkpoint | ✓ (predict returns real actions) | ✓ FLOWING — self-contained, no IPC |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Config import + validation | `python -c "from surg_rl.ros2.config import Ros2BridgeConfig; c = Ros2BridgeConfig(state_topic='/a', command_topic='/b')"` | Config created with correct defaults | ✓ PASS |
| HAS_ROS2 on macOS | `python -c "from surg_rl.ros2 import HAS_ROS2; print(HAS_ROS2)"` | `False` with WARNING log | ✓ PASS |
| Dummy node imports | `python -c "from surg_rl.ros2.bridge_node import Ros2BridgeNode; n = Ros2BridgeNode(); print(n)"` | Dummy node created | ✓ PASS |
| Controller mode switch | `python -c "... EnvironmentController().set_real_robot_mode(True) ..."` | Mode switches to real_robot | ✓ PASS |
| CLI help listing | `python -m surg_rl.cli --help \| grep ros2` | Both commands listed | ✓ PASS |
| Full test suite | `pytest tests/test_ros2_*.py -v` | 51 passed, 2 skipped | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ROS2-01 | 09-01, 09-02, 09-05 | Publisher publishes joint_states at simulation frequency | ✓ SATISFIED | BridgeNode.publish_state() wired into step(), publishes JointState every step |
| ROS2-02 | 09-02, 09-05 | Subscriber receives commands and injects as external actions | ✗ BLOCKED | **CR-01**: Subscriber code exists but IPC is broken — queue.Queue is process-local; commands never reach main process |
| ROS2-03 | 09-03, 09-05 | Trajectory replay from checkpoints at reduced speed | ✓ SATISFIED | TrajectoryReplay class with PPO.load(), predict loop, speed throttle, self-contained |
| ROS2-04 | 09-02, 09-05 | Runtime mode switch between sim and real_robot | ⚠️ PARTIAL | Mode switch API exists and works. But real_robot mode never receives commands (CR-01 affects injection path) |
| ROS2-05 | 09-04, 09-05 | ros2-bridge CLI command with configurable topics | ✓ SATISFIED | `ros2-bridge` and `ros2-replay` Typer commands, --config YAML loading, macOS guard |
| ROS2-06 | 09-04, 09-05 | [ros2] extra with deps | ✓ SATISFIED | pyproject.toml [ros2] extra with PyYAML + apt docs comment. ROADMAP SC#6 says "installs rclpy" but this is technically impossible (rclpy not on PyPI) — implementation correctly documents apt deps instead |

**Note on ROS2-06 vs ROADMAP SC#6:** The ROADMAP success criterion #6 states "`pip install 'surg-rl[ros2]'` installs `rclpy` and message packages" but this is technically infeasible — `rclpy`, `sensor_msgs`, `geometry_msgs`, and `std_msgs` are apt-only packages not distributed on PyPI. The implementation correctly documents apt dependencies in the pyproject.toml comment. This is a roadmap spec issue, not an implementation bug. To close this gap, either update ROADMAP SC#6 to match reality or document the override.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `bridge_node.py` | 159 | `queue.Queue(maxsize=1)` instead of `multiprocessing.Queue` | 🛑 BLOCKER | CR-01: subscriber IPC broken, commands never reach main process |
| `bridge_node.py` | 226 | `"world"` hardcoded instead of config.frame_id | ⚠️ WARNING | WR-01: user-configured frame_id ignored |
| `bridge_node.py` | 161-162 | `create_publisher(..., 10)` — default QoS, no sensor_data profile | ⚠️ WARNING | WR-02: config.qos_profile field unused |
| `bridge_node.py` | 213-222 | NaN/Inf always raises ValueError — no sanitize path | ⚠️ WARNING | WR-04: config.on_nan_inf field unused |
| `bridge_node.py` | 265-272 | Dimension mismatch always zero — no warn path | ⚠️ WARNING | WR-04: config.on_dimension_mismatch field unused |
| `bridge_node.py` | — | No on_missing_topic startup check | ⚠️ WARNING | WR-05: config.on_missing_topic field unused |
| `ros2/__init__.py` | 17 | `logging.getLogger(__name__)` instead of `get_logger` | ⚠️ WARNING | WR-06: inconsistent with project-standard Rich logger |
| `ros2/config.py` | 10 | Unused imports: `ClassVar`, `Optional` | ℹ️ INFO | IN-01: type checker noise |
| `ros2/replay.py` | 11 | Unused import: `queue` | ℹ️ INFO | IN-02: no queue usage in replay |

### Human Verification Required

#### 1. Publisher Output Verification
**Test:** On a Linux machine with ROS2 installed, run `surg-rl ros2-bridge --config ros2_bridge.yaml --scene scene.json --headless`, then in another terminal run `ros2 topic list | grep surg_rl`
**Expected:** `/surg_rl/joint_states` appears in the topic list. `ros2 topic echo /surg_rl/joint_states` shows JointState messages with position/velocity/name fields.
**Why human:** Requires ROS2 installation (apt deps: rclpy, sensor-msgs) and Linux platform.

#### 2. Command Subscriber Verification (after CR-01 fix)
**Test:** After fixing the multiprocessing IPC, publish a command: `ros2 topic pub /surg_rl/commands std_msgs/msg/Float64MultiArray "data: [0.5, -0.3, 0.1]"` and observe the robot joints move in the simulation viewer.
**Expected:** Robot joints respond to the published command values. The controller's real_robot mode pulls the external command and applies it to the simulator.
**Why human:** End-to-end integration test requiring ROS2, running bridge, and visual or state inspection.

#### 3. Trajectory Replay Validation
**Test:** `surg-rl ros2-replay --checkpoint models/ppo_suturing.zip --scene scenes/suturing_demo.json --speed 0.1` on Linux with ROS2.
**Expected:** Replay completes without crashes. Stats printed show steps_executed, total_wall_time, avg_step_time. The replay publishes Float64MultiArray actions to `/surg_rl/commands`.
**Why human:** Requires a trained SB3 checkpoint file and ROS2 environment.

### Gaps Summary

**BLOCKER — CR-01: Subscriber IPC is broken.** The command subscriber pathway is non-functional in production. `Ros2BridgeNode` uses `queue.Queue` (stdlib, thread-safe only), which is pickled/copied when the node is sent to the child `multiprocessing.Process`. The child's subscriber callback writes to the child's copy, and `get_latest_command()` reads from the main process's copy — these are separate queues. External ROS2 commands never reach the action pipeline. This directly violates ROS2-02 and makes the real_robot mode (ROS2-04) non-functional for external commands.

**Root cause:** The node architecture creates the queue internally, then passes the entire node to a child process. The fix requires either:
1. Using `multiprocessing.Queue` and injecting it from the parent process (recommended), or
2. Restructuring so the node is only instantiated in the child and communication uses a separate shared-memory IPC channel.

**WARNING — Config fields unwired (WR-01 to WR-05):** Five configurable fields (`frame_id`, `qos_profile`, `batch_size`, error strategies) are declared in `Ros2BridgeConfig` and validated by Pydantic, but the runtime behavior ignores them. They exist as schema without effect. These are not blockers for the core goal but should be wired before production use.

**WARNING — Logging inconsistency (WR-06):** The `ros2/` package uses `logging.getLogger(__name__)` instead of the project-standard `from surg_rl.utils.logging import get_logger`. This is a code quality issue — not a functional bug — but creates inconsistency in log formatting (no Rich renderer).

**Publisher side (state → ROS2) is fully functional.** All tests pass (51 passed, 2 skipped appropriately). macOS graceful degradation works correctly. Trajectory replay is self-contained and correct.

---

_Verified: 2026-05-03_
_Verifier: OpenCode (gsd-verifier)_
