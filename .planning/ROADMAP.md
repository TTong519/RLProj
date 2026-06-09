# Roadmap: Surg-RL

## Milestones

- ✅ **v0.1.0 Stabilization** — Phases 1–5 (shipped 2026-05-02)
- ✅ **v0.2.0 Scaling, Rendering & Real Robot** — Phases 6–9 (shipped 2026-05-03)
- ✅ **v0.3.0 Production & Cross-Platform** — Phases 10–13 (shipped 2026-05-04)
- ✅ **v0.3.1 Audit Gap Closure** — Phase 14 (shipped 2026-05-04) · [archive](milestones/v0.3.1-ROADMAP.md)
- ✅ **v0.3.2 Advanced Simulation** — Phases 15–18 (shipped 2026-05-05)
- 🚧 **v0.4.0 Training Infrastructure & Realism** — Phases 19–24 (in progress)

## Phases

<details>
<summary>✅ v0.1.0 Stabilization (Phases 1–5) — SHIPPED 2026-05-02</summary>

- [x] Phase 1: Critical Bug Fixes (3/3 plans)
- [x] Phase 2: Action Space + Gripper (3/3 plans)
- [x] Phase 3: Simulator Robustness (2/2 plans)
- [x] Phase 4: Task Geometry + Real Assets (2/2 plans)
- [x] Phase 5: Experiment Tracking + Infrastructure (2/2 plans)

</details>

<details>
<summary>✅ v0.2.0 Scaling, Rendering & Real Robot (Phases 6–9) — SHIPPED 2026-05-03</summary>

- [x] Phase 6: Universal Hardware Acceleration (3/3 plans)
- [x] Phase 7: Real-time Rendering (3/3 plans)
- [x] Phase 8: Distributed Training with Ray/RLlib (6/6 plans)
- [x] Phase 9: ROS2 Bridge (5/5 plans + 2 gap closure)

</details>

<details>
<summary>✅ v0.3.0 Production & Cross-Platform (Phases 10–13) — SHIPPED 2026-05-04</summary>

- [x] Phase 10: Metal GPU Compute + macOS Test Parity (4/4 plans)
- [x] Phase 11: Multi-platform Docker (3/3 plans)
- [x] Phase 12: ros2_control + ROS2 Launch Files (6/6 plans)
- [x] Phase 13: Kubernetes Deployment (5/5 plans)

</details>

<details>
<summary>✅ v0.3.1 Audit Gap Closure (Phase 14) — SHIPPED 2026-05-04</summary>

- [x] Phase 14: Audit Gap Closure (1/1 plan, 5 gaps closed)

</details>

<details>
<summary>✅ v0.3.2 Advanced Simulation (Phases 15–18) — SHIPPED 2026-05-05</summary>

- [x] Phase 15: Tetgen Mesh Generation (1/1 plan)
- [x] Phase 16: Deformable Objects (2/2 plans)
- [x] Phase 17: Volumetric Cutting (3/3 plans)
- [x] Phase 18: Grid-based Fluids (3/3 plans, inlined)

</details>

### 🚧 v0.4.0 Training Infrastructure & Realism (In Progress)

**Milestone Goal:** Transform Surg-RL from a simulation framework into a competitive RL research platform with real surgical assets, comprehensive task curriculum, systematic benchmarking, multi-agent support, and DreamerV3 world models.

- [x] **Phase 19: Schema Foundation** — Pydantic v2 models + optional dependency groups for all five v0.4.0 feature modules
- [x] **Phase 20: Real Surgical Assets** — trimesh OBJ loading for instruments (11) and organs (4) with decimation, fallback, and [assets] extras
- [x] **Phase 21: Surgical Task Curriculum** — 6 task types × 3 difficulty levels integrated with CurriculumScheduler, structured success/failure detection · [Plans](phases/21-surgical-task-curriculum/)
- [x] **Phase 22: Multi-Agent RL** — PettingZoo ParallelEnv dual-arm coordination, SuperSuit SB3 wrappers, thin adapter over SurgicalEnv · [Plans](phases/22-multi-agent-rl/)
- [x] **Phase 23: Performance Benchmarking** — ExperimentRunner with SB3-only comparison, publication plots/tables, per-backend reporting
- [ ] **Phase 24: DreamerV3 World Models** — feasibility spike, process-isolated JAX training, GymToEmbodiedWrapper, pixel/state observation

## Phase Details

### Phase 19: Schema Foundation
**Goal**: All new Pydantic v2 models exist in `schema.py` with `None` defaults, all optional dependency groups declared in `pyproject.toml` — no feature work can start until its config model exists.
**Depends on**: Nothing (first phase of v0.4.0)
**Requirements**: (none — foundational phase, prerequisite for all feature phases)
**Success Criteria** (what must be TRUE):
  1. `schema.py` contains `MeshAsset`, `TaskConfig`, `BenchmarkConfig`, `MultiAgentConfig`, `DreamerConfig` Pydantic v2 models — all new fields default to `None`, all existing models unchanged and backward-compatible
  2. `pyproject.toml` declares `[assets]` (trimesh>=4.5.0), `[benchmark]` (matplotlib, seaborn, pandas, rliable), `[marl]` (pettingzoo>=1.24.0, supersuit>=3.9.0), `[dreamer]` (dreamerv3, jax, optax) optional dependency groups with pinned versions
   3. Lazy import guards exist for all new optional dependencies — `import surg_rl` succeeds without trimesh, pettingzoo, or jax installed
   4. All 910 existing tests pass with new schema in place — no regressions from optional field additions to existing Pydantic models
**Plans**: 3 plans in 1 wave

Plans:
- [ ] 19-01-PLAN.md — Extend MeshAsset/TaskConfig, add BenchmarkConfig/MultiAgentConfig/DreamerConfig schema models
- [ ] 19-02-PLAN.md — LazyImport infrastructure + 4 per-package __init__.py lazy import guards
- [ ] 19-03-PLAN.md — pyproject.toml [assets]/[benchmark]/[marl]/[dreamer] optional dependency groups

### Phase 20: Real Surgical Assets
**Goal**: Surgical instrument and organ meshes load via trimesh, integrate with existing scene_builder and tetgen pipeline, silently fall back to primitives when meshes are missing.
**Depends on**: Phase 19
**Requirements**: ASET-01, ASET-02, ASET-03, ASET-04, ASET-05
**Success Criteria** (what must be TRUE):
  1. System loads OBJ instrument meshes (forceps, scalpel, needle driver, retractor, trocar, scissors, clamp, +3 general-purpose) via trimesh and generates URDF/MJCF collision geometry for both MuJoCo and PyBullet backends
  2. System loads 4 organ OBJ meshes (liver, stomach, kidney, gallbladder) and converts them through the existing tetgen pipeline into deformable tetrahedral meshes with volumetric cutting support
  3. When a configured mesh path is missing or points to an invalid file, the system falls back to the existing primitive geometry pipeline — no crashes, no breaking changes to existing scenes, a single warning is emitted
  4. Mesh decimation via `target_face_count` parameter works end-to-end — loading the same mesh at `target_face_count=500` vs `target_face_count=2000` produces visibly different triangle counts in the resulting collision geometry
  5. `pip install surg-rl[assets]` installs trimesh; `import surg_rl` succeeds without trimesh installed — lazy import guard prevents ImportError
**Plans**: TBD

### Phase 21: Surgical Task Curriculum
**Goal**: Six surgical task types with progressive difficulty levels integrate with the existing CurriculumScheduler; structured success/failure detection feeds into benchmarking.
**Depends on**: Phase 20 (tasks reference asset names for instrument assignment)
**Can run in parallel with**: Phase 22 (MARL — both depend on Phase 20, not on each other)
**Requirements**: TASK-01, TASK-02, TASK-03, TASK-04
**Success Criteria** (what must be TRUE):
  1. Six task types (suturing, knot-tying, needle insertion, grasping, cutting, dissection) are defined with distinct reward functions — running `surg-rl train --task grasping` trains an SB3 agent that receives task-specific reward signals
  2. Each task supports easy/medium/hard difficulty levels — difficulty changes observable scene parameters (tissue stiffness, precision tolerance, tool position noise, time limit); running `env.reset(options={"difficulty": "hard"})` produces a noticeably harder configuration than easy
  3. `CurriculumStageConfig.task_difficulty` field exists and integrates with the existing CurriculumScheduler — when agents meet performance thresholds, the scheduler triggers a difficulty bump, observable in training logs as staged difficulty progression
  4. `check_success()` and `check_failure()` return structured results (`success: bool`, `failure_reason: str`, `metrics: dict`) at episode end — an agent that completes a grasping task reports `success=True` with task-specific metrics (e.g. `grasp_completion_time`) in the metrics dict
   5. The Phase 3 CurriculumScheduler `apply_parameters` fix is never modified — all task curriculum additions are purely additive extensions
