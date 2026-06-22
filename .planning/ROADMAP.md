# Roadmap: Surg-RL

**Defined:** 2026-06-18 (v0.5.0 Scene Editor & UX Polish planning)
**Next Milestone:** v0.5.0 — Phases 31–35 (PLANNING)
**Previous Milestone:** v0.4.2 Audit Leftovers — Phases 29–30 (SHIPPED 2026-06-14)

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
| v0.5.0 | 🚧 PLANNING | 31–35 | TBD | TBD | — | — |

## Milestone v0.5.0 Overview

**Goal:** Ship a full PySide6 scene editor (3D viewport + tree/form editor + LLM-prompt-to-JSON), polish 3 surgical task demos (suturing, knot-tying, needle-passing) with consistent narration and walkthroughs, refresh user-facing docs (README, CONTRIBUTING, CHANGELOG), and interleave tech debt cleanup (421 ruff, HARD fixture test, fluid step hook, cut cooldown test, Dockerfile.ros2 amd64, PhiFlow multi-obstacle union() workaround).

**Marquée feature:** PySide6 GUI scene editor (Phase 33). Demos and docs support adoption; tech debt is swept so the editor phase starts on a clean baseline.

**Phase ordering rationale** (from `research/SUMMARY-v0.5.0.md`):

- **Phase 31 first** — Ruff-clean baseline + mjpython helper + `[gui]` extra + `surg-rl-gui` console script must exist before the editor phase. Closes 5 quick-win tech-debt items.
- **Phase 32 second** — Demos are independent of Qt; produce artifacts Phase 34 needs (`_common.py` resolver, narration transcripts, optional GIFs).
- **Phase 33 third (marquée)** — Depends on Phase 31's `[gui]` extra + console script + mjpython helper, and Phase 32's `_common.py` resolver. Largest single contribution; naturally sits in the middle.
- **Phase 34 fourth** — Needs Phase 33's screenshots and Phase 32's transcripts; sequential artifacts.
- **Phase 35 last** — Only needs Phase 31's clean baseline; runs in parallel with Phases 32–34 via worktrees per `CLAUDE.md` rules.

## Phases

- [x] **Phase 31: Tech Debt Foundation** - Sweep 5 quick-win debt items (421 ruff in `src/surg_rl/dreamer/`, Dockerfile.ros2 `$TARGETARCH`, fluid step hook, cut cooldown test, PhiFlow union doc); set up `[gui]` extra + `surg-rl-gui` console script + mjpython re-exec helper so Phase 33 has scaffolding
- [x] **Phase 32: Demo Suite Polish** - Refactor suturing demo + create knot-tying + needle-passing demos with shared `demos/_common.py` (banner, scene resolver) + `NARRATION_TEMPLATE.md` + 3 per-demo regression tests (completed 2026-06-19)
- [x] **Phase 33: PySide6 Scene Editor** - Marquée phase: render bridge + schema walker + tree/form + viewport + undo/redo + LLM panel + shell + smoke tests (all 10 GUI requirements) (completed 2026-06-21)
- [ ] **Phase 34: User-Facing Docs Refresh** - Rewrite README + overhaul CONTRIBUTING + CHANGELOG v0.5.0 entry + embed 3 demo GIFs (from Phase 32) + 3 GUI screenshots (from Phase 33)
- [ ] **Phase 35: Advanced Tech Debt** - HARD-fixture `SurgicalEnv`-construction integration test + `CurriculumStageConfig.difficulty` normalization + organ mesh licensing research spike

## Phase Details

### Phase 31: Tech Debt Foundation

