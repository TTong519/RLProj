# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system with production deployment infrastructure and competitive RL research capabilities. Generates and simulates surgical scenes from text/images via LLM/VLM or JSON scene definitions, trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, adaptive difficulty, and dual-arm multi-agent support. Real instrument and organ meshes (trimesh) replace primitive fallbacks; 6 surgical task types span easy/medium/hard difficulty; SB3 benchmark reports with publication-quality plots; optional DreamerV3 world model integration runs in process isolation. Features platform-agnostic tetgen mesh generation, FEM deformable objects, real-time volumetric tetrahedral mesh cutting, and Eulerian grid fluid simulation. Supports Apple Silicon Metal GPU compute, multi-arch Docker images, ROS2 ros2_control integration, and Kubernetes deployment. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.

## Current State

**Shipped v0.4.2** (2026-06-14) — Audit Leftovers. All v0.1.0 through v0.4.2 milestones shipped (8 milestones, 30 phases, 87 plans, 23/23 v1 requirements satisfied, 0 partial, 0 deferred). v0.4.2 closed the 2 residual v0.4.0 audit gaps (TASK-02 3-difficulty-levels + DreamerV3 real-subprocess E2E) with 2 surgical phases (3 plans).

## Current Milestone: v0.4.2 Audit Leftovers (SHIPPED 2026-06-14)

**Goal:** Close the 2 remaining items deferred from the v0.4.0 audit gap closure milestone: TASK-02 3-difficulty-levels (easy/medium/hard presets) and DreamerV3 real-subprocess E2E test. Pure gap-closure — no new features, only the missing presets + a real subprocess smoke test for the Phase 26 DreamerV3 fixes.

**Audit verdict:** `passed` — 11/11 v1 requirements satisfied (6 TASK-02-01..06 + 5 DMV3-E2E-01..05), 0 partial, 0 deferred.

**Delivered:**
- ✓ `DifficultyLevel` enum (EASY=0.0, MEDIUM=0.5, HARD=1.0) with float-mixin semantics — `DifficultyLevel.EASY == 0.0` is True via `_FloatMixin(float, Enum)` (Python stdlib has no `FloatEnum`)
- ✓ All 6 task reward classes expose `get_params_for_difficulty()` (delegates to existing `interpolate_params()`) and `apply_difficulty()` (per-subclass field mutation). 4 generic rewards inherit a no-op `BaseRewardFunction.apply_difficulty()` default
- ✓ `TaskRewardRouter` accepts `float | DifficultyLevel` with strict scalar normalization (`type() is float`); float path preserved for backwards compat
- ✓ `TaskConfig.difficulty_level: DifficultyLevel | None` Pydantic v2 field with default None; coerces by float value (0.0/0.5/1.0 → EASY/MEDIUM/HARD), not by name
- ✓ `CurriculumStageConfig.difficulty: float | DifficultyLevel` — mixed-stage configs work without migration
- ✓ Pydantic v2 + cross-package cycle-resolution pattern established: `from __future__ import annotations` + string forward-ref + late import at module bottom + `Model.model_rebuild()` + lazy local imports inside function bodies
- ✓ `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — 3-test pytest module gated by module-level `pytest.mark.skipif` on (GPU + `dreamerv3` + `jax`); macOS local skips with `pip install '.[dreamer]'` remediation; CI GPU host runs and exercises `_JsonStdout` wrapper + `DREAMER_COLOR` + checkpoint auto-discovery path

**Key Deliverables (v0.4.2):**
- `src/surg_rl/rl/difficulty.py` — `_FloatMixin(float, Enum)` base + `DifficultyLevel` (EASY=0.0, MEDIUM=0.5, HARD=1.0); leaf-module (zero in-project imports) to break future circular import risk
- `src/surg_rl/rl/rewards.py` — `BaseRewardFunction.apply_difficulty()` no-op default + 6 task reward overrides (`SuturingReward`, `KnotTyingReward`, `NeedlePassingReward`/`NeedleInsertionReward`, `GraspingReward`, `CuttingReward`, `DissectionReward`)
- `src/surg_rl/rl/task_reward_router.py` — accepts `float | DifficultyLevel`; normalizes to `float(difficulty.value)` internally; `build()` calls `apply_difficulty(self._difficulty)` on the constructed task reward
- `src/surg_rl/scene_definition/schema.py` — `TaskConfig.difficulty_level` Pydantic v2 optional field with cycle resolution
- `src/surg_rl/rl/environment.py` — `SurgicalEnv._setup_rewards()` reads `task.difficulty_level` first, then `config.difficulty`, then defaults to 0.5; lazy local `SceneLoader` import inside `_load_scene()`
- `src/surg_rl/dynamics/curriculum.py` — `CurriculumStageConfig.difficulty: float | DifficultyLevel = 0.5`
- `tests/fixtures/scenes/suturing_difficulty_hard.json` — fixture for end-to-end float-value enum coercion test
- `tests/dreamer/__init__.py` + `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — 3-test E2E smoke test, module-level skipif
- `29-VERIFICATION.md` — 6/6 must-haves verified
- `30-VERIFICATION.md` — 10/10 must-haves verified

