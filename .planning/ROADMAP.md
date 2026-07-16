# Roadmap: Surg-RL

**Defined:** 2026-07-15 (v0.7.0 GUI Editor Depth & Scene Generation planning)
**Last Shipped:** v0.6.0 Carried-Forward Debt Closure — Phases 36–40.1 (SHIPPED 2026-07-15)
**Current Milestone:** v0.7.0 GUI Editor Depth & Scene Generation — Phases 41–51 (PLANNING)

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
| v0.7.0 | 🚧 PLANNING | 41–51 | TBD | — | — | — |

## v0.7.0 Phases (current milestone)

**Milestone Goal:** Deepen the PySide6 scene editor with a render/sim-decoupled viewport, multi-view/lighting/gizmos/recording, editing UX, and file/IO — fixing the three known GUI bugs (dock-panel layout reset on rerun, <10fps frame rate, immobile scene preview) — then expand scene generation (more task templates, better LLM text→scene, VLM image→scene, procedural/batch gen, interactive LLM clarifying-question flow).

**Phase numbering continues from v0.6.0 (ended at 40.1).** Build order is user-confirmed: GUI-18 → GUI-11 → GUI-12 → GUI-13 → GUI-14 → GUI-15 → GUI-16 → GUI-17 → GEN-01 → GEN-02 → GEN-03/04/05. One phase per GUI requirement (no GUI grouping against the build order); GEN-03/04/05 grouped (tightly coupled — share the GEN-02 bounded repair loop + structured-output protocol).

- [ ] **Phase 41: Dock Layout Reset & CloseEvent Teardown** - GUI-18 — fixes bug #3 (dock panels not reset on rerun) + closeEvent teardown harness
- [ ] **Phase 42: Render/Sim Decoupling & Animated Viewport** - GUI-11 — fixes bugs #1 (immobile preview) + #2 (<10fps) via SimStepWorker + RenderPollLoop
- [ ] **Phase 43: Multi-View Layout** - GUI-12 — synchronized N-view layout sharing one sim-state source
- [ ] **Phase 44: Lighting Controls** - GUI-13 — add/move/intensity/color lights, persisted + undoable
- [ ] **Phase 45: Transform Gizmos** - GUI-14 — translate/rotate/scale handles (approach resolved by a research spike)
- [ ] **Phase 46: Viewport Recording** - GUI-15 — record viewport to mp4 (new dep imageio-ffmpeg>=0.6.0)
- [ ] **Phase 47: Multi-Select & Editing UX** - GUI-16 — multi-select, copy/paste, duplicate, selection sync across tree/viewport/form
- [ ] **Phase 48: Autosave & Crash Recovery** - GUI-17 — autosave + recovery prompt + recent-files fix
- [ ] **Phase 49: Task Templates for 6 Task Types** - GEN-01 — templates for all 6 reward types with difficulty variants
- [ ] **Phase 50: LLM Text→Scene Structured Output + Bounded Repair** - GEN-02 — structured output + 1-2 repair attempts + template graceful degradation
- [ ] **Phase 51: VLM Image→Scene, Batch Generation, Clarifying Questions** - GEN-03/04/05 — VLM panel, batch sweeps, interactive clarifying-question state machine

## Phase Details

### Phase 41: Dock Layout Reset & CloseEvent Teardown

**Goal**: User can reset the editor layout to default (dock panels restore on rerun) and closing the editor mid-operation does not crash — fixes bug #3
**Depends on**: Nothing (first phase of milestone; builds on v0.6.0 baseline)
**Requirements**: GUI-18
**Success Criteria** (what must be TRUE):

  1. User clicks "Reset Layout" and the dock panels restore to the factory-default arrangement (tabification/floating/closed state included) — bug #3 closed
  2. User rearranges docks, closes the editor, and reopens it — the saved layout restores on rerun (not reset to a broken state)
  3. User closes the editor mid-LLM-call (or mid-any long-running panel operation) — the editor exits cleanly without segfault or `RuntimeError: Internal C++ object already deleted`
  4. Every dock panel has a unique `objectName` so `saveState()`/`restoreState()` round-trip correctly (not silently no-op)