**Goal**: Retiring 5 quick-win tech-debt items (421 ruff, Dockerfile.ros2 amd64, fluid step hook, cut cooldown test, PhiFlow union doc) plus scaffolding Phase 33 (editor) needs: `[gui]` extra in pyproject.toml, `surg-rl-gui` console script entry point, mjpython re-exec helper, and the `editor/__init__.py` `LazyImport` + `HAS_GUI` sentinel skeleton.
**Depends on**: Nothing (first v0.5.0 phase)
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, DEBT-05
**Success Criteria** (what must be TRUE):

  1. `ruff check src/surg_rl/dreamer/` exits 0 (no issues) and the existing 1,134-test baseline still passes with PySide6 unimported
  2. `Dockerfile.ros2` uses `$TARGETARCH` instead of hardcoded `amd64`; `docker buildx build --platform linux/amd64,linux/arm64 .` completes without error
  3. `BaseSimulator.fluid_step(dt)` exists as a no-op default; MuJoCo and PyBullet simulators override with their existing fluid step logic; existing fluid tests still pass
  4. `tests/test_cutting_cooldown.py` asserts the 500ms cut cooldown (parametrized over both backends) using a mockable time source, and the test passes
  5. PhiFlow multi-obstacle `union()` workaround is documented in `src/surg_rl/dynamics/fluids.py` as a docstring with example + upstream issue link, and the existing fluid obstacle test passes; the `[gui]` extra is installable via `pip install -e ".[gui]"` and `surg-rl-gui --help` exits 0 (with install hint if PySide6 missing)

**Plans**: TBD

### Phase 32: Demo Suite Polish

**Goal**: Three task demos (suturing + knot-tying + needle-passing) share a common narration script (`demos/_common.py` with Rich banner, scene resolver, regression-test contract), follow the `NARRATION_TEMPLATE.md` 5-stage structure (Setup → Action → Critical Moment → Outcome → Takeaway), and each has a per-demo regression test that runs `--headless --steps 0` and asserts exit 0.
**Depends on**: Phase 31
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05
**Success Criteria** (what must be TRUE):

  1. User can run `python demos/suturing_demo.py --headless --steps 0` and see a consistent Rich banner + scene info + 1168-test-clean suturing walkthrough (matching the 2026-06-17 suturing demo style)
  2. User can run `python demos/knot_tying_demo.py --headless --steps 0` and see the same consistent shell; the demo loads `tests/fixtures/scenes/knot_tying.json` and narrates 3–4 steps (needle insertion, knot formation, knot tightening) using the `KNOT_TIER` instrument
  3. User can run `python demos/needle_passing_demo.py --headless --steps 0` and see the same consistent shell; the demo loads the needle-passing scene fixture and narrates 3–4 steps (needle pick-up, target approach, pass-through, withdrawal) using a dual-arm `MultiAgentConfig`
  4. `tests/test_demos.py` contains 3 regression tests (one per demo); each spawns the demo as a subprocess with `--headless --steps 0`, asserts exit 0 and an expected banner substring; all 3 tests pass on Linux and macOS CI
  5. `demos/NARRATION_TEMPLATE.md` documents the shared 5-stage narration structure (Setup / Action / Critical Moment / Outcome / Takeaway) with vocabulary constraints, and is committed BEFORE any new demo is refactored

**Plans**: 3 plans

Plans:

- [x] 32-01-PLAN.md — NARRATION_TEMPLATE.md (DEMO-05) + demos/_common.py (shared banner/scene/narration helpers) + refactor demos/demo.py → demos/suturing_demo.py (DEMO-01)
- [x] 32-02-PLAN.md — tests/fixtures/scenes/knot_tying.json (byte-identical fixture copy) + demos/knot_tying_demo.py (DEMO-02)
- [x] 32-03-PLAN.md — scenes/needle_passing.json (dual-arm MultiAgentConfig) + demos/needle_passing_demo.py (DEMO-03) + tests/test_demos.py (6 regression tests for demos + template + fixtures, DEMO-04)

### Phase 33: PySide6 Scene Editor

