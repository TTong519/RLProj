# Phase 25: Fix MARL Runtime Wiring — Context

**Gathered:** 2026-06-10
**Status:** Ready for planning
**Source:** v0.4.0 milestone audit (`v0.4.0-MILESTONE-AUDIT.md`) — all decisions extracted from the audit's "Critical Issues to Fix" section.

<domain>
## Phase Boundary

Close the runtime wiring gaps in Phase 22 (Multi-Agent RL) identified by the v0.4.0 milestone audit. Make the `surg-rl marl-train` CLI runnable end-to-end, fix the broken `env.step()` path, complete the public scene_definition API surface, and verify the integration test suite passes. The MARL-04 requirement (thin adapter over SurgicalEnv) is moved from Phase 22 → Phase 25 in the REQUIREMENTS.md traceability table.
</domain>

<decisions>
## Implementation Decisions

### MARL step() wiring fix
- **D-01:** Add a `passthrough_step()` method to `SurgicalEnv` (in `src/surg_rl/rl/environment.py`) that steps the simulator using actions already applied via `simulator.apply_action(action, arm_id=...)` and returns the env-style `(obs, reward, terminated, truncated, info)` tuple. This method MUST NOT re-process actions through the action builder — per-arm targets are already set on the simulator.
- **D-02:** Refactor `SurgicalEnv.step()` to delegate its simulator+observation+reward body to the same internal helper that `passthrough_step()` uses. Avoid duplicating logic between the two step paths.
- **D-03:** Replace `self._surgical_env.step(np.zeros(0))` at `src/surg_rl/marl/multi_agent_env.py:320-322` with `self._surgical_env.passthrough_step()`. Per-arm actions are already applied via the loop on lines 313-317.
- **D-04:** Initialize `self.agents` and `self.possible_agents` in `MultiAgentSurgicalEnv.__init__` so the property works after construction (PettingZoo contract). The current code only sets `self.agents` in `reset()`, breaking `test_env_agents_property`.

### MARL CLI constructor fix
- **D-05:** Update `src/surg_rl/cli.py:597` (`surg-rl marl-train`) to construct `MultiAgentSurgicalEnv` correctly. The constructor expects `config: dict[str, Any] | None`, so pass `{"scene_path": scene, "simulator_type": simulator, "render_mode": render_mode, "seed": seed}`. Drop the `render_mode=render_mode` kwarg (constructor does not accept it).
- **D-06:** Verify the surgical env's render_mode kwarg reaches `SurgicalEnvConfig` through the dict (it already does — `_create_surgical_env` reads `config.get("render_mode")`).

### Public API completeness
- **D-07:** Export `ArmConfig` and `ArmRole` from `src/surg_rl/scene_definition/__init__.py` top-level `__all__` and re-export import block. Currently only `MultiAgentConfig` is exported — `ArmConfig` and `ArmRole` are accessible only via deep import from `.schema`.

### Verification
- **D-08:** The 4 failing integration tests in `tests/test_multi_agent_env.py` (`test_env_agents_property`, `test_env_step_returns_5_tuple_of_dicts`, `test_reward_dict_separate_values`, `test_env_close_cleans_up`) MUST pass after this phase.
- **D-09:** `surg-rl marl-train --scene scenes/dual_arm_*.json --timesteps 100` MUST run end-to-end (no crash, no exception) on a dummy scene. Use a dual-arm scene JSON committed in the test fixture set (the test fixture already exists at `tests/test_multi_agent_env.py:420-474`).

### OpenCode's Discretion
- Exact method signature for `SurgicalEnv.passthrough_step()` (kwargs, return type, docstring wording)
- Refactor of `SurgicalEnv.step()` to share the internal helper (inline vs. private method)
- Whether to add a guard at `MultiAgentSurgicalEnv.step()` that checks `self.agents` is non-empty
- Test additions beyond fixing the 4 known failures (e.g., a unit test for `SurgicalEnv.passthrough_step()` in `tests/test_rl_environment.py`)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — MARL-04 requirement, traceability table
- `.planning/ROADMAP.md` § Phase 25 — success criteria
- `.planning/v0.4.0-MILESTONE-AUDIT.md` — gap evidence, line numbers, severity ratings

