# Roadmap: Surg-RL

**Defined:** 2026-06-24 (v0.6.0 Carried-Forward Debt Closure planning)
**Last Shipped:** v0.6.0 Carried-Forward Debt Closure — Phases 36–40.1 (SHIPPED 2026-07-15)
**Current Milestone:** None — awaiting next milestone (`/gsd-new-milestone`)

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
| v0.6.0 | ✅ SHIPPED | 36–40.1 | 18 | 1,513 | 2026-07-15 | [v0.6.0-ROADMAP.md](milestones/v0.6.0-ROADMAP.md) |

## v0.6.0 Phases (shipped)

<details>
<summary>✅ v0.6.0 Carried-Forward Debt Closure (Phases 36–40.1) — SHIPPED 2026-07-15</summary>

Pure closure milestone — no new user-facing features (GUI editor depth + scene generation deferred to v0.7.0). Closes the four carried-forward tech-debt items deferred from v0.4.0–v0.5.0: real DreamerV3 integration, TASK-02 per-level difficulty schema, K8s PVC e2e + organ-mesh licensing decision, and the 3D fluid flag. Every item additive — the v0.4.0 + v0.4.2 + v0.5.0 test baseline passes unchanged.

- [x] **Phase 36: Difficulty Schema + Discrete Curriculum** — `DifficultyLevelConfig` leaf model + additive `CurriculumScheduler` level progression (3/3 plans, completed 2026-06-25)
- [x] **Phase 37: Scene-Level difficulty_blocks + Env Wiring** — scene JSON `difficulty_blocks` + `SurgicalEnv` 4-level precedence truth-table + 6-scene regression (3/3 plans, completed 2026-06-25)
- [x] **Phase 38: 3D Fluid Flag (dim_3d=True)** — 3D Eulerian grid fluids via PhiFlow 3D `Box`/`StaggeredGrid`; additive, 2D path byte-identical (4/4 plans, completed 2026-06-27)
- [x] **Phase 39: K8s PVC e2e + Organ-Mesh Licensing ADR** — de-stub checkpoint-persistence e2e via `pytest-kind` + procedural-vs-SurgToolLoc ADR-0001 (2/2 plans, completed 2026-06-27; CI re-verified GREEN 2026-07-09)
- [x] **Phase 40: Real DreamerV3 Integration + Sentinel Flip** — replace 5 stub functions with real `dreamerv3.Agent`; flip Phase 30 sentinel negative→positive; GPU-gated (4/4 plans, completed 2026-07-12; `dreamer-gpu` CI GREEN user-confirmed 2026-07-15)
- [x] **Phase 40.1: Close gap — DMV3-08 checkpoint_dir threading + Phase 38 advisory cleanups** (INSERTED) — thread `checkpoint_dir` into `_find_latest_checkpoint` + both call sites + CR-01 3D force-unit magnitude test + real TWO_WAY obstacle-velocity feedback + substep loop (2/2 plans, completed 2026-07-15)

**Requirements:** 13/13 closed (DMV3-07..10, TASK-06..09, FLUID-01..03, DEPLOY-01, ASET-06). All 6 phases VERIFIED `passed` (Phase 40 re-verified 2026-07-15 after the `dreamer-gpu` CI job was observed GREEN).

Full phase goals, success criteria, and plan lists: see
[`.planning/milestones/v0.6.0-ROADMAP.md`](milestones/v0.6.0-ROADMAP.md).

</details>

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

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 36. Difficulty Schema + Discrete Curriculum | v0.6.0 | 3/3 | Complete | 2026-06-25 |
| 37. Scene-Level difficulty_blocks + Env Wiring | v0.6.0 | 3/3 | Complete | 2026-06-25 |
| 38. 3D Fluid Flag (dim_3d=True) | v0.6.0 | 4/4 | Complete | 2026-06-27 |
| 39. K8s PVC e2e + Organ-Mesh Licensing ADR | v0.6.0 | 2/2 | Complete | 2026-06-27 |
| 40. Real DreamerV3 Integration + Sentinel Flip | v0.6.0 | 4/4 | Complete | 2026-07-12 |
| 40.1 DMV3-08 checkpoint_dir + Phase 38 advisories | v0.6.0 | 2/2 | Complete | 2026-07-15 |

---

*Roadmap defined: 2026-06-24 — v0.6.0 milestone initiated (Carried-Forward Debt Closure, PLANNING)*
*v0.6.0 SHIPPED 2026-07-15 — all 6 phases complete, 13/13 requirements closed, all phases VERIFIED passed.*
*Next: `/gsd-new-milestone` to plan the next milestone (v0.7.0 GUI editor depth + scene generation is the deferred candidate).*