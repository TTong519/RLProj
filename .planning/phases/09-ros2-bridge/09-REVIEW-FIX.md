---
phase: 09-ros2-bridge
fixed_at: 2026-05-03T00:00:00Z
review_path: .planning/phases/09-ros2-bridge/09-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 09: ROS2 Bridge Code Review Fix Report

**Fixed at:** 2026-05-03
**Source review:** .planning/phases/09-ros2-bridge/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10
- Fixed: 6
- Already fixed (pre-existing in source): 4
- Skipped: 0

## Fixed Issues

### CR-01: `queue.Queue` is not process-safe — external commands never reach main process

**Files modified:** `src/surg_rl/ros2/bridge_node.py`
**Commit:** cf38d9e
**Applied fix:** Replaced `queue.Queue(maxsize=1)` fallback with `multiprocessing.Queue(maxsize=1)` in both the dummy implementation (line 69) and real implementation (line 178). The `_setup_bridge()` method in `environment.py` already creates a `multiprocessing.Queue` and injects it — these fallbacks ensure consistent behavior when no queue is provided.

### WR-03: `batch_size` config field is unused — no batching implemented

**Files modified:** `src/surg_rl/ros2/config.py`
**Commit:** 6d95a09
**Applied fix:** Added comment `# reserved for future batching (always 1 per step)` on the `batch_size` field declaration. Batching is complex and deferred; the field is retained in the schema for future use.

### WR-06: Inconsistent logging — uses `logging.getLogger` instead of project-standard `get_logger`

**Files modified:** `src/surg_rl/ros2/__init__.py`, `src/surg_rl/ros2/config.py`, `src/surg_rl/ros2/bridge_node.py`, `src/surg_rl/ros2/replay.py`
**Commit:** ac91341
**Applied fix:** Replaced `import logging` / `logger = logging.getLogger(__name__)` with `from surg_rl.utils.logging import get_logger` / `logger = get_logger(__name__)` in all four ROS2 bridge modules. This aligns with the project-wide Rich-enhanced logger.

### IN-01: Unused imports in `config.py`

**Files modified:** `src/surg_rl/ros2/config.py`
**Commit:** 9c63141
**Applied fix:** Removed unused `ClassVar` and `Optional` imports from the `typing` import line. Neither is referenced anywhere in the file.

### IN-02: Unused import in `replay.py`

**Files modified:** `src/surg_rl/ros2/replay.py`
**Commit:** ac91341
**Applied fix:** Removed `import queue` from replay.py (bundled in WR-06 commit). The real implementation publishes via `rclpy` and does not use the `queue` module.

### IN-03: String-annotation for `Ros2BridgeConfig` in `SurgicalEnvConfig`

**Files modified:** `src/surg_rl/rl/environment.py`
**Commit:** cc25a71
**Applied fix:** Added explicit import `from surg_rl.ros2.config import Ros2BridgeConfig` at module level. Changed `ros2_bridge_config: "Ros2BridgeConfig | None"` to `ros2_bridge_config: Ros2BridgeConfig | None` and `config: "Ros2BridgeConfig"` to `config: Ros2BridgeConfig` in the `Ros2Bridge.__init__` signature. This provides static type-checker confidence without relying on lazy import ordering.

## Pre-Existing Fixes (already applied in source)

The following findings were already addressed in the source code at review time:

- **WR-01** (`frame_id`): Already wired from `_setup_bridge()` through `Ros2BridgeNode.__init__` and used in `publish_state()` at line 248.
- **WR-02** (`qos_profile`): Already wired; `qos_profile` resolved to `qos_profile_sensor_data` at construction (line 180-182) and used when creating the publisher.
- **WR-04** (error strategies): `on_nan_inf` and `on_dimension_mismatch` already wired from config into `publish_state()` (lines 236-244) and `_on_command()` (lines 287-302) with branching logic.
- **WR-05** (`on_missing_topic`): Startup check already implemented in `Ros2Bridge.start()` (lines 876-897) using `rclpy.get_topic_names_and_types()` with `"error"`/`"warn"` branching.

---

_Fixed: 2026-05-03_
_Fixer: OpenCode (gsd-code-fixer)_
_Iteration: 1_
