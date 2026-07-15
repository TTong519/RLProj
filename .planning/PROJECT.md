# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system with an interactive PySide6 scene editor, production deployment infrastructure, and competitive RL research capabilities. Generates and simulates surgical scenes from text/images via LLM/VLM or JSON scene definitions — or builds them by hand in the GUI editor — and trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, adaptive difficulty, and dual-arm multi-agent support. Real instrument and organ meshes (trimesh) replace primitive fallbacks; 6 surgical task types span easy/medium/hard difficulty; SB3 benchmark reports with publication-quality plots; optional DreamerV3 world model integration runs in process isolation. Features platform-agnostic tetgen mesh generation, FEM deformable objects, real-time volumetric tetrahedral mesh cutting, and Eulerian grid fluid simulation. Supports Apple Silicon Metal GPU compute, multi-arch Docker images, ROS2 ros2_control integration, and Kubernetes deployment. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.

## Current State

**Shipped v0.6.0** (2026-07-15) — Carried-Forward Debt Closure. All v0.1.0 through v0.6.0 milestones shipped (10 milestones, 41 phases, 127 plans, 13/13 v0.6.0 requirements satisfied). v0.6.0 was pure closure — no new user-facing features (GUI editor depth + scene generation deferred to v0.7.0). It closed the four carried-forward tech-debt items from v0.4.0–v0.5.0: real DreamerV3 integration, the TASK-02 per-level difficulty schema, K8s PVC e2e + organ-mesh licensing ADR, and the 3D fluid flag. Every item additive — the v0.4.0 + v0.4.2 + v0.5.0 baseline passes unchanged. Test baseline grew 1,325 → 1,513 passing.

**Next:** v0.7.0 (not yet planned) — the deferred candidate is GUI editor depth (render/sim-decoupled viewport, multi-view/lighting/gizmos/recording, editing UX, file/IO, perf/stability: GUI-11..15) + scene generation (more task templates, better LLM text→scene, VLM image→scene, procedural/batch gen, interactive LLM clarifying-question flow: GEN-01..05). Run `/gsd-new-milestone` to plan it.

**v0.6.0 outcome:** Phases 36 (difficulty schema), 37 (scene-level `difficulty_blocks` + env wiring), 38 (3D fluid flag `dim_3d=True`), 39 (K8s PVC e2e + organ-mesh licensing ADR), 40 (real DreamerV3 integration + sentinel flip), and 40.1 (post-verification gap-close: DMV3-08 `checkpoint_dir` threading + Phase 38 advisories) all complete and VERIFIED `passed`. 6 phases / 18 plans; 13/13 v0.6.0 requirements closed. **Phase 40 re-verified `passed` 2026-07-15** after the `dreamer-gpu` GitHub Actions job was observed GREEN on `ubuntu-latest-4-core-gpu` — DMV3-07 real-agent runtime, DMV3-08 resume, and DMV3-10 CI GREEN are now certified (previously deferred to CI per INV-8). **Phase 40.1** closed the DMV3-08 parent-side resume gap (`checkpoint_dir` threaded into `_find_latest_checkpoint` + both call sites) and landed the Phase 38 advisories (CR-01 3D force-unit magnitude regression test green + real TWO_WAY obstacle-velocity feedback with a `dt/coupling_substeps` substep loop, 2D byte-identical). Test baseline 1,513 passing (Phase 39's e2e test is CI-only; macOS local skips by design; Phase 40's GPU-gated tests SKIP cleanly on macOS per INV-8).

## Shipped Milestone: v0.6.0 Carried-Forward Debt Closure (SHIPPED 2026-07-15)

**Goal:** Close the four carried-forward tech-debt items deferred from v0.4.0–v0.5.0 — real DreamerV3 integration, the TASK-02 per-level difficulty schema, K8s PVC e2e + organ-mesh licensing decision, and the 3D fluid flag. Pure closure: no new user-facing features (those are queued for v0.7.0).

