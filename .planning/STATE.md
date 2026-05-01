# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-29)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Phase 2 complete — proceeding to Phase 3

## Current Position

Phase: 3 of 5 (Simulator Robustness)
Plan: 0 of 2 planned
Status: Ready to execute
Last activity: 2026-04-30 — Phase 3 planned; 4 requirements mapped (PERF-01..PERF-04)

Progress: [██████████████░░░░░░░░] 40%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: ~15 minutes
- Total execution time: ~1.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Critical Bug Fixes | 3/3 | 3 | ~10 min |
| 2. Action Space + Gripper | 3/3 | 3 | ~20 min |

**Recent Trend:**
- Last plans: 02-01 (JOINT_TORQUES), 02-02/03 (IK + gripper + validation), 02 wrap-up
- Trend: parallel subagents for IK implementations, zero regressions across 567 tests

## Phase 2 Summary

### What was built

1. **JOINT_TORQUES (ACT-01)** — Implemented in both backends:
   - `ActionBuilder` no longer raises `NotImplementedError` for torque
   - MuJoCo: informational `set_action_mode("torque")`; ctrl write path unchanged (motor actuators)
   - PyBullet: `set_action_mode("torque")` disables default motors via `VELOCITY_CONTROL` force=0, then uses `TORQUE_CONTROL` in `_apply_action`
   - `SurgicalEnv` auto-propagates torque mode on init

2. **ENDEFFECTOR_POSE / ENDEFFECTOR_DELTA (ACT-02/03)** — IK-based control:
   - PyBullet: `_compute_ik()` via `calculateInverseKinematics` + `_apply_action_ik()` with pose/delta routing
   - MuJoCo: `_compute_ik()` with 1-DOF direct mapping + multi-DOF Jacobian-based damped least-squares IK + pose/delta routing in `_apply_action`
   - `set_action_mode()` propagates pose/delta from `SurgicalEnv` to simulators

3. **Gripper (ACT-04)** — Auto-detection + end-to-end:
   - `SurgicalEnv._default_action_config()` queries simulator `_control_map` for `is_gripper`, or falls back to scene `robot.end_effectors`
   - `num_joints` = total_controls - gripper_count when gripper present
   - Tests verify explicit gripper config, MuJoCo/PyBullet step with gripper, and auto-detection from scene

4. **Validation (ACT-05)** — Load-time guards:
   - Empty `unsupported_types = ()` allow-list since all ActionTypes are now implemented
   - Guard is ready for future unsupported types without structural changes
   - Tests verify ENDEFFECTOR_POSE and ENDEFFECTOR_DELTA do not raise on init

### Commits

- `3ebbe9f` — ACT-01: JOINT_TORQUES
- `ea032de` — ACT-04/05: gripper + validation
- `6a6f924` — ACT-02/03: end-effector IK in MuJoCo + updated validation
- `(parallel)` — ec681ab, 01e10bf: PyBullet IK via subagent

*Updated: 2026-04-30*
