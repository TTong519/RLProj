# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system with production deployment infrastructure and competitive RL research capabilities. Generates and simulates surgical scenes from text/images via LLM/VLM or JSON scene definitions, trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, adaptive difficulty, and dual-arm multi-agent support. Real instrument and organ meshes (trimesh) replace primitive fallbacks; 6 surgical task types span easy/medium/hard difficulty; SB3 benchmark reports with publication-quality plots; optional DreamerV3 world model integration runs in process isolation. Features platform-agnostic tetgen mesh generation, FEM deformable objects, real-time volumetric tetrahedral mesh cutting, and Eulerian grid fluid simulation. Supports Apple Silicon Metal GPU compute, multi-arch Docker images, ROS2 ros2_control integration, and Kubernetes deployment. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.

## Current State

**Shipped v0.4.1** (2026-06-11) — Audit Gap Closure. All v0.1.0 through v0.4.1 milestones shipped (7 milestones, 28 phases, 84 plans, 22/23 v1 requirements satisfied, 1 partial).

## Current Milestone: v0.4.1 Audit Gap Closure (SHIPPED)

**Goal:** Close 14 gaps from the v0.4.0 milestone audit (`.planning/v0.4.0-MILESTONE-AUDIT.md`, status: `gaps_found`). Pure gap-closure milestone — no new features, only bug fixes, retroactive verification, and process reconciliation.

**Audit verdict:** `passed` — 12/14 gaps fully closed, 1 partial (TASK-02 3-difficulty-levels → v0.5.0 backlog), 1 deferred (DreamerV3 real-subprocess E2E → v0.5.0 testing, requires GPU + dreamerv3 install).

**Delivered:**
- ✓ Fixed 4 high-severity MARL runtime bugs (MARL-step, MARL-CLI, MARL-agents, ArmConfig-export) + closed MARL-04 requirement
- ✓ Fixed 3 production-blocking DreamerV3 defects (indig→indent typo, os.fdopen→_JsonStdout wrapper, DREAMER_COLOR)
- ✓ Closed 3 benchmark scene coverage gaps (5 missing task scene JSONs created, task_type wired on all 6 scenes, experiments/{name}.yaml auto-write)
- ✓ Retroactively verified Phases 21, 22, 23 with canonical VERIFICATION.md files
- ✓ Promoted 21-VALIDATION.md to Nyquist-compliant
- ✓ Reconciled REQUIREMENTS.md (BENCH-01 body checkbox flipped to [x])

### Key Deliverables (v0.4.1)
- `SurgicalEnv.passthrough_step()` + `_step_simulator_and_build_outputs()` helper — eliminates ~90 lines of duplicate body, fixes MARL `env.step()` empty-action crash
- `MultiAgentSurgicalEnv.agents` init + `marl-train` CLI dict config — fixes PettingZoo ParallelEnv contract
- `_JsonStdout` wrapper class — replaces `os.fdopen` on PyTorch's non-blocking Pipe (DreamerV3 subprocess)
- 5 new task scene JSONs (knot_tying, needle_insertion, grasping, cutting, dissection) aligned with Phase 24 dreamer_training test contract
- `ExperimentRunner.__init__` writes `experiments/{name}.yaml` so CLI "Reproduce with: --config experiments/{name}.yaml" hint is functional
- 3 retroactive VERIFICATION.md files (Phases 21, 22, 23) citing v0.4.0 audit as source-of-truth
- 28-CLOSURE-REPORT.md — consolidated gap closure matrix (14 gaps: 12 closed, 1 partial, 1 deferred)
- 28-VERIFICATION.md — 7/7 must-haves passed

### Previous Milestone: v0.4.0 Training Infrastructure & Realism (SHIPPED 2026-06-09)

**Goal:** Transform Surg-RL from a simulation framework into a competitive RL research platform with real surgical assets, comprehensive task curriculum, systematic benchmarking, multi-agent support, and DreamerV3 world models.

**Delivered features:**
- ✓ Real surgical instrument meshes (9 URDFs) + organ geometries (4 OBJ→tetgen) replacing primitive fallbacks
- ✓ Full surgical task suite: 6 task types with structured TaskResult hierarchy
- ✓ Reproducible experiment runner with SB3 + DreamerV3 comparison, IQM/mean±std, per-backend reports
- ✓ PettingZoo MARL framework: dual-arm coordination, asymmetric observation/action spaces
- ✓ DreamerV3 world model integration (process-isolated JAX, GymToEmbodiedWrapper, pixel/state obs)
- ✓ Pydantic v2 schema foundation with optional dependency groups (`[assets]`, `[benchmark]`, `[marl]`, `[dreamer]`)

**Key Deliverables (v0.4.0):**
- Schema foundation: 5 new Pydantic v2 config models (MeshAsset, TaskConfig, BenchmarkConfig, MultiAgentConfig, DreamerConfig) with `None` defaults
- trimesh asset pipeline: 9 instrument URDFs with V-HACD collision decomposition, 4 organ meshes through tetgen deformable pipeline
- 6 surgical task types with Pydantic v2 TaskResult hierarchy + TaskRewardRouter; CurriculumScheduler extended additively
- `MultiAgentSurgicalEnv` PettingZoo ParallelEnv + SuperSuit wrappers + shared/independent policy modes
- `ExperimentRunner` with multiprocessing seed sweeps, rliable IQM + mean±std aggregation, publication plots/tables
- DreamerV3 feasibility spike + process-isolated training: GymToEmbodiedWrapper, JAX subprocess with XLA memory fraction, 64×64 RGBA pixel and state observation modes
- Gap closure Plan 24-05: added 3 task types (knot_tying, needle_insertion, dissection) and KNOT_TIER/NEEDLE instrument types

### Accepted Tech Debt (deferred across milestones)
- Per-tet generation counter for degenerate tets after multiple cuts (v0.3.2) — single cut per episode typical
- Cut cooldown unit test (v0.3.2) — requires full env lifecycle, cooldown is simple arithmetic
- Fluid step hook in base_simulator.py (v0.3.2) — env-level hook sufficient
- PhiFlow multi-obstacle union() bug requires merged SDF workaround — documented pitfall
- 2D fluids only (xz-plane); 3D behind dim_3d=True flag, not yet implemented
- Dockerfile.ros2 amd64 hardcode, K8S PVC e2e, KubeRay prerequisite (from v0.3.1)
- Organ mesh source licensing (v0.4.0 Phase 20) — procedural generation or surgtoolloc dataset
- Pre-existing lint issues in `src/surg_rl/dreamer/` (F841, B904, E402; 421 ruff issues total per Phase 24 Nyquist audit) — out of v0.4.1 scope
- REQUIREMENTS.md BENCH-02..05 body checkboxes remain `[ ]` (pre-existing v0.4.0 audit process gap, out of Phase 28 scope)
- Task chain system compositing subtasks (TASK-05) — v2
- RLlib centralized critic for MARL (MARL-05) — v2
- DreamerV3 offline training from recorded demos (DMV3-06) — v2

## Requirements

### Validated (v0.4.0–v0.4.1)

- ✓ All v0.3.0–v0.3.2 features (Metal GPU, multi-arch Docker, ros2_control, K8s, tetgen, FEM deformables, volumetric cutting, grid fluids)
- ✓ **Real Surgical Assets** — trimesh OBJ loading, V-HACD collision, organ OBJ→tetgen, primitive fallback (ASET-01..05) — v0.4.0
- ✓ **Surgical Task Curriculum** — 6 task types, TaskResult hierarchy, TaskRewardRouter activated, additive CurriculumScheduler (TASK-01..04) — v0.4.0
- ✓ **Multi-Agent RL** — PettingZoo ParallelEnv dual-arm, SuperSuit wrappers, shared/independent policies, `SurgicalEnv.passthrough_step()` adapter (MARL-01..04) — v0.4.0 + v0.4.1
- ✓ **Performance Benchmarking** — ExperimentRunner multiprocessing, rliable IQM, per-backend reports, deterministic YAML, 6 task scene JSONs (BENCH-01..05) — v0.4.0 + v0.4.1
- ✓ **DreamerV3 World Models** — Feasibility spike, process-isolated JAX, `_JsonStdout` wrapper, pixel/state obs, auto-discovery (DMV3-01..05) — v0.4.0 + v0.4.1

### Active (Next Milestone — v0.5.0)

- TBD (start v0.5.0 with `/gsd-new-milestone`)
- **TASK-02 3-difficulty-levels** — carried from v0.4.0 audit closure. Each task type must support easy/medium/hard with progressive parameter changes (tissue stiffness, target precision tolerance, tool position noise, time limit). PARAM_BOUNDS + interpolate_params() exists; easy/medium/hard presets not yet defined.
- **DreamerV3 real-subprocess E2E test** — carried from v0.4.1. Code-level fix verified (`_JsonStdout` wrapper + typo + color); real subprocess end-to-end test requires GPU + dreamerv3 install.

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent / dual-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient
- DirectML / Vulkan compute backends — Windows not primary target; niche use case
- Linux-only ROS2 subscriber e2e tests — Requires real ROS2 runtime; mock coverage is sufficient for macOS
- Helm chart — Kustomize overlays sufficient; Helm can be added later
- Real-time ROS2 DDS router for K8s multicast — DDS multicast issue is platform-level; document workaround
- 3D fluid simulation — 2D xz-plane slice is sufficient for surgical bleeding/irrigation; 3D behind dim_3d=True flag
- GPU fluid acceleration — PhiFlow CPU-first; GPU acceleration can be added when needed
- Task chain system (grasp→cut→suture) — Deferred to v0.5.0; requires novel composite scheduling
- RLlib MARL centralized critic — Independent SB3 policies via SuperSuit sufficient; centralized critic adds complexity
- 3D DreamerV3 video prediction — 2D pixel reconstruction sufficient for feasibility assessment
- COLLADA/glTF mesh format — OBJ is universal baseline; multi-format adds complexity without benefit

