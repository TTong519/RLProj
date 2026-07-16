---
gsd_state_version: 1.0
milestone: v0.7.0
milestone_name: Phases
current_phase: 41
current_phase_name: Dock Layout Reset & CloseEvent Teardown
status: executing
stopped_at: Completed 41-01-PLAN.md
last_updated: "2026-07-16T01:24:41.307Z"
last_activity: 2026-07-15
last_activity_desc: Phase 41 execution started
progress:
  total_phases: 11
  completed_phases: 0
  total_plans: 2
  completed_plans: 1
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-15 — v0.7.0 milestone started)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.
**Current focus:** Phase 41 — Dock Layout Reset & CloseEvent Teardown

> **Note:** v0.6.0 SHIPPED 2026-07-15 (verified closeout, 6 phases / 18 plans / 13 requirements closed, test baseline 1,513 passing). v0.7.0 roadmap created 2026-07-15 — 11 phases following the user-confirmed build order GUI-18 → GUI-11 → GUI-12 → GUI-13 → GUI-14 → GUI-15 → GUI-16 → GUI-17 → GEN-01 → GEN-02 → GEN-03/04/05. Three known GUI bugs fold into the relevant phases (bug #3 → Phase 41; bugs #1/#2 → Phase 42). Phase 45 (gizmos) flagged for `/gsd-plan-phase --research-phase 45` (2D QPainter overlay vs 3D pipeline disagreement). Phase 51 flagged for OpenAI Structured Outputs + Anthropic tool-use spike.

## Current Position

Phase: 41 (Dock Layout Reset & CloseEvent Teardown) — EXECUTING
Plan: 2 of 2
Status: Ready to execute
Last activity: 2026-07-15 — Phase 41 execution started

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**

- Total plans completed: 133 across v0.1.0–v0.6.0 (12 + 19 + 18 + 1 + 9 + 21 + 4 + 3 + 22 + 18)
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
| v0.5.0 | 31–35 | 22 | 1,325 |
| v0.6.0 | 36–40.1 | 18 | 1,513 |
| v0.7.0 | 41–51 | TBD | — |

**Recent Trend:**

- Last 5 milestones: 21 → 4 → 3 → 22 → 18 plans
- Trend: Stable — v0.7.0 is a depth milestone on a shipped app (GUI + scene gen); single new dep `imageio-ffmpeg>=0.6.0`

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 41 P01 | 31m | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Architecture Decisions. Recent decisions affecting current work:

- [v0.7.0 roadmap]: Build order is user-confirmed and NON-NEGOTIABLE — GUI-18 → GUI-11 → GUI-12 → GUI-13 → GUI-14 → GUI-15 → GUI-16 → GUI-17 → GEN-01 → GEN-02 → GEN-03/04/05. GUI-11 decoupling MUST precede GUI-12 multi-view (else multi-view forces render rework).
- [v0.7.0 roadmap]: One phase per GUI requirement (no GUI grouping against the build order). GEN-03/04/05 grouped in Phase 51 (tightly coupled — share GEN-02 repair loop + structured-output protocol).
- [v0.7.0 research]: Bugs #1 (immobile preview) + #2 (<10fps) share a SINGLE root cause (render/sim coupling in `_tick`) — both fixed by GUI-11 decoupling. Bug #3 (dock-not-reset-on-rerun) is a SEPARATE root cause (QMainWindow saveState/restoreState + widget recreation) — fixed by GUI-18.
- [v0.7.0 research]: Net new pip deps for the whole milestone = exactly ONE (`imageio-ffmpeg>=0.6.0`, added to `[gui]` extra for GUI-15 recording). Everything else is code on existing deps.
- [v0.7.0 research]: GUI stays in the stock interpreter (no `mjpython` re-exec — regresses the v0.5.0 main-thread hang fix). Custom `ViewportCanvas(QWidget)` painted from numpy-rasterized `QPixmap` (no live OpenGL context on macOS).
- [v0.7.0 research]: Persistent edits (lights, gizmos, transforms) MUST round-trip through `SceneDefinition` + `SceneUndoStack` (Pitfall 7) — NOT poke simulator attrs directly, or undo/save/revert silently corrupt.
- [v0.7.0 research]: `closeEvent` must gain a teardown harness — every long-running panel gets a `stop()` (cooperative cancel + `thread.quit()` + `thread.wait(3000)`); `EditorWindow.closeEvent` calls all `stop()`s BEFORE `super().closeEvent()` (Pitfall 3).
- [v0.6.0 shipped]: Real DreamerV3 integration complete; `dreamer-gpu` CI GREEN on `ubuntu-latest-4-core-gpu` (2026-07-15). All v0.4.0+v0.4.2+v0.5.0 baseline passes unchanged (1,513 passing).
- [Phase ?]: D-01: Factory-default dock layout captured at first showEvent via QByteArray (primary) + code-level rebuild (fallback), NOT persisted to QSettings
- [Phase ?]: D-06: In-place update_scene on ViewportPanel + SceneTreeView (no widget recreation) — bug #3 root cause fix; PropertyForm NOT folded in this phase

### Pending Todos

- None. Roadmap created; next: `/gsd-plan-phase 41` (Dock Layout Reset & CloseEvent Teardown — GUI-18, cheapest independent high-trust win, fixes bug #3).

### Blockers/Concerns

- **Phase 45 (Transform Gizmos):** gizmo rendering approach (2D `QPainter` overlay vs 3D pipeline) is an unresolved cross-researcher disagreement — flag for `/gsd-plan-phase --research-phase 45` with a working spike on a real cutting/fluid scene before committing. Affects which package owns gizmo rendering (`editor/gizmo_overlay.py` vs `simulators/*`) and whether `render()` gains gizmo kwargs.
- **Phase 51 (GEN-03/GEN-05):** OpenAI Structured Outputs vs the 62-class `SceneDefinition` Pydantic schema needs validation (`strict: True` constraints, max schema depth, all-fields-required); the Anthropic tool-use structured-output path is a different code path and needs a spike. Batch-gen reproducibility: `temperature=0` does NOT guarantee byte-identical output — document residual nondeterminism, don't claim reproducibility.
- **Phase 43 (Multi-View):** macOS `_renderer_available=False` short-circuit must be verified to hold with N render calls per frame (one GL context, many cameras — NOT many GL contexts). PyBullet multi-view at 4 views × ~50-120ms/render ≈ 8fps — mitigation (stagger views / lower per-view res) needs validation during Phase 43 planning.
- **Phase 42 (Render/Sim Decoupling):** the keystone — naive fixes (inject `step()` into `_tick`, or add a second `QTimer.singleShot`) double the bug. Must use ONE render timer on main thread + sim step loop on `QThread` worker with fixed-step accumulator; render-poll reads latest snapshot only.

### Roadmap Evolution

- v0.7.0 roadmap created 2026-07-15: 11 phases (41–51), 13/13 requirements mapped, 0 unmapped.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| TASK-02 | 3-difficulty-levels (easy/medium/hard presets) | **Closed in v0.4.2** | v0.4.1 |
| DreamerV3 | Real-subprocess E2E test | **Closed in v0.4.2** | v0.4.1 |

### Acknowledged at v0.6.0 close (2026-07-15) — carried forward (out of v0.6.0 scope, not blockers)

| Category | Item | Status | Note |
|----------|------|--------|------|
| verification | Phase 09 ros2-bridge `09-VERIFICATION.md` gaps_found | Acknowledged | Older v0.3.0 verification debt; out of v0.6.0's 13 requirements |
| uat | Phase 24 DreamerV3 `24-UAT.md` partial | Effectively closed | GPU-gated; closed by the Phase 40 sentinel flip + `dreamer-gpu` CI GREEN (2026-07-15); stale `partial` marker left as-is |
| quick_task | `demo-rework` (20260617) | Stale marker | Work was complete at v0.5.0 close |

### Carried forward (unchanged, out of v0.6.0 scope)

| Category | Item | Status |
|----------|------|--------|
| Phase 17 | Per-tet generation counter for degenerate tets | Deferred (v0.3.2) |
| v2 | TASK-05 task chains (grasp→cut→suture) | v2 |
| v2 | MARL-05 RLlib centralized critic | v2 |
| v2 | DMV3-06 DreamerV3 offline training from demos | v2 |
| v2 | GUI-19 true 3D scene-graph viewport (Qt3D) | v2 |
| v2 | GUI-20 surface/vertex snapping | v2 (grid-snap may fold into v0.7.0 if cheap) |
| v2 | GEN-06 local VLM inference | v2 (hosted-API is v0.7.0 target) |
| v2 | GEN-07 SurgVLM-style fine-tuning | v2 (out of charter) |
| Process | REQUIREMENTS.md BENCH-02..05 body checkboxes remain `[ ]` | Acknowledged (v0.4.0) |
| Testing | Linux-only ROS2 subscriber e2e tests | Acknowledged (v0.3.1) |

## Session Continuity

Last session: 2026-07-16T01:24:41.295Z
Stopped at: Completed 41-01-PLAN.md
Resume file: None

*Updated: 2026-07-15 — v0.7.0 roadmap created. 11 phases (41–51), 13/13 requirements mapped (0 unmapped). Next: `/gsd-plan-phase 41`.*

## Operator Next Steps

- Plan Phase 41 with `/gsd-plan-phase 41` (Dock Layout Reset & CloseEvent Teardown — GUI-18, fixes bug #3, cheapest independent high-trust win, research-endorsed to lead).
- Phase 45 (gizmos) will need `/gsd-plan-phase --research-phase 45` (gizmo rendering approach spike).
- Phase 51 (GEN-03/04/05) will need validation of OpenAI Structured Outputs against the 62-class schema + Anthropic tool-use spike.
