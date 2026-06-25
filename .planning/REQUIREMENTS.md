# Requirements: Surg-RL

**Defined:** 2026-06-24
**Milestone:** v0.6.0 — Carried-Forward Debt Closure
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.

## v0.6.0 Requirements

Carried-forward tech-debt closure. Each maps to a roadmap phase (36–40). No new user-facing features — GUI editor depth and scene-generation features are deferred to v0.7.0.

### DreamerV3

<!-- Continues DMV3-01..05 (v0.4.0/v0.4.1/v0.4.2). DMV3-06 (offline training from demos) stays v2. -->

- [ ] **DMV3-07**: Researcher can train a real DreamerV3 agent on a surgical task via the process-isolated JAX subprocess (replaces the `_build_agent` stub and the 4 sibling stubs `_train_loop`/`_evaluate`/`_save_checkpoint`/`_load_checkpoint`)
- [ ] **DMV3-08**: DreamerV3 checkpoints persist per task/obs-type and resume training across subprocess restarts
- [ ] **DMV3-09**: The Phase 30 E2E test asserts positive real-agent completion (sentinel flipped from the `RuntimeError("Agent not configured")` negative assertion) and guards against stub regression
- [ ] **DMV3-10**: Real DreamerV3 training runs end-to-end on the CI GPU host — smoke test asserts structural properties (finite/decreasing loss, checkpoint exists), not the v0.4.0 spike's converged `MSE<0.01` thresholds

### Task Difficulty

<!-- Continues TASK-01..04 (v0.4.0/v0.4.2). TASK-05 (task chains) stays v2. -->

- [x] **TASK-06**: Per-level difficulty overrides (`DifficultyLevelConfig`: tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit) apply additively over `interpolate_params()` — never replace it
- [x] **TASK-07**: `CurriculumScheduler` advances through discrete EASY→MEDIUM→HARD levels via an additive `progression_mode` (the continuous float `advance_stage` path is preserved unchanged)
- [x] **TASK-08**: Scene JSON can specify `difficulty_blocks` per level and `SurgicalEnv` applies them at construction with a documented, tested override-precedence chain
- [x] **TASK-09**: The existing v0.4.0 + v0.4.2 curriculum suite passes unchanged (additive-regression gate)

### Fluids

- [ ] **FLUID-01**: `FluidConfig.dim_3d=True` enables 3D Eulerian grid fluids (3D `Box`/`StaggeredGrid` + 3D pressure projection); `dim_3d=False` default preserves the validated 2D xz-slice behavior
- [ ] **FLUID-02**: 3D fluid/solid coupling runs stably with one-way coupling as the default (two-way opt-in) on thin instruments
- [ ] **FLUID-03**: The 3D solver is memory-bounded via a separate smaller 3D default `grid_size` + validator; the `union(*geoms)` multi-obstacle SDF NaN-regression test covers the 3D path

### Deploy & Assets

- [ ] **DEPLOY-01**: K8s PVC checkpoint-persistence e2e test asserts write → pod restart → read on a bound PVC (de-stubbed via `pytest-kind` `kind_cluster` fixture + `kubectl wait --for=condition=Bound`)
- [ ] **ASET-06**: Organ-mesh licensing decision is recorded as an ADR — procedural generation as the default, surgtoolloc rejected with cited rationale (continues ASET-01..05)

## v2 Requirements

Deferred. Tracked but not in the current roadmap.

### GUI Editor Depth (deferred to v0.7.0)

- **GUI-11**: Render/sim-decoupled viewport — render thread pulls last sim state at display rate while sim steps independently (structural FPS fix over the v0.5.0 20 Hz QTimer loop)
- **GUI-12**: Viewport rendering additions — multi-view, lighting controls, transform gizmos, screenshot + video recording
- **GUI-13**: Editing UX — multi-select + copy/paste, tree search/filter, inline validation feedback, asset browser
- **GUI-14**: File/IO — robust save/load with schema migration, JSON/YAML/URDF import-export, templates picker, recent files
- **GUI-15**: Perf/stability — large-scene handling, undo memory bounds, faster cold-start, render-bridge edge-crash hardening

### Scene Generation (deferred to v0.7.0)

- **GEN-01**: More task templates — parametric variants across the 6 task types
- **GEN-02**: Better text→scene — improved LLM prompts + structured-output enforcement + validation-and-repair loop
- **GEN-03**: Image→scene — stronger vision_parser (VLM routing, detection→schema mapping)
- **GEN-04**: Procedural / batch generation — randomized scene families + batch generation for benchmark dataset expansion
- **GEN-05**: Interactive generation — conversational LLMPanel mode (LLM asks clarifying questions, scene updates live) + `surg-rl generate --interactive` CLI mirror

### Pre-existing v2 (unchanged)

- **TASK-05**: Task chains (grasp→cut→suture) — v2
- **MARL-05**: RLlib centralized critic for MARL — v2
- **DMV3-06**: DreamerV3 offline training from recorded demos — v2

## Out of Scope

| Feature | Reason |
|---------|--------|
| surgtoolloc organ meshes | Research confirmed it is endoscopic video with tool-presence labels, NOT organ geometry; challenge guidelines also prohibit commercial use. Procedural generation is the licensing default (ASET-06) |
| DreamerV3 convergence-threshold validation on full 6-task suite | Flagged uncertain in STATE.md; CI asserts structural smoke properties only (DMV3-10). Full convergence deferred until real-agent stability is proven |
| GPU fluid acceleration | CPU-first per existing v0.3.2 decision; GPU fluids can be added when needed |
| Two-way 3D fluid/solid coupling as default | Unstable on thin instruments; one-way is the 3D default, two-way is opt-in (FLUID-02) |
| 3D DreamerV3 video prediction | 2D pixel reconstruction sufficient; out of scope (carried forward) |
| Helm chart / ROS2 DDS router | Kustomize overlays + documented workaround sufficient (carried forward) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation (2026-06-24).

| Requirement | Phase | Status |
|-------------|-------|--------|
| DMV3-07 | Phase 40 | Pending |
| DMV3-08 | Phase 40 | Pending |
| DMV3-09 | Phase 40 | Pending |
| DMV3-10 | Phase 40 | Pending |
| TASK-06 | Phase 36 | Complete |
| TASK-07 | Phase 36 | Complete |
| TASK-08 | Phase 37 | Complete |
| TASK-09 | Phase 36 | Complete |
| FLUID-01 | Phase 38 | Pending |
| FLUID-02 | Phase 38 | Pending |
| FLUID-03 | Phase 38 | Pending |
| DEPLOY-01 | Phase 39 | Pending |
| ASET-06 | Phase 39 | Pending |

**Coverage:**

- v0.6.0 requirements: 13 total
- Mapped to phases: 13/13 ✓
- Unmapped: 0

**Phase mapping summary:**

- Phase 36 (Difficulty Schema + Discrete Curriculum): TASK-06, TASK-07, TASK-09
- Phase 37 (Scene-Level difficulty_blocks + Env Wiring): TASK-08
- Phase 38 (3D Fluid Flag): FLUID-01, FLUID-02, FLUID-03
- Phase 39 (K8s PVC e2e + Organ-Mesh Licensing ADR): DEPLOY-01, ASET-06
- Phase 40 (Real DreamerV3 Integration + Sentinel Flip): DMV3-07, DMV3-08, DMV3-09, DMV3-10

---
*Requirements defined: 2026-06-24*
*Last updated: 2026-06-24 — v0.6.0 roadmap created; traceability section populated (13/13 mapped)*