**Goal**: A full PySide6 scene editor (the marquee feature) launches via `surg-rl-gui [scene.json]` and provides: 3D viewport (orbit/pan/zoom, 20 Hz throttle) backed by `sim.render_to_numpy()`; tree view of scene elements with right-click context menu (add/remove/duplicate), drag-reorder, validation icons; schema-driven property form via `SchemaWalker` + `FieldRenderer` registry (no if/elif rot); LLM-prompt-to-JSON panel via background QThread; undo/redo (Cmd+Z / Cmd+Shift+Z) scoped per scene; standard workspace shell with File menu + drag-drop; all API keys and error messages passed through a `safe_error_message()` regex redactor before reaching logs/UI.
**Depends on**: Phase 31 (`[gui]` extra, `surg-rl-gui` console script, mjpython helper, `editor/__init__.py` skeleton), Phase 32 (`demos/_common.py` scene resolver)
**Requirements**: GUI-01, GUI-02, GUI-03, GUI-04, GUI-05, GUI-06, GUI-07, GUI-08, GUI-09, GUI-10
**Success Criteria** (what must be TRUE):

  1. User can run `surg-rl-gui [scene.json]` and see a window populated with the viewport, tree, form, and LLM panel (or receives a clear install hint if `[gui]` is not installed, exiting non-zero)
  2. User can open a `.planning/scenes/*.json` file, edit a field via the form, save with Cmd+S, reload the file, and the edited value persists (Pydantic v2 round-trip via `scene_to_jsonable`/`scene_from_jsonable` preserves all 63 schema classes including `_FloatMixin` `DifficultyLevel`)
  3. User sees a 3D viewport rendering the loaded scene at ≥15 FPS, with mouse orbit/pan/zoom and a camera-reset keybinding
  4. User can right-click a tree node to add/remove/duplicate, drag-reorder within parents, and see red/green validation icons; the LLM panel accepts a text prompt, runs `TextParser.parse_sync()` on a background QThread, and shows a JSON preview the user can accept (writes to draft scene) or reject
  5. User can undo/redo any property change (Cmd+Z / Cmd+Shift+Z) within the session, and the 14-subcommand `surg-rl` CLI still works without importing PySide6 even when `[gui]` is installed

**Plans**: 7/7 plans complete
**UI hint**: yes

Plans:

- [x] 33-01-PLAN.md — EditorWindow (QMainWindow) + 4-pane QDockWidget layout + safe_error_message redactor + EditorSettings QSettings wrapper + drag-drop + status bar
- [x] 33-02-PLAN.md — SchemaWalker (recursive over 62 classes) + FieldRenderer widget-factory registry (vec3-spinbox, enum-combobox, file-picker, color-picker, range-slider)
- [x] 33-03-PLAN.md — ViewportPanel (20 Hz frame loop, mouse orbit/pan/zoom, R-key camera reset) + mujoco_simulator.py refactor to use shared _is_running_under_mjpython helper
- [x] 33-04-PLAN.md — SceneTreeView (right-click context menu Add/Remove/Duplicate, drag-reorder, validation icons) + PropertyForm (QFormLayout with FieldRenderer widgets, 150 ms debounced validation)
- [x] 33-05-PLAN.md — LLMPanel (QThread TextParserWorker calling TextParser.parse_sync) + SceneUndoStack (deep-copy snapshots, 100-level cap) + file operations (New/Open/Save/Save As) + tests/gui/ smoke test capturing 3 screenshots
- [x] 33-06-PLAN.md — [GAP CLOSURE] Fix --headless demo scene listing (4-level path) + guard mjpython re-exec against crash/loop (shutil.which + _SURG_RL_GUI_REEXECED env var)
- [x] 33-07-PLAN.md — [GAP CLOSURE] Harden viewport render loop (_running flag + __del__ guard + simulator.close try/except) + wire closeEvent to stop viewport + launch smoke test

### Phase 34: User-Facing Docs Refresh

**Goal**: README, CONTRIBUTING, and CHANGELOG are rewritten to reflect v0.5.0 features (GUI editor, 2 new demos, docs refresh, 6 tech debt items fixed); 3 demo GIFs (suturing + knot-tying + needle-passing, ~30s each) captured during Phase 32 are embedded in the README walkthrough sections; 3 GUI screenshots (viewport + tree/form + LLM panel) captured during Phase 33 are embedded in the README.
**Depends on**: Phase 32 (demo GIFs), Phase 33 (GUI screenshots)
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05
**Success Criteria** (what must be TRUE):

  1. README.md is rewritten with a project banner, 60-second quickstart, 3 demo walkthrough sections each containing an embedded GIF, a GUI editor section with a launch instruction (`pip install '.[gui]'` → `surg-rl-gui`) and at least one embedded screenshot, install instructions for core + `[gui]` + `[marl]` + `[dreamer]` extras, and links to CONTRIBUTING + CHANGELOG
  2. CONTRIBUTING.md is overhauled with dev setup (`pip install -e ".[dev,gui]"`), branch / PR workflow, the GSD workflow overview (`/gsd-discuss-phase` → `/gsd-plan-phase` → `/gsd-execute-phase`), lint/type/test commands, and an optional-dep matrix
  3. CHANGELOG.md gains a `[0.5.0]` entry in Keep-a-Changelog 1.1.0 format with sections for Added (GUI editor, 2 new demos, docs refresh), Changed (demo narration refactor), and Fixed (6 tech debt items per the DEBT category)
  4. Three demo GIFs exist at `docs/demos/{suturing,knot_tying,needle_passing}.gif`, each ~30s, captured during Phase 32, and embedded in the README walkthrough sections
  5. Three GUI screenshots exist at `docs/gui/{viewport,tree_form,llm_panel}.png`, captured during Phase 33 via `QWidget.grab()` (no external screenshot tool), and embedded in the README

