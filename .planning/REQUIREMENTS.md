# Requirements: Surg-RL v0.4.0

**Defined:** 2026-05-13
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation

## v1 Requirements

### Real Assets

- [x] **ASET-01**: System loads OBJ instrument meshes (forceps, scalpel, needle driver, retractor, trocar, scissors, clamp, plus 3 general-purpose instruments) via trimesh, generating URDF/MJCF collision geometry for both MuJoCo and PyBullet backends
- [x] **ASET-02**: System loads 4 organ meshes (liver, stomach, kidney, gallbladder) as OBJ surface meshes, converting them through the existing tetgen pipeline for deformable simulation with volumetric cutting support
- [x] **ASET-03**: All real meshes silently fall back to existing primitive geometry when the mesh file is not found at the configured path — no crashes, no breaking changes to existing scenes
- [x] **ASET-04**: Mesh assets support configurable decimation (target face count) to control simulation performance without manual mesh editing
- [x] **ASET-05**: New `[assets]` optional dependency group (`trimesh>=4.5.0`) with lazy import; mesh pipeline is additive and never blocks core imports

### Surgical Task Curriculum

- [x] **TASK-01**: System provides 6 surgical task types (suturing, knot-tying, needle insertion, grasping, cutting, dissection), each with a TaskConfig schema defining task-specific reward functions and success/failure detection criteria
- [ ] **TASK-02**: Each task type supports 3 difficulty levels (easy/medium/hard) with progressive parameter changes (tissue stiffness, target precision tolerance, tool position noise, time limit)
- [x] **TASK-03**: Task difficulty integrates with the existing `CurriculumScheduler` — `CurriculumStageConfig` extended with a `task_difficulty` field without replacing or rewriting existing curriculum machinery
- [x] **TASK-04**: Task success/failure is detectable at episode end via `check_success()` and `check_failure()` methods, returning structured results (success, failure_reason, metrics) for benchmarking integration

### Performance Benchmarking

- [x] **BENCH-01**: `ExperimentRunner` wraps the existing `TrainingManager` and runs configurable multi-seed, multi-algorithm experiments on surgical tasks with automatic results aggregation
- [ ] **BENCH-02**: Benchmarking compares SB3 algorithms (PPO, SAC, TD3, DDPG, A2C) against DreamerV3 world models with standardized metrics: mean reward, success rate, episode length, wall-clock time, sample efficiency
- [ ] **BENCH-03**: Benchmark output includes publication-quality plots (learning curves with mean ± std across seeds, success rate bar charts) and tables (algorithm comparison with statistical significance via rliable)
- [ ] **BENCH-04**: Experiment configurations are serializable (JSON/YAML) for reproducibility — a single command (`surg-rl benchmark`) reproduces an entire experiment run
- [ ] **BENCH-05**: Benchmarking treats MuJoCo and PyBullet as separate hardware targets — never assumes cross-backend determinism; reports results per backend

### Multi-Agent RL

- [x] **MARL-01**: `MultiAgentSurgicalEnv` implements PettingZoo `ParallelEnv` with asymmetric roles: surgeon arm (dexterous manipulation) and assistant/camera arm (positioning/visualization), each with distinct observation and action spaces
- [x] **MARL-02**: SuperSuit wrappers enable SB3-compatible policy training from PettingZoo environments without manual Gymnasium conversion
- [x] **MARL-03**: Multi-agent configuration (`MultiAgentConfig`) supports both shared policy (both agents learn from a single model) and independent per-agent policies
- [x] **MARL-04**: The multi-agent env delegates to the canonical `SurgicalEnv` for simulation — never duplicates sim logic; MARL is a thin adapter layer

### DreamerV3 World Models

- [x] **DMV3-01**: Feasibility spike verifies that DreamerV3's RSSM can learn dynamics of a simple surgical scene (single instrument + deformable tissue) from pixel observations — report pass/fail with quantitative evidence (reconstruction quality, reward prediction accuracy)
- [x] **DMV3-02**: If spike passes: `GymToEmbodiedWrapper` adapts `SurgicalEnv` to the `embodied.Env` protocol (action dict with reset signal, flat observation dict with is_first/is_last/is_terminal), enabling DreamerV3 to train on surgical scenes
- [x] **DMV3-03**: DreamerV3 runs in process isolation (separate subprocess or venv) from PyTorch/SB3 code to prevent JAX+PyTorch GPU memory conflicts
- [x] **DMV3-04**: DreamerV3 supports both pixel-based observation (raw render) and low-dim state observation, configurable via `DreamerConfig`
- [x] **DMV3-05**: If spike fails: DreamerV3 is deferred to v0.5.0 with documented failure evidence; Phase 4 benchmarking reverts to SB3-only comparison

## v2 Requirements

### Future Features

- **TASK-05**: Task chain system compositing subtasks into procedures (grasp → cut → suture)
- **MARL-05**: RLlib-backed centralized critic for MARL training (beyond independent SB3 policies)
- **DMV3-06**: DreamerV3 offline training from recorded surgical demonstrations

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time multi-user networked surgery | Single-agent / dual-agent training scope |
| FDA certification / medical-grade validation | Research and simulation tool, not clinical device |
| Task chains (grasp→cut→suture) | Deferred to v0.5.0 — composite scheduling requires novel infrastructure; individual tasks sufficient for v0.4.0 |
| RLlib MARL centralized critic | Independent SB3 policies via SuperSuit sufficient for dual-arm; centralized critic adds RLlib complexity |
| 3D DreamerV3 video prediction | 2D pixel reconstruction sufficient for feasibility assessment |
| COLLADA/glTF mesh format support | OBJ is the universal baseline for both backends; multi-format adds complexity without clear benefit |
| Helm chart | Kustomize overlays sufficient; Helm can be added later |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ASET-01 | Phase 20 | Complete |
| ASET-02 | Phase 20 | Complete |
| ASET-03 | Phase 20 | Complete |
| ASET-04 | Phase 20 | Complete |
| ASET-05 | Phase 20 | Complete |
| TASK-01 | Phase 21 | Complete |
| TASK-02 | Phase 27 | Pending |
| TASK-03 | Phase 21 | Complete |
| TASK-04 | Phase 21 | Complete |
| BENCH-01 | Phase 27 | Complete |
| BENCH-02 | Phase 23 | Complete |
| BENCH-03 | Phase 23 | Complete |
| BENCH-04 | Phase 23 | Complete |
| BENCH-05 | Phase 23 | Complete |
| MARL-01 | Phase 22 | Complete |
| MARL-02 | Phase 22 | Complete |
| MARL-03 | Phase 22 | Complete |
| MARL-04 | Phase 25 | Complete |
| DMV3-01 | Phase 24 | Complete |
| DMV3-02 | Phase 24 | Complete |
| DMV3-03 | Phase 24 | Complete |
| DMV3-04 | Phase 24 | Complete |
| DMV3-05 | Phase 24 | Complete |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23 ✓
- Unmapped: 0

---

*Requirements defined: 2026-05-13 after v0.4.0 milestone research*
*Traceability updated: 2026-05-13 after roadmap creation; v0.4.1 gap-closure phases assigned 2026-06-10*
