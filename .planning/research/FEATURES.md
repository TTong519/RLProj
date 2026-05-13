# Feature Landscape: v0.4.0 — Training Infrastructure & Realism

**Domain:** Surgical robotics RL training system
**Milestone:** v0.4.0
**Researched:** 2026-05-13
**Overall confidence:** HIGH

---

## Feature 1: Real Surgical Assets (Instrument Meshes + Organ Geometries)

### Table Stakes (must have, or product feels incomplete)

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| OBJ/STL/URDF mesh loading for instruments | Users expect instruments to look like instruments, not colored boxes | MEDIUM | `scene_builder.py` (extends MJCF/URDF generation to reference real mesh files instead of primitive fallbacks) |
| Forceps mesh with identifiable jaws | Table stakes for any grasping demo — users need to see what they're manipulating | LOW | `InstrumentConfig` in `schema.py` already has `mesh_path` field |
| Scalpel/blade mesh | Cutting tasks need a visual cutting tool | LOW | Existing `InstrumentType` enum already has scalpel entry |
| Needle driver mesh | Suturing tasks need realistic needle holder | LOW | Existing `InstrumentConfig` supports mesh overrides |
| Liver and stomach as deformable organ meshes | Soft-tissue surgical simulation is what Surg-RL claims to do; liver is the most common benchmark organ | HIGH | `TissueConfig` + `scene_builder.py` + tetgen pipeline (Phase 15) + FEM pipeline (Phase 16) |
| Organ meshes must support volumetric cutting | Cutting is the v0.3.2 headline feature; assets must work with it | HIGH | Volumetric cutting engine (Phase 17) — requires tetrahedral meshes from tetgen |

### Differentiators (competitive advantage)

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Kidney, gallbladder as additional organ geometries | Most surgical sims stop at liver; multi-organ suite is rare in open-source | HIGH | Same tetgen+FEM pipeline, but per-organ tet parameter tuning |
| Procedural organ mesh generation (tetgen from surface mesh) | User brings a surface mesh → Surg-RL tetrahedralizes it automatically | MEDIUM | `mesh_generation.py` (procedural tetgen box/sphere/cylinder) + `vtk_io.py` — extend to surface-to-tet pipeline |
| Retractors and trocars as distinct instrument meshes | Trocar placement is a real surgical subtask; retractor simulation requires dual-arm | MEDIUM | `InstrumentType` enum + mesh assets; retractor needs attachment physics |
| Per-instrument physics properties (mass, friction, stiffness) | Real scalpels weigh different amounts than forceps; gripper forces differ | LOW | `InstrumentConfig` already has physics overrides — just need defaults per type |
| Mesh fallback chain: real OBJ → procedural primitives → colored box | Graceful degradation keeps demos working even when assets are missing | LOW | Already implemented in `scene_builder.py` — extend to check for real mesh first |

### Anti-Features (explicitly do NOT build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Photorealistic texture baking / PBR materials | MuJoCo/PyBullet renderers are not physically-based; textures would add complexity with no visual benefit in sim | Flat colors with material properties (specular, diffuse) — sufficient for RL training |
| Patient-specific organ meshes from CT/MRI | HIPAA/GDPR compliance nightmare; requires DICOM parsing, segmentation, registration pipeline | Procedural/synthetic organ shapes that approximate real anatomy without patient data |
| Built-in mesh asset library with dozens of variants | Licensing burden; every institution has different preferences; bloats repo | Ship 1-2 canonical meshes per instrument type; document how users register custom meshes |
| Rigged/skeletonized instrument meshes with animation | Instruments in RL sims are positioned via physics, not animation; rigging is for rendering tools like Blender | Position meshes via simulator transforms (position+quaternion) — no skeleton needed |
| Organ texture maps (veins, arteries) | MuJoCo texture support is limited; PyBullet ignores them; visual detail irrelevant for RL state vectors | If needed for pixel-based policies, add simple procedural color variation (not texture maps) |

### Feature Dependency Graph (Feature 1)

```
Real OBJ/STL Mesh Files
    │
    ├──> scene_builder.py: load OBJ → reference in MJCF/URDF (replaces primitive fallback)
    │
    ├──> schema.py: InstrumentConfig.mesh_path populated with real paths
    │
    └──> Organ meshes require:
              ├── surface mesh → tetgen tetrahedralization (Phase 15)
              ├── tet mesh → MJCF flex (MuJoCo) or .vtk (PyBullet) (Phase 16)
              └── tet mesh → volumetric cutting engine (Phase 17)
```