**Audit verdict:** `gaps_found` at the 2026-07-12 milestone audit (which predated Phase 40.1 and flagged the GPU-runtime GREEN as outstanding) → **closed 2026-07-15**. Phase 40.1 closed the audit's two code-level follow-ups (DMV3-08 `checkpoint_dir` threading + Phase 38 CR-01/WR-01/WR-02). The remaining audit gap — the `dreamer-gpu` CI job GREEN — was resolved when the user enabled GitHub-hosted GPU Actions runners and observed the first GREEN run on 2026-07-15; Phase 40 was re-verified `passed` (5/5 truths). All 6 v0.6.0 phases VERIFIED `passed` → verified closeout. Pre-close `audit-open` found 3 older-milestone items (Phase 09 verification gaps, Phase 24 UAT partial, demo-rework quick task); demo-rework was already complete (stale marker), the other two are pre-v0.6.0 cross-milestone debt acknowledged in STATE.md.

**Target items:**
- Real DreamerV3 integration — flip the Phase 24 `_build_agent` stub sentinel, wire a real DreamerV3 agent into the process-isolated JAX subprocess, validate end-to-end on GPU (CI GPU host; macOS local skips)
- TASK-02 per-level schema — `DifficultyLevelConfig` (tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit overrides) + discrete `CurriculumScheduler` level progression + scene-level `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] | None` in scene JSON
- K8s PVC e2e — de-stub the checkpoint-persistence e2e test; organ-mesh licensing decision (procedural generation vs surgtoolloc dataset)
- 3D fluid flag — implement the `dim_3d=True` path for Eulerian grid fluids (currently 2D xz-slice only)

**Deferred to v0.7.0 (acknowledged, not in this roadmap):** GUI editor depth (render/sim-decoupled viewport, multi-view/lighting/gizmos/recording, editing UX, file/IO, perf/stability) + scene generation (more task templates, better LLM text→scene, VLM image→scene, procedural/batch gen, interactive LLM clarifying-question flow in GUI + CLI).

**Key context:** Phase numbering continues from 36. DreamerV3 real-integration is GPU-gated (CI GPU host required; macOS local skips). This mirrors the v0.4.1/v0.4.2 gap-closure pattern — small, focused, audit-driven.

## Shipped Milestone: v0.5.0 Scene Editor & UX Polish (SHIPPED 2026-06-24)

**Goal:** Ship a full PySide6 scene editor (3D viewport + tree/form editor + LLM-prompt-to-JSON), polish 3 surgical task demos (suturing, knot-tying, needle-passing) with consistent narration and walkthroughs, refresh user-facing docs (README, CONTRIBUTING, CHANGELOG), and interleave tech debt cleanup (421 ruff issues, HARD fixture test, fluid step hook, cut cooldown test, Dockerfile.ros2 amd64, PhiFlow multi-obstacle union() workaround). Marquée feature is the GUI editor; demos and docs support adoption.

**Audit verdict:** count-complete — 5/5 phases shipped (22 plans), 26/26 v1 requirements delivered. Pre-close `audit-open` found 3 older-milestone items (Phase 09 verification gaps, Phase 24 UAT partial, demo-rework quick task); demo-rework was already complete (stale marker), the other two acknowledged as deferred in STATE.md. No `v0.5.0-MILESTONE-AUDIT.md` was run.

**Delivered:**
- ✓ **PySide6 Scene Editor** (Phase 33, marquée) — `surg-rl-gui` console script launches a full editor: 3D viewport (orbit/pan/zoom, custom `ViewportCanvas`, MuJoCo/PyBullet render bridge with framebuffer retry + persistent-failure short-circuit), schema-driven tree+form via `SchemaWalker` + `FieldRenderer` registry, LLM-prompt-to-JSON panel on a background QThread, undo/redo, File menu + drag-drop, `safe_error_message()` redactor. Optional `[gui]` extra keeps PySide6 install-optional; CLI stays headless-clean.
- ✓ **Demo suite polish** (Phase 32) — `demos/_common.py` shared narration + `NARRATION_TEMPLATE.md` (5-stage: Setup → Action → Critical Moment → Outcome → Takeaway) + suturing/knot-tying/needle-passing demos + 6 regression tests
- ✓ **User-facing docs refresh** (Phase 34) — README + CONTRIBUTING + CHANGELOG rewritten for v0.5.0; 3 demo GIFs + 3 GUI screenshots embedded
- ✓ **Tech debt cleanup** (Phases 31 + 35) — 421→0 ruff in `src/surg_rl/dreamer/`, `Dockerfile.ros2` multi-arch via `$TARGETARCH`, `BaseSimulator.fluid_step` hook, cut cooldown test parametrized over both backends, PhiFlow `union()` workaround documented, HARD-fixture `SurgicalEnv`-construction integration test, `CurriculumStageConfig.difficulty` normalization at env-construction, K8s PVC e2e scaffolding (stubbed, deferred to v0.6.0), organ mesh licensing research spike (deferred decision to v0.6.0)

