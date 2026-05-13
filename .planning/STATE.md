# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Phase 19 — Schema Foundation

## Current Position

Milestone: v0.4.0 — Training Infrastructure & Realism
Phase: 19 of 24 (Schema Foundation)
Plan: —
Status: Ready to plan
Last activity: 2026-05-13 — v0.4.0 phased roadmap created (Phases 19–24)

Progress: ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 67 (across v0.1.0 through v0.3.2)
- Total execution time: tracked per phase in milestone archives

**By Milestone:**

| Milestone | Phases | Plans | Tests |
|-----------|--------|-------|-------|
| v0.1.0 | 1–5 | 12 | 607 |
| v0.2.0 | 6–9 | 19 | 775 |
| v0.3.0 | 10–13 | 18 | 826 |
| v0.3.1 | 14 | 1 | 833 |
| v0.3.2 | 15–18 | 9 | 910 |

## Accumulated Context

### Decisions

- [v0.3.2]: Tetgen replaces VTK entirely (not side-by-side); MuJoCo `<flex>` (not `<flexcomp>`) for arbitrary tetgen meshes; cutting is discrete trigger with 500ms cooldown; PhiFlow over Mantaflow for Eulerian fluids
- [v0.4.0 research]: Schema-first (all new Pydantic v2 models, all optional fields); trimesh is sole new mesh library; PettingZoo ParallelEnv MUST be separate class from SurgicalEnv; DreamerV3 needs process isolation via JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`; benchmarking treats MuJoCo and PyBullet as separate targets; CurriculumScheduler extension must be additive (never replace Phase 3 fix)

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

Last session: 2026-05-13
Stopped at: ROADMAP.md, STATE.md, REQUIREMENTS.md traceability written for v0.4.0
Resume file: None

---

*Updated: 2026-05-13 — v0.4.0 roadmap created*