### Source artifacts (Phase 22)
- `src/surg_rl/marl/multi_agent_env.py` — broken step() at lines 282-350 (esp. 310-322); uninitialized `self.agents` (only set in reset())
- `src/surg_rl/marl/training.py` — `MultiAgentTrainingManager` (consumes env, no changes needed)
- `src/surg_rl/marl/observation_filter.py` — per-agent key filtering
- `src/surg_rl/marl/wrappers.py` — SuperSuit wrapper chain

### SurgicalEnv / RL environment
- `src/surg_rl/rl/environment.py` — `SurgicalEnv` class (lines 481-663 for reset/step)
- `src/surg_rl/rl/environment.py:544-663` — current step() body (action processing, simulator.step, observation, reward, info, fluid, bridge, controller)
- `src/surg_rl/rl/environment.py:775-819` — `_build_info` helper
- `src/surg_rl/rl/action.py` — `ActionBuilder.process_action` (rejects empty action)

### Simulator contracts
- `src/surg_rl/simulators/base_simulator.py:292-301` — `apply_action(action, arm_id=None)` contract
- `src/surg_rl/simulators/mujoco_simulator.py:767-884` — MuJoCo `_apply_action` with arm_id routing
- `src/surg_rl/simulators/pybullet_simulator.py:1489-1585` — PyBullet arm_id routing

### CLI
- `src/surg_rl/cli.py:580-616` — `marl-train` command (broken constructor call at line 597)
- `src/surg_rl/scene_definition/__init__.py` — top-level `__all__` and re-export block (missing `ArmConfig`, `ArmRole`)

### Schema
- `src/surg_rl/scene_definition/schema.py:101-105` — `ArmRole` enum
- `src/surg_rl/scene_definition/schema.py:1117-1131` — `ArmConfig` model
- `src/surg_rl/scene_definition/schema.py:1134-1163` — `MultiAgentConfig` model (already exported)

### Tests
- `tests/test_multi_agent_env.py:420-474` — `dual_arm_scene` fixture (dual-arm scene JSON writer)
- `tests/test_multi_agent_env.py:519-533` — `test_env_agents_property` (failing — needs D-04)
- `tests/test_multi_agent_env.py:536-567` — `test_env_step_returns_5_tuple_of_dicts` (failing — needs D-01/D-03)
- `tests/test_multi_agent_env.py:593-615` — `test_reward_dict_separate_values` (failing — needs D-01/D-03)
- `tests/test_multi_agent_env.py:618-635` — `test_env_close_cleans_up` (failing — needs D-01/D-03)

### Prior phase context
- `.planning/phases/22-multi-agent-rl/22-CONTEXT.md` — D-09 (arm_id routing), D-10 (per-agent reward routing), D-11 (passthrough composition)
- `.planning/phases/22-multi-agent-rl/22-02-SUMMARY.md` — Phase 22 plan 02 implementation record
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`SurgicalEnv.step()` body** (lines 555-663): action processing → simulator.step → observation → reward → info → fluid → bridge → controller. The body from line 572 onward (after `processed_action` is computed) is exactly what `passthrough_step()` needs.
- **`_build_info()`** (line 775): builds the env-style info dict — reused by `passthrough_step()`.
- **`MultiAgentSurgicalEnv.step()`** (lines 282-350): already applies per-arm actions via `simulator.apply_action(action, arm_id=agent_id)` (lines 313-317). The bug is the call to `self._surgical_env.step(np.zeros(0))` on line 320.
- **`MultiAgentConfig.arm_configs`**: list of `ArmConfig` (each with `role: ArmRole` and `robot_ref: str`) — already populated from scene JSON in `MultiAgentSurgicalEnv.__init__` (line 102-104).
- **`ActionBuilder.process_action()`** (line 313): the path that crashes on `np.zeros(0)` because action space bounds can't be broadcast against shape (0,).

