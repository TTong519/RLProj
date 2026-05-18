# Phase 22: Multi-Agent RL — Discussion Log

**Gathered:** 2026-05-18
**Status:** Complete

## Areas Discussed

### 1. Dual-arm scene construction

| Question | Options | Selection | Notes |
|----------|---------|-----------|-------|
| How should dual-arm scene be constructed? | Two RobotConfig entries / One robot + static assistant / Programmatic | **Two RobotConfig entries** | Reuses existing scene_builder path |
| Fixed roles or swappable? | Fixed / Swapable / Symmetric | **Swapable roles** | Role determined by config, not robot name |
| Config location? | MultiAgentConfig in SceneDefinition / RobotConfig.role field / Constructor-only | **MultiAgentConfig in SceneDefinition** | Scene files remain single source of truth |

### 2. Action/observation space design

| Question | Options | Selection | Notes |
|----------|---------|-----------|-------|
| Per-agent observation strategy? | Filtered subset / Shared full / Separate pipelines | **Per-agent filtered observation** | Full Observation computed once, sliced per agent via key mapping |
| Per-agent action spaces? | Asymmetric per-role / Symmetric same-dim / RobotConfig-driven | **RobotConfig-driven** | Action dimensions auto-computed from RobotConfig DOF |
| Reuse ObservationBuilder? | Reuse / Per-agent mapping | **Per-agent observation mapping** | Per-agent observation_keys list defines filtered subset |

### 3. PettingZoo ↔ SB3 integration

| Question | Options | Selection | Notes |
|----------|---------|-----------|-------|
| Conversion pipeline? | SuperSuit / Custom Gym wrapper / Built-in .to_sb3() | **SuperSuit** | pettingzoo_env_to_vec_env_v1 + concat_vec_envs_v1 |
| Shared vs independent training? | Wrapper per mode / Shared only / Deferred | **Wrapper per policy mode** | Both shared and independent paths supported |
| Independent policy coordination? | Sequential learn() / Parallel threads / Deferred | **Parallel learn() threads** | Both agents learn concurrently in separate threads |

### 4. Thin adapter design

| Question | Options | Selection | Notes |
|----------|---------|-----------|-------|
| Action routing strategy? | Concatenated vector / Sequential steps / Parallel injection | **Parallel action injection** | apply_action per arm, single physics step |
| apply_action API? | Extend with arm_id / Pre-assembled vector | **Extend apply_action** | arm_id=None default (backward compat) |
| Reward assignment? | Per-agent routing / Shared reward | **Per-agent reward routing** | Task-specific to surgeon, positioning to assistant |
| Delegation pattern? | Pure passthrough composition / Subclass SurgicalEnv | **Pure passthrough composition** | Owns SurgicalEnv instance, never subclasses |

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 22-Multi-Agent RL*
*Discussion completed: 2026-05-18*