### Implementation Notes

- **Source of meshes:** Use MIT-licensed or CC0 meshes. The [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) has robot meshes but no surgical instruments. Candidate sources: [SurgToolLoc](https://github.com/surgical-robotics-research/surgtoolloc) dataset, procedural OpenSCAD instrument generators, or hand-modeled low-poly meshes.
- **Minimum viable:** 1 forceps + 1 scalpel + 1 liver (deformable) + 1 stomach (deformable) = 4 real meshes replacing primitives. Ship with just these.
- **Mesh formats:** OBJ is the universal fallback — MuJoCo supports OBJ natively, PyBullet loads OBJ via `createCollisionShape`/`createVisualShape`. STL is common in surgical tool datasets. Avoid GLTF/glb (not supported by PyBullet).
- **Confidence:** HIGH for instrument meshes (well-understood pattern), MEDIUM for organ meshes (tetgen parameter tuning is organ-specific and may need iteration).

---

## Feature 2: Surgical Task Curriculum

### Table Stakes

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| Suturing task with needle passing reward | Suturing is the single most recognizable surgical task; SB3 training must produce non-trivial suturing policies | MEDIUM | `SuturingReward` already exists in `rewards.py`; `templates.py` has suturing template; action space needs EE+deltas (Phase 2 work) |
| Knot-tying task | Standard dexterity benchmark in surgical robotics research (JIGSAWS dataset evaluates knot-tying) | HIGH | Requires dual-arm or sequential arm coordination; no existing knot-tying reward function; needs suture thread physics model |
| Needle insertion task | Entry point into tissue is a fundamental surgical primitive; tests puncture physics | MEDIUM | Needle mesh + tissue contact detection + insertion depth observation — no existing insertion reward |
| Grasping task (pick-and-place) | Every manipulation RL benchmark starts with grasping; table stakes for any robotics system | LOW | `ManipulationTemplate` exists; `GraspingReward` implicit in composite reward; gripper actuation (Phase 2) |
| Cutting task (straight line incision) | Cutting is Surg-RL's headline feature (Phase 17); must be a trainable task | MEDIUM | Volumetric cutting engine exists; needs `CuttingReward` (straightness, depth consistency) |
| Progressive difficulty levels (3-4 levels per task) | Users expect progressive difficulty out of the box — `easy/medium/hard` is the standard vocabulary | MEDIUM | `CurriculumScheduler` (4-stage) exists in `curriculum.py` but is generic — needs per-task parameter mappings |
| Benchmark metrics per task (success rate, completion time, tissue damage) | Evaluators need quantitative metrics to compare agents | LOW | `EvaluationCallback` exists; extend to per-task metric logging |

### Differentiators

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Task chain/sequence system (compositing subtasks into procedures) | Grasp → cut → suture is a mini-procedure; no open-source RL framework has task composition for surgical workflows | HIGH | Novel infrastructure: `TaskChain` scheduler with prerequisite gates, carry-over state, composite success criteria |
| Multi-task training (single policy on multiple tasks) | Transfer learning across surgical primitives accelerates convergence; SB3 supports multi-env VecEnv out of the box | MEDIUM | `make_vec_env` with task-typed envs; requires unified observation/action space across tasks |
| Task-specific domain randomization (different noise levels per task) | Suturing needs fine position noise; cutting needs coarse force noise; one-size-fits-all randomization hurts learning | MEDIUM | `ParameterRandomizer` already supports per-parameter config; extend to per-task noise profiles |
| Dissection task (separating tissue layers) | Distinct from cutting; requires force-controlled peeling rather than position-controlled slicing | HIGH | Requires tissue adhesion physics + layer separation detection; no existing dissection physics model |
| Curriculum that auto-advances across task types | Start on grasping → unlock cutting at 80% success → unlock suturing at 80% | MEDIUM | `CurriculumScheduler` has stage advancement; extend to cross-task stage gating |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full cholecystectomy (gallbladder removal) procedure | Complete procedures have dozens of subtasks; training a single policy end-to-end is a research problem, not an engineering deliverable | Task chain of 2-3 composited subtasks (e.g., expose → cut → extract) as a demonstration ceiling |
| Real-time surgeon-in-the-loop (human vs agent evaluation) | Requires VR/haptic interface, network synchronization, human study IRB approval | Offline evaluation against recorded trajectories or scripted baseline policies |
| Automated surgical skill assessment (OSATS scoring) | Subjective surgical skill metrics require expert annotation and validated rubrics; outside scope of an RL training system | Objective metrics only: path length, smoothness, tissue damage count, completion time |
| Patient-specific anatomy adaptation | Requires segmentation pipeline + patient data compliance — medical device territory | Parameterized anatomical variation (size, shape, stiffness ranges) — not patient-specific |

### Feature Dependency Graph (Feature 2)

```
Feature 1 (Real Assets)
    │
    └──> SurgicalTask base class (new)
              │
              ├── SuturingTask (extends, uses needle driver mesh + thread reward)
              ├── KnotTyingTask (extends, uses dual-arm + thread physics)
              ├── NeedleInsertionTask (extends, uses needle + tissue)
              ├── GraspingTask (extends, uses forceps + object)
              ├── CuttingTask (extends, uses scalpel + volumetric cut)
              └── DissectionTask (extends, uses retractor + layer peel)
              │
              v
         TaskRegistry (maps task name → task class + default curriculum)
              │
              v
         TaskChainScheduler (new — composes tasks into procedures)
              │
              v
         SurgicalEnv (extended — supports multi-task reset)
              │
              v
         TrainingManager (extended — multi-task training with VecEnv)
```

### Implementation Notes

- **Existing foundation:** 8 templates in `templates.py` provide scene definitions but no task-specific training logic. The gap is that templates define *what's in the scene* but not *how to train on it*. A `SurgicalTask` base class with `get_reward_fn()`, `get_curriculum()`, `check_success()` is needed.
- **Task chain design:** Use a directed acyclic graph (DAG) where nodes are tasks and edges are success gates. `TaskChainScheduler` advances to the next node when `check_success()` returns `True` for the current node. State carry-over (grasped object, cut tissue state) must persist across chain transitions.
- **Confidence:** HIGH for individual task implementations (SB3 training on single tasks is well-understood), MEDIUM for task chains (novel composite infrastructure, needs spike).

---

## Feature 3: Performance Benchmarking

### Table Stakes

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| Reproducible experiment runner (fixed seeds, config hashing) | Without reproducible experiments, benchmarking is meaningless; SB3 already uses `seed` parameter but Surg-RL's env pipeline has additional randomization points | LOW | `EnvironmentController.reset()` already accepts seed; need end-to-end seed propagation + config hash |
| Training curves (reward vs timesteps) | Universal format for RL results; users expect plots | LOW | SB3 TensorBoard integration exists; add matplotlib export |
| Evaluation metrics table (mean reward, std, success rate per task) | Tabular comparison is the standard format for RL papers | LOW | `EvaluationCallback` already computes these per evaluation; serialize to CSV/table |
| SB3 algorithm comparison (PPO vs SAC vs TD3 on same task) | Users want to know which algorithm works best for their task | LOW | `TrainingManager.train()` already supports all 5 algorithms; just need a runner script that loops over algorithm names |

### Differentiators

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| SB3 vs DreamerV3 comparison (same task, same compute budget) | No open-source surgical RL baseline does cross-paradigm benchmarking; this is publication-quality research output | MEDIUM | Requires Feature 5 (DreamerV3) to be operational; needs common evaluation protocol across model-free and model-based methods |
| Publication-quality plots (LaTeX-ready, consistent styling) | Researchers want figures they can drop into papers without reformatting | LOW | Matplotlib + seaborn with configurable style presets |
| Benchmark report auto-generation (Markdown + PDF) | One-command reproducibility: `surg-rl benchmark --task suturing --algorithms ppo,sac,dreamerv3` → report.md | MEDIUM | All components above + Jinja2/Markdown template for report generation |
| Compute budget normalization (wall-clock time or FLOPs, not just steps) | Model-based methods (DreamerV3) use environment steps differently than model-free methods (SB3); fair comparison needs wall-clock equivalence | MEDIUM | Instrument training loops for wall-clock tracking; FLOP estimation needs JAX profiling |
| Hyperparameter sweep support | RL results are sensitive to hyperparameters; benchmarks are more convincing when they show sensitivity | MEDIUM | Optuna integration or simple grid search; RL Baselines3 Zoo (`rl_zoo3`) already does this for gym envs |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time web dashboard for live benchmarking | Adds web stack (JS, websockets); benchmarking is a batch process, not interactive | CLI output + static report files |
| Cloud-based benchmark service (submit job → get results) | Turns a research tool into a SaaS product; users have their own compute | Local runner + documented cloud scripts (Slurm, AWS Batch) |
| Leaderboard / public ranking of submitted results | Requires moderation, anti-cheating, persistent storage; community management headache | Encourage users to publish results in their own papers citing Surg-RL |
| Automatic significance testing (t-test, bootstrap CI) | Statistical rigor is important but easy to misuse; leave statistical analysis to the researcher | Provide raw CSV data + documentation on how to run statistical tests |

### Feature Dependency Graph (Feature 3)

```
ExperimentConfig (Pydantic v2 — seeds, algorithms, tasks, budget, repetitions)
    │
    v
ExperimentRunner (new)
    │
    ├──> Reproducibility: seed propagation → config hash → deterministic env reset
    │
    ├──> SB3 training loop (existing TrainingManager.train())
    │
    ├──> DreamerV3 training loop (new — Feature 5)
    │
    ├──> Evaluation: shared protocol across algorithm backends
    │         ├── collect episode metrics (reward, length, success)
    │         └── aggregate stats (mean, std, CI over N repetitions)
    │
    └──> Output:
              ├── training_curves.png (matplotlib — reward vs steps)
              ├── comparison_table.csv (algorithm × task × metric)
              └── benchmark_report.md (Jinja2 template → Markdown)
```

### Implementation Notes

- **Existing foundation:** `TrainingManager` has `train()` and `evaluate()` methods. `EvaluationCallback` logs metrics during training. The gap is the *orchestration* — nothing ties together multiple algorithm runs with seed management and report generation.
- **RL Baselines3 Zoo precedent:** The SB3 ecosystem already has `rl_zoo3` (a.k.a. RL Baselines3 Zoo) which handles training, hyperparameter tuning, evaluation, and plotting for Gymnasium environments. Surg-RL should model its benchmark runner on `rl_zoo3`'s `benchmark` module, adapting it for surgical tasks.
- **DreamerV3 evaluation protocol:** DreamerV3's `embodied` framework uses its own evaluation loop with configurable environment steps. Surg-RL must define a common evaluation protocol (N episodes × M env steps) that works for both SB3's `model.predict()` interface and DreamerV3's `agent.policy()` interface.
- **Confidence:** HIGH for SB3-only benchmarking (well-understood pattern from `rl_zoo3`), MEDIUM for cross-paradigm comparison (need DreamerV3 operational first).

---

## Feature 4: Multi-Agent RL (PettingZoo)

### Table Stakes

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| PettingZoo `ParallelEnv` wrapper for surgical scenes | PettingZoo is the Farama Foundation standard for MARL; Gymnasium compatibility is insufficient for multi-agent | MEDIUM | New `surg_rl/rl/multi_agent.py` implementing `ParallelEnv`; wraps `SurgicalEnv` per agent |
| Dual-arm robot (two `RobotConfig` instances in one scene) | Most surgical robots are dual-arm (da Vinci has 4 arms, but 2 "working" arms is the minimum viable dual-arm scenario) | MEDIUM | `SceneDefinition.robots` is a list — already supports multiple robots; need coordination layer between two sim-controlled arms |
| Independent PPO training (each arm gets own SB3 policy) | Simplest MARL setup; each arm is a separate SB3 agent with its own observation/action space | LOW | `pettingzoo_env_to_vec_env_v1` + `concat_vec_envs_v1` from SuperSuit; documented pattern in PettingZoo SB3 tutorial |
| Shared observation space (both arms see the same scene state) | Starting point for dual-arm; both policies get the same observation dict | LOW | `ObservationBuilder` already produces backend-agnostic Observation; just duplicate for each agent |

### Differentiators

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Asymmetric observation spaces (dominant arm vs assisting arm see different things) | Real surgery has role differentiation: one arm cuts, the other retracts; each needs different observations | MEDIUM | `observation_space(agent)` in PettingZoo `ParallelEnv` already supports per-agent spaces; need role-aware `ObservationBuilder` |
| Asymmetric action spaces (dominant arm has 6-DOF, assisting arm has 3-DOF) | Retractor arm needs fewer DOF than scalpel arm; reduces action space dimensionality | MEDIUM | `action_space(agent)` in PettingZoo already supports per-agent spaces; `ActionConfig` per robot |
| Shared vs custom policy toggle | Researchers need to test whether arms should share a common policy or specialize | LOW | In shared mode, both agents use the same SB3 model; in custom mode, each loads separate model |
| Dual-arm coordination reward (synergy bonus for coordinated actions) | Arms that work together (e.g., one holds tissue while other cuts) should get a coordination bonus | MEDIUM | New `CoordinationReward` component measuring relative tool distance, complementary action patterns |
| Mixed robot types (one robot is position-controlled, other is torque-controlled) | Different arms may have different control modalities; realistic for heterogeneous surgical setups | MEDIUM | `RobotConfig` per instance already has action type; action space mapping per agent |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full da Vinci 4-arm simulation | 4-arm coordination is exponentially harder than dual-arm; diminishing returns for research value | Cap at dual-arm; document how to extend to N arms |
| Multi-surgeon coordination (human + robot + robot) | Human-in-the-loop MARL is an active research area; integrating it into Surg-RL would be a PhD thesis, not a feature | Single-surgeon setting: one operator controlling N robotic arms via RL policies |
| PettingZoo AEC API (turn-based surgical actions) | Surgery is not turn-based; arms act simultaneously in parallel | Use only PettingZoo's Parallel API (AEC conversion is available if needed) |
| Centralized training with decentralized execution (CTDE) architectures like MADDPG | MA-specific algorithms require significant infrastructure (centralized critic, agent communication channels); SB3 doesn't support them natively | Start with independent PPO/SAC per agent; document how to plug in MA algorithms later |
| Inter-agent communication channel (arms "talk" to each other) | Adds communication learning research question on top of already-complex surgical task learning | Implicit coordination via shared observation space; no explicit communication channel |

### Feature Dependency Graph (Feature 4)

```
Feature 1 (Real Assets — dual-arm needs two instrument meshes)
    │
    v
SceneDefinition with two robots + two instruments
    │
    v
SurgicalMultiAgentEnv (new — extends pettingzoo.ParallelEnv)
    │
    ├── agent "arm_0" (dominant): observation_space(), action_space()
    ├── agent "arm_1" (assisting): observation_space(), action_space()
    │
    ├── reset(): creates SurgicalEnv with both arms → returns {agent: obs}
    ├── step(actions): applies actions to both arms → returns {agent: (obs, reward, term, trunc, info)}
    │
    v
SuperSuit wrappers (pettingzoo_env_to_vec_env_v1, concat_vec_envs_v1)
    │
    v
SB3 training (PPO/SAC per agent or shared model)
    │
    v
PettingZoo evaluation (AEC loop for agent-aware evaluation)
```

### Implementation Notes

- **PettingZoo integration pattern:** The standard approach is to implement `ParallelEnv` (not AEC) for surgical tasks. Each agent is a surgical arm. The environment owns a single `SurgicalEnv` internally and routes observations/actions per agent.
- **SuperSuit dependency:** `supersuit` package is required for `pettingzoo_env_to_vec_env_v1` and `concat_vec_envs_v1`. Add to `[dev]` optional deps or make it a core dependency of the MARL feature.
- **Agent lifecycle:** Unlike PettingZoo game environments where agents can die/spawn, surgical arms persist for the entire episode. This simplifies the wrapper — no `black_death` wrapper needed.
- **State carry-over for shared sim:** Both arms share one physics simulation. Actions from all agents are collected in `step()` and applied simultaneously. Reward is per-agent but can include team bonuses.
- **Confidence:** HIGH for basic dual-arm with independent policies (PettingZoo provides this pattern out of the box), MEDIUM for asymmetric spaces (per-agent space definitions are standard PettingZoo but role-aware observation building is custom).

---

## Feature 5: DreamerV3 World Models

### Table Stakes

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| DreamerV3 agent instantiation with surgical observation/action spaces | DreamerV3 claims "fixed hyperparameters across 150+ tasks" — users expect it to "just work" on surgical environments too | HIGH | JAX + `dreamerv3` package; `embodied` framework; observation space mapping from Gymnasium → elements.Space |
| Training from pixel observations (render → world model → plan) | DreamerV3's headline capability is learning from pixels; surgical sims render RGB views that the world model should consume | HIGH | MuJoCo 3.x `Renderer` API or PyBullet `getCameraImage()` for pixel observations; DreamerV3 CNN encoder config |
| Training from low-dimensional state (proprioception vectors) | Not all surgical RL uses pixels; proprioception (joint angles, EE pose, forces) should also work as DreamerV3 input | MEDIUM | `ObservationBuilder` already produces structured observations; map to DreamerV3's vector observation space |
| Checkpoint save/restore for long training runs | DreamerV3 training can take days; checkpointing is non-negotiable | LOW | DreamerV3 `elements.Checkpoint` already handles this; logdir management |

### Differentiators

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Surgical scene planning (world model imagines cutting outcomes before acting) | The world model should predict how tissue deforms after a cut and plan accordingly — this is the core value of model-based RL for surgery | VERY HIGH | Requires DreamerV3's RSSM to accurately model deformable tissue dynamics, fluid effects, and cutting discontinuities — this is an open research question |
| Learned dynamics transfer (pre-train world model on simple tasks, fine-tune on complex) | World model trained on grasping should accelerate learning for suturing; DreamerV3's RSSM is a reusable internal simulator | HIGH | Checkpoint transfer between DreamerV3 runs; latent representation compatibility across tasks |
| Pixel-based policy that "sees" tissue color changes during cutting | DreamerV3 CNN encoder processes RGB frames; could learn to associate tissue color with damage state | MEDIUM | RGB rendering from MuJoCo/PyBullet; color-based tissue state visualization (already in `scene_builder.py` with `RgbColor`) |
| DreamerV3 + SB3 hybrid (use DreamerV3 latent states as SB3 observations) | Combines model-based representation learning with model-free policy optimization — a novel hybrid approach | HIGH | DreamerV3 latent encoder → SB3 observation space bridge; non-trivial integration |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time world model inference during live surgery | DreamerV3 inference is computationally expensive (RSSM+CNN+actor); real-time requirements would require model distillation/quantization | Offline planning: world model runs in training loop, not at deployment time |
| DreamerV3 from scratch on full surgical procedures | Training world models on complex multi-task procedures is computationally prohibitive and success is not guaranteed | Start with single primitive tasks (grasping, cutting); progressively scale up |
| Custom DreamerV3 architecture modifications | DreamerV3's claim is fixed hyperparameters; modifying the architecture undermines the reproducibility guarantee | Use stock DreamerV3 config; only tune environment integration, not the algorithm |
| Multi-agent DreamerV3 (RSSM for each agent) | Multi-agent world models are an active research area; combining PettingZoo MARL with DreamerV3 is a PhD-level project | Single-agent DreamerV3 only for v0.4.0 |

### Feature Dependency Graph (Feature 5)

```
JAX (>=0.4.0) + DreamerV3 package + Embodied framework
    │
    v
Observation Space Bridge (new: Gymnasium spaces → elements.Space)
    │
    ├── Pixel mode: MuJoCo/PyBullet render → (H, W, C) uint8 → DreamerV3 encoder
    ├── Vector mode: ObservationBuilder → flat vector → DreamerV3 encoder
    │
    v
DreamerV3 Agent (stock config from configs.yaml, task-appropriate overrides)
    │
    ├── Encoder: CNN (pixel) or MLP (vector)
    ├── RSSM: deter=4096, stoch=32, classes=32 (default; scale with --size flag)
    ├── Decoder: predicts next observation + reward
    ├── Actor: continuous action space (EE pose deltas, joint torques)
    └── Critic: symexp_twohot value distribution
    │
    v
Training Loop (embodied.Driver + data stream from replay buffer)
    │
    ├── Environment interaction: SurgicalEnv.step() → embodied transition
    ├── Replay buffer: uniform sampling with configurable capacity
    ├── Model training: world model loss + actor-critic loss + KL balancing
    └── Logging: embodied.Logger → JSONL metrics + Scope viewer
    │
    v
Evaluation: agent.policy(mode='eval') → deterministic actions → episode metrics
    │
    v
Benchmark integration: Feature 3's ExperimentRunner drives DreamerV3 training
```

### Implementation Notes

- **JAX requirement:** DreamerV3 requires JAX (not PyTorch). This is a new dependency with significant implications:
  - JAX + PyTorch coexistence is supported but requires careful CUDA version management
  - Apple Silicon MPS (Phase 10) — JAX supports Metal via `jax-metal` but DreamerV3's `jax.platform` flag must be set to `cpu` on macOS (Metal support in JAX is less mature than CUDA)
  - Docker images (Phase 11) need JAX + CUDA layers added
- **DreamerV3 as optional dependency:** Add `[dreamer]` extras group: `jax, jaxlib, dreamerv3, embodied`. Like `[vision]` and `[ros2]`, lazy import — no crash if not installed.
- **Environment integration challenge:** DreamerV3's `embodied` framework expects environments that produce transitions in `embodied` format. Surg-RL must implement an `embodied.Env` adapter that wraps `SurgicalEnv`. This is non-trivial — `embodied` has its own reset/step/observation space conventions that differ from Gymnasium.
- **Scalability concerns:** DreamerV3 training on pixel observations is GPU-intensive. A typical surgical scene rendered at 64×64 pixels, trained for 1M environment steps, could take 12-24 hours on a single A100. The `debug` config mode should be provided for quick smoke tests.
- **Confidence:** MEDIUM. DreamerV3's "fixed hyperparameters" claim is tested on DMC, Atari, Crafter, and Minecraft — none involve deformable physics or discontinuous dynamics (cutting). Whether the RSSM can model tet mesh cutting dynamics is an open question that requires experimental validation. The integration plumbing (env adapter, obs space mapping) is engineering — well-understood. The learning performance is research — uncertain.

---

## Cross-Feature Dependencies (Full System)

```
                    ┌─────────────────────┐
                    │  Real Assets (F1)    │ ← replaces primitive fallbacks
                    └────────┬────────────┘
                             │ provides meshes & organ geometries
              ┌──────────────┼──────────────┐
              v              v              v
    ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Task Curric  │  │ Multi-Agent  │  │  DreamerV3   │
    │   (F2)       │  │   (F4)       │  │    (F5)      │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           │                 │                 │
           │     uses both   │                 │
           └────────┬────────┘                 │
                    │                          │
                    v                          v
         ┌──────────────────────────────────────┐
         │     Performance Benchmarking (F3)    │ ← consumes all above
         │   (SB3 + DreamerV3 comparison)      │
         └──────────────────────────────────────┘
```

### Phase Ordering Implication

The dependency graph suggests this phase ordering:

1. **Real Assets (F1)** — Foundation for everything. All downstream features need real meshes to produce meaningful results.
2. **Surgical Task Curriculum (F2)** — Requires real assets for task-specific meshes. Independent of MARL and DreamerV3.
3. **Multi-Agent RL (F4)** — Requires dual-arm instrument meshes (F1). Can be developed in parallel with task curriculum on single tasks.
4. **DreamerV3 (F5)** — Requires surgical environments to exist (F1+F2). The riskiest feature — start early to validate feasibility.
5. **Performance Benchmarking (F3)** — Consumes all features. Must be last since it benchmarks everything.

**Revised ordering** (to de-risk DreamerV3):
1. **Real Assets** — Unblocking prerequisite
2. **Surgical Task Curriculum** — Core training value
3. **DreamerV3 (feasibility spike)** — Validate that RSSM can learn surgical dynamics; defer full integration if results are negative
4. **Multi-Agent RL** — Can be developed in parallel after real assets
5. **Performance Benchmarking** — Final integration layer

---

## Overall Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Technical Risk | Priority | Category |
|---------|------------|---------------------|----------------|----------|----------|
| Real instrument meshes (forceps, scalpel, needle driver) | HIGH | LOW | LOW | P1 | Table Stakes |
| Real organ meshes (liver, stomach) as deformable | HIGH | HIGH | MEDIUM | P1 | Table Stakes |
| Suturing task with training pipeline | HIGH | MEDIUM | LOW | P1 | Table Stakes |
| Grasping task with training pipeline | HIGH | LOW | LOW | P1 | Table Stakes |
| Cutting task with training pipeline | HIGH | MEDIUM | LOW | P1 | Table Stakes |
| Progressive difficulty per task | MEDIUM | MEDIUM | LOW | P1 | Table Stakes |
| Reproducible experiment runner | HIGH | LOW | LOW | P1 | Table Stakes |
| SB3 benchmark plots and tables | MEDIUM | LOW | LOW | P2 | Table Stakes |
| Knot-tying task | MEDIUM | HIGH | MEDIUM | P2 | Differentiator |
| Needle insertion task | MEDIUM | MEDIUM | LOW | P2 | Table Stakes |
| Task chain system (composite procedures) | HIGH | HIGH | MEDIUM | P2 | Differentiator |
| PettingZoo dual-arm (independent policies) | MEDIUM | MEDIUM | LOW | P2 | Table Stakes |
| Asymmetric observation/action spaces | MEDIUM | MEDIUM | LOW | P3 | Differentiator |
| DreamerV3 from pixels | HIGH | HIGH | HIGH | P2 | Differentiator |
| DreamerV3 from low-dim state | MEDIUM | MEDIUM | MEDIUM | P3 | Table Stakes |
| SB3 vs DreamerV3 comparison | HIGH | MEDIUM | MEDIUM | P3 | Differentiator |
| Publication-quality report generation | MEDIUM | LOW | LOW | P3 | Differentiator |
| Hyperparameter sweep support | LOW | MEDIUM | LOW | P3 | Differentiator |

---

## MVP Definition for v0.4.0

### Must Ship (P1 — v0.4.0 is incomplete without these)

- [ ] 4 real instrument meshes: forceps, scalpel, needle driver, retractor — loaded as OBJ, replacing primitive boxes
- [ ] 2 deformable organ meshes: liver, stomach — tetrahedralized via tetgen pipeline
- [ ] 3 trainable tasks: suturing, grasping, cutting — each with reward function, curriculum, SB3 training
- [ ] Progressive difficulty (easy/medium/hard) for all 3 tasks
- [ ] Reproducible experiment runner: `surg-rl benchmark --task suturing --algorithms ppo,sac`
- [ ] Training curves and evaluation metric tables (matplotlib)
- [ ] Dual-arm PettingZoo environment (independent PPO policies, shared observation)

### Should Ship (P2 — deferrable to v0.4.1 if schedule slips)

- [ ] Knot-tying and needle insertion tasks
- [ ] Task chain system (grasp → cut → suture)
- [ ] DreamerV3 integration for single surgical task (pixel mode)
- [ ] SB3 algorithm comparison report template

### Nice to Have (P3 — v0.5.0 candidates)

- [ ] Asymmetric observation/action spaces per arm
- [ ] DreamerV3 from low-dim state
- [ ] SB3 vs DreamerV3 benchmark comparison
- [ ] Publication-quality report generation
- [ ] Hyperparameter sweep support
- [ ] Kidney and gallbladder organ meshes
- [ ] Dissection task with layer separation

---

## Sources

- **PettingZoo** — Context7 `/farama-foundation/pettingzoo` + official docs at [pettingzoo.farama.org](https://pettingzoo.farama.org). Custom environment creation tutorial, ParallelEnv API, SB3 integration pattern confirmed.
- **DreamerV3** — Context7 `/danijar/dreamerv3` + [arXiv 2301.04104](https://arxiv.org/abs/2301.04104) + [GitHub repo](https://github.com/danijar/dreamerv3). Architecture: RSSM (GRU+stochastic latents) + CNN/MLP encoder + actor-critic on imagined rollouts. JAX-based, `embodied` framework for env integration.
- **RL Baselines3 Zoo** — Context7 `/dlr-rm/rl-baselines3-zoo`. Benchmark runner pattern, hyperparameter tuning with Optuna, plot generation.
- **Surg-RL codebase** — `templates.py` (8 existing templates, all use primitive meshes), `environment.py` (`SurgicalEnv` class), `training.py` (`TrainingManager`), `curriculum.py` (4-stage scheduler), `rewards.py` (10+ reward components). Grep confirms zero existing PettingZoo or DreamerV3 code.
- **MuJoCo Menagerie** — [GitHub](https://github.com/google-deepmind/mujoco_menagerie) for robot mesh reference; no surgical instruments available.
- **Surgical robotics literature** — JIGSAWS dataset for task definitions (suturing, knot-tying, needle passing), dVRK for dual-arm reference architecture.
- **PROJECT.md** — Current milestone definition and scope boundaries (no FDA, no Unity, no real patient data).

---

*Feature research for: Surg-RL v0.4.0 — Training Infrastructure & Realism*
*Researched: 2026-05-13*
*Ready for roadmap: yes*