### Established Patterns
- **Passthrough composition (D-11):** `MultiAgentSurgicalEnv` owns exactly ONE `SurgicalEnv` and delegates all sim logic. Adding a `passthrough_step()` method to `SurgicalEnv` honors this pattern — the MARL env stays a thin adapter, no sim logic is duplicated.
- **Backward-compatible kwarg (D-09):** `apply_action(action, arm_id=None)` — `None` applies to all arms, specific value routes to that arm. The `passthrough_step()` design follows the same additive-extension pattern.
- **Lazy imports in MARL:** `_get_parallel_env_base()` lazily imports `pettingzoo.ParallelEnv` — keeps marl optional without breaking the env.

### Integration Points
1. **`SurgicalEnv.passthrough_step()` (NEW)**: delegates to internal helper used by `step()`. Called only by `MultiAgentSurgicalEnv.step()`.
2. **`MultiAgentSurgicalEnv.__init__` (MODIFY)**: initialize `self.agents` from `self.possible_agents` so the property works after construction.
3. **`MultiAgentSurgicalEnv.step()` (MODIFY line 320-322)**: replace `self._surgical_env.step(np.zeros(0))` with `self._surgical_env.passthrough_step()`.
4. **`cli.py marl-train` (MODIFY line 597)**: pass dict config to `MultiAgentSurgicalEnv`, drop `render_mode` kwarg.
5. **`scene_definition/__init__.py` (MODIFY)**: add `ArmConfig`, `ArmRole` to imports and `__all__`.
</code_context>

<specifics>
## Specific Ideas

- **D-01 `passthrough_step()` shape**: it should accept no action argument (per-arm actions are already applied) and return `(obs_dict, reward, terminated, truncated, info)`. Internally it should call the simulator's `step()` with a properly-shaped no-op (size = number of controls, all zeros — which is the simulator's "hold current pose" state), then call `_build_info()` etc.
- **D-02 refactor approach**: extract a private `_step_simulator_and_build_outputs(self, sim_obs=None, sim_reward=None, sim_terminated=None, sim_truncated=None, sim_info=None)` helper that does lines 572-663 of the current step() body. `step()` calls `simulator.step(processed_action)` then the helper; `passthrough_step()` calls `simulator.step(np.zeros(num_controls))` then the helper. This avoids duplicating ~90 lines of obs/reward/info/fluid/bridge/controller code.
- **D-04 `self.agents` initialization**: set `self.agents = list(self.possible_agents)` in `__init__` after the `possible_agents` list is built (around line 104). This is the PettingZoo contract — `possible_agents` is the immutable set of all agents, `agents` is the active subset.
- **D-05 CLI fix shape**: change line 597 from `env = MultiAgentSurgicalEnv(config, render_mode=render_mode)` to `env = MultiAgentSurgicalEnv({**config.model_dump(), "render_mode": render_mode, "seed": seed})` or build a plain dict explicitly. Use a plain dict — avoid relying on `SurgicalEnvConfig.model_dump()` quirks.
- **D-07 export shape**: add `from .schema import ArmConfig, ArmRole` to the import block, then add `"ArmConfig"`, `"ArmRole"` entries to `__all__` in the appropriate section (under "Robot" or a new "Multi-agent" section).
</specifics>

<deferred>
## Deferred Ideas

- DreamerV3 training bugs (`indig` typo, subprocess pipe, color) — Phase 26
- Benchmark scene coverage (5 missing task scenes) — Phase 27
- Retroactive VERIFICATION.md for Phases 21-23 + REQUIREMENTS.md checkbox sync — Phase 28
- Re-running the v0.4.0 milestone audit to confirm `passed` status — after Phase 28 closes
</deferred>

---

*Phase: 25-Fix MARL Runtime Wiring*
*Context gathered: 2026-06-10 from v0.4.0 milestone audit (gap-closure phase, no discuss-phase)*
