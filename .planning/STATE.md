# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-09)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** v0.4.0 milestone shipped — planning v0.5.0

## Current Position

Milestone: v0.4.0 — Training Infrastructure & Realism (SHIPPED 2026-06-09)
Phase: 24 of 24 complete
Status: Milestone closed — ready for v0.5.0 planning
Last activity: 2026-06-09 — v0.4.0 archived: 6 phases (19–24), 21 plans, 23/23 v1 requirements complete

Progress: ████████████████████████████████ 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 94 across v0.1.0–v0.4.0 (12 + 19 + 18 + 1 + 9 + 21 = 80 plans from v0.1.0–v0.3.2 per archive; 14 from v0.4.0 phase 24 = 5, plus earlier; see archive)
- Total execution time: tracked per phase in milestone archives

**By Milestone:**

| Milestone | Phases | Plans | Tests |
|-----------|--------|-------|-------|
| v0.1.0 | 1–5 | 12 | 607 |
| v0.2.0 | 6–9 | 19 | 775 |
| v0.3.0 | 10–13 | 18 | 826 |
| v0.3.1 | 14 | 1 | 833 |
| v0.3.2 | 15–18 | 9 | 910 |
| v0.4.0 | 19–24 | 21 | TBD |

## Accumulated Context

### Decisions

- [v0.3.2]: Tetgen replaces VTK entirely (not side-by-side); MuJoCo `<flex>` (not `<flexcomp>`) for arbitrary tetgen meshes; cutting is discrete trigger with 500ms cooldown; PhiFlow over Mantaflow for Eulerian fluids
- [v0.4.0 research]: Schema-first (all new Pydantic v2 models, all optional fields); trimesh is sole new mesh library; PettingZoo ParallelEnv MUST be separate class from SurgicalEnv; DreamerV3 needs process isolation via JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`; benchmarking treats MuJoCo and PyBullet as separate targets; CurriculumScheduler extension must be additive (never replace Phase 3 fix)
- [v0.4.0 Phase 21]: TaskResult Pydantic v2 hierarchy with 6 per-task sub-models; TASK_REWARD_REGISTRY dispatch replaces string-matching; PARAM_BOUNDS + interpolate_params() for continuous difficulty interpolation; check_success/check_failure on all 6 reward classes; TaskRewardRouter with safe None/unknown handling; D-10: apply_parameters() never modified
- [v0.4.0 Phase 23]: Dual statistical aggregation (mean±1σ + IQM+CI) on learning curves per D-08; Seaborn colorblind-safe palette with fixed algorithm color cycle; standalone HTML report with embedded CSS; per-backend directory structure; DreamerV3 pending status shown gracefully in all outputs
- [v0.4.0 Phase 24]: Feasibility spike: forceps + liver tet mesh suturing scene, MSE < 0.01 / reward MAE < 0.5 thresholds; multiprocessing + stdin/stdout process isolation with XLA_PYTHON_CLIENT_MEM_FRACTION=0.4; GymToEmbodiedWrapper with reset-in-action protocol; pixel obs (RGB+depth 64×64) + low-dim state (~50-100 dims); auto-discovery checkpoints from models/dreamerv3/{task}_{obs_type}/; kill switch defers to v0.5.0 if spike fails

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 24 (DreamerV3):** DreamerV3's ability to model tet mesh cutting dynamics is uncertain — the feasibility spike (DMV3-01) has a kill switch to defer to v0.5.0. JAX+PyTorch GPU memory conflict requires robust process isolation.
- **Phase 20 (Assets):** Organ mesh source licensing — need MIT/CC0 organ meshes. Candidate: procedural generation or surgtoolloc dataset.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Phase 17 | Per-tet generation counter for degenerate tets | Deferred | v0.3.2 |
| Phase 17 | Cut cooldown unit test | Deferred | v0.3.2 |
| Phase 18 | Fluid step hook in base_simulator.py | Deferred | v0.3.2 |
| Config | PhiFlow multi-obstacle union() workaround | Documented pitfall | v0.3.2 |
| Config | 2D fluids only (3D behind dim_3d=True flag) | Deferred | v0.3.2 |
| Config | Previous v0.3.1 deferred (Dockerfile.ros2, K8S PVC, KubeRay) | Acknowledged | v0.3.2 |

## Session Continuity

Last session: 2026-06-09
Stopped at: v0.4.0 milestone closed and archived; ready to plan v0.5.0
Resume file: (none — start v0.5.0 with /gsd-new-milestone)

---

*Updated: 2026-06-09 — v0.4.0 milestone shipped*
