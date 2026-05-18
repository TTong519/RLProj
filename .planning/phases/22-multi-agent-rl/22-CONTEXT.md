# Phase 22: Multi-Agent RL — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Dual-arm PettingZoo ParallelEnv with surgeon and assistant arm coordination, SuperSuit SB3 wrappers for both shared and independent policy training, implemented as a thin adapter layer over the canonical SurgicalEnv — zero simulation logic is duplicated.
</domain>

<decisions>
## Implementation Decisions

### Dual-arm scene construction
- **D-01:** Two `RobotConfig` entries in `SceneDefinition` for dual-arm scenes — reuses the existing scene_builder path for robot construction without inventing a new mechanism
- **D-02:** Swappable roles — either arm can be surgeon or assistant, determined by a `role` field in the multi-agent config, not hardcoded by robot name
- **D-03:** `MultiAgentConfig` section in `SceneDefinition` (multi_agent: {arms: [{role: 'surgeon'|'assistant', robot_ref: 'robot_1'}, ...]}) keeps dual-arm configuration separate from single-arm scenes

### Action/observation space design
- **D-04:** Per-agent filtered observation via key mapping — the full `Observation` dataclass is computed once per step, then each agent receives a filtered subset of keys defined by a per-agent `observation_keys` list
- **D-05:** RobotConfig-driven action spaces — action dimensions are auto-computed from each RobotConfig's DOF count, no role-based presets required

### PettingZoo ↔ SB3 integration
- **D-06:** SuperSuit wrappers (`pettingzoo_env_to_vec_env_v1` + `concat_vec_envs_v1`) as the canonical conversion pipeline
- **D-07:** Shared policy: single SB3 model trains both agents via converted VecEnv. Independent policy: two parallel SB3 models, each with its own per-agent VecEnv conversion
- **D-08:** Parallel `learn()` threads for independent policy training — each agent's SB3 model runs `learn()` concurrently in its own thread, sharing the same env instance

### Thin adapter design
- **D-09:** Parallel action injection via extended `apply_action(action, arm_id=None)` on `BaseSimulator` — default `None` applies to all arms (backward compatible), `arm_id='surgeon'` applies only to that arm
- **D-10:** Per-agent reward routing — `compute()` runs once, the adapter distributes reward components: task-specific reward goes to the surgeon arm, positioning/camera reward goes to the assistant arm
- **D-11:** Pure passthrough composition — `MultiAgentSurgicalEnv` owns exactly ONE `SurgicalEnv` instance and delegates all simulation logic to it, never subclasses `SurgicalEnv`

### OpenCode's Discretion
- Exact `MultiAgentConfig` Pydantic schema fields and validation
- Per-agent `observation_keys` filter implementation (key mapping from full Observation to per-agent subset)
- SuperSuit wrapper chain details (ordering, shape transformations)
- Thread coordination for parallel `learn()` loops (synchronization, env thread-safety)
- `apply_action(arm_id)` implementation in both MuJoCo and PyBullet backends
- MultiAgentTrainingManager CLI integration and entry point
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 22 — success criteria (MARL-01..MARL-04)
- `.planning/REQUIREMENTS.md` — MARL-01 through MARL-04 requirements

### Schema contracts (from Phase 19)
- `src/surg_rl/scene_definition/schema.py` — `TaskConfig`, `MultiAgentConfig` (has `shared_policy: bool`, `num_agents: int`), `RobotConfig`

### Existing RL infrastructure
- `src/surg_rl/rl/environment.py` — `SurgicalEnv` (reset, step, reward computation), `check_task_success()`
- `src/surg_rl/rl/observation.py` — `ObservationBuilder`, `ObservationSpaceSpec`
- `src/surg_rl/rl/rewards.py` — `BaseRewardFunction`, `CompositeReward`, 6 task reward subclasses
- `src/surg_rl/rl/task_reward_router.py` — `TaskRewardRouter`, `TASK_REWARD_REGISTRY`
- `src/surg_rl/rl/task_results.py` — `TaskResult` hierarchy, `TASK_RESULT_MAP`

### Simulator contracts
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator.apply_action(action)`, `Observation`, `step()` interface
- `src/surg_rl/simulators/scene_builder.py` — MJCF/URDF generation from SceneDefinition

### Prior phase context
- `.planning/phases/19-schema-foundation/19-CONTEXT.md` — `MultiAgentConfig` model spec, lazy import pattern
- `.planning/phases/20-real-surgical-assets/20-CONTEXT.md` — Real instrument mesh loading for dual-arm scenes
- `.planning/phases/21-surgical-task-curriculum/21-CONTEXT.md` — TaskRewardRouter, check_success/check_failure contracts

### External docs
- PettingZoo ParallelEnv API: https://pettingzoo.farama.org/api/parallel/
- SuperSuit SB3 integration: https://pettingzoo.farama.org/tutorials/sb3/
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`SurgicalEnv`**: Full RL environment with simulator + controller + observation/action builders — the sole simulation source MultiAgentSurgicalEnv delegates to
- **`CompositeReward`**: Already accepts list of `BaseRewardFunction` with weights — per-agent reward routing can inject different component lists per agent
- **`TaskRewardRouter.build(task_type)`**: Returns `list[BaseRewardFunction]` — adapter can build separate reward lists per agent role
- **`ObservationBuilder`**: Already maps `Observation` dataclass to `gym.spaces.Dict` — per-agent filtering can work at this level
- **`SceneBuilder` + `scene_builder.py`**: Already generates MJCF/URDF from `SceneDefinition.robots[]` — dual-arm scenes flow through the same path

### Established Patterns
- **Strategy pattern (BaseSimulator ABC)**: Extend `apply_action()` with optional `arm_id` parameter — zero breaking changes
- **Pydantic v2 schema-first**: `MultiAgentConfig` already exists in schema.py from Phase 19 — extend with arm role configuration
- **Composite controller pattern**: `EnvironmentController` composes curriculum/randomization/adaptive controllers — multi-agent training manager follows same composition pattern
- **Lazy imports**: `src/surg_rl/marl/__init__.py` has `LazyImport` guard for pettingzoo — no import-time dependency

### Integration Points
1. **SceneDefinition → SceneBuilder**: MultiAgentConfig section must be in SceneDefinition for scene files to remain the single source of truth
2. **SurgicalEnv → MultiAgentSurgicalEnv**: Adapter wraps SurgicalEnv, mapping `action_dict` → per-arm `apply_action()` calls
3. **ObservationBuilder → Per-agent filtering**: Full observation computed once, then filtered per agent via `observation_keys` mapping
4. **SB3 training loop → MultiAgentTrainingManager**: Orchestrates shared vs independent policy training, SuperSuit wrapper chains
5. **CLI → `surg-rl marl-train`**: New CLI subcommand for multi-agent training entrypoint
</code_context>

<specifics>
## Specific Ideas

No specific UX/visual references — Phase 22 is pure infrastructure (env adapter + training loop), no user-facing UI beyond CLI.

### Key architectural constraints
- Zero simulation logic duplication — `MultiAgentSurgicalEnv` is strictly an adapter layer
- Backward compatible `apply_action(action, arm_id=None)` — existing single-arm code works unchanged
- `MultiAgentConfig` is additive to `SceneDefinition` — single-arm scenes don't reference it
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 22-Multi-Agent RL*
*Context gathered: 2026-05-18*