## Recent Milestones

| Milestone | Phases | Plans | Status |
|-----------|--------|-------|--------|
| v0.1.0 | 1–5 | 12 | Complete |
| v0.2.0 | 6–9 | 19 | Complete |
| v0.3.0 | 10–13 | 18 | Complete |
| v0.3.1 | 14 | 1 | Complete |
| v0.3.2 | 15–18 | 9 | Complete |
| v0.4.0 | 19–24 | 21 | Complete |
| v0.4.1 | 25–28 | 4 | Complete |

## Context

**Platform:** Python ≥3.10, MuJoCo 3.x, PyBullet ≥3.2.5, Gymnasium ≥0.29, Stable-Baselines3 ≥2.0
**Build:** setuptools, pip, pyproject.toml
**CLI:** Typer + Rich (`surg-rl` command, 14 subcommands: train, evaluate, benchmark, dreamer-train, dreamer-spike, marl-train, download-assets, version, plus others)
**Config:** Pydantic v2 dataclasses + pydantic-settings (.env support)
**Testing:** pytest (pytest.ini with `pythonpath = src`), 1,053+ tests, 0 failures
**Lint/Type:** ruff, black, mypy

## Key Architecture Decisions

- Dual-backend simulation via `BaseSimulator` ABC (Strategy pattern)
- Pydantic v2 `SceneDefinition` as single source of truth
- Optional dependency groups: `[distributed]`, `[ros2]`, `[llm]`, `[vision]`, `[assets]`, `[benchmark]`, `[marl]`, `[dreamer]`
- Lazy imports for optional deps (Ray, ROS2, trimesh, dreamerv3) — no crash on missing packages
- `PYTHONPATH=src` required for direct Python script invocations
- Cross-backend state save/restore via `get_state()`/`set_state()`
- Observation dataclass as cross-backend contract for RL layer
- Simulator owns threads/processes; env owns lifecycle via start/stop
- Kustomize overlays for K8s deployment variants (CPU vs GPU)
- Tetgen replaces VTK entirely for platform-agnostic meshing (not side-by-side)
- MuJoCo `<flex>` (not `<flexcomp>`) for arbitrary tetgen meshes
- Cutting is discrete trigger (not continuous action) with 500ms cooldown
- PyBullet cuts use RESET_USE_DEFORMABLE_WORLD + full reload (removeBody() unsafe)
- PhiFlow over Mantaflow for Eulerian fluids (Mantaflow abandoned since 2022)
- CPU-first fluids (GPU deferred); in-memory tetgen → MJCF bridge for zero-file-I/O path
- Schema-first for new features: all v0.4.0 Pydantic v2 models with `None` defaults; existing models unchanged
- trimesh is sole new mesh library; no glTF/COLLADA complexity
- `MultiAgentSurgicalEnv` is a separate class from `SurgicalEnv` — clean adapter pattern, no shared mutable state
- DreamerV3 process isolation via JAX subprocess (`XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`) prevents JAX+PyTorch GPU memory conflict
- `SurgicalEnv.passthrough_step()` for MARL per-arm action passthrough (no-op action, size = num_controls zeros) — cleanest solution vs. allowing zero-sized action arrays
- Extract `_step_simulator_and_build_outputs(processed_action, source_action)` helper so `step()` and `passthrough_step()` share post-step observation/reward building
- CurriculumScheduler extension is additive — never replaces Phase 3 fix
- Benchmarking treats MuJoCo and PyBullet as separate targets — no cross-backend aggregation
- Dual statistical aggregation (mean±1σ + IQM+CI) per D-08
- Seaborn colorblind-safe palette with fixed algorithm color cycle; DreamerV3 distinct orange (`#FF8C00`)
- `_JsonStdout` wrapper class replaces `os.fdopen` on PyTorch's non-blocking Pipe for DreamerV3 subprocess stdout
- 5 new task scene JSONs aligned with Phase 24 `test_dreamer_training.py` parametrize contract (instrument + tissue types per task)
- `ExperimentRunner.__init__` writes `experiments/{name}.yaml` so CLI "Reproduce with: --config experiments/{name}.yaml" hint is functional

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-06-11 after v0.4.1 milestone close*
