# Architecture Research: v0.4.0 — Training Infrastructure & Realism

**Domain:** Surgical-robotics RL training system — research platform upgrade
**Researched:** 2026-05-13
**Confidence:** HIGH

## Executive Summary

The existing v0.3.2 architecture is a clean 5-layer monolith (scene_definition → simulators → dynamics → rl → cli) with dual-backend Strategy pattern and composite controllers. v0.4.0 adds five major subsystems that must integrate without breaking this structure. The key architectural challenge is that **DreamerV3 and PettingZoo use fundamentally different environment interfaces** than the existing Gymnasium contract. The solution is to keep `SurgicalEnv` as the canonical single-agent Gymnasium env, then build thin adapter wrappers (`PettingZooSurgicalEnv`, `DreamerEnvBridge`) that delegate to it. Real assets and task curriculum extend existing modules (schema + scene_builder + rl/rewards). Benchmarking is a new top-level module that wraps `TrainingManager`.

## Overall v0.4.0 Architecture (Target State)

```
                           ┌────────────────────────────────┐
                           │            CLI Layer             │
                           │  surg-rl benchmark, chain, marl │
                           │  surg-rl dreamer (new subcmd)   │
                           └──────────────┬─────────────────┘
                                          │
        ┌──────────────┬──────────────────┼──────────────────┬──────────────────┐
        ▼              ▼                  ▼                  ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ benchmarking │ │    marl/     │ │   dreamer/   │ │    task/     │ │   assets/    │
│ (NEW module) │ │ (NEW module) │ │ (NEW module) │ │ (NEW module) │ │ (NEW module) │
│              │ │              │ │              │ │              │ │              │
│ Experiment   │ │ PettingZoo   │ │ DreamerEnv   │ │ TaskCurric   │ │ MeshPipeline │
│ Runner       │ │ Env Wrapper  │ │ Bridge       │ │ TaskChain    │ │ AssetLoader  │
│ MetricColl   │ │ MultiAgent   │ │ TrainingLoop │ │ Executor     │ │ URDF/MJCF    │
│ ReportGen    │ │ ObsRouter     │ │ World Model  │ │ DiffProg     │ │  Generator   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │                │
       ▼                ▼                ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        EXISTING LAYERS (v0.3.2, extended)                         │
├──────────────────────────────────────────────────────────────────────────────────┤
│  rl/                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────┐│
│  │ SurgicalEnv      │  │ TrainingManager  │  │ ActionBuilder / ObsBuilder /     ││
│  │ (gym.Env)        │  │ (SB3 wrapper)    │  │ RewardFn (extended per task)     ││
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────────┘│
├──────────────────────────────────────────────────────────────────────────────────┤
│  dynamics/    [extended: TaskCurric hooks + reward shaping per task]              │
│  simulators/  [extended: real mesh loading in scene_builder, coll. geom gen]     │
│  scene_definition/  [extended: MeshAsset → real mesh refs, TaskChainConfig]      │
│  cutting/ + fluids/  [unchanged]                                                 │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Feature 1: Real Surgical Assets

### New Module: `src/surg_rl/assets/`

```
src/surg_rl/assets/
├── __init__.py
├── mesh_pipeline.py        # MeshAssetPipeline: load → validate → simplify → export
├── mesh_validator.py        # Watertightness, manifold, non-degenerate checks
├── collision_generator.py   # Convex decomposition, VHACD, primitives from mesh
├── mjcf_generator.py        # Generate <body>/<geom>/<mesh> from real mesh
├── urdf_generator.py        # URDF <link>/<visual>/<collision> from real mesh
├── texture_mapper.py        # UV mapping, texture atlas for organ meshes
└── instrument_registry.py   # Pre-defined instrument mesh catalog
```

### Integration Points

**Schema extension (`scene_definition/schema.py`)** — add `RealMeshAsset` model:

```python
class RealMeshAsset(BaseModel):
    """Reference to a real (non-procedural) mesh file."""
    path: str                           # Relative to assets/
    mesh_type: Literal["obj", "stl", "ply", "glb"] = "obj"
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    collision_mesh_path: str | None = None  # Simplified collision proxy
    convex_decomp: bool = False             # VHACD for concave shapes
    texture_path: str | None = None