**Plans**: TBD

### Phase 35: Advanced Tech Debt

**Goal**: Close the medium-priority deferred items from v0.4.2 closeout: an end-to-end `SurgicalEnv`-construction integration test for the HARD-fixture suturing scene (Phase 29 code review WR-02), `CurriculumStageConfig.difficulty` normalization at env-construction (Phase 29 code review WR-03), K8s PVC e2e scaffolding (skipped body), and an organ mesh licensing research spike.
**Depends on**: Phase 31 (clean baseline; can run in parallel with Phases 32–34 via worktrees)
**Requirements**: DEBT-06
**Success Criteria** (what must be TRUE):

  1. `tests/integration/test_suturing_hard_env_construction.py` loads `tests/fixtures/scenes/suturing_difficulty_hard.json`, constructs a `SurgicalEnv`, calls `reset()`, and asserts no exception is raised
  2. `CurriculumStageConfig.difficulty` is normalized to `float` at env-construction in `SurgicalEnv._setup_rewards()` (the float-mixin enum path now resolves to a scalar before the reward is built); existing curriculum tests still pass
  3. `tests/k8s/test_pvc_e2e.py` is committed with a `[k8s]` pytest marker and a `kind`-cluster skip; the test body is stubbed with a TODO and a deferred-to-v0.6.0 rationale
  4. `docs/research/organ-mesh-licensing.md` documents candidate sources (surgtoolloc, MakeHuman, BodyParts3D) and the licensing constraints of each, deferring the license decision to v0.6.0
  5. The Phase 29 code review WR-02 and WR-03 deferred items are explicitly marked as "Closed in v0.5.0" in `STATE.md`

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 31. Tech Debt Foundation | 4/4 | Complete | 2026-06-18 |
| 32. Demo Suite Polish | 3/3 | Complete    | 2026-06-19 |
| 33. PySide6 Scene Editor | 7/7 | Complete   | 2026-06-21 |
| 34. User-Facing Docs Refresh | 4/4 | Complete | 2026-06-21 |
| 35. Advanced Tech Debt | 0/TBD | Not started | - |

## Coverage

- v1 requirements: 26 total (10 GUI + 5 DEMO + 5 DOC + 6 DEBT)
- Mapped to phases: 26/26 ✓
  - GUI-01..10 → Phase 33
  - DEMO-01..05 → Phase 32
  - DOC-01..05 → Phase 34
  - DEBT-01..05 → Phase 31
  - DEBT-06 → Phase 35
- Unmapped: 0

## Next Steps

1. `/gsd-plan-phase 31` — begin Phase 31 (Tech Debt Foundation)
2. Phase 31 establishes the clean baseline + editor scaffolding before Phase 32 (demos) and Phase 33 (editor) can start
3. Phase 32 can run in parallel with Phase 35 (Advanced Tech Debt) via worktrees after Phase 31 completes
4. Phase 33 (marquée) runs after Phase 32 (depends on `_common.py` resolver); Phase 34 runs after both Phase 32 and Phase 33 (consumes their artifacts)

---

*Roadmap defined: 2026-06-18 — v0.5.0 milestone initiated (Scene Editor & UX Polish, PLANNING)*
*Last updated: 2026-06-18 after v0.5.0 roadmap drafting*