**Plans:** 2 plans
Plans:
**Wave 1**

- [ ] 41-01-PLAN.md — DockStateManager + Reset Layout + update_scene in-place swap (SC#1, SC#2, SC#4)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 41-02-PLAN.md — aboutToClose teardown harness + LLMPanel.stop() + closeEvent emit (SC#3)

**UI hint**: yes

### Phase 42: Render/Sim Decoupling & Animated Viewport

**Goal**: User sees an animated scene preview (simulation steps live in the editor viewport) at >30 fps — fixes bugs #1 + #2
**Depends on**: Phase 41 (closeEvent teardown harness needed for the new SimStepWorker QThread)
**Requirements**: GUI-11
**Success Criteria** (what must be TRUE):

  1. User opens a scene in the editor and sees the preview animate (physics steps live in the viewport) — bug #1 (immobile preview) closed
  2. User observes the viewport animating at >30fps on a typical scene (not the <10fps frozen state) — bug #2 (<10fps) closed
  3. User can pause/resume the simulation preview and step it one frame at a time from the editor
  4. Render rate and sim rate are decoupled — a slow render does not slow the physics, and a fast sim does not flood the UI thread (snapshot publish capped at ~30Hz)

**Plans**: TBD
**UI hint**: yes

### Phase 43: Multi-View Layout

**Goal**: User can switch between standard views (front/side/top/perspective) in a synchronized multi-view layout sharing one sim-state source
**Depends on**: Phase 42 (needs a responsive decoupled viewport to render multiple views)
**Requirements**: GUI-12
**Success Criteria** (what must be TRUE):

  1. User selects a standard view preset (front/side/top/perspective) and the viewport camera switches to that view
  2. User opens a multi-view (quad) layout and sees N viewports rendering the same sim state from different angles, updated in sync
  3. Editing/stepping the sim in one view is reflected immediately in all views (single sim-state source, not N independent sims)
  4. On macOS, the `_renderer_available=False` short-circuit holds with N render calls per frame (no CGL/EGL re-probe storm) — verified during planning

**Plans**: TBD
**UI hint**: yes

### Phase 44: Lighting Controls

**Goal**: User can adjust scene lighting (add/move/intensity/color lights) from the editor, with edits persisted to SceneDefinition and undoable
**Depends on**: Phase 43 (render API extensions for camera/light params established)
**Requirements**: GUI-13
**Success Criteria** (what must be TRUE):

  1. User adds a new light, moves it, adjusts intensity and color — the viewport updates in real time
  2. User undoes a light edit — the light reverts in both the tree/form and the viewport render
  3. User saves the scene and reloads it — the light edits persist in the SceneDefinition JSON (not lost)
  4. Light edits round-trip through SceneDefinition + SceneUndoStack (not poked into simulator attrs directly) — undo/save/revert do not silently corrupt

**Plans**: TBD
**UI hint**: yes

### Phase 45: Transform Gizmos

**Goal**: User can transform selected objects with on-screen gizmos (translate/rotate/scale) by dragging handles
**Depends on**: Phase 44 (needs render API + selection/picking infrastructure)
**Requirements**: GUI-14
**Success Criteria** (what must be TRUE):

  1. User selects an object and sees a translate gizmo; dragging an axis handle moves the object along that axis
  2. User switches to rotate mode and drags a rotation handle — the object rotates around the intended axis
  3. User transforms an object and the edit is written to SceneDefinition first (undoable, saveable, revert-able) — not poked into simulator attrs
  4. Gizmo handles track the camera correctly on a real cutting/fluid scene — the chosen rendering approach (2D QPainter overlay vs 3D pipeline) is validated by a working spike before committing

**Plans**: TBD (flag for `/gsd-plan-phase --research-phase 45` — the gizmo rendering approach is an unresolved cross-researcher disagreement needing a working spike before committing)
**UI hint**: yes

### Phase 46: Viewport Recording

**Goal**: User can record the viewport to an mp4 video from within the editor
**Depends on**: Phase 42 (decoupled render loop to capture frames from; closeEvent flush harness from Phase 41)
**Requirements**: GUI-15
**Success Criteria** (what must be TRUE):

  1. User starts recording from a menu/button, performs operations in the viewport, stops recording — an mp4 file is written to disk
  2. The recorded mp4 plays back at the correct frame rate (not stuttering or dropped-frame corrupt)
  3. Recording does not freeze the editor UI (encode happens off the main thread on a RecorderWorker QThread with a bounded queue)
  4. Closing the editor mid-recording flushes the file cleanly (no corrupt/truncated mp4)

**Plans**: TBD
**UI hint**: yes

### Phase 47: Multi-Select & Editing UX

**Goal**: User can multi-select, copy/paste, and duplicate scene nodes with keyboard shortcuts, with selection synced across tree, viewport, and form
**Depends on**: Phase 45 (needs gizmo pick infrastructure for viewport→tree selection sync)
**Requirements**: GUI-16
**Success Criteria** (what must be TRUE):

  1. User multi-selects nodes in the tree (shift/ctrl-click) and the selection is highlighted in the viewport (gizmo reflects the active selection)
  2. User presses Ctrl+C/Ctrl+V to copy/paste a node and Ctrl+D to duplicate — the new node appears in tree, viewport, and form
  3. User selects an object in the viewport (click) and the tree + form sync to that selection
  4. Keyboard shortcuts (Ctrl+C/V, Del/X, Ctrl+D) work as expected without conflicting with existing editor shortcuts

**Plans**: TBD
**UI hint**: yes

### Phase 48: Autosave & Crash Recovery

**Goal**: User can recover unsaved work via autosave + a crash-recovery prompt on launch, and the recent-files list works correctly
**Depends on**: Phase 41 (closeEvent teardown harness for the autosave worker)
**Requirements**: GUI-17
**Success Criteria** (what must be TRUE):

  1. User edits a scene, waits (or triggers autosave), and force-quits — on next launch a recovery prompt offers the unsaved work
  2. The recent-files list shows the last N opened files (deduplicated, capped at 10-20) and opening one works — the duplicated `_refresh_recent_menu` latent bug is fixed
  3. Autosave writes to a recovery location on a timer interval (60-120s) only when the scene is dirty (no idle writes)
  4. Closing the editor cleanly does not trigger a false recovery prompt on next launch

**Plans**: TBD
**UI hint**: yes

### Phase 49: Task Templates for 6 Task Types

**Goal**: User can generate scenes from task templates covering all 6 task types with easy/medium/hard difficulty variants
**Depends on**: Phase 48 (editor stable; scene generation begins after GUI depth)
**Requirements**: GEN-01
**Success Criteria** (what must be TRUE):

  1. User invokes template generation for each of the 6 task types (suturing/knot-tying/needle-passing/grasping/cutting/dissection) and gets a valid, loadable SceneDefinition
  2. Each task type template has easy/medium/hard difficulty variants that produce meaningfully different scenes (not byte-identical)
  3. Generated scenes pass SceneDefinition validation and load into the simulator without errors
  4. Templates serve as the graceful-degradation fallback for the GEN-02 repair loop (a template exists for every reward type)

**Plans**: TBD

### Phase 50: LLM Text→Scene Structured Output + Bounded Repair

**Goal**: User can generate a scene from a text prompt with structured output + automatic validation/repair, degrading gracefully to a template if repair fails
**Depends on**: Phase 49 (templates are the graceful-degradation fallback)
**Requirements**: GEN-02
**Success Criteria** (what must be TRUE):

  1. User enters a text prompt and gets a valid SceneDefinition back (structured output via `json_schema` or tool-calling where supported)
  2. When the LLM returns malformed/invalid JSON, the repair loop feeds the `ValidationError` back as model-readable prose and retries — bounded to 1 attempt default, max 2
  3. When repair fails after the bound, the user gets a template scene (graceful degradation), not an error/crash
  4. The structured-output protocol + repair loop are built to be reused by GEN-03 (VLM) and GEN-05 (clarifying questions) — not a single-purpose path

**Plans**: TBD
**UI hint**: yes

### Phase 51: VLM Image→Scene, Batch Generation, Clarifying Questions

**Goal**: User can generate a scene from an image (VLM), batch-generate parameterized scene sets, and answer clarifying questions interactively before the LLM generates a scene
**Depends on**: Phase 50 (reuses GEN-02 repair loop + structured-output protocol); Phase 49 (GEN-04 reuses GEN-01 templates)
**Requirements**: GEN-03, GEN-04, GEN-05
**Success Criteria** (what must be TRUE):

  1. User uploads an image (endoscopic/sim screenshot) in the editor VLM panel or via CLI `--image` and gets a valid SceneDefinition back (image→scene)
  2. User runs a batch generation spec (difficulty/instrument/organ sweeps) and gets N valid SceneDefinition files for a curriculum/benchmark dataset
  3. User answers 1-3 clarifying questions in the GUI chat panel (or CLI stdin) before the LLM generates the scene — the state machine transitions IDLE→AWAITING_QUESTIONS→AWAITING_ANSWERS→GENERATING→DONE cleanly (no double-spawn race)
  4. VLM payload is downscaled (≤1024px JPEG q85) and non-existent mesh paths are sanitized to OBJ fallback (no 404 at sim load)
  5. GEN-03/GEN-05 reuse the GEN-02 structured-output protocol (OpenAI Structured Outputs with freeform fallback for Anthropic/Ollama)

**Plans**: TBD (note: OpenAI Structured Outputs vs the 62-class Pydantic schema needs validation — `strict: True` constraints, max schema depth; the Anthropic tool-use structured-output path needs a spike)
**UI hint**: yes

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

**Execution Order:**
Phases execute in numeric order: 41 → 42 → 43 → ... → 51

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 41. Dock Layout Reset & CloseEvent Teardown | v0.7.0 | 0/TBD | Not started | - |
| 42. Render/Sim Decoupling & Animated Viewport | v0.7.0 | 0/TBD | Not started | - |
| 43. Multi-View Layout | v0.7.0 | 0/TBD | Not started | - |
| 44. Lighting Controls | v0.7.0 | 0/TBD | Not started | - |
| 45. Transform Gizmos | v0.7.0 | 0/TBD | Not started | - |
| 46. Viewport Recording | v0.7.0 | 0/TBD | Not started | - |
| 47. Multi-Select & Editing UX | v0.7.0 | 0/TBD | Not started | - |
| 48. Autosave & Crash Recovery | v0.7.0 | 0/TBD | Not started | - |
| 49. Task Templates for 6 Task Types | v0.7.0 | 0/TBD | Not started | - |
| 50. LLM Text→Scene Structured Output + Bounded Repair | v0.7.0 | 0/TBD | Not started | - |
| 51. VLM Image→Scene, Batch Generation, Clarifying Questions | v0.7.0 | 0/TBD | Not started | - |
| 36. Difficulty Schema + Discrete Curriculum | v0.6.0 | 3/3 | Complete | 2026-06-25 |
| 37. Scene-Level difficulty_blocks + Env Wiring | v0.6.0 | 3/3 | Complete | 2026-06-25 |
| 38. 3D Fluid Flag (dim_3d=True) | v0.6.0 | 4/4 | Complete | 2026-06-27 |
| 39. K8s PVC e2e + Organ-Mesh Licensing ADR | v0.6.0 | 2/2 | Complete | 2026-06-27 |
| 40. Real DreamerV3 Integration + Sentinel Flip | v0.6.0 | 4/4 | Complete | 2026-07-12 |
| 40.1 DMV3-08 checkpoint_dir + Phase 38 advisories | v0.6.0 | 2/2 | Complete | 2026-07-15 |

---

*Roadmap defined: 2026-07-15 — v0.7.0 milestone initiated (GUI Editor Depth & Scene Generation, PLANNING)*
*v0.6.0 SHIPPED 2026-07-15 — all 6 phases complete, 13/13 requirements closed, all phases VERIFIED passed.*
*Build order: GUI-18 → GUI-11 → GUI-12 → GUI-13 → GUI-14 → GUI-15 → GUI-16 → GUI-17 → GEN-01 → GEN-02 → GEN-03/04/05*
