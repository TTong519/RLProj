---
phase: 02-action-space-gripper
plan: 02
subsystem: simulators
type: execute
requires: [02-01]
provides: [ACT-02, ACT-03]
tags: [ik, inverse-kinematics, end-effector, pose, delta, mujoco, pybullet]
dependency_graph:
  requires: [02-01]
  provides: [ACT-02, ACT-03]
  affects:
    - src/surg_rl/simulators/mujoco_simulator.py
    - src/surg_rl/simulators/pybullet_simulator.py
    - src/surg_rl/rl/action.py
    - src/surg_rl/rl/environment.py
    - tests/test_simulators.py
    - tests/test_rl_environment.py
decisions:
  - "PyBullet IK uses calculateInverseKinematics with last-link-as-EE heuristic for primitive robots"
  - "PyBullet: endeffector_pose = absolute target; endeffector_delta = relative offset from current base pose"
  - "MuJoCo 1-DOF: pitch Euler angle mapped directly to hinge joint via sin/cos"
  - "MuJoCo multi-DOF: Jacobian-based damped least-squares via mj_jacBody + SVD regularization (α=0.5, λ=0.1)"
  - "ActionBuilder NotImplementedError removed entirely — all 7 ActionTypes now supported"
  - "Both modes fail gracefully to current joint state on any IK failure"
metrics:
  duration_minutes: 25
  tasks_completed: 3
  files_modified: 5
  lines_added: ~335
  lines_removed: 4
---

# Phase 02 Plan 02: ENDEFFECTOR_POSE/DELTA IK — Summary

**One-liner:** Implemented inverse kinematics (IK) for `ENDEFFECTOR_POSE` and `ENDEFFECTOR_DELTA` action types in both MuJoCo and PyBullet simulators, and removed all remaining `NotImplementedError` guards from `ActionBuilder`.

## What was built

### 1. PyBullet IK (subagent + manual merge)

- **`_compute_ik(robot_name, target_pos, target_quat)`** in `pybullet_simulator.py`
  - Looks up robot `body_id` from `self._body_ids`
  - Computes EE link index as `num_joints - 1`
  - Calls `calculateInverseKinematics` with position + optional orientation target
  - Returns `np.ndarray` of joint angles; on error returns current joint state as fallback

- **`_apply_action_ik(action)`** in `pybullet_simulator.py`
  - Parses action vector `[px, py, pz, rx, ry, rz, (gripper)]`
  - `endeffector_delta`: adds position delta to current base pose, Euler delta to current orientation
  - `endeffector_pose`: treats action as absolute target position + Euler angles
  - Converts Euler to quaternion via `getQuaternionFromEuler`
  - Calls `_compute_ik()` then applies joint angles via `POSITION_CONTROL`

- **`_apply_action` dispatch**: pose/delta modes call `_apply_action_ik()`

- **Subagent**: `ses_21fe1e043ffeUvUPRW5btcLOrI` produced commits `ec681ab` and `01e10bf`

### 2. MuJoCo IK (manual implementation)

- **`set_action_mode("endeffector_pose")` / `set_action_mode("endeffector_delta")`** with dual strategy:
  - **1-DOF primitive**: pitch Euler angle mapped directly to hinge joint via sin/cos; X/Z position via linear mapping
  - **Multi-DOF**: Jacobian-based damped least-squares via `mj_jacBody` + SVD regularization (α=0.5, λ=0.1)
  - Gracefully falls back to current joint state on any error

- **`_apply_action` routing**: pose/delta modes call `_compute_ik()` then write resulting joint angles to `self._data.ctrl`

### 3. ActionBuilder cleanup

- Removed the entire `NotImplementedError` block from `process_action`
- All 7 `ActionType` values now pass through without error

### 4. Tests

- `tests/test_simulators.py`:
  - `test_endeffector_pose_action_sets_joint_targets` (PyBullet)
  - `test_endeffector_delta_action_sets_joint_targets` (PyBullet)
  - `test_endeffector_pose_ik_no_crash` (MuJoCo)
  - `test_endeffector_delta_ik_no_crash` (MuJoCo)
- `tests/test_rl_environment.py`:
  - `test_endeffector_pose_does_not_raise` (end-to-end MuJoCo)
  - `test_endeffector_delta_does_not_raise` (end-to-end MuJoCo)

## Deviations from Plan

- PyBullet IK was partially completed during 02-01 execution (subagent commits). Remainder merged into 02-02.
- Subagent for MuJoCo IK (`ses_21fe1e050ffeeeaySv4HeF7La5`) returned empty result; agent finished manually instead of retrying.

## Known Stubs

- `get_end_effector_pose` returns base pose, not actual EE link pose
- PyBullet IK uses base position as current pose for delta calculations (acceptable for 1-DOF primitives, needs `getLinkState` for URDFs)

## Threat Flags

No new threats. IK computation is local to simulators.

## Self-Check: PASSED

- [x] `src/surg_rl/rl/action.py` no longer raises for any ActionType
- [x] `src/surg_rl/simulators/pybullet_simulator.py` contains `_compute_ik`, `_apply_action_ik`
- [x] `src/surg_rl/simulators/mujoco_simulator.py` contains `_compute_ik`, Jacobian IK, pose/delta routing
- [x] `tests/test_simulators.py -k endeffector` passes
- [x] `tests/test_rl_environment.py::TestActionTypeValidation` passes
- [x] Commits: `ec681ab`, `01e10bf`, `6a6f924`
