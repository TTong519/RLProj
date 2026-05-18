---
phase: 22-multi-agent-rl
plan: 02
subsystem: marl + simulators
tags: [pettingzoo, parallelenv, arm-id, action-routing, observation-filter, reward-splitting]
depends_on:
  requires: ["22-01"]
  provides: [arm-id-routing, multi-agent-surgical-env, observation-filter, reward-splitting]
  affects: ["22-03"]
tech-stack:
  added: []
  patterns: [passthrough-composition, arm-id-routing, per-agent-filtering]
key-files:
  created:
    - src/surg_rl/marl/multi_agent_env.py
    - src/surg_rl/marl/observation_filter.py
    - tests/test_multi_agent_env.py
  modified:
    - src/surg_rl/simulators/base_simulator.py
    - src/surg_rl/simulators/mujoco_simulator.py
    - src/surg_rl/simulators/pybullet_simulator.py
metrics:
  duration: "~10min"
  completed_date: "2026-05-18"
---

# Phase 22 Plan 02: MultiAgentSurgicalEnv + arm_id routing

**One-liner:** PettingZoo ParallelEnv passthrough adapter over SurgicalEnv with per-arm action routing, observation filtering, and reward splitting.

## Tasks Executed

| # | Name | Type | Commit | Result |
|---|------|------|--------|--------|
| 1 | Extend BaseSimulator.apply_action with arm_id + per-backend routing | tdd | 7163107, c6db6c6 | arm_id=None backward compat, per-arm routing in MuJoCo + PyBullet |
| 2 | Implement MultiAgentSurgicalEnv + ObservationFilter | tdd | 65c6ea5 | ParallelEnv contract, passthrough delegation, per-agent obs/action/reward |

## Decisions Made
- D-09: arm_id injected into apply_action() with None default — backward compatible
- D-10: Per-agent reward routing — surgeon gets task reward, assistant gets positioning
- D-11: Pure composition — MultiAgentSurgicalEnv owns SurgicalEnv, never subclasses
- D-04: ObservationFilter maps per-agent observation_keys to filtered observation dicts
- D-05: Action spaces auto-computed from RobotConfig DOF counts

## Deviations
- Task 2 files created but not committed by executor — rescued by orchestrator

---
*Phase: 22-Multi-Agent RL*
*Plan: 02*
*Completed: 2026-05-18*
