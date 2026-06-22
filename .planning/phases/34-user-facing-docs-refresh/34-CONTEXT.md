---
gsd_context_version: 1.0
phase: 34
phase_name: user-facing-docs-refresh
gathered: 2026-06-21
status: Ready for planning
source: Roadmap + prior phase artifacts
---

# Phase 34: User-Facing Docs Refresh - Context

## Phase Boundary

This phase rewrites the user-facing documentation for the v0.5.0 release.
It consumes the artifacts produced by Phase 32 (three polished surgical demos with
shared narration conventions) and Phase 33 (PySide6 GUI scene editor with
headless smoke-test screenshots). The output is a refreshed README,
CONTRIBUTING, and CHANGELOG plus embedded demo GIFs and GUI screenshots.

**What this phase delivers:**
- A rewritten `README.md` at repo root with a project banner, 60-second quickstart,
  three demo walkthrough sections (each with an embedded GIF), a GUI editor section
  with a screenshot, install instructions for all extras, and links to CONTRIBUTING + CHANGELOG.
- An overhauled `CONTRIBUTING.md` with dev setup, branch/PR workflow, GSD workflow overview,
  lint/type/test commands, and an optional-dependency matrix.
- A `[0.5.0]` entry in `CHANGELOG.md` in Keep-a-Changelog 1.1.0 format.
- Three ~30s demo GIFs at `docs/demos/{suturing,knot_tying,needle_passing}.gif`.
- Three GUI screenshots at `docs/gui/{viewport,tree_form,llm_panel}.png`.

**What this phase does NOT deliver:**
- New simulation features, RL algorithms, or scene editor functionality.
- Automated GIF/screen-capture infrastructure beyond a lightweight script/helper.
- Docs site generation or Sphinx migration (docs extra remains unchanged).

## Implementation Decisions

### Locked decisions (from ROADMAP.md / prior phases)
- README must embed GIFs using relative markdown image syntax (`![alt](docs/demos/...gif)`).
- GUI screenshots must be captured via `QWidget.grab()` (Phase 33 already produced them at
  `tests/gui/screenshots/`); this phase only copies them to `docs/gui/`.
- Demo GIFs must be ~30 seconds, captured from the Phase 32 demos. The capture mechanism
  will reuse the simulator's `render(mode="rgb_array")` path inside a short scripted runner,
  not an external screen recorder.
- CHANGELOG entry must follow Keep-a-Changelog 1.1.0 format with Added / Changed / Fixed sections.
- CONTRIBUTING must reference `pip install -e ".[dev,gui]"` because the editor is a first-class
  v0.5.0 feature.

### the agent's Discretion
- Exact wording and section ordering in README/CONTRIBUTING, provided all mandatory
  elements from the success criteria appear.
- Whether to extend `demos/_common.py` with a GIF capture helper or to create a standalone
  `demos/capture_demo_gif.py` script.
- Choice of frame rate / resolution for GIFs, provided file size is reasonable and
  visual content is recognizable.

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value proposition and v0.5.0 milestone overview.
- `.planning/ROADMAP.md` — Phase 34 entry, success criteria, dependencies on Phases 32 and 33.
- `.planning/REQUIREMENTS.md` — DOC-01..DOC-05 acceptance criteria.

### Prior phase artifacts
- `.planning/phases/32-demo-suite-polish/32-01-PLAN.md` — narration template + `_common.py` contract.
- `.planning/phases/32-demo-suite-polish/32-02-PLAN.md` — knot-tying demo creation.
- `.planning/phases/32-demo-suite-polish/32-03-PLAN.md` — needle-passing demo creation + regression tests.
- `.planning/phases/33-pyside6-scene-editor/33-01-PLAN.md` — editor foundation (MainWindow, 4-pane layout).
- `.planning/phases/33-pyside6-scene-editor/33-07-PLAN.md` — gap-closure screenshots captured at
  `tests/gui/screenshots/{viewport,tree_form,llm_panel}.png`.

### Source-of-truth docs
- `README.md` (current) — existing structure to preserve only where useful; mostly replaced.
- `CONTRIBUTING.md` (current) — existing dev setup and conventions to carry forward.
- `CHANGELOG.md` (current) — existing Keep-a-Changelog 1.0.0 header; update to 1.1.0 is allowed.
- `demos/NARRATION_TEMPLATE.md` — 5-stage narration structure to echo in demo walkthroughs.
- `demos/_common.py` — shared demo helpers; GIF capture may extend this.

### Code references
- `pyproject.toml` — `[gui]` extra (`PySide6>=6.8.0,<7.0`, `markdown-it-py>=3.0.0`) and
  `surg-rl-gui` console script entry point.
- `demos/suturing_demo.py`, `demos/knot_tying_demo.py`, `demos/needle_passing_demo.py` —
  sources for GIF frames.

## Specific Ideas

- README banner: ASCII art or markdown header with badges (Python >=3.10, License MIT).
- README "60-second quickstart" block: `pip install -e ".[dev]"`, `surg-rl version --verbose`,
  `surg-rl-gui scenes/simple_suturing.json`.
- Demo walkthrough sections should follow the 5-stage template language (Setup / Action /
  Critical Moment / Outcome / Takeaway) without copying entire narration blocks.
- CONTRIBUTING optional-dep matrix: core, dev, gui, marl, dreamer, ros2, simulation, distributed,
  vision, llm, tracking, meshing, docs.

## Deferred Ideas

- Sphinx/mkdocs migration and hosted docs site.
- Automated GIF regeneration in CI (kept manual for v0.5.0 to avoid headless Qt/GL variance).
- Tutorial notebooks beyond the three task demos.

*Phase: 34-user-facing-docs-refresh*
*Context gathered: 2026-06-21*
