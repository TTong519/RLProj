# Roadmap: Surg-RL

**Defined:** 2026-06-24 (v0.6.0 Carried-Forward Debt Closure planning)
**Last Shipped:** v0.5.0 Scene Editor & UX Polish — Phases 31–35 (SHIPPED 2026-06-24)
**Current Milestone:** v0.6.0 Carried-Forward Debt Closure — Phases 36–40

For the historical record of shipped milestones, see `.planning/milestones/v0.X.Y-ROADMAP.md`.

## Milestones

| Milestone | Status | Phases | Plans | Tests | Shipped | Archive |
|-----------|--------|--------|-------|-------|---------|---------|
| v0.1.0 | ✅ SHIPPED | 1–5 | 12 | 607 | 2026-05-02 | [v0.1.0-ROADMAP.md](milestones/v0.1.0-ROADMAP.md) |
| v0.2.0 | ✅ SHIPPED | 6–9 | 19 | 775 | 2026-05-03 | [v0.2.0-ROADMAP.md](milestones/v0.2.0-ROADMAP.md) |
| v0.3.0 | ✅ SHIPPED | 10–13 | 18 | 826 | 2026-05-04 | [v0.3.0-ROADMAP.md](milestones/v0.3.0-ROADMAP.md) |
| v0.3.1 | ✅ SHIPPED | 14 | 1 | 833 | 2026-05-04 | [v0.3.1-ROADMAP.md](milestones/v0.3.1-ROADMAP.md) |
| v0.3.2 | ✅ SHIPPED | 15–18 | 9 | 910 | 2026-05-05 | [v0.3.2-ROADMAP.md](milestones/v0.3.2-ROADMAP.md) |
| v0.4.0 | ✅ SHIPPED | 19–24 | 21 | 1,043 | 2026-06-09 | [v0.4.0-ROADMAP.md](milestones/v0.4.0-ROADMAP.md) |
| v0.4.1 | ✅ SHIPPED | 25–28 | 4 | 1,053 | 2026-06-11 | [v0.4.1-ROADMAP.md](milestones/v0.4.1-ROADMAP.md) |
| v0.4.2 | ✅ SHIPPED | 29–30 | 3 | 1,134 | 2026-06-14 | [v0.4.2-ROADMAP.md](milestones/v0.4.2-ROADMAP.md) |
| v0.5.0 | ✅ SHIPPED | 31–35 | 22 | 1,325 | 2026-06-24 | [v0.5.0-ROADMAP.md](milestones/v0.5.0-ROADMAP.md) |
| v0.6.0 | 🚧 ACTIVE | 36–40 | TBD | — | — | — |

## v0.5.0 Phases (shipped)

<details>
<summary>✅ v0.5.0 Scene Editor & UX Polish (Phases 31–35) — SHIPPED 2026-06-24</summary>

- [x] **Phase 31: Tech Debt Foundation** — 5 quick-win debt items (421 ruff in `src/surg_rl/dreamer/`, Dockerfile.ros2 `$TARGETARCH`, fluid step hook, cut cooldown test, PhiFlow union doc) + `[gui]` extra + `surg-rl-gui` console script + mjpython helper + editor skeleton (4/4 plans, completed 2026-06-18)
- [x] **Phase 32: Demo Suite Polish** — `demos/_common.py` shared narration + `NARRATION_TEMPLATE.md` + suturing/knot-tying/needle-passing demos + 6 regression tests (3/3 plans, completed 2026-06-19)
- [x] **Phase 33: PySide6 Scene Editor** — marquée: render bridge + schema walker + tree/form + viewport + undo/redo + LLM panel + shell + smoke tests (all 10 GUI requirements) (7/7 plans, completed 2026-06-21)
- [x] **Phase 34: User-Facing Docs Refresh** — README + CONTRIBUTING + CHANGELOG + 3 demo GIFs + 3 GUI screenshots (4/4 plans, completed 2026-06-21)
- [x] **Phase 35: Advanced Tech Debt** — HARD-fixture `SurgicalEnv`-construction integration test + `CurriculumStageConfig.difficulty` normalization + K8s PVC scaffolding + organ mesh licensing research spike (4/4 plans, completed 2026-06-22)

Full phase goals, success criteria, and plan lists: see
[`.planning/milestones/v0.5.0-ROADMAP.md`](milestones/v0.5.0-ROADMAP.md).

</details>

## v0.6.0 Carried-Forward Debt Closure

**Goal:** Close the four carried-forward tech-debt items deferred from v0.4.0–v0.5.0 — real DreamerV3 integration, the TASK-02 per-level difficulty schema, K8s PVC e2e + organ-mesh licensing decision, and the 3D fluid flag. Pure closure: no new user-facing features (those are queued for v0.7.0). Every item is additive — the v0.4.0 + v0.4.2 + v0.5.0 test baseline passes unchanged.

