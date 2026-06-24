# Roadmap: Surg-RL

**Defined:** 2026-06-18 (v0.5.0 Scene Editor & UX Polish planning)
**Last Shipped:** v0.5.0 Scene Editor & UX Polish — Phases 31–35 (SHIPPED 2026-06-24)
**Next Milestone:** Not yet defined — run `/gsd-new-milestone` to start the next cycle.

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

## Coverage

- v0.5.0 requirements: 26 total (10 GUI + 5 DEMO + 5 DOC + 6 DEBT) — 26/26 mapped, all delivered
  - GUI-01..10 → Phase 33 · DEMO-01..05 → Phase 32 · DOC-01..05 → Phase 34 · DEBT-01..05 → Phase 31 · DEBT-06 → Phase 35

## Next Steps

1. `/gsd-new-milestone` — start the next milestone (questioning → research → requirements → roadmap)
2. Phase numbering continues from 36 (never restart at 01)

---

*Roadmap defined: 2026-06-18 — v0.5.0 milestone initiated (Scene Editor & UX Polish, PLANNING)*
*Last updated: 2026-06-24 — v0.5.0 SHIPPED and archived to milestones/v0.5.0-ROADMAP.md*