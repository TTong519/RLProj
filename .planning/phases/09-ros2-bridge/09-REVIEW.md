---
phase: 09-ros2-bridge
reviewed: 2026-05-03T00:00:00Z
depth: deep
files_reviewed: 8
files_reviewed_list:
  - src/surg_rl/ros2/__init__.py
  - src/surg_rl/ros2/config.py
  - src/surg_rl/ros2/bridge_node.py
  - src/surg_rl/ros2/replay.py
  - src/surg_rl/dynamics/environment_controller.py
  - src/surg_rl/rl/environment.py
  - src/surg_rl/cli.py
  - pyproject.toml
findings:
  critical: 1
  warning: 6
  info: 3
  total: 10
status: issues_found
---
# Phase 09: ROS2 Bridge for Real Hardware — Code Review

**Reviewed:** 2026-05-03
**Depth:** deep (cross-file call chains, import graph, process-lifecycle analysis)
**Files Reviewed:** 8 source files
**Status:** issues_found — 1 critical, 6 warnings, 3 info

## Summary

The Phase 9 implementation has strong structure — config, node, replay, controller, env integration, and CLI are all present and wire together cleanly. Tests cover the mock/dummy code paths and confirm that the env remains functional on macOS.

However, a **critical process-lifetime bug** in the IPC design means the command-subscriber pathway is non-functional in production. The bridge node's `queue.Queue` is shared across a `multiprocessing.Process` boundary (pickled/copied, not shared-memory), so external commands from ROS2 will never reach the main sim thread. Additionally, four configurable fields (frame_id, qos_profile, batch_size, and error-strategy controls) are declared but never wired into runtime behavior — they exist only as schema without effect. Finally, the new code does not use the project-standard logging helper, creating inconsistency with the existing codebase.

The publisher side (state → ROS2) works correctly. The controller mode-switch and replay tool are sound. But the subscriber side needs the IPC to be reworked before this ship-ready.

---

## Critical Issues

### CR-01: `queue.Queue` is not process-safe — external commands never reach main process

**File:** `src/surg_rl/ros2/bridge_node.py:159`, `src/surg_rl/rl/environment.py:370–410`

**Issue:**

The `Ros2BridgeNode._command_queue` is a `queue.Queue` (from the standard library). This class uses Python-level locks on an in-process deque — it is **thread-safe** but **not process-safe**. When the node object is passed to a child `multiprocessing.Process` (via `Ros2Bridge.start()` at line 868–872 of `environment.py`), Python **pickles** the node object and sends a **copy** to the child. The child's subscriber callback writes to the child's copy of `_command_queue`, but the main process reads from its own copy. The two queues are entirely independent — no data crosses the process boundary.

**Impact:** Commands published to ROS2 by external nodes (e.g., `ros2 topic pub /surg_rl/commands std_msgs/msg/Float64MultiArray ...`) are received by the child process, but `SurgicalEnv.step()` always sees an empty queue because `get_latest_command()` reads from the main process's disconnected copy. The entire command-subscriber path is broken. ROS2-01 and ROS2-02 are not satisfied.

**Fix:**

Replace `queue.Queue` with `multiprocessing.Queue` for the command channel:
```python
# In Ros2BridgeNode.__init__ (real implementation, line 159):
import multiprocessing
self._command_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
```
Note: This requires the node to be constructed in the parent process *after* `multiprocessing.Queue` is created. The queue must be passed to the child explicitly (it is pickle-safe and uses shared-memory pipes). The `_on_command` and `get_latest_command` callbacks then read/write the same underlying queue. Test: construct the queue in `_setup_bridge()`, pass it to both `Ros2BridgeNode.__init__` (as an optional injection) and `_run_bridge`.

---

## Warnings

### WR-01: `frame_id` from `Ros2BridgeConfig` is ignored — hardcoded to `"world"`

**File:** `src/surg_rl/ros2/bridge_node.py:226`

**Issue:**
The `Ros2BridgeConfig.frame_id` field (default `"world"`, configurable — D-05) is never passed to `Ros2BridgeNode`. The node only receives `joint_names`, `publisher_topic`, and `command_topic`. Line 226 hardcodes `"world"` regardless of the config value.

**Fix:**
Add a `frame_id` parameter to `Ros2BridgeNode.__init__` and wire it from `_setup_bridge()`:
```python
# In environment.py _setup_bridge(), after line 399:
node = Ros2BridgeNode(
    joint_names=joint_names,
    publisher_topic=bridge_cfg.state_topic,
    command_topic=bridge_cfg.command_topic,
    frame_id=bridge_cfg.frame_id,  # ← add this
)
```
Then in `bridge_node.py` line 226:
```python
msg.header.frame_id = self._frame_id  # instead of hardcoded "world"
```

### WR-02: `qos_profile` config field is unused — publisher uses default QoS

**File:** `src/surg_rl/ros2/bridge_node.py:161–163`, `src/surg_rl/ros2/config.py:29`

**Issue:**
The `Ros2BridgeConfig.qos_profile` field defaults to `"sensor_data"` (per D-06), but `Ros2BridgeNode.__init__` calls `self.create_publisher(JointState, publisher_topic, 10)` — this uses the default QoS profile. The `qos_profile_sensor_data` profile (RELIABLE, KEEP_LAST(5)) is never applied.

**Fix:**
```python
# In bridge_node.py, after importing rclpy.qos:
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, qos_profile_sensor_data

# In __init__:
qos = qos_profile_sensor_data if bridge_cfg.qos_profile == "sensor_data" else 10
self._pub = self.create_publisher(JointState, publisher_topic, qos)
```
Wire the config value: pass it as a constructor argument or look up the named profile at construction time.