**Plans**: 3 plans in 3 waves

Plans:
- [ ] 21-01-PLAN.md — Pydantic v2 TaskResult hierarchy (base + 6 per-task sub-models)
- [ ] 21-02-PLAN.md — 3 new + 3 updated reward subclasses with check_success/check_failure/interpolate_params + TaskRewardRouter
- [ ] 21-03-PLAN.md — CurriculumScheduler TaskResult integration + SurgicalEnv router wiring + task_termination per-task delegation

### Phase 22: Multi-Agent RL
**Goal**: Dual-arm PettingZoo ParallelEnv with shared or independent SB3 policies, implemented as a thin adapter layer over the canonical SurgicalEnv — never duplicates sim logic.
**Depends on**: Phase 20 (needs real instruments for dual-arm scene construction)
**Can run in parallel with**: Phase 21 (Task Curriculum — both depend on Phase 20, architecturally independent)
**Requirements**: MARL-01, MARL-02, MARL-03, MARL-04
**Success Criteria** (what must be TRUE):
  1. `MultiAgentSurgicalEnv(ParallelEnv)` creates a dual-arm scene: surgeon arm (dexterous manipulation) + assistant/camera arm (positioning), each with distinct observation and action spaces — `env.reset()` returns a dict of `{agent_id: observation}` per the PettingZoo API
  2. SuperSuit wrappers (e.g. `ss.pettingzoo_env_to_vec_env_v1`) convert the PettingZoo env to a format SB3 can train on — running an SB3 PPO policy against the MARL env completes a full training loop without error
  3. `MultiAgentConfig.shared_policy=True` trains both agents from a single SB3 model; `shared_policy=False` trains independent per-agent policies — both paths complete training and produce checkpoint files
  4. `MultiAgentSurgicalEnv` owns exactly ONE `SurgicalEnv` instance and delegates all simulation logic (physics stepping, reward computation, scene loading) to it — zero simulation code is duplicated in the MARL layer, routing is pure adapter logic
**Plans**: 3 plans in 3 waves

Plans:
- [ ] 22-01-PLAN.md — ArmRole/ArmConfig schema + MultiAgentConfig expansion + SceneDefinition.multi_agent
- [ ] 22-02-PLAN.md — BaseSimulator arm_id routing + MultiAgentSurgicalEnv ParallelEnv + ObservationFilter
- [ ] 22-03-PLAN.md — SuperSuit wrapper pipeline + MultiAgentTrainingManager + surg-rl marl-train CLI

### Phase 23: Performance Benchmarking
**Goal**: Reproducible experiment runner comparing SB3 algorithms across surgical tasks, producing publication-quality plots, tables, and per-backend reports — treats MuJoCo and PyBullet as separate hardware targets.
**Depends on**: Phase 21 (needs task definitions), Phase 22 (needs multi-agent scenes for optional MARL benchmarks)
**Requirements**: BENCH-01, BENCH-02, BENCH-03, BENCH-04, BENCH-05
**Success Criteria** (what must be TRUE):
  1. `surg-rl benchmark --task suturing --algorithms PPO,SAC --seeds 5` runs a 10-experiment sweep (2 algorithms × 5 seeds), aggregates results, and produces a JSON report with per-algorithm metrics (mean reward, success rate, episode length, wall-clock time, sample efficiency)
  2. Benchmark output includes publication-quality learning curves (mean ± 1σ across seeds per timestep) and bar charts (success rate by algorithm with rliable statistical significance: IQM, stratified bootstrap CI)
  3. `ExperimentConfig` serializes to YAML deterministically — `surg-rl benchmark --config experiments/suturing_v1.yaml` reproduces the exact same experiment run with identical seed propagation and hyperparameters
  4. Benchmark reports include a `backend` column — MuJoCo and PyBullet results appear in separate rows/tables; cross-backend aggregation is never performed and the system does not claim cross-backend determinism
  5. SB3-only benchmarking is fully functional at this phase; DreamerV3 comparison is present as a conditional integration point that reports `DreamerV3: pending — Phase 24` when DreamerV3 checkpoints are not yet available
