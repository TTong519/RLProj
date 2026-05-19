---
status: complete
phase: 22-multi-agent-rl
source:
  - 22-01-SUMMARY.md
  - 22-02-SUMMARY.md
  - 22-03-SUMMARY.md
started: 2026-05-18T12:00:00Z
updated: 2026-05-18T12:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Schema — ArmRole, ArmConfig, MultiAgentConfig import and validation
expected: |
  ArmRole.SURGEURON == "surgeon", ArmRole.ASSISTANT == "assistant".
  ArmConfig(role="surgeon", robot_ref="r1") validates.
  ArmConfig(role="invalid") raises ValidationError.
  MultiAgentConfig(arm_configs=[...]) with duplicate roles raises ValidationError.
result: pass

### 2. SceneDefinition.multi_agent field + cross-validation
expected: |
  SceneDefinition has multi_agent: MultiAgentConfig | None = None field.
  SceneDefinition with multi_agent pointing to missing robot_ref raises ValidationError.
  SceneDefinition with multi_agent=None validates (single-arm backward compat).
  JSON round-trip preserves MultiAgentConfig.
result: pass

### 3. apply_action(arm_id=None) backward compat + per-arm routing
expected: |
  apply_action(action, arm_id=None) works (applies to all joints).
  apply_action(action, arm_id="surgeon") routes to correct arm.
  apply_action(action, arm_id="nonexistent") raises ValueError.
result: pass

### 4. MultiAgentSurgicalEnv ParallelEnv contract
expected: |
  MultiAgentSurgicalEnv imports as ParallelEnv subclass.
  env.reset() returns ({agent_id: obs}, {agent_id: info}) dicts.
  env.agents == ["surgeon", "assistant"].
  env.step({"surgeon": a1, "assistant": a2}) returns 5-tuple.
result: pass
issue: "Missing ParallelEnv inheritance — MultiAgentSurgicalEnv was a bare class, causing isinstance and SuperSuit compatibility failures. Fixed by adding lazy dynamic base class resolution (8e89ead)."

### 5. ObservationFilter + per-agent reward routing
expected: |
  Surgeon observation differs from assistant observation (filtered by observation_keys).
  Reward dict has separate values for surgeon and assistant.
  env owns exactly ONE SurgicalEnv (isinstance check: NOT SurgicalEnv, has _surgical_env).
result: pass

### 6. SuperSuit wrappers + MultiAgentTrainingManager
expected: |
  wrap_for_sb3(env) returns VecEnv that SB3 can use.
  MultiAgentTrainingManager(env).train() dispatches to shared/independent.
  _train_shared() creates single model; _train_independent() uses threads.
result: pass

### 7. CLI surg-rl marl-train command
expected: |
  surg-rl marl-train --help shows options (--scene, --algorithm, --policy, --timesteps).
  surg-rl marl-train --policy invalid exits with error.
result: pass

### 8. Full test suite passes (945 tests)
expected: |
  PYTHONPATH=src python -m pytest tests/ -m "not integration" -x -q runs 945 tests, 0 failures.
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