### WR-03: `batch_size` config field is unused — no batching implemented

**File:** `src/surg_rl/ros2/config.py:26`, `src/surg_rl/rl/environment.py:559–561`

**Issue:**
`Ros2BridgeConfig.batch_size` (default 1) is a declared field per D-20, but the bridge publishes on every `step()` call unconditionally. There is no buffering/accumulation logic that would respect `batch_size > 1`.

**Fix:**
Either implement batching (accumulate N states in a buffer, publish as a batch of N messages) or remove the field from the config schema if batching is deferred. If deferred, document clearly that `batch_size` is reserved for future use and currently defaults to 1 with no batching.

### WR-04: Configurable error strategies are not wired — hardcoded behavior

**File:** `src/surg_rl/ros2/config.py:35–39`, `src/surg_rl/ros2/bridge_node.py:190–230,247–280`

**Issue:**
Three configurable error-strategy fields (`on_nan_inf`, `on_dimension_mismatch`, `on_missing_topic`) are declared in `Ros2BridgeConfig` per D-25 and D-26, but the runtime behavior is hardcoded:

- `on_nan_inf: "raise"` — `publish_state()` always raises `ValueError` (never sanitizes)
- `on_dimension_mismatch: "zero"` — `_on_command()` always applies zero action (never warns)
- `on_missing_topic: "error"` — no check for missing counterpart topics exists (never fatal)

The config schema suggests pluggable strategies but the implementation doesn't read them.

**Fix:**
Pass the `Ros2BridgeConfig` (or its error-strategy fields) into `Ros2BridgeNode.__init__`. In `publish_state()`, read `self._on_nan_inf` and branch: `"raise"` → raise ValueError, `"sanitize"` → replace NaN→0.0 and Inf→limits. In `_on_command()`, read `self._on_dimension_mismatch` and branch: `"zero"` → zero action, `"warn"` → log warning and pass through.

### WR-05: `on_missing_topic` check never implemented

**File:** `src/surg_rl/ros2/bridge_node.py:161–163`, `src/surg_rl/ros2/config.py:32`

**Issue:**
Per D-24, the bridge should detect when the counterpart topic is missing at startup and either fail (`"error"`) or warn (`"warn"`). There is no startup check — if the subscriber topic doesn't exist, the bridge silently proceeds.

**Fix:**
Add a startup check in `_setup_bridge()` (or `Ros2Bridge.__init__`/`start()`):
```python
# After bridge starts, poll for available topics:
import rclpy
existing_topics = [name for name, _ in rclpy.get_topic_names_and_types()]
if bridge_cfg.command_topic not in existing_topics:
    if bridge_cfg.on_missing_topic == "error":
        raise RuntimeError(...)
    elif bridge_cfg.on_missing_topic == "warn":
        logger.warning(...)
```

### WR-06: Inconsistent logging — uses `logging.getLogger` instead of project-standard `get_logger`

**File:** `src/surg_rl/ros2/__init__.py:17`, `src/surg_rl/ros2/config.py:14`, `src/surg_rl/ros2/bridge_node.py:20`, `src/surg_rl/ros2/replay.py:17`

**Issue:**
All four ROS2 bridge modules use `logging.getLogger(__name__)` directly. Every other module in `src/surg_rl/` (16 modules in `rl/`, `simulators/`, `dynamics/`, `utils/`, `scene_definition/`, `scene_generation/`, `cli.py`) uses `from surg_rl.utils.logging import get_logger` — the project's Rich-enhanced logger with consistent formatting. The `ros2/` package breaks this convention.

**Fix:**
Replace `import logging` / `logger = logging.getLogger(__name__)` with:
```python
from surg_rl.utils.logging import get_logger
logger = get_logger(__name__)
```

---

## Info

### IN-01: Unused imports in `config.py`

**File:** `src/surg_rl/ros2/config.py:10`

**Issue:**
`ClassVar` and `Optional` are imported from `typing` but never used in the file. The Pydantic dataclass has no ClassVar fields, and all Optional-like behavior is handled by default values rather than `Optional[...]` annotations.

**Fix:**
Remove unused imports:
```python
# Before:
from typing import ClassVar, Optional
# After:
# (none needed; remove the line)
```

### IN-02: Unused import in `replay.py`

**File:** `src/surg_rl/ros2/replay.py:11`

**Issue:**
`import queue` is present at module level but neither the dummy `TrajectoryReplay` class nor the real implementation uses the `queue` module. The real class publishes directly via `rclpy`; it doesn't maintain a command queue at all.

**Fix:**
Remove `import queue` from `replay.py`.

### IN-03: String-annotation for `Ros2BridgeConfig` in `SurgicalEnvConfig`

**File:** `src/surg_rl/rl/environment.py:88`

**Issue:**
The `ros2_bridge_config` field is declared as `"Ros2BridgeConfig | None"` — a string forward-reference. While valid, it requires the actual `Ros2BridgeConfig` to be defined at module-import time (which `surg_rl.ros2` does via lazy imports). This is functional but slightly brittle: if the import order changes, this reference could break silently.

**Fix:**
Add an explicit import guard at the top of `environment.py`:
```python
from surg_rl.ros2.config import Ros2BridgeConfig  # noqa: E402
```
Then declare the field as `ros2_bridge_config: Ros2BridgeConfig | None = None`.

---

_Reviewed: 2026-05-03_
_Reviewer: OpenCode (gsd-code-reviewer)_
_Depth: deep_
