# Roadmap: Surg-RL

**Defined:** 2026-06-14 (post-v0.4.2 close)
**Next Milestone:** v0.5.0 — TBD (use `/gsd-new-milestone` to define)

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
| v0.5.0 | 📋 not yet planned | — | — | — | — | — |

## Next Steps

1. `/gsd-new-milestone` — define v0.5.0 scope (questioning → research → requirements → roadmap)
2. Tech debt candidates to consider for v0.5.0+: 421 ruff issues in `src/surg_rl/dreamer/`, TASK-02 per-level overrides, CurriculumScheduler discrete progression, scene-level difficulty blocks, Dockerfile.ros2 amd64 hardcode, K8s PVC e2e, KubeRay prereq, 3D fluid flag, organ mesh source licensing, DreamerV3 real-dreamerv3 integration (flips Phase 30 sentinel)
3. v2 candidates: TASK-05 task chains, MARL-05 RLlib centralized critic, DMV3-06 offline training from demos

---

*Roadmap defined: 2026-06-14 (post-v0.4.2 close)*
*Last updated: 2026-06-14 after v0.4.2 milestone archive*