**Key context:** The GUI no longer re-execs under `mjpython` — mjpython runs Python on a secondary thread, violating PySide6's main-thread requirement and producing the "dock icon, no window" hang (resolved in commit `3031ed9` F-01). Heavy `stable_baselines3`/`torch` re-exports are PEP-562 lazy via `surg_rl.rl.__init__.__getattr__` so editor import does not freeze for 9–11s. Phase 30 DreamerV3 stub-state sentinel carries forward (flips when real dreamerv3 is integrated, NOT in v0.5.0 scope).

### Previous Milestone: v0.4.2 Audit Leftovers (SHIPPED 2026-06-14)

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
- TASK-02 scene-level `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig]` blocks — Phase 37 (TASK-08) complete; D-29-03 exclusion lifted (verification 5/5 PASSED)
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
- 3D Eulerian grid fluids now implemented behind `dim_3d=True` (Phase 38); 2D xz-slice remains the validated default path. **Phase 40.1 closed the Phase 38 advisories:** CR-01 3D force-unit magnitude regression test now green, and `coupling_mode`/`coupling_substeps` are no longer inert — real TWO_WAY obstacle-velocity feedback runs with a `dt/coupling_substeps` substep loop (2D path byte-identical). `render_fluid_3d` remains a z-slice fallback, not a true volume renderer (deferred per CONTEXT.md D-18)
- Dockerfile.ros2 amd64 hardcode, K8S PVC e2e, KubeRay prerequisite (from v0.3.1)
- Organ mesh source licensing (v0.4.0 Phase 20) — procedural generation or surgtoolloc dataset
- Pre-existing lint issues in `src/surg_rl/dreamer/` (F841, B904, E402; 421 ruff issues total per Phase 24 Nyquist audit) — out of v0.4.1 scope
- REQUIREMENTS.md BENCH-02..05 body checkboxes remain `[ ]` (pre-existing v0.4.0 audit process gap, out of Phase 28 scope)
- Task chain system compositing subtasks (TASK-05) — v2
- RLlib centralized critic for MARL (MARL-05) — v2
- DreamerV3 offline training from recorded demos (DMV3-06) — v2

## Requirements

### Validated (v0.4.0–v0.5.0)

