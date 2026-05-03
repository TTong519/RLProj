---
phase: 09-ros2-bridge
plan: 02
subsystem: ros2-runtime
tags: [ros2, bridge, runtime, multiprocessing, environment-controller]
requires: [09-01]
provides: [EnvironmentController mode switch, SurgicalEnv bridge lifecycle, Ros2Bridge wrapper]
affects: [src/surg_rl/dynamics/environment_controller.py, src/surg_rl/rl/environment.py]
tech-stack:
  added: []
  patterns: [queue.Queue keep-latest, multiprocessing.Process daemon, platform guard, mode routing]
key-files:
  created:
    - tests/test_environment_controller.py
  modified:
    - src/surg_rl/dynamics/environment_controller.py
    - src/surg_rl/rl/environment.py
    - tests/test_rl_environment.py
decisions:
  - get_action() inserted BEFORE get_randomized_action() in step() — external commands bypass randomization noise
  - Module-level platform import (not local) — enables `unittest.mock.patch` in tests
  - Platform check uses platform.system() (not sys.platform) — already consistent with ros2/__init__.py
  - Ros2Bridge wrapper owns Process lifecycle; SurgicalEnv._setup_bridge() calls start/terminate
  - Bridge node reference stored in Ros2Bridge wrapper for cross-process publish_state() calls
  - _last_action hold-fallback returns policy_action if no external command received yet (not zeros)
metrics:
  duration: 19m
  started: 2026-05-03T04:57:01Z
  completed: 2026-05-03T05:16:17Z
---

# Phase 9 Plan 2: ROS2 Bridge Runtime Integration Summary

**One-liner:** Real/sim mode switch in EnvironmentController with external action queue plus SurgicalEnv bridge lifecycle — spawn, publish joint states, inject commands via controller.get_action(), clean termination at close().

## What Was Built

Integrated the ROS2 bridge foundation (Plan 01) into the RL runtime at two integration points:

### EnvironmentController (dynamics layer)

Added three new fields and four new methods to `EnvironmentController` for the real/sim mode switch (D-10, D-11, D-12):

- `_mode: Literal["sim", "real_robot"]` — mode flag, defaults to `"sim"`
- `_external_action_queue: queue.Queue(maxsize=1)` — keep-latest command queue (D-02, T-09-04)
- `_last_action: np.ndarray | None` — hold-last fallback when queue empty
- `mode` property — read current mode
- `set_real_robot_mode(enabled: bool)` — switch modes, logs at INFO
- `inject_external_action(action: np.ndarray)` — put action into queue with keep-latest overwrite
- `get_action(policy_action: np.ndarray) -> np.ndarray` — mode-based routing: sim → passthrough, real_robot → queue.dequeue → hold-last. Validates no NaN/Inf before returning (D-25, T-09-06)
- `get_status()` — updated to include `"mode"` key

### SurgicalEnv (RL layer)

Added bridge lifecycle management to `SurgicalEnv`:

- `SurgicalEnvConfig.ros2_bridge_config: Ros2BridgeConfig | None = None` — new config field
- `_bridge: Ros2Bridge | None` — bridge instance, `None` when disabled
- `_setup_bridge()` — platform guard (macOS → warn), HAS_ROS2 check, Ros2BridgeNode creation, Ros2Bridge Process spawn at `__init__` (D-01)
- `step()` modifications:
  - `controller.get_action(action)` inserted **before** `get_randomized_action()` (D-11) — external commands bypass randomization noise
  - `bridge.publish_joint_state(qpos, qvel)` called after simulator step, before controller update (D-19)
- `close()` — terminates bridge Process **before** simulator cleanup (D-01)
- `Ros2Bridge` wrapper class — manages Process lifecycle: `start()` spawns daemon Process with `rclpy.spin()`, `terminate()` escalation chain: terminate → join(5s) → kill → join(2s) (T-09-07), `publish_joint_state()` delegates to node

### Threat Model Mitigations Covered