```

The existing `MeshAsset` model in schema.py (line ~280) is extended with an optional `type` discriminator: `"procedural"` vs `"real"`. When `type="real"`, the `RealMeshAsset` sub-model is populated.

**SceneBuilder extension (`simulators/scene_builder.py`)** — the `_build_robot_geoms()` and `_build_tissue_geoms()` methods gain a branch:

```python
if mesh_asset.type == "real":
    # Load via assets.mesh_pipeline
    pipeline = MeshAssetPipeline(assets_dir)
    result = pipeline.load(mesh_asset.path)
    # Write processed mesh to temp file for MJCF/URDF
    # Generate collision geometry via assets.collision_generator
```

**Data Flow:**

```
SceneDefinition (with RealMeshAsset)
    ↓
SceneBuilder._build_entity_geoms()
    ↓
assets.MeshAssetPipeline.load(path)
    → trimesh.load() → validate → normalize → decimate (if needed)
    ↓
assets.CollisionGenerator.from_mesh()
    → convex_decomp (VHACD) or simplified hull
    ↓
Write processed .obj/.stl to tempfile
    ↓
MJCF <mesh file="tempfile"/> or URDF <geometry><mesh filename="tempfile"/>
    ↓
Simulator renders real mesh; collisions use simplified proxy
```

### Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| trimesh | >=4.0 | Mesh I/O, validation, simplification, convex hull |
| pyhocon / vhacdx | latest | Optional: concave→convex decomposition (VHACD) |
| numpy-stl | >=3.0 | STL binary read/write (some organ datasets use STL) |

**Primitive fallback preserved:** If `RealMeshAsset.path` doesn't resolve, `MeshAssetPipeline.load()` raises `AssetMissingError`, and `SceneBuilder` falls back to existing procedural primitives. This maintains the v0.3.2 contract: "primitive fallbacks when assets are missing."

### Confidence: HIGH
Pattern is well-established (trimesh is the standard Python mesh library). Integration into existing SceneBuilder is additive, not modifying fallback paths.

---

## Feature 2: Task Curriculum

### New Module: `src/surg_rl/task/`

```
src/surg_rl/task/
├── __init__.py
├── task_config.py           # SurgicalTaskConfig: difficulty params per task
├── task_registry.py         # Pre-defined task suite (suturing, knot-tying, etc.)
├── task_progression.py      # DifficultyProgression model (linear, exponential, adaptive)
├── task_chain.py            # TaskChain: sequence of subtasks with transition rules
├── task_chain_executor.py   # Executor: orchestrates chain at runtime
└── reward_shaper.py         # Per-task reward shaping (extends rl/rewards.py)
```

### Integration Points

**Schema extension** — `TaskConfig` (schema.py line 1047) is currently single-task. It is extended:

```python
class TaskDifficulty(BaseModel):
    """Difficulty progression parameters."""
    level: int = Field(ge=1, le=10)
    tolerance_mm: float = 5.0          # Position tolerance in mm
    time_multiplier: float = 1.0       # Time limit multiplier
    randomization_scale: float = 0.0   # Domain rand intensity
    prerequisite_success_rate: float = 0.7

class TaskChainStep(BaseModel):
    """A single step in a surgical task chain."""
    task_name: str
    instrument: str                     # Which instrument(s) required
    difficulty_progression: list[TaskDifficulty]
    transition_on: Literal["success", "timeout", "manual"] = "success"
    timeout_steps: int = 500

class TaskChainConfig(BaseModel):
    """Sequence of tasks forming a surgical procedure."""
    name: str
    steps: list[TaskChainStep]
    loop: bool = False                  # Repeat chain after completion
    global_time_limit: float = 300.0    # Total procedure time
```

**Execution flow** — `TaskChainExecutor` is a state machine owned by `SurgicalEnv`:

```
SurgicalEnv.reset()
    ↓
TaskChainExecutor.reset(chain_config)
    → select current_step based on difficulty progression
    → set _target_pos, _target_quat, reward_fn from current step's task
    ↓
SurgicalEnv.step()
    ↓
TaskChainExecutor.check_transition(obs, reward, success)
    → if transition condition met: advance to next step
    → update reward_fn, reset target
    ↓
(repeat until chain exhausted or global timeout)
```

**Integration with existing `dynamics/curriculum.py`** — the existing `CurriculumScheduler` adjusts physical difficulty (mass ranges, friction, action noise). The new task curriculum adjusts **task difficulty** (tolerance, time limits, procedural complexity). They compose:

```python
# In SurgicalEnv.reset():
if self._chain_executor is not None:
    task_params = self._chain_executor.get_current_task()
    self.set_target(task_params.target_pos, task_params.target_quat)
    self._reward_fn = task_params.reward_fn
    
if self._curriculum is not None:
    sim_params = self._curriculum.reset(seed)
    self._curriculum.apply_parameters(sim_params, self._simulator)
```

**Reward shaping per task** — the existing `create_default_reward(task_name=...)` factory is extended with task-specific reward functions: `SuturingReward`, `KnotTyingReward`, `NeedleInsertionReward`, `GraspingReward`, `CuttingReward`, `DissectionReward`. Each adds task-specific observations (needle pose, thread tension, cut depth, grasp force) from the `Observation.custom` dict.

### Confidence: HIGH
Clean extension of existing TaskConfig + CurriculumScheduler patterns. TaskChainExecutor is a straightforward state machine. The reward shaper builds on the existing `BaseRewardFunction` ABC.

---

## Feature 3: Benchmarking

### New Module: `src/surg_rl/benchmarking/`

```
src/surg_rl/benchmarking/
├── __init__.py
├── experiment_config.py     # BenchmarkConfig: algorithm matrix, seeds, scenes
├── experiment_runner.py     # ExperimentRunner: orchestrates TrainingManager instances
├── metrics.py               # MetricsCollector: episode returns, success rate, wall time
├── compare.py               # Algorithm comparator (t-tests, learning curves)
├── report.py                # ReportGenerator: markdown, JSON, HTML
├── plots.py                 # PlotRenderer: matplotlib learning curves, radar charts
└── reproducibility.py       # Seed matrix, env hash, dependency freeze
```

### Integration Points

**`ExperimentRunner` wraps `TrainingManager`:**

```python
class ExperimentRunner:
    """Run a matrix of (algorithm × scene × seed) experiments."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self._runs: list[TrainingManager] = []
        self._collector = MetricsCollector()
    
    def run(self) -> dict[str, Any]:
        """Execute all experiments and return aggregated results."""
        for algo in self.config.algorithms:
            for scene in self.config.scenes:
                for seed in self.config.seeds:
                    train_config = TrainingConfig(
                        scene_path=scene,
                        algorithm=AlgorithmConfig(name=algo),
                        seed=seed,
                        ...
                    )
                    mgr = TrainingManager(train_config)
                    model = mgr.train()
                    eval_results = mgr.evaluate(n_episodes=self.config.eval_episodes)
                    self._collector.record(algo, scene, seed, eval_results)
        return self._collector.aggregate()
```

**CLI additions:**

```
surg-rl benchmark       --config benchmark.yaml    (run full matrix)
surg-rl compare         --results results.json     (statistical comparison)
surg-rl report          --results results.json     (generate report)
```

**Data Flow:**

```
BenchmarkConfig (YAML)
    ↓
ExperimentRunner.run()
    → for each (algo, scene, seed):
        → TrainingManager(config) → .train() → .evaluate()
        → MetricsCollector.record(run_results)
    ↓
MetricsCollector.aggregate()
    → {algo: {scene: {mean_reward, std_reward, success_rate, wall_time}}}
    ↓
ReportGenerator.generate(markdown=True, html=True)
    → .planning/benchmarks/{timestamp}/report.md
PlotRenderer.render()
    → .planning/benchmarks/{timestamp}/plots/learning_curve.png
```

### Confidence: HIGH
The pattern is standard (wrap TrainingManager in a loop with metric aggregation). Matplotlib for plots, jinja2 for HTML reports. No new architectural complexity — benchmarking is a top-level consumer of existing modules.

---

## Feature 4: Multi-Agent RL (MARL via PettingZoo)

### New Module: `src/surg_rl/marl/`

```
src/surg_rl/marl/
├── __init__.py
├── parallel_env.py          # PettingZooSurgicalEnv: extends ParallelEnv
├── agent_registry.py        # AgentConfig: observation/action per agent
├── observation_router.py    # Split sim Observation → per-agent dicts
├── action_aggregator.py     # Aggregate per-agent actions → sim action
├── policy_config.py         # SharedPolicyConfig vs IndependentPolicyConfig
├── reward_splitter.py       # Team reward → per-agent credit assignment
└── dual_arm_env.py          # Pre-built dual-arm coordination environment
```

### Integration Points

**Key architectural decision:** `PettingZooSurgicalEnv` is a **thin adapter** over `SurgicalEnv`, not a rewrite. It delegates simulation to the existing `BaseSimulator` stack.

```python
from pettingzoo import ParallelEnv

class PettingZooSurgicalEnv(ParallelEnv):
    """PettingZoo wrapper over SurgicalEnv for multi-agent training."""
    
    def __init__(self, config: MultiAgentConfig):
        self._single_env = SurgicalEnv(config.to_single_agent_config())
        self._router = ObservationRouter(config.agent_configs)
        self._aggregator = ActionAggregator(config.agent_configs)
        self.possible_agents = config.agent_names
        self.agents = []
    
    def observation_space(self, agent):
        return self._router.observation_space(agent)
    
    def action_space(self, agent):
        return self._aggregator.action_space(agent)
    
    def reset(self, seed=None, options=None):
        gym_obs, info = self._single_env.reset(seed=seed)
        self.agents = self.possible_agents[:]
        obs = self._router.split(gym_obs)
        return obs, {a: {} for a in self.agents}
    
    def step(self, actions):
        sim_action = self._aggregator.combine(actions)
        gym_obs, reward, terminated, truncated, info = self._single_env.step(sim_action)
        obs = self._router.split(gym_obs)
        
        # Per-agent rewards (from reward_splitter or shared)
        rewards = self._reward_splitter.compute(gym_obs, reward, info)
        terminations = {a: terminated for a in self.agents}
        truncations = {a: truncated for a in self.agents}
        
        if terminated or truncated:
            self.agents = []
        
        return obs, rewards, terminations, truncations, {a: {} for a in self.agents}
```

**Observation Router** — maps the flat `Observation` dataclass into per-agent views:

```
Simulator Observation (single flat dict)
    ↓
ObservationRouter.split()
    ├── agent_0 (left arm):  [joint_positions[:7], end_effector_pos_left, target_pos, ...]
    └── agent_1 (right arm): [joint_positions[7:14], end_effector_pos_right, target_pos, ...]
```

**Shared vs independent policies:**

| Mode | Config | Training | Use Case |
|------|--------|----------|----------|
| Independent | Each agent has own policy network | Separate SB3 model per agent | Heterogeneous agents (camera arm ≠ tool arm) |
| Shared | Single policy for all agents | One SB3 model, agents share weights | Homogeneous dual-arm, swarm instruments |
| Centralized critic | Independent actors, shared critic | MADDPG-style with joint observation | Coordinated tasks (one holds tissue, other cuts) |

**Integration with TrainingManager** — PettingZoo envs don't work directly with SB3 (SB3 is single-agent). Training uses either:
1. SB3's `SubprocVecEnv` with independent envs per agent (for independent policies)
2. RLlib's multi-agent API (for centralized critic)
3. Custom training loop that iterates agents

Since RLlib already has partial support in `src/surg_rl/rl/rllib/`, the MARL training path uses RLlib for centralized critic and SB3 for independent policies.

**Data Flow:**

```
PettingZooSurgicalEnv.reset()
    ↓
SurgicalEnv.reset() → gym_obs
    ↓
ObservationRouter.split(gym_obs) → {agent_0: obs_0, agent_1: obs_1}
    ↓
Agent policies produce actions: {agent_0: act_0, agent_1: act_1}
    ↓
ActionAggregator.combine({agent_0: act_0, agent_1: act_1}) → sim_action (16D vector)
    ↓
SurgicalEnv.step(sim_action) → gym_obs, reward
    ↓
ObservationRouter.split(gym_obs) + RewardSplitter.compute() → per-agent rewards
```

### Confidence: MEDIUM
PettingZoo `ParallelEnv` API is well-documented. The adapter pattern (wrapping SurgicalEnv) is clean. The MEDIUM confidence is because RLlib multi-agent training introduces complexity in the policy mapping and training orchestration. This is the riskiest feature to architect correctly.

---

## Feature 5: DreamerV3 World Models

### New Module: `src/surg_rl/dreamer/`

```
src/surg_rl/dreamer/
├── __init__.py
├── dreamer_config.py        # DreamerConfig: world model, policy, training params
├── dreamer_env.py           # DreamerEnvBridge: SurgicalEnv → embodied env interface
├── training_loop.py         # DreamerTrainingLoop: embodied driver + checkpoint
├── world_model.py           # WorldModel wrapper: RSSM encoder/decoder/dynamics
├── planning.py              # PlanningModule: MPPI/CEM planning in latent space
├── pixel_path.py            # PixelObservationPath: CNN encoder for pixel inputs
├── lowdim_path.py           # LowDimPath: MLP encoder for proprioceptive inputs
└── report.py                # DreamerMetrics: imagination rollouts, open-loop preds
```

### Integration Points

**Key architectural decision:** DreamerV3 uses the `embodied` and `elements` libraries (by Danijar), which have their own environment interface. `DreamerEnvBridge` bridges Gymnasium → embodied:

```python
import embodied
import numpy as np

class DreamerEnvBridge(embodied.Env):
    """Bridge SurgeryEnv to DreamerV3's embodied environment interface."""
    
    def __init__(self, config: DreamerConfig):
        self._gym_env = SurgicalEnv(config.to_surgical_env_config())
        self._use_pixels = config.use_pixels
        
        # Define embodied obs_space
        if self._use_pixels:
            self._obs_space = {
                'image': elements.Space(np.uint8, (64, 64, 3)),
                'reward': elements.Space(np.float32),
                'is_first': elements.Space(bool),
                'is_last': elements.Space(bool),
                'is_terminal': elements.Space(bool),
            }
        else:
            # Low-dim: add proprioceptive fields
            obs_size = self._gym_env.observation_space.shape[0]
            self._obs_space = {
                'vector': elements.Space(np.float32, (obs_size,)),
                'reward': elements.Space(np.float32),
                'is_first': elements.Space(bool),
                'is_last': elements.Space(bool),
                'is_terminal': elements.Space(bool),
            }
        
        # Define embodied act_space
        self._act_space = {
            'action': elements.Space(
                np.float32, (self._gym_env.action_space.shape[0],),
                self._gym_env.action_space.low[0],
                self._gym_env.action_space.high[0],
            ),
            'reset': elements.Space(bool),
        }
    
    @property
    def obs_space(self):
        return self._obs_space
    
    @property
    def act_space(self):
        return self._act_space
    
    def step(self, action):
        """DreamerV3 step: dict action → dict observation."""
        if action.get('reset', False):
            gym_obs, _ = self._gym_env.reset()
            return self._convert_obs(gym_obs, reward=0.0, is_first=True)
        
        gym_act = action['action']
        gym_obs, reward, terminated, truncated, info = self._gym_env.step(gym_act)
        done = terminated or truncated
        
        return self._convert_obs(
            gym_obs,
            reward=float(reward),
            is_first=False,
            is_last=done,
            is_terminal=terminated,
        )
    
    def _convert_obs(self, gym_obs, reward, is_first, is_last=False, is_terminal=False):
        """Convert Gymnasium obs dict to embodied obs dict."""
        if self._use_pixels:
            rgb = self._gym_env.render()
            return {
                'image': rgb,
                'reward': np.array(reward, np.float32),
                'is_first': np.array(is_first, bool),
                'is_last': np.array(is_last, bool),
                'is_terminal': np.array(is_terminal, bool),
            }
        else:
            flat_obs = self._gym_env._obs_builder.flatten_observation(gym_obs)
            return {
                'vector': flat_obs.astype(np.float32),
                'reward': np.array(reward, np.float32),
                'is_first': np.array(is_first, bool),
                'is_last': np.array(is_last, bool),
                'is_terminal': np.array(is_terminal, bool),
            }
```

**Two observation paths:**

| Path | Input | Encoder | Use Case |
|------|-------|---------|----------|
| Pixel path | `(H, W, 3)` rendered image | CNN encoder (4-layer, depth 64) | Vision-based surgical planning |
| Low-dim path | Flat proprioceptive vector | MLP encoder (3-layer, 1024 units) | State-based policies (faster, more sample-efficient) |

Both paths share the same RSSM and decoder. The `DreamerConfig` selects the path at construction time.

**Training loop:**

```
DreamerTrainingLoop.run()
    ↓
dreamerv3.agent.Agent(obs_space, act_space, config)
    ↓
embodied.driver.Driver([DreamerEnvBridge(config)])
    ↓
Loop:
    driver(policy_fn, steps=10)           # collect experience
    replay.add(transitions)
    if should_train:
        stream_train = agent.stream(replay)  # sample batches
        agent.train(batch)                   # update world model + policy
    if should_log:
        logger.write(metrics)
    if should_save:
        checkpoint.save(agent, replay)
```

**World model architecture (from DreamerV3, no customization):**

```
Observation → Encoder (CNN/MLP) → tokens
    ↓
RSSM: deter(8192) + stoch(32 classes × 64) → latent state
    ↓
Decoder (CNN/MLP): latent → reconstructed observation
    ↓
Reward head: latent → predicted reward
    ↓
Continue head: latent → predicted terminal
    ↓
Actor: latent → action (via imagination in latent space)
    ↓
Critic: latent → value (symexp_twohot, 255 bins)
```

**CLI additions:**

```
surg-rl dreamer train   --scene scenes/suturing.json --pixels --timesteps 1e6
surg-rl dreamer eval     --model models/dreamer_model
surg-rl dreamer imagine  --model models/dreamer_model --steps 50  (open-loop rollout)
```

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| dreamerv3 | latest (git) | World model algorithm (agent, RSSM, encoder, decoder) |
| embodied | latest (git) | Environment driver, checkpoint, logger |
| elements | latest (git) | Config system, spaces, checkpoint |
| jax | >=0.4.20 | JIT compilation for RSSM forward/backward passes |
| jaxlib | >=0.4.20 | JAX runtime (CPU/CUDA/Metal) |
| optax | >=0.1.7 | Optimizer (AdamW for DreamerV3) |
| tensorflow-cpu | >=2.15 | embodied uses TF for data pipelines (replay buffer streaming) |

These go into a new `[dreamer]` optional dependency group.

### Confidence: MEDIUM
The `embodied` env interface is well-defined. The adapter pattern is clean. MEDIUM confidence because:
1. DreamerV3 has heavy dependencies (JAX, TF) that may conflict with PyTorch-based training
2. The pixel rendering path requires synchronous render in the env loop (performance concern)
3. JAX on Apple Silicon (Metal) is not as mature as on CUDA — macOS testing will need xfails

---

## Suggested Build Order (Phase Dependencies)

```
Phase A (schema)
│   scene_definition/schema.py
│   ├── RealMeshAsset model
│   ├── TaskChainConfig / TaskDifficulty models
│   ├── MultiAgentConfig model
│   └── DreamerConfig model
│
├── Phase B (assets)
│   │   src/surg_rl/assets/
│   │   scene_builder.py extension
│   │   Depends on: Phase A (RealMeshAsset schema)
│   │
│   ├── Phase C (task curriculum)
│   │   │   src/surg_rl/task/
│   │   │   dynamics/curriculum.py extension
│   │   │   rl/rewards.py extension (per-task reward fns)
│   │   │   Depends on: Phase A (TaskChainConfig schema)
│   │   │
│   │   ├── Phase D (benchmarking)
│   │   │   │   src/surg_rl/benchmarking/
│   │   │   │   CLI: surg-rl benchmark/report/compare
│   │   │   │   Depends on: Phase C (task curriculum provides runnable tasks)
│   │   │   │              Phase B (optional: real assets for visual reports)
│   │   │   │
│   │   │   ├── Phase E (MARL)
│   │   │   │   │   src/surg_rl/marl/
│   │   │   │   │   Depends on: Phase A (MultiAgentConfig schema)
│   │   │   │   │   Can run in parallel with Phase C+D
│   │   │   │   │
│   │   │   │   └── Phase F (DreamerV3)
│   │   │   │       │   src/surg_rl/dreamer/
│   │   │   │       │   Depends on: Phase D (benchmarking for comparison reports)
│   │   │   │       │              Phase C (task curriculum for training scenarios)
│   │   │   │       │   Can run in parallel with Phase E
```

**Phase ordering rationale:**

1. **Schema first** (Phase A) — all five features need new models in `schema.py`. Pydantic v2 single source of truth is the existing pattern; no feature can start before its schema is defined.

2. **Assets + Task Curriculum** (Phase B+C) — the core surgical realism work. These are independent of each other (assets don't need curriculum, curriculum works with primitive meshes). They can run in parallel.

3. **Benchmarking** (Phase D) — wraps the training pipeline. Needs task curriculum to have meaningful tasks to benchmark against. Optionally uses real assets for report visuals.

4. **MARL** (Phase E) — PettingZoo adapter is architecturally clean but adds RLlib complexity. Can start as early as Phase A is done (ParallelEnv wraps SurgicalEnv, which doesn't need assets or curriculum). Best parallelized with C+D.

5. **DreamerV3** (Phase F) — highest risk (heavy deps, JAX, new training paradigm). Placed last so it can benchmark against established SB3 baselines from Phase D and train on task curriculum tasks from Phase C.

---

## Cross-Cutting Concerns

### Dependency Management

The `[dreamer]` extra must be isolated from the PyTorch-based stack to avoid JAX+TF vs PyTorch conflicts:

```ini
# pyproject.toml
[project.optional-dependencies]
dreamer = [
    "dreamerv3 @ git+https://github.com/danijar/dreamerv3",
    "embodied @ git+https://github.com/danijar/embodied",
    "elements @ git+https://github.com/danijar/elements",
    "jax>=0.4.20",
    "jaxlib>=0.4.20",
    "optax>=0.1.7",
    "tensorflow-cpu>=2.15",
]
```

Lazy imports in `dreamer/__init__.py` mirror the existing pattern:

```python
try:
    import dreamerv3
    HAS_DREAMER = True