**Inherited tech debt (NOT in v0.4.2 scope, per user direction):**
- 421 ruff issues in `src/surg_rl/dreamer/` (pre-existing, deferred)
- Cut cooldown unit test, per-tet generation counter, fluid step hook in base_simulator
- Dockerfile.ros2 amd64 hardcode, K8S PVC e2e, KubeRay prerequisite
- 3D fluid flag (`dim_3d=True`), PhiFlow multi-obstacle union() workaround
- Linux-only ROS2 subscriber e2e tests
- Organ mesh source licensing
- REQUIREMENTS.md BENCH-02..05 body checkboxes (pre-existing v0.4.0 audit process gap)
- TASK-02 per-level override schema (`DifficultyLevelConfig` with tissue_stiffness/target_precision_tolerance/tool_position_noise/time_limit) — D-29-03 explicit exclusion
- TASK-02 `CurriculumScheduler` discrete level progression — D-29-03 explicit exclusion
- TASK-02 scene-level `difficulty_levels: list[3]` blocks — D-29-03 explicit exclusion
- End-to-end `SurgicalEnv`-construction integration test for HARD fixture scene (Phase 29 code review WR-02)
- `CurriculumStageConfig.difficulty` normalization at env-construction (Phase 29 code review WR-03)
- Phase 30 stub-state sentinel flip when real dreamerv3 is integrated (replaces `_build_agent` at `subprocess.py:127-131`)

**v0.4.1 (Archived, 2026-06-11)**

**Goal:** Close 14 gaps from the v0.4.0 milestone audit. Pure gap-closure milestone — no new features, only bug fixes, retroactive verification, and process reconciliation.

**Audit verdict:** `passed` — 12/14 gaps fully closed, 1 partial (TASK-02 3-difficulty-levels → v0.4.2), 1 deferred (DreamerV3 real-subprocess E2E → v0.4.2, requires GPU + dreamerv3 install).

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

### Validated (v0.4.0–v0.4.2)

- ✓ All v0.3.0–v0.3.2 features (Metal GPU, multi-arch Docker, ros2_control, K8s, tetgen, FEM deformables, volumetric cutting, grid fluids)
- ✓ **Real Surgical Assets** — trimesh OBJ loading, V-HACD collision, organ OBJ→tetgen, primitive fallback (ASET-01..05) — v0.4.0
- ✓ **Surgical Task Curriculum** — 6 task types, TaskResult hierarchy, TaskRewardRouter activated, additive CurriculumScheduler, DifficultyLevel enum (EASY/MEDIUM/HARD) with per-task `get_params_for_difficulty()` (TASK-01..04) — v0.4.0 + v0.4.2
- ✓ **Multi-Agent RL** — PettingZoo ParallelEnv dual-arm, SuperSuit wrappers, shared/independent policies, `SurgicalEnv.passthrough_step()` adapter (MARL-01..04) — v0.4.0 + v0.4.1
- ✓ **Performance Benchmarking** — ExperimentRunner multiprocessing, rliable IQM, per-backend reports, deterministic YAML, 6 task scene JSONs (BENCH-01..05) — v0.4.0 + v0.4.1
- ✓ **DreamerV3 World Models** — Feasibility spike, process-isolated JAX, `_JsonStdout` wrapper, pixel/state obs, auto-discovery, real-subprocess E2E test gated on GPU+dreamerv3+jax (DMV3-01..05) — v0.4.0 + v0.4.1 + v0.4.2

### Active (v0.5.0+)

_None yet — use `/gsd-new-milestone` to define v0.5.0 requirements._

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
| v0.4.2 | 29–30 | 3 | Complete |
| v0.5.0 | TBD | TBD | Planning |

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
- `DifficultyLevel` enum uses `_FloatMixin(float, Enum)` (Python stdlib has no `FloatEnum`) to make `DifficultyLevel.EASY == 0.0` True — duck-typed `level.value` consumers mean the enum works transparently in tests and downstream code
- `DifficultyLevel` is enum-only, not Pydantic-validated scalar; internally only the scalar (`0.0`/`0.5`/`1.0`) is used — avoids confusing double-validation
- Pydantic v2 + cross-package enum cycle resolution: `from __future__ import annotations` + string forward-ref + late import at module bottom + `Model.model_rebuild()` + lazy local imports inside function bodies (pattern reusable for any future cross-package Pydantic v2 schema work)
- `TaskRewardRouter` uses strict `type() is float` check (not `==`) in tests to avoid float-mixin equality false-positive (which would mask failure mode where router stored the enum member instead of normalizing)
- Phase 30 E2E test asserts the EXPECTED `RuntimeError("Agent not configured")` from the current Phase 24 `_build_agent` stub, rather than positive completion — sentinel that will START FAILING when real dreamerv3 is integrated and must be flipped then
- Phase 30 module-level `pytest.mark.skipif` evaluates at collection time (BEFORE test bodies run); heavy imports (e.g., `run_dreamer_training`) live inside test methods so a missing import in the production module does not crash collection on macOS

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

*Last updated: 2026-06-14 after v0.4.2 milestone archive*
