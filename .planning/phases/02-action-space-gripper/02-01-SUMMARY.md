---
phase: 02
plan: 01
subsystem: simulators
requires: [01-01, 01-02, 01-03]
provides: [ACT-01, ACT-02]
tags: [pybullet, ik, action-space, simulator]
tech-stack:
  added: []
patterns:
  - "_action_mode routing in _apply_action for IK modes"
  - "calculateInverseKinematics with graceful fallback"
dependency_graph:
  requires: [01-01, 01-02, 01-03]
  provides: [ACT-02, ACT-03]
  affects: [tests/test_simulators.py]
key-files:
  created: []
  modified:
    - src/surg_rl/simulators/pybullet_simulator.py
    - tests/test_simulators.py
decisions:
  - "IK link index = num_joints - 1 (last link as end-effector for primitive robots)"
  - "calculateInverseKinematics availability checked via hasattr(self._pb, ...)"
  - "Euler angle input converted to quaternion via getQuaternionFromEuler"
  - "Delta mode adds action to current base pose; pose mode uses absolute values"
  - "Joint angles applied in joint-index order to match IK output ordering"
  - "Gripper target optionally appended as 7th action dimension"
metrics:
  duration_minutes: 15
  tasks_completed: 1
  files_modified: 2
  lines_added: ~150
  lines_removed: 2
---

# Phase 02 Plan 01: PyBullet IK Action Space Support — Summary

**One-liner:** Implemented inverse kinematics (IK) control for PyBullet simulator backend, supporting `endeffector_pose` and `endeffector_delta` action modes via `calculateInverseKinematics` with graceful error fallback.

## What was built

1. **`_compute_ik(robot_name, target_pos, target_quat)`** in `pybullet_simulator.py`
   - Looks up robot `body_id` from `self._body_ids`
   - Computes end-effector link index as `num_joints - 1`
   - Calls `calculateInverseKinematics` with position and optional orientation target
   - Returns `np.ndarray` of joint angles; on any error (missing API, IK failure), returns current joint state as fallback
   - Verified `hasattr(self._pb, 'calculateInverseKinematics')` before use

2. **`set_end_effector_target(position, orientation)`** in `pybullet_simulator.py`
   - Stores target pose in `self._endeffector_target_pos` and `self._endeffector_target_quat`

3. **`_apply_action` routing** in `pybullet_simulator.py`
   - Added early dispatch: if `_action_mode` is `endeffector_pose` or `endeffector_delta`, calls `_apply_action_ik(action)`

4. **`_apply_action_ik(action)`** in `pybullet_simulator.py`
   - Parses action vector `[px, py, pz, rx, ry, rz, (gripper)]`
   - For `endeffector_delta`: adds position delta to current base pose, adds Euler delta to current orientation
   - For `endeffector_pose`: treats action values as absolute target position + Euler angles
   - Converts Euler to quaternion via `getQuaternionFromEuler`
   - Calls `_compute_ik()` to get joint angles
   - Applies joint angles to all non-gripper joints via `setJointMotorControl2(POSITION_CONTROL)`
   - Applies optional gripper target if present in action and gripper joint exists

5. **Tests** in `test_simulators.py` (class `TestPyBulletSimulator`)
   - `test_endeffector_pose_action_sets_joint_targets`: Loads suturing scene, sets mode to `endeffector_pose`, applies zero action → passes without crash
   - `test_endeffector_delta_action_sets_joint_targets`: Same for `endeffector_delta`

## Deviations from Plan

None — plan executed exactly as instructed by user.

## Known Stubs

- `get_end_effector_pose` still returns base pose (not actual EE link pose). This was explicitly out of scope for this task.
- `_endeffector_target_pos/quat` are stored but not consumed by `_apply_action_ik`; the full target is computed from current pose + action instead.

## Threat Flags

No new threat surface introduced. IK computation is local to the simulator and does not add network endpoints, file I/O, or auth paths.

## Self-Check: PASSED

- [x] `src/surg_rl/simulators/pybullet_simulator.py` exists and contains `_compute_ik`, `_apply_action_ik`, `set_end_effector_target`
- [x] `tests/test_simulators.py` contains `test_endeffector_pose_action_sets_joint_targets` and `test_endeffector_delta_action_sets_joint_targets`
- [x] Commit `ec681ab` (feat) and `01e10bf` (test) verified via `git log`
- [x] Full test suite `tests/test_simulators.py` passes: 64 passed, 1 xfailed, 3 xpassed