except ImportError:
    HAS_DREAMER = False
```

### Threading / Process Model

| Module | Thread/Process Owner | Notes |
|--------|---------------------|-------|
| SurgicalEnv | Single process | Existing: owns simulator lifecycle |
| PettingZooSurgicalEnv | Single process | Delegates to SurgicalEnv |
| DreamerTrainingLoop | Single process + JAX GPU | embodied driver runs in-process; JAX allocates GPU memory separately |
| ExperimentRunner | Single process (sequential) | Serializes TrainingManager runs |

No distributed MARL or DreamerV3 training in v0.4.0 — single-machine scope.

### Configuration Hierarchy

```
.env (pydantic-settings)
    ↓
BenchmarkConfig / DreamerConfig / MultiAgentConfig (YAML/JSON)
    ↓
TrainingConfig / SurgicalEnvConfig (dataclass/Pydantic)
    ↓
Simulator constructor args
```

### Anti-Patterns to Avoid

1. **Don't rewrite SurgicalEnv for PettingZoo** — the adapter pattern keeps the canonical single-agent env and adds a multi-agent view layer. Rewriting means maintaining two parallel environment implementations.

2. **Don't put DreamerV3 training state in SurgicalEnv** — DreamerV3 has its own replay buffer and RSSM state. These live in `dreamer/` only. The env bridge is a stateless translator.

3. **Don't hardcode task curriculum in the simulator** — task progression is an RL layer concern. The simulator doesn't know about difficulty levels; it receives physical parameters from the controller.

4. **Don't bake benchmark report formatting into ExperimentRunner** — separate `MetricsCollector` (data) from `ReportGenerator` (presentation). This lets reports evolve independently of the experiment protocol.

---

## State of Architecture Changes

### Existing Modules — Extensions

| Module | Change | Impact |
|--------|--------|--------|
| `scene_definition/schema.py` | New models: RealMeshAsset, TaskChainConfig, MultiAgentConfig, DreamerConfig | Additive — existing models unchanged |
| `simulators/scene_builder.py` | Branch for real mesh loading via assets/ | Moderate — new code path alongside existing primitives |
| `rl/rewards.py` | New task-specific reward functions | Additive — new subclasses of BaseRewardFunction |
| `rl/training.py` | Expose TrainingManager to benchmarking | Minor — TrainingManager is already public API |
| `dynamics/curriculum.py` | Task difficulty awareness | Minor — add `get_task_difficulty()` method |
| `cli.py` | New subcommands: benchmark, compare, report, chain, marl, dreamer | Moderate — additive subcommands |

### Existing Modules — Unchanged

| Module | Reason |
|--------|--------|
| `cutting/` | No changes — cutting engine is feature-complete for v0.4.0 |
| `fluids/` | No changes — PhiFlow integration is stable |
| `utils/mesh_generation.py` | No changes — procedural mesh gen remains the fallback path |
| `utils/vtk_io.py` | No changes — VTK writing unchanged |
| `scene_generation/` | No changes — LLM parsers don't need asset awareness yet |
| `simulators/base_simulator.py` | No changes — Observation dataclass already has enough fields |
| `simulators/mujoco_simulator.py` | Minor — load_scene handles real meshes via scene_builder |
| `simulators/pybullet_simulator.py` | Minor — load_scene handles real meshes via scene_builder |

---

## Sources

- **Context7 /danijar/dreamerv3** — embodied env interface, spaces API, training loop pattern (CONFIRMED: uses elements.Space for obs/act definitions, embodied.Env for env interface)
- **Context7 /farama-foundation/pettingzoo** — ParallelEnv API, AEC/Parallel conversion (CONFIRMED: ParallelEnv with reset/step/observation_space/action_space contract)
- **Context7 /mikedh/trimesh** — mesh loading, validation, convex hull (CONFIRMED: trimesh.load() supports .obj, .stl, .ply, .glb)
- Existing codebase:
  - `base_simulator.py` — Observation/State/StepResult dataclasses, BaseSimulator ABC
  - `environment.py` — SurgicalEnv (gym.Env), env config, env factory
  - `training.py` — TrainingManager, TrainingConfig, AlgorithmConfig
  - `curriculum.py` — CurriculumScheduler, CurriculumStage
  - `rewards.py` — BaseRewardFunction ABC, RewardConfig, RewardResult
  - `schema.py` — SceneDefinition, TaskConfig, MeshAsset (existing)
  - `scene_builder.py` — SceneBuilder with primitive fallback pattern
- `.planning/PROJECT.md` — v0.4.0 milestone goals and deferred items
- `.planning/research/PITFALLS.md` — known anti-patterns (backend leakage, monolithic controllers)

---

*Architecture research for: surg-rl v0.4.0 Training Infrastructure & Realism*
*Researched: 2026-05-13*
*Ready for roadmap: yes*