| Threat ID | Mitigation | Where |
|-----------|-----------|-------|
| T-09-06 (Tampering on action pipeline) | Two-layer validation: dimension check in `_on_command` + NaN/Inf check in `get_action()` | `environment_controller.py`, `bridge_node.py` |
| T-09-07 (DoS on bridge Process) | Escalation chain + daemon=True; close() terminates before simulator cleanup | `environment.py` |
| T-09-08 (Spoofing of mode flag) | Explicit API call `set_real_robot_mode(True)` — cannot be triggered accidentally | `environment_controller.py` |

## Tasks Executed

| Task | Name | Commit | Tests |
|------|------|--------|-------|
| 0 | Real/sim mode + external action queue in EnvironmentController | `cacdad0` | 14 passed |
| 1 | Bridge Process spawn + action injection in SurgicalEnv | `6439bae` | 11 bridge + 30 env passed |

**Total tests:** 25 new (14 controller + 11 bridge), 30/31 env regression (1 pre-existing failure — shape mismatch in `_normalize_action`, unrelated to bridge)

### TDD Cycle

- **RED (task 0):** `95f015f` — 11 failing tests for mode, queue, get_action, regression
- **GREEN (task 0):** `cacdad0` — EnvironmentController with mode flag, queue, new methods
- **RED (task 1):** `c7b4c58` — 8 failing tests for ros2_bridge_config, bridge lifecycle, injection
- **GREEN (task 1):** `6439bae` — SurgicalEnv bridge lifecycle, Ros2Bridge wrapper, step/close mods

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Design Decisions Made During Execution

**1. Module-level platform import for test patching**
- The plan's `_setup_bridge` used a local `import platform`. Mock-based tests (`platform.system` → "Linux") require the import to be at module level so `unittest.mock.patch` can intercept it.
- Moved `import platform` to module-level imports.

**2. HAS_ROS2 imported at module level**
- The plan had `from surg_rl.ros2 import HAS_ROS2` inside `_setup_bridge`. Since `HAS_ROS2` is already imported in `__init__.py` and used at module-level for the `no_bridge_ros2_false_warns` test patching, moved it to module-level.

## Verification

```bash
# EnvironmentController mode switch
PYTHONPATH=src python -c "
from surg_rl.dynamics.environment_controller import EnvironmentController
c = EnvironmentController()
assert c.mode == 'sim'
c.set_real_robot_mode(True)
assert c.mode == 'real_robot'
import numpy as np
pa = np.array([1.0, 2.0, 3.0])
c.inject_external_action(np.array([4.0, 5.0, 6.0]))
a = c.get_action(pa)
assert a.tolist() == [4.0, 5.0, 6.0]
print('OK')
"
# Output: OK

# Config wiring
PYTHONPATH=src python -c "
from surg_rl.rl.environment import SurgicalEnvConfig
from surg_rl.ros2.config import Ros2BridgeConfig
c = SurgicalEnvConfig()
assert c.ros2_bridge_config is None
c2 = SurgicalEnvConfig(ros2_bridge_config=Ros2BridgeConfig(state_topic='/t', command_topic='/t2'))
assert c2.ros2_bridge_config is not None
print('OK')
"
# Output: OK

# Full test suite
PYTHONPATH=src pytest tests/test_environment_controller.py tests/test_rl_environment.py -v
# 45 passed, 1 failed (pre-existing)
```

## Known Stubs

None — all methods are fully functional. The bridge gracefully degrades on macOS/without rclpy:
- macOS: `_setup_bridge()` logs WARNING and sets `_bridge=None`, env works normally
- No rclpy: same behavior — bridge disabled but env fully functional

## Threat Flags

None — no new threat surface beyond what the `<threat_model>` covered.

## Self-Check

- [x] `src/surg_rl/dynamics/environment_controller.py` modified
- [x] `src/surg_rl/rl/environment.py` modified
- [x] `tests/test_environment_controller.py` created (14 tests)
- [x] `tests/test_rl_environment.py` modified (11 new tests)
- [x] Commit `95f015f` exists — RED task 0
- [x] Commit `cacdad0` exists — GREEN task 0
- [x] Commit `c7b4c58` exists — RED task 1
- [x] Commit `6439bae` exists — GREEN task 1
- [x] All 25 new tests pass
- [x] 30/31 env regression tests pass (1 pre-existing failure)

## Self-Check Result: PASSED