- ✓ All v0.3.0–v0.3.2 features (Metal GPU, multi-arch Docker, ros2_control, K8s, tetgen, FEM deformables, volumetric cutting, grid fluids)
- ✓ **Real Surgical Assets** — trimesh OBJ loading, V-HACD collision, organ OBJ→tetgen, primitive fallback (ASET-01..05) — v0.4.0
- ✓ **Surgical Task Curriculum** — 6 task types, TaskResult hierarchy, TaskRewardRouter activated, additive CurriculumScheduler, DifficultyLevel enum (EASY/MEDIUM/HARD) with per-task `get_params_for_difficulty()` (TASK-01..04) — v0.4.0 + v0.4.2
- ✓ **Multi-Agent RL** — PettingZoo ParallelEnv dual-arm, SuperSuit wrappers, shared/independent policies, `SurgicalEnv.passthrough_step()` adapter (MARL-01..04) — v0.4.0 + v0.4.1
- ✓ **Performance Benchmarking** — ExperimentRunner multiprocessing, rliable IQM, per-backend reports, deterministic YAML, 6 task scene JSONs (BENCH-01..05) — v0.4.0 + v0.4.1
- ✓ **DreamerV3 World Models** — Feasibility spike, process-isolated JAX, `_JsonStdout` wrapper, pixel/state obs, auto-discovery, real-subprocess E2E test gated on GPU+dreamerv3+jax (DMV3-01..05) — v0.4.0 + v0.4.1 + v0.4.2
- ✓ **PySide6 Scene Editor** — `surg-rl-gui` with 3D viewport, schema-driven tree/form, LLM-prompt-to-JSON, undo/redo, `[gui]` optional extra (GUI-01..10) — v0.5.0
- ✓ **Demo Suite Polish** — 3 demos (suturing + knot-tying + needle-passing) with shared `demos/_common.py` narration + regression tests (DEMO-01..05) — v0.5.0
- ✓ **User-Facing Docs Refresh** — README + CONTRIBUTING + CHANGELOG with embedded demo GIFs + GUI screenshots (DOC-01..05) — v0.5.0
- ✓ **Tech Debt Cleanup** — 421→0 ruff in `dreamer/`, Dockerfile.ros2 multi-arch, fluid_step hook, cut cooldown test, PhiFlow union doc, HARD-fixture env-construction test, CurriculumStageConfig difficulty normalization (DEBT-01..06) — v0.5.0

### Validated (v0.6.0)

