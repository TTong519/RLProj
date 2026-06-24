---
gsd_state_version: 1.0
milestone: v0.5.0
milestone_name: Scene Editor & UX Polish
current_phase: null
status: Awaiting next milestone
stopped_at: null
last_updated: "2026-06-24T05:18:29.700Z"
last_activity: 2026-06-24
last_activity_desc: Milestone v0.5.0 completed and archived
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 22
  completed_plans: 22
  percent: 100
current_phase_name: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-24 v0.5.0 milestone shipped)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with an interactive PySide6 GUI scene editor, automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.
**Current focus:** v0.5.0 shipped; next milestone not yet defined — run `/gsd-new-milestone`

## Current Position

Phase: Milestone v0.5.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-06-24 — Milestone v0.5.0 completed and archived

## Performance Metrics

**Velocity:**

- Total plans completed: 88 across v0.1.0–v0.4.1 (12 + 19 + 18 + 1 + 9 + 21 + 4)
- Total execution time: tracked per phase in milestone archives

**By Milestone:**

| Milestone | Phases | Plans | Tests |
|-----------|--------|-------|-------|
| v0.1.0 | 1–5 | 12 | 607 |
| v0.2.0 | 6–9 | 19 | 775 |
| v0.3.0 | 10–13 | 18 | 826 |
| v0.3.1 | 14 | 1 | 833 |
| v0.3.2 | 15–18 | 9 | 910 |
| v0.4.0 | 19–24 | 21 | 1,043 |
| v0.4.1 | 25–28 | 4 | 1,053 |
| v0.4.2 | 29–30 | 3 | 1,134 |
| v0.5.0 | 31 | 4 | 1,200 |
| v0.5.0 | 32–35 | TBD | TBD |

## Accumulated Context

### Decisions

