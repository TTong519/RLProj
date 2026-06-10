# Phase 22: Multi-Agent RL — Research

**Researched:** 2026-05-18
**Researcher model:** deepseek-v4-pro:cloud

## Standard Stack (What We Use)

| Component | Library | Version | Why |
|-----------|---------|---------|-----|
| MARL environment | PettingZoo ParallelEnv | >=1.24.0 | Standard POSG-inspired parallel API, RLlib/Ray compatibility path |
| SB3 conversion | SuperSuit | >=3.9.0 | Canonical PettingZoo↔Gymnasium vectorization, maintained by Farama |
| SB3 training | Stable-Baselines3 | >=2.0.0 (already in use) | PPO/SAC policies, already the project's single-agent trainer |
| Thread coordination | threading (stdlib) | — | D-08: parallel `learn()` threads, no external scheduler needed |
| Config models | Pydantic v2 | >=2.0.0 (already in use) | Schema-first, MultiAgentConfig already skeletal in schema.py |
| Lazy imports | surg_rl.utils.lazy_imports.LazyImport | — | Already exists in marl/__init__.py, no import-time dependency |

## Architecture Patterns (How We Build It)

### Pattern 1: Thin Adapter (Passthrough Delegation)

**Source:** CONTEXT.md D-11, MARL-04, existing Ros2Bridge/ControllerBridge patterns

MultiAgentSurgicalEnv is a **passthrough adapter**, not a subclass of SurgicalEnv. It owns one SurgicalEnv instance and maps multi-agent semantics onto single-agent internals:

```
MultiAgentSurgicalEnv(ParallelEnv)
    ├── owns _surgical_env: SurgicalEnv   (single instance, all sim logic)
    ├── step({agent_id: action})
    │       → maps per-agent actions → per-arm apply_action(arm_id=...)
    │       → calls _surgical_env.step() once
    │       → splits observation/reward per agent
    └── reset()
            → resets _surgical_env
            → returns per-agent observations
```

**Key constraint:** Zero simulation code in MultiAgentSurgicalEnv. All physics stepping, reward computation, scene loading flow through SurgicalEnv unchanged.

### Pattern 2: Strategy Pattern Extension (apply_action arm_id)

**Source:** D-09, BaseSimulator ABC pattern

The existing `BaseSimulator.apply_action(action)` is a strategy method. Extending it with an optional `arm_id` parameter follows the established pattern of optional arguments (see: `render(mode, width, height, camera_name)`, `set_state(state)`).

```python
# base_simulator.py (ABC)
def apply_action(self, action: np.ndarray, arm_id: str | None = None) -> None:
    self._apply_action(action, arm_id=arm_id)

# Backward-compatible: existing code without arm_id works unchanged
```

**MuJoCo implementation:** Index into `self._model.actuator(arm_dof_start)` by joint offset.
**PyBullet implementation:** Use `setJointMotorControlArray` with robot-specific joint indices.

### Pattern 3: Composite Controller (Training Manager)

**Source:** EnvironmentController composition pattern

EnvironmentController composes CurriculumController + Randomizer + AdaptiveDifficulty. MultiAgentTrainingManager follows the same pattern:

```
MultiAgentTrainingManager
    ├── env: MultiAgentSurgicalEnv
    ├── shared_policy: bool
    ├── train_shared()        → single SB3 model, D-07
    │       SuperSuit wrapper → VecEnv → model.learn()
    └── train_independent()   → two SB3 models, D-07/D-08
            thread_1: surgeon_model.learn()
            thread_2: assistant_model.learn()
```

## Don't Hand Roll (Use Libraries)

| Task | Use | Don't Use |
|------|-----|-----------|
| Multi-agent env | PettingZoo ParallelEnv | Custom Gym wrapper, RLlib MultiAgentEnv |
| SB3 conversion | `supersuit.pettingzoo_env_to_vec_env_v1` | Manual dict→array conversion |
| VecEnv stacking | `supersuit.concat_vec_envs_v1` | Manual np.concatenate |
| Action/obs filtering | Native Python dict comprehension + numpy slicing | PettingZoo wrappers (not needed for per-agent subset) |
| Thread safety | `threading.Thread` + synchronized env access | multiprocessing (overkill, shared SurgicalEnv is single process) |

### SuperSuit Conversion Pipeline (D-06)

The canonical path from PettingZoo ParallelEnv to SB3-compatible VecEnv:

```python
from supersuit import pettingzoo_env_to_vec_env_v1, concat_vec_envs_v1

# ParallelEnv → Gym-compatible vectorized env
vec_env = pettingzoo_env_to_vec_env_v1(parallel_env)
# Stack environments for parallel rollouts (if needed)
vec_env = concat_vec_envs_v1(vec_env, num_vec_envs=2, num_cpus=1)
```

**What pettingzoo_env_to_vec_env_v1 does:**
1. Wraps ParallelEnv observations (dict of {agent: obs}) into stacked array
2. Wraps action space into single Box
3. Wraps rewards/terminations/truncations similarly
4. Produces VecEnv compatible with SB3's `model.learn()`

**Shared policy path:** One env → one VecEnv → one SB3 model. All agents share parameters.

**Independent policy path:** Two separate MultiAgentSurgicalEnv instances each filtered to a single agent → each gets its own VecEnv → each gets its own SB3 model.

### Thread Safety for Parallel learn() (D-08)

Both agents share the same SurgicalEnv instance for simulation. The env is NOT thread-safe for concurrent step() calls. The independent training mode therefore alternates:

```python
def train_independent(self):
    # Create two env views, each filtering to one agent
    env_surgeon = SingleAgentView(self.env, "surgeon")
    env_assistant = SingleAgentView(self.env, "assistant")
    
    # Each agent collects rollouts synchronously
    # (alternating: surgeon step → assistant step → repeat)
    def surgeon_loop():
        model_surgeon.learn(total_timesteps=...)
    
    def assistant_loop():
        model_assistant.learn(total_timesteps=...)
    
    # Threads synchronize on env access (lock-protected)
```

Alternative for true parallel: Two independent SurgicalEnv instances, each with a single robot. This doubles simulation cost but avoids thread contention.

**Chosen approach:** Single env with synchronized access (simpler, matches D-11's "one SurgicalEnv instance").

## Common Pitfalls

### Pitfall 1: ParallelEnv agents property must be mutable

**Problem:** PettingZoo's `agents` list changes during an episode (agents can be added/removed). The test suite expects this.
**Fix:** `self.agents = ["surgeon", "assistant"]` not `self.agents = tuple(...)`. Reset must re-populate.

### Pitfall 2: SuperSuit expects Dict obs/action spaces

**Problem:** `pettingzoo_env_to_vec_env_v1` internally expects Gymnasium `Dict` spaces for observation/action when the ParallelEnv has heterogeneous spaces per agent.
**Fix:** Define `observation_spaces` and `action_spaces` as `Dict[str, Space]` properties matching agent IDs.

### Pitfall 3: SB3 VecEnv expects consistent observation shape

**Problem:** If surgeon arm has 7-DOF and assistant has 3-DOF, their observation vectors differ in length.
**Fix:** `pettingzoo_env_to_vec_env_v1` handles this via padding/masking. For independent policies, use SingleAgentView. For shared policy, pad to max shape.

### Pitfall 4: PyBullet joint indexing for arm_id routing

**Problem:** PyBullet joint indices are global (not robot-scoped). Need to know which joint range belongs to which arm.
**Fix:** Track per-robot joint index ranges during load_scene(), store in `_arm_joint_ranges: dict[str, tuple[int, int]]`.

### Pitfall 5: Reward routing must not double-count

**Problem:** Per-agent reward routing (D-10) could sum to more than the single-agent reward if components overlap.
**Fix:** Task-specific reward goes to surgeon. Assistant gets positioning/camera-specific reward (computed separately, not a subset of the total).

## Validation Architecture

### Test Strategy

| Layer | Test Type | Framework | What It Tests |
|-------|-----------|-----------|---------------|
| Schema | Unit | pytest + Pydantic | MultiAgentConfig validation, arm role defaults |
| MultiAgentConfig | Unit | pytest | ArmRole enum, per-agent observation_keys validation |
| BaseSimulator.arm_id | Unit | pytest + mock | arm_id routing, backward compat with None |
| MultiAgentSurgicalEnv | Integration | pytest + SurgicalEnv | ParallelEnv contract (reset, step, render, close) |
| SuperSuit pipeline | Integration | pytest + pettingzoo | Wrapper chain end-to-end, VecEnv shape |
| Training loop | Integration | pytest + SB3 | Shared policy training completes, independent training completes |
| CLI | Integration | pytest + Typer | `surg-rl marl-train --scene ... --policy shared` |

### ParallelEnv Contract Tests (Nyquist)

Per PettingZoo's `parallel_api_test`:
- `reset()` returns `(obs_dict, info_dict)` with correct agent keys
- `step()` returns 5-tuple of dicts
- `agents` list is non-empty after reset
- `render()` returns valid ndarray or None
- `close()` cleans up without error
- `observation_space(agent)` and `action_space(agent)` work for all agents

## Cross-Phase Dependencies

| Depends On | What We Need | Status |
|------------|-------------|--------|
| Phase 19 (Schema) | MultiAgentConfig skeleton, LazyImport | ✅ Complete |
| Phase 20 (Assets) | Real instrument meshes for dual-arm scenes | ✅ Complete |
| Phase 21 (Tasks) | TaskRewardRouter, check_success/failure | ✅ Complete |
| Phase 22 → Phase 23 | MultiAgentSurgicalEnv for MARL benchmarks | Output |

## Decision Map

| CONTEXT.md Decision | Implementation Location | Approach |
|---------------------|------------------------|----------|
| D-01 (Two RobotConfigs) | schema.py MultiAgentConfig | arm_configs list |
| D-02 (Swappable roles) | schema.py ArmConfig | `role: Literal["surgeon","assistant"]` + `robot_ref: str` |
| D-03 (MultiAgentConfig section) | schema.py SceneDefinition | Add `multi_agent: MultiAgentConfig | None` |
| D-04 (Observation filtering) | marl/observation_filter.py | Key mapping from Observation.to_dict() |
| D-05 (RobotConfig action dims) | marl/multi_agent_env.py | Auto-compute from DOF count |
| D-06 (SuperSuit pipeline) | marl/wrappers.py | pettingzoo_env_to_vec_env_v1 |
| D-07 (Shared vs independent) | marl/training.py | MultiAgentTrainingManager |
| D-08 (Thread coordination) | marl/training.py | threading.Thread + Lock |
| D-09 (arm_id injection) | base_simulator.py + backends | Optional param on apply_action |
| D-10 (Reward routing) | marl/multi_agent_env.py | compute() once, split per role |
| D-11 (Passthrough) | marl/multi_agent_env.py | Owns SurgicalEnv, never subclasses |

---

*Phase 22 Research complete • 2026-05-18*
