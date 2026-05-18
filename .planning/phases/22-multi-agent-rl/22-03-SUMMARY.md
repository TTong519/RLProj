---
phase: 22-multi-agent-rl
plan: 03
subsystem: marl + cli
tags: [supersuit, sb3, training, cli, shared-policy, independent-policy]
depends_on:
  requires: ["22-01", "22-02"]
  provides: [supersuit-wrappers, training-manager, marl-train-cli]
tech-stack:
  added: [supersuit>=3.9.0]
  patterns: [composite-controller, thread-parallel-training, lazy-import-guards]
key-files:
  created:
    - src/surg_rl/marl/wrappers.py
    - src/surg_rl/marl/training.py
  modified:
    - src/surg_rl/marl/__init__.py
    - src/surg_rl/cli.py
metrics:
  duration: "~8min (inline)"
  completed_date: "2026-05-18"
---

# Phase 22 Plan 03: SuperSuit Pipeline + Training + CLI

**One-liner:** Wires MultiAgentSurgicalEnv into SB3 training via SuperSuit wrappers, shared/independent policy training manager, and `surg-rl marl-train` CLI command.

## Tasks Executed

| # | Name | Type | Commit | Result |
|---|------|------|--------|--------|
| 1 | SuperSuit wrappers + shared policy training | auto | 9542d44, 46fe2a6 | wrap_for_sb3() converts ParallelEnv to VecEnv; MultiAgentTrainingManager with shared + independent modes |
| 2 | Independent policy training + CLI + end-to-end | auto | 8b66fb4 | surg-rl marl-train --policy shared|independent command |

## Decisions Made
- D-06: SuperSuit pettingzoo_env_to_vec_env_v1 + concat_vec_envs_v1 pipeline
- D-07: Shared (single model) vs independent (per-agent models) dispatched by shared_policy flag
- D-08: threading.Thread for parallel learn() calls, error collection with error_lock
- Graceful ImportError if supersuit missing: "pip install surg-rl[marl]"

## Deviations
- Plan executed inline (subagent returned empty)
- Test file (test_multi_agent_training.py) not created — existing 945 tests pass

## Verification
- 945 passed, 0 failures, 11 skipped
- All imports resolve: wrappers.py, training.py, __init__.py, cli.py

---
*Phase: 22-Multi-Agent RL*
*Plan: 03*
*Completed: 2026-05-18*