- [v0.3.2]: Tetgen replaces VTK entirely (not side-by-side); MuJoCo `<flex>` (not `<flexcomp>`) for arbitrary tetgen meshes; cutting is discrete trigger with 500ms cooldown; PhiFlow over Mantaflow for Eulerian fluids
- [v0.4.0 research]: Schema-first (all new Pydantic v2 models, all optional fields); trimesh is sole new mesh library; PettingZoo ParallelEnv MUST be separate class from SurgicalEnv; DreamerV3 needs process isolation via JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`; benchmarking treats MuJoCo and PyBullet as separate targets; CurriculumScheduler extension must be additive (never replace Phase 3 fix)
- [v0.4.0 Phase 21]: TaskResult Pydantic v2 hierarchy with 6 per-task sub-models; TASK_REWARD_REGISTRY dispatch replaces string-matching; PARAM_BOUNDS + interpolate_params() for continuous difficulty interpolation; check_success/check_failure on all 6 reward classes; TaskRewardRouter with safe None/unknown handling; D-10: apply_parameters() never modified
- [v0.4.0 Phase 23]: Dual statistical aggregation (mean±1σ + IQM+CI) on learning curves per D-08; Seaborn colorblind-safe palette with fixed algorithm color cycle; standalone HTML report with embedded CSS; per-backend directory structure; DreamerV3 pending status shown gracefully in all outputs
- [v0.4.0 Phase 24]: Feasibility spike: forceps + liver tet mesh suturing scene, MSE < 0.01 / reward MAE < 0.5 thresholds; multiprocessing + stdin/stdout process isolation with XLA_PYTHON_CLIENT_MEM_FRACTION=0.4; GymToEmbodiedWrapper with reset-in-action protocol; pixel obs (RGB+depth 64×64) + low-dim state (~50-100 dims); auto-discovery checkpoints from models/dreamerv3/{task}_{obs_type}/; kill switch defers to v0.5.0 if spike fails
- [v0.4.1 Phase 25]: SurgicalEnv.passthrough_step() for MARL per-arm action passthrough (no-op action, size = num_controls zeros); _step_simulator_and_build_outputs() helper shared by step() and passthrough_step()
- [v0.4.1 Phase 26]: _JsonStdout wrapper class replaces os.fdopen on PyTorch's non-blocking Pipe (fixes DreamerV3 subprocess hang); indigo→indent typo fix; DREAMER_COLOR constant for ANSI palette
- [v0.4.1 Phase 27]: 5 new task scene JSONs aligned with Phase 24 dreamer_training test contract (instrument + tissue types per task); ExperimentRunner.__init__ writes experiments/{name}.yaml for CLI reproducibility
- [v0.4.1 Phase 28]: v0.4.0 audit gap closure: 12/14 gaps fully closed, 1 partial (TASK-02 3-difficulty-levels), 1 deferred (DreamerV3 real-E2E); REQUIREMENTS.md BENCH-01 body checkbox flipped to [x]; 3 retroactive VERIFICATION.md files (Phases 21, 22, 23)
- [v0.4.2]: User selected v0.4.2 (not v0.5.0) for the audit leftovers — small focused gap closure. Tech debt cleanup (421 ruff in dreamer/, cut cooldown test, fluid step hook, 3D fluid flag, K8s e2e, etc.) explicitly deferred to v0.5.0+.
- [v0.4.2 D-29-01..05]: TASK-02 closes with DifficultyLevel enum (EASY=0.0, MEDIUM=0.5, HARD=1.0) + per-task `get_params_for_difficulty()` wrappers around existing `interpolate_params()` + TaskRewardRouter accepting both float and enum + TaskConfig.difficulty_level optional field + CurriculumScheduler accepting both float and enum. No new DifficultyLevelConfig schema model — out of scope.
- [v0.4.2 D-30-01..05]: DreamerV3 E2E is a single pytest test in `tests/dreamer/test_dreamerv3_subprocess_e2e.py` (or `tests/test_dreamerv3_subprocess_e2e.py` if `tests/dreamer/` is not a directory). Gated by `@pytest.mark.skipif` on (GPU + dreamerv3 + jax). macOS local xfail-skip expected; CI with GPU validates.
- [v0.4.2 Phase 29]: DifficultyLevel uses `_FloatMixin(float, Enum)` to make `DifficultyLevel.EASY == 0.0` True (no stdlib FloatEnum). Pydantic v2 cycle resolution pattern established: `from __future__ import annotations` + string forward-ref + late import + `Model.model_rebuild()`; plus lazy local import of `SceneLoader` inside `_load_scene()` to break the second cycle. Code review identified 3 MEDIUM future-hardening items: CurriculumScheduler.current_difficulty type lie, missing end-to-end env-construction test, and CurriculumStageConfig union not normalized at env. These are explicitly deferred per CONTEXT.md scope.
- [v0.4.2 Phase 30]: DreamerV3 E2E test uses module-level `pytest.mark.skipif` evaluated at collection time; heavy imports live inside test methods to avoid macOS collection crash. Tests assert the EXPECTED `RuntimeError("Agent not configured")` from the Phase 24 `_build_agent` stub state — sentinel that will START FAILING when real dreamerv3 is integrated. macOS local: 3 SKIP, exit 0. CI GPU host: will run and document the stub state. No production code modified (smoke-test gap-closure only).
- [v0.4.2 close]: Both phase verifications passed (6/6 + 10/10 must-haves). 11/11 v1 requirements satisfied. 0 partial, 0 deferred. 421 ruff issues in `src/surg_rl/dreamer/` and other tech debt items remain deferred to v0.5.0+ per user direction.
- [v0.5.0 roadmap]: 5 phases (31–35) derived from 26 v1 requirements (10 GUI + 5 DEMO + 5 DOC + 6 DEBT). Marquée = PySide6 Scene Editor (Phase 33). Phase 31 = 5 quick-win DEBT items + `[gui]` extra + `surg-rl-gui` console script + mjpython helper so Phase 33 starts on a clean baseline. Phase 32 = `_common.py` refactor + 2 new demos + 3 regression tests + `NARRATION_TEMPLATE.md`. Phase 34 = README + CONTRIBUTING + CHANGELOG + 3 demo GIFs + 3 GUI screenshots (sequential after 32 + 33). Phase 35 = DEBT-06 (HARD-fixture integration test) + CurriculumStageConfig normalization + K8s PVC scaffolding + organ mesh licensing research spike (can run in parallel with 32–34 via worktrees).
- [v0.5.0 Phase 31]: All 5 DEBT-01..05 requirements closed (ruff cleanup 10→0 issues in `src/surg_rl/dreamer/`; Dockerfile.ros2 multi-arch via `$TARGETARCH`; BaseSimulator.fluid_step hook with MuJoCo/PyBullet overrides + env wiring + 5 tests; TestCutCooldown parametrized over both backends with 6 collected tests; PhiFlow multi-obstacle `union()` workaround documented at module level with upstream link). Phase 31 also shipped GUI scaffolding for Phase 33: `[gui]` optional-dependency group (PySide6>=6.8.0,<7.0 + markdown-it-py>=3.0.0), `surg-rl-gui` console-script entry as separate from `surg-rl` CLI, `surg_rl.editor` package with `LazyImport` + `HAS_GUI` sentinel, `_is_running_under_mjpython()` + `_ensure_mjpython_or_warn()` helpers extracted from `mujoco_simulator.py:1294-1298`, `surg_rl.editor.app.main()` install-hint entrypoint, and 19-test regression suite in `tests/test_gui_scaffold.py`. Test baseline: 1134→1200 passed (+66 new), 17 skipped, 0 failed.

### Pending Todos

- None. v0.5.0 Phase 31 complete; next: `/gsd-execute-phase 32` (Demo Suite Polish) — independent of Phase 33; can also run in parallel with Phase 35 via worktrees.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260614-1 | Clean up pre-GSD files: archived STATUS, IMPLEMENTATION_PLAN, SOFTBODY_PLAN, superpowers/, root-level misc to .planning/milestones/v0.0.0-*. Fixed broken cross-refs in docs/README.md, docs/QUICK_REFERENCE.md, .planning/codebase/STRUCTURE.md | 2026-06-14 | (this commit) | (inline) |
| 20260617-demo-rework | Reworked scenes/suturing_demo.json + scene_builder: soft FEM tissue (flexcomp), realistic needle (procedural thin-torus), visible gripper jaws. Updated demo banner. Added 3 regression tests. 1168/1168 tests pass. | 2026-06-17 | 9e11c3f | [20260617-demo-rework](./quick/20260617-demo-rework/) |

### Blockers/Concerns

- **Phase 24 (DreamerV3):** DreamerV3's ability to model tet mesh cutting dynamics is uncertain — the feasibility spike (DMV3-01) has a kill switch to defer to v0.5.0. JAX+PyTorch GPU memory conflict requires robust process isolation.
- **Phase 20 (Assets):** Organ mesh source licensing — need MIT/CC0 organ meshes. Candidate: procedural generation or surgtoolloc dataset.
- **v0.4.2 Phase 29 (TASK-02):** The EASY/HARD scalar assignment is a design choice. If any PARAM_BOUNDS has `lo > hi` (inverted bounds), 0.0 = strict and 1.0 = loose — must verify direction in test, not just inequality. Implementation must audit all 6 PARAM_BOUNDS dictionaries and ensure EASY = 0.0 = loose, HARD = 1.0 = strict consistently.
- **v0.4.2 Phase 30 (DreamerV3 E2E):** GPU + dreamerv3 install are hard prereqs. macOS local run will likely be xfail-skip; CI runner with GPU required for full E2E coverage. The test is the deferred DMV3-03 E2E validation, not a regression suite — only verifies Phase 26 fixes hold end-to-end on real hardware.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| TASK-02 | 3-difficulty-levels (easy/medium/hard presets) | **Closed in v0.4.2** | v0.4.1 |
| DreamerV3 | Real-subprocess E2E test | **Closed in v0.4.2** | v0.4.1 |

### Acknowledged at v0.5.0 close (2026-06-23)

Open artifacts from the pre-close `audit-open` scan, acknowledged and
carried forward (3 items; the v0.5.0-relevant `gui-no-render-under-mjpython`
debug session was resolved by commit `3031ed9` and closed separately):

| Category | Item | Status | Note |
|----------|------|--------|------|
| verification | Phase 09 ros2-bridge `09-VERIFICATION.md` gaps_found | Deferred | Older milestone (v0.3.0) verification debt |
| uat | Phase 24 DreamerV3 `24-UAT.md` partial | Deferred | GPU-gated; macOS local xfail-skip, CI GPU host required |
| quick_task | demo-rework (20260617) | **Complete** | SUMMARY records "Verified (1168/1168 tests pass)"; audit read stale `[unknown]` marker — actually shipped in commit `9e11c3f` |
| TASK-02 | Per-level override schema (DifficultyLevelConfig with tissue_stiffness/target_precision_tolerance/tool_position_noise/time_limit) | Deferred | v0.4.2 |
| TASK-02 | CurriculumScheduler discrete level progression | Deferred | v0.4.2 |
| TASK-02 | Scene-level `difficulty_levels: list[3]` blocks in scene JSON files | Deferred | v0.4.2 |
| Phase 29 | End-to-end SurgicalEnv-construction integration test for HARD fixture scene | Closed in v0.5.0 | v0.4.2 |
| Phase 29 | CurriculumStageConfig.difficulty normalization at env-construction | Closed in v0.5.0 | v0.4.2 |
| Phase 30 | Stub-state sentinel flip when real dreamerv3 is integrated (replaces `_build_agent`) | Deferred | v0.4.2 |
| Phase 17 | Per-tet generation counter for degenerate tets | Deferred | v0.3.2 |
| Phase 17 | Cut cooldown unit test | **Closed in Phase 31 (TestCutCooldown x 2 backends)** | v0.3.2 |
| Phase 18 | Fluid step hook in base_simulator.py | **Closed in Phase 31 (BaseSimulator.fluid_step + overrides + env wiring)** | v0.3.2 |
| Config | PhiFlow multi-obstacle union() workaround | **Documented at module level + linked in Phase 31** | v0.3.2 |
| Config | 2D fluids only (3D behind dim_3d=True flag) | Deferred | v0.3.2 |
| Config | Previous v0.3.1 deferred (Dockerfile.ros2, K8S PVC, KubeRay) | Acknowledged | v0.3.2 |
| Lint | 421 ruff issues in src/surg_rl/dreamer/ (F841, B904, E402) | **Closed in Phase 31 (10→0 issues)** | v0.4.1 |
| Process | REQUIREMENTS.md BENCH-02..05 body checkboxes remain `[ ]` | Acknowledged | v0.4.0 |
| v2 | TASK-05 task chains (grasp→cut→suture) | v2 | v0.4.0 |
| v2 | MARL-05 RLlib centralized critic | v2 | v0.4.0 |
| v2 | DMV3-06 DreamerV3 offline training from demos | v2 | v0.4.0 |
| Assets | Organ mesh source licensing (surgtoolloc or procedural) | Researched; deferred to v0.6.0 | v0.4.0 |
| Testing | Linux-only ROS2 subscriber e2e tests | Acknowledged | v0.3.1 |

## Session Continuity

Last session: 2026-06-19T19:26:16.130Z
Stopped at: Phase 33 context gathered
Resume file: .planning/phases/33-pyside6-scene-editor/33-CONTEXT.md

---

*Updated: 2026-06-18 — Phase 31 SHIPPED (4/4 plans, 5/5 DEBT-01..05 closed; 1200 tests pass)*

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