- ✓ **Real DreamerV3 integration + sentinel flip** — the 5 `_build_agent`/`_train_loop`/`_evaluate`/`_save_checkpoint`/`_load_checkpoint` stubs replaced with real `dreamerv3.Agent` (PyPI 1.5.0 object API; manual `embodied.Driver` + `agent.train()` loop, NOT `embodied.run.train`); Phase 30 sentinel flipped negative→positive with a CPU-runnable AST regression guard; `.pt` retired for `embodied.Checkpoint` native `*.ckpt`; `task`+`checkpoint_dir` threaded to the child and (Phase 40.1) into `_find_latest_checkpoint` + both call sites. `dreamer-gpu` CI job observed GREEN on `ubuntu-latest-4-core-gpu` (2026-07-15). JAX isolation preserved (0 module-top jax/dreamerv3/embodied imports; logger→stderr). (DMV3-07, DMV3-08, DMV3-09, DMV3-10) — Phases 40 + 40.1
- ✓ **TASK-02 per-level difficulty schema** — `DifficultyLevelConfig` leaf model (tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit) composing additively over `interpolate_params()`; additive `CurriculumScheduler.progression_mode` with `set_difficulty_level`/`advance_level` (continuous `advance_stage` byte-identical); scene-level `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] | None` with a 4-level precedence truth-table wired into `SurgicalEnv._setup_rewards`. (TASK-06, TASK-07, TASK-08, TASK-09) — Phases 36 + 37
- ✓ **3D Fluid Flag (`dim_3d=True`)** — 3D Eulerian grid fluids via PhiFlow 3D `Box`/`StaggeredGrid` + `make_incompressible` pressure projection; ONE_WAY coupling default (stable on thin instruments), TWO_WAY opt-in with real obstacle-velocity feedback + `dt/coupling_substeps` substep loop (Phase 40.1 closed the previously-inert knobs); `grid_size`-required memory-blow-up guard (SC#3); `union(*geoms)` NaN-regression covering both dims (SC#4); `fluid_step` hook unchanged (SC#5). 2D xz-slice path byte-identical to v0.5.0 (SC#1); CR-01 3D force-unit magnitude regression test green. (FLUID-01, FLUID-02, FLUID-03) — Phases 38 + 40.1
- ✓ **K8s PVC e2e + organ-mesh licensing decision** — checkpoint-persistence e2e de-stubbed via `pytest-kind`'s session-scoped `kind_cluster` fixture (apply → `kubectl wait --for=condition=Bound` → write/read Jobs → `assert read_sha == write_sha` on a bound PVC); dedicated CPU-only `k8s-e2e` CI job on ubuntu-latest (observed GREEN 2026-07-04; re-verified 2026-07-09). Organ-mesh licensing recorded as ADR-0001 (MADR, status accepted): procedural generation is the DEFAULT, SurgToolLoc REJECTED on modality mismatch (primary — endoscopic video + tool-presence labels, no organ meshes) + MICCAI/EndoVis non-commercial clause (secondary, quoted verbatim, both public URLs cited). (DEPLOY-01, ASET-06) — Phase 39

### Active (next milestone — not yet planned)

- [ ] **GUI editor depth** (GUI-11..15) — render/sim-decoupled viewport, multi-view/lighting/gizmos/recording, editing UX, file/IO, perf/stability (deferred to v0.7.0)
- [ ] **Scene generation** (GEN-01..05) — more task templates, better LLM text→scene, VLM image→scene, procedural/batch gen, interactive LLM clarifying-question flow (deferred to v0.7.0)

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent / dual-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient
- DirectML / Vulkan compute backends — Windows not primary target; niche use case
- Linux-only ROS2 subscriber e2e tests — Requires real ROS2 runtime; mock coverage is sufficient for macOS
- Helm chart — Kustomize overlays sufficient; Helm can be added later
- Real-time ROS2 DDS router for K8s multicast — DDS multicast issue is platform-level; document workaround
- True 3D volume fluid rendering — 3D Eulerian grid solver is now available behind `dim_3d=True` (Phase 38, opt-in; `render_fluid_3d` is a z-slice fallback per D-18), but true volume rendering remains deferred; the validated default stays the 2D xz-slice
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
| v0.5.0 | 31–35 | 22 | Complete (Scene Editor & UX Polish) |

## Context

**Platform:** Python ≥3.10, MuJoCo 3.x, PyBullet ≥3.2.5, Gymnasium ≥0.29, Stable-Baselines3 ≥2.0
**Build:** setuptools, pip, pyproject.toml
**CLI:** Typer + Rich (`surg-rl` command, 14 subcommands: train, evaluate, benchmark, dreamer-train, dreamer-spike, marl-train, download-assets, version, plus others)
**Config:** Pydantic v2 dataclasses + pydantic-settings (.env support)
**Testing:** pytest (pytest.ini with `pythonpath = src`), 1,325+ tests, 0 failures
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
- **v0.5.0 GUI does NOT re-exec under `mjpython`** — mjpython runs Python on a secondary thread, violating PySide6's main-thread requirement and causing a silent "dock icon, no window" hang. The GUI stays in the stock interpreter; mjpython is detected only for a warning banner. (commit `3031ed9` F-01)
- **PEP 562 lazy `__getattr__` in `surg_rl.rl.__init__`** — heavy `stable_baselines3`/`torch` re-exports load on first attribute access, not at import, so the editor import path does not freeze for 9–11s before `window.show()`
- **Editor viewport uses a custom `ViewportCanvas(QWidget)`**, not a `QLabel` — reliable mouse/wheel event delivery on macOS; camera offsets are pushed into the simulator via `_editor_camera_*` attrs (PyBullet offscreen fallback honors them; MuJoCo ignores them)
- **PyBullet RGB normalization** — `_normalize_pb_rgb()` converts all `getCameraImage` pixel payloads (HxWx4, HxWx3, flat tuples/arrays) to a canonical `(H, W, 3) uint8` so the render bridge is robust across PyBullet versions/flags
- **MuJoCo offscreen renderer short-circuits on persistent CGL/EGL failure** (`_renderer_available = False`) instead of repeating the same error every frame
- **ADR-0001 (MADR format) records the organ-mesh licensing decision**
- **Phase 40 Real DreamerV3 + sentinel flip — the 5 stub functions are replaced with real implementations against the PyPI 1.5.0 object API** — `Agent(obs_space, act_space, step, agent_config)` 4-arg ctor; manual `embodied.Driver` + `agent.train()` batch loop — NOT `embodied.run.train` which double-checkpoints; `agent.policy` rollouts; `cp.save()` / `cp.load()` + `cp.load_or_save()` fallback delegation. The Phase 30 sentinel is FLIPPED negative→positive — `test_e2e_run_dreamer_training_real_agent` asserts finite + non-explosive loss + training completes — NO `MSE<0.01` convergence threshold per DMV3-10 smoke-vs-convergence split; guarded by a CPU-runnable AST source-inspection regression guard — `test_dreamerv3_regression_guard.py` fails closed if `_build_agent` ever returns `None`. `.pt` checkpoint format retired cleanly for `embodied.Checkpoint` native `*.ckpt` — D-09, no dual-glob compat shim; `task`+`checkpoint_dir` threaded to the child so `_build_agent` honors the parent's checkpoint dir — the 40-04-prep fix `81588c2` for the two latent GPU bugs 40-03 flagged. SC#5 JAX isolation preserved — 0 module-top jax/dreamerv3/embodied/optax imports; logger→stderr. The `dreamer-gpu` GitHub Actions job — ubuntu-latest-4-core-gpu, NOT per-PR per D-02 — fires on merge-to-main + `v*` tags + workflow_dispatch; jax[cuda12]~=0.4.20 installed before `.[dev,dreamer]`; `pytest tests/dreamer/ -v -rs`; timeout-minutes:15 — is the DMV3-10 closure signal. **GPU GREEN observed 2026-07-15** — GitHub-hosted GPU Actions runners enabled and the first `dreamer-gpu` job went GREEN on `ubuntu-latest-4-core-gpu` (all 5 `tests/dreamer/` PASS); Phase 40 re-verified `passed` (5/5 truths) and DMV3-07/08/10 are certified at runtime. Phase 40.1 then closed the DMV3-08 parent-side resume gap by threading `checkpoint_dir` into `_find_latest_checkpoint` + both call sites (CPU-runnable stub test), and landed the Phase 38 advisories (CR-01 3D force-unit magnitude regression test green + real TWO_WAY obstacle-velocity feedback with a `dt/coupling_substeps` substep loop, 2D byte-identical). (Phase 40) — procedural generation is the DEFAULT organ-mesh source; SurgToolLoc is REJECTED on dual grounds (PRIMARY modality mismatch — endoscopic video + tool-presence labels, no organ geometry; SECONDARY licensing — MICCAI/EndoVis non-commercial clause quoted verbatim on a single grep-matchable line, both public challenge-site URLs cited). `docs/adr/` is the canonical ADR directory with 4-digit zero-padded numbering. (Phase 39)
- **pytest-kind session-scoped `kind_cluster` fixture drives the K8s PVC e2e test** — apply `-k k8s/overlays/e2e` → `kubectl wait --for=condition=Bound` → write/read Jobs → `assert read_sha == write_sha` on a bound PVC. A module-level `pytestmark = pytest.mark.skipif(not _k8s_e2e_available(), ...)` is required (not just an in-test `pytest.skip`) so the test SKIPs cleanly when Docker is down — the `kind_cluster` fixture errors at setup before the test body runs. The e2e Kustomize overlay references `../../base/pvc.yaml` directly (NOT `- ../../base`, to avoid pulling the GPU training-job + raycluster + secret); `read-job.yaml` is applied standalone via `kubectl apply -f` in the test body (NOT in overlay `resources:`) to avoid racing the write-Job. (Phase 39)

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

*Last updated: 2026-07-15 — v0.6.0 Carried-Forward Debt Closure SHIPPED. 6 phases (36–40.1) / 18 plans / 13-of-13 requirements closed; all phases VERIFIED `passed`. Phase 40 re-verified `passed` after the `dreamer-gpu` CI job was observed GREEN on `ubuntu-latest-4-core-gpu` (2026-07-15) — DMV3-07/08/10 runtime GREEN certified. Phase 40.1 closed the DMV3-08 parent-side resume-path gap (`checkpoint_dir` threaded into `_find_latest_checkpoint` + both call sites) and the Phase 38 advisories (CR-01 magnitude test green + real TWO_WAY feedback + `dt/coupling_substeps` substep loop, 2D byte-identical). Test baseline 1,513 passing. See `.planning/milestones/v0.6.0-ROADMAP.md` for the archived milestone.*