**Phase Numbering:**

- Integer phases (36, 37, ...): Planned milestone work continuing from v0.5.0 Phase 35
- Decimal phases (e.g., 37.1): Urgent insertions (marked INSERTED), created via `/gsd-phase --insert`

### Phases

- [x] **Phase 36: Difficulty Schema + Discrete Curriculum** - DifficultyLevelConfig leaf model + additive CurriculumScheduler level progression (non-GPU, lowest risk, unblocks 37) (completed 2026-06-25)
- [x] **Phase 37: Scene-Level difficulty_blocks + Env Wiring** - Scene JSON difficulty_blocks + SurgicalEnv precedence truth-table + load-all-6-scenes regression (completed 2026-06-24)
- [ ] **Phase 38: 3D Fluid Flag (dim_3d=True)** - 3D Eulerian grid fluids via PhiFlow 3D Box/StaggeredGrid; additive, 2D path stays green; independent of 36/37/39
- [ ] **Phase 39: K8s PVC e2e + Organ-Mesh Licensing ADR** - De-stub checkpoint-persistence e2e via pytest-kind + record procedural-vs-surgtoolloc ADR; independent, low-risk before GPU-gated 40
- [ ] **Phase 40: Real DreamerV3 Integration + Sentinel Flip** - Replace 5 stub functions with real dreamerv3.Agent; flip Phase 30 sentinel negative→positive; GPU-gated LAST phase

### Phase Details

#### Phase 36: Difficulty Schema + Discrete Curriculum

**Goal**: Researchers can define per-level difficulty overrides (tissue stiffness, precision tolerance, tool noise, time limit) that apply additively over the existing `interpolate_params()` baseline, and the curriculum can advance through discrete EASY→MEDIUM→HARD levels without touching the validated continuous `advance_stage` path.
**Depends on**: Nothing (first phase of v0.6.0; continues from v0.5.0 Phase 35)
**Requirements**: TASK-06, TASK-07, TASK-09
**Success Criteria** (what must be TRUE):

  1. A `DifficultyLevelConfig` Pydantic v2 model accepts the four override fields (tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit) and validates types and ranges
  2. Per-level overrides compose additively over `interpolate_params()` — overriding a field changes only that field; unoverridden fields retain the interpolated value (verified by a truth-table test)
  3. `CurriculumScheduler` has an additive `progression_mode` that advances EASY→MEDIUM→HARD via new `set_difficulty_level` / `advance_level` methods, while the continuous `advance_stage` path produces identical output to v0.5.0
  4. The full v0.4.0 + v0.4.2 curriculum + difficulty test suite passes unchanged (additive-regression gate; no test edits beyond additions)
  5. `DifficultyLevelConfig` is a leaf module (zero in-project imports) wired via the v0.4.2 `model_rebuild()` cycle-resolution pattern — no Pydantic cross-package cycle re-introduced

**Plans**: 3/3 plans complete
**Wave 1**