**Plans**: 3 plans in 2 waves

Plans:
- [x] 23-01-PLAN.md — ExperimentConfig schema, YAML round-trip, lazy imports, CLI benchmark subcommand
- [x] 23-02-PLAN.md — ExperimentRunner (multiprocessing seed sweeps), MetricCollectorCallback, Aggregator (IQM, mean±std, scalar metrics)
- [x] 23-03-PLAN.md — PlotRenderer (learning curves, bar charts, tables), ReportGenerator (HTML + JSON), CLI integration

### Phase 24: DreamerV3 World Models
**Goal**: Feasibility spike determines whether DreamerV3's RSSM can model surgical dynamics; if yes, integrate DreamerV3 with process isolation for surgical scene training from pixels or low-dim state.
**Depends on**: Phase 23 (needs benchmarking infrastructure for DreamerV3 vs SB3 comparison), Phase 21 (needs task definitions for training targets)
**Requirements**: DMV3-01, DMV3-02, DMV3-03, DMV3-04, DMV3-05
**Success Criteria** (what must be TRUE):
  1. Feasibility spike produces a definitive report: RSSM trained on a single-instrument + deformable-tissue surgical scene from pixel observations, with quantitative evidence (reconstruction MSE on held-out frames, reward prediction MAE) and a clear pass/fail recommendation against a pre-defined threshold
  2. If spike passes: `surg-rl dreamer-train --task grasping --obs_type pixels` runs DreamerV3 training in a JAX subprocess isolated from the PyTorch/SB3 stack — GPU memory conflicts do not occur (JAX subprocess uses `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`)
  3. If spike passes: `GymToEmbodiedWrapper` translates `SurgicalEnv` to the `embodied.Env` protocol — reset signal embedded in action dict, observations returned as flat dicts with `is_first`/`is_last`/`is_terminal` keys
  4. DreamerV3 supports both pixel-based observation (raw render tensor from MuJoCo/PyBullet) and low-dim state observation (joint positions, task configuration, tissue deformation state) via `DreamerConfig.obs_type` — both modes initialize and begin training without errors
  5. If spike fails: DMV3-02, DMV3-03, DMV3-04 are skipped; full DreamerV3 integration is deferred to v0.5.0 per DMV3-05 with documented failure evidence; Phase 23 benchmark reports are updated to remove the DreamerV3 pending stub and declare SB3-only as the v0.4.0 benchmarking scope
**Plans**: 4 plans in 4 waves

Plans:
- [ ] 24-01-PLAN.md — Feasibility spike infrastructure: DreamerSubprocess (JAX isolation), GymToEmbodiedWrapper, SpikeOrchestrator (forceps+liver+suturing scene, 100k steps, MSE/MAE eval)
- [ ] 24-02-PLAN.md — DreamerV3 training CLI: surg-rl dreamer-train with checkpoint management, resume, eval-only, both obs modes
- [ ] 24-03-PLAN.md — Benchmark integration: auto-discovery of DreamerV3 checkpoints, evaluation without training, orange visualization, HTML/JSON reporting
- [ ] 24-04-PLAN.md — Deferral handling: spike failure report, dreamer-train exit with v0.5.0 pointer, dreamer-spike CLI, SB3-only benchmark mode

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 19. Schema Foundation | 3/3 | Complete | 2026-05-13 |
| 20. Real Surgical Assets | 4/4 | Complete | 2026-05-13 |
| 21. Surgical Task Curriculum | 3/3 | Complete | 2026-05-17 |
| 22. Multi-Agent RL | 3/3 | Complete | 2026-05-18 |
| 23. Performance Benchmarking | 3/3 | Complete | 2026-06-08 |
| 24. DreamerV3 World Models | 0/4 | Planning complete | 2026-06-08 |

---

*Roadmap last updated: 2026-06-08 — Phase 24 context gathered*