- [x] 36-01-PLAN.md — DifficultyLevelConfig Pydantic v2 leaf model + range validators (TDD, Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 36-02-PLAN.md — difficulty_wiring module (ABSTRACT_TO_CONCRETE + DiscreteCurriculumConfig + compose_difficulty_overrides) + truth-table test (TDD, Wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 36-03-PLAN.md — additive CurriculumScheduler progression_mode + set/advance_level + advance_stage parity (TDD, Wave 3)

#### Phase 37: Scene-Level difficulty_blocks + Env Wiring

**Goal**: Scene JSON authors can specify `difficulty_blocks` per level on a task, and `SurgicalEnv` applies them at construction with a single, documented, tested override-precedence chain — so a researcher loading a scene with hard-mode blocks gets a hard-mode environment without code changes.
**Depends on**: Phase 36 (uses DifficultyLevelConfig)
**Requirements**: TASK-08
**Success Criteria** (what must be TRUE):

  1. A scene JSON with `difficulty_blocks` for all three levels loads via `SceneLoader` without error and the blocks round-trip through Pydantic v2 validation
  2. `SurgicalEnv._setup_rewards` applies overrides in a documented precedence: scene-level `difficulty_blocks[level]` > `TaskConfig.difficulty_level` > `config.difficulty` > default 0.5 — verified by a parametrized truth-table test
  3. Loading all 6 v0.4.0 task scene fixtures (suturing, knot_tying, needle_insertion, grasping, cutting, dissection) with each of the three difficulty levels succeeds and produces a stepped environment (regression gate)
  4. Existing v0.4.2 fixture `suturing_difficulty_hard.json` still loads and produces the same difficulty scalar it did before this phase (back-compat gate)
  5. Naming drift reconciled: `difficulty_blocks` is the canonical field name across PROJECT.md, schema, and STATE.md (the prior `difficulty_levels` spelling is gone)

**Plans**: 3/3 plans complete
**Wave 1**

- [x] 37-01-PLAN.md — TaskConfig.difficulty_blocks schema field + SC#1 round-trip + SC#5 naming-drift reconciliation (TDD, Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 37-02-PLAN.md — apply_params refactor on 6 task rewards + SurgicalEnvConfig.difficulty + _setup_rewards 4-level precedence branch + SC#2 truth table (TDD, Wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 37-03-PLAN.md — SC#3 6×3 scene regression gate + SC#4 hard-fixture back-compat scalar gate (Wave 3)

#### Phase 38: 3D Fluid Flag (dim_3d=True)

**Goal**: Simulation authors can opt into 3D Eulerian grid fluids via `FluidConfig.dim_3d=True` and get a stable, memory-bounded 3D solver with one-way fluid/solid coupling by default, while the validated 2D xz-slice path stays unchanged for existing scenes.
**Depends on**: Nothing (independent of the difficulty chain and of Phase 39; parallelizable via worktrees alongside 36/37/39)
**Requirements**: FLUID-01, FLUID-02, FLUID-03
**Success Criteria** (what must be TRUE):

  1. `FluidConfig.dim_3d=True` constructs a 3D `Box(x,y,z)` + `StaggeredGrid` and runs `make_incompressible` + pressure projection in 3D; `dim_3d=False` (default) produces byte-identical 2D solver output to v0.5.0 (regression gate)
  2. 3D fluid/solid coupling runs stably for a full episode with the default `coupling_mode="one_way"` on thin instruments (no NaN, no simulation blow-up); `two_way` is opt-in and documented as unstable on thin instruments
  3. A separate, smaller 3D default `grid_size` + Pydantic validator prevents the cubic NxNxN memory blow-up when `dim_3d=True` is set without an explicit grid size
  4. The documented `union(*geoms)` multi-obstacle SDF workaround has a NaN-regression test covering BOTH the 2D and 3D paths
  5. `BaseSimulator.fluid_step(dt)` hook still fires for both `dim_3d` modes (the v0.5.0 5-test regression suite passes unchanged)

**Plans**: 4 plans in 3 waves

Plans:
**Wave 1**
- [ ] 38-01-PLAN.md — FluidConfig 3D schema (dim_3d, grid_size, FluidCouplingMode, coupling_substeps, _cap_grid_size, _require_grid_size_when_dim_3d) — TDD

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 38-02-PLAN.md — 3D FluidSimulator (init/step/add_instrument) + _compute_obstacle_forces_3d (obstacle-mask + per-axis clamp) — TDD [depends_on: 38-01]
- [ ] 38-03-PLAN.md — render_fluid_3d z-layer slice + _render_np_2d helper extraction (2D byte-identical guarded) — TDD [depends_on: 38-01]

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 38-04-PLAN.md — Regression gates: SC#1 2D byte-identical baseline + SC#2 3D coupling + SC#4 NaN parametrized + SC#5 confirmation [depends_on: 38-01, 38-02, 38-03]

**Cross-cutting constraints** (must_haves truths enforced by ≥2 plans):
- 2D byte-identical preservation (SC#1/SC#5) — Plans 01, 02, 03, 04: every plan's `must_not` requires the existing 2D path (`_cap_resolution`/`resolution`, `compute_obstacle_forces`/`FluidSimulator`, `render_fluid_2d`, `test_fluid_step.py` 5-test suite) to stay byte-identical.
- Additive-only — Plans 01-04: no plan edits existing 2D production code or existing 2D tests; new 3D code lives in `if config.dim_3d:` / `else:` branches or new functions/classes.
- PhiFlow 3.4.0 solver settings — Plans 02, 04: `fluid.make_incompressible(..., solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500))` reused for both dims (production in 02, test fixtures in 04).

#### Phase 39: K8s PVC e2e + Organ-Mesh Licensing ADR

**Goal**: The K8s checkpoint-persistence path is verified end-to-end on a bound PVC (de-stubbed via `pytest-kind`), and the organ-mesh licensing decision is recorded as a cite-able ADR so future asset work has a single source of truth.
**Depends on**: Nothing (independent; low-risk landing before the GPU-gated Phase 40; parallelizable via worktrees alongside 36/37/38)
**Requirements**: DEPLOY-01, ASET-06
**Success Criteria** (what must be TRUE):

  1. A `pytest-kind` session-scoped `kind_cluster` fixture brings up a local Kubernetes cluster in CI and a de-stubbed PVC e2e test asserts write → pod restart → read on a bound PVC (`kubectl wait --for=condition=Bound`)
  2. The PVC e2e test runs in CI on a path that does not require a GPU (CPU-only K8s node) and is skipped gracefully on macOS local runs that lack Docker/kind
  3. A `k8s/overlays/e2e/` Kustomize overlay exists and applies the PVC + training job used by the e2e test
  4. An ADR document records the organ-mesh licensing decision: procedural generation is the default; surgtoolloc is rejected with cited rationale (endoscopic video with tool-presence labels, not organ geometry; MICCAI/EndoVis challenge guidelines prohibit commercial use)
  5. The ADR cites the specific SurgToolLoc/EndoVis MICCAI license clause text (or the public challenge terms URL) so the rejection is auditable

**Plans**: TBD

#### Phase 40: Real DreamerV3 Integration + Sentinel Flip

**Goal**: A researcher can train a real DreamerV3 agent on a surgical task via the process-isolated JAX subprocess (the stub is gone), checkpoints persist and resume per task/obs-type, and the milestone's closure signal — the Phase 30 sentinel flipped from negative to positive — guards against stub regression.
**Depends on**: Phases 36, 37, 38, 39 landed (clean baseline; GPU-gated; highest external-API risk → last)
**Requirements**: DMV3-07, DMV3-08, DMV3-09, DMV3-10
**Success Criteria** (what must be TRUE):

  1. The 5 stub functions (`_build_agent` / `_train_loop` / `_evaluate` / `_save_checkpoint` / `_load_checkpoint`) are replaced with real implementations against `embodied.run.train` / `dreamerv3.Agent`, and the JSON-over-stdio subprocess protocol, `_JsonStdout` wrapper, and `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` isolation are unchanged
  2. DreamerV3 checkpoints persist per task/obs-type under `models/dreamerv3/{task}_{obs_type}/` and resume training across subprocess restarts (verified by a restart-then-continue test)
  3. The Phase 30 E2E test is INVERTED, not deleted: it asserts positive real-agent completion AND includes a regression guard that fails if `_build_agent` ever returns `None` again
  4. The CI GPU host runs the real-agent smoke test and asserts structural properties only (finite and non-increasing loss, checkpoint file exists) — NOT the v0.4.0 spike's converged `MSE<0.01` thresholds; macOS local runs skip cleanly per INV-8
  5. JAX never leaks into the parent process (no `import jax` / `import dreamerv3` in `surg_rl` parent-package import path), and the dreamerv3 logger writes to stderr (not stdout — stdout stays clean for the JSON pipe)

**Plans**: TBD

### Coverage

- v0.6.0 requirements: 13 total — 13/13 mapped ✓
  - TASK-06, TASK-07, TASK-09 → Phase 36 · TASK-08 → Phase 37
  - FLUID-01, FLUID-02, FLUID-03 → Phase 38
  - DEPLOY-01, ASET-06 → Phase 39
  - DMV3-07, DMV3-08, DMV3-09, DMV3-10 → Phase 40
- No orphaned requirements; no duplicate mappings

### Progress

**Execution Order:**
Phases execute in numeric order: 36 → 37 → 38 → 39 → 40. Phases 38 and 39 are independent of the 36→37 difficulty chain and may be parallelized via git worktrees alongside 36/37. Phase 40 is GPU-gated and runs LAST on the CI GPU host.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 36. Difficulty Schema + Discrete Curriculum | 3/3 | Complete    | 2026-06-25 |
| 37. Scene-Level difficulty_blocks + Env Wiring | 3/3 | Complete    | 2026-06-25 |
| 38. 3D Fluid Flag (dim_3d=True) | 0/4 | Planned | - |
| 39. K8s PVC e2e + Organ-Mesh Licensing ADR | 0/TBD | Not started | - |
| 40. Real DreamerV3 Integration + Sentinel Flip | 0/TBD | Not started | - |

## Next Steps

1. `/gsd-plan-phase 36` — Difficulty Schema + Discrete Curriculum (non-GPU, lowest risk, unblocks 37)
2. Phases 38 and 39 may be planned/parallelized via worktrees once 36 is underway
3. Phase 40 (Real DreamerV3) is GPU-gated and runs LAST — schedule CI GPU host provisioning before planning 40

---

*Roadmap defined: 2026-06-24 — v0.6.0 milestone initiated (Carried-Forward Debt Closure, PLANNING)*
*Phase numbering continues from v0.5.0 Phase 35 → starts at Phase 36 (never restart at 01)*
