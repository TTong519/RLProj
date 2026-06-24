---
phase: 34
phase_name: "User-Facing Docs Refresh"
project: "Surg-RL"
generated: "2026-06-24"
counts:
  decisions: 5
  lessons: 4
  patterns: 4
  surprises: 4
missing_artifacts:
  - "VERIFICATION.md"
  - "UAT.md"
---

# Phase 34 Learnings: User-Facing Docs Refresh

## Decisions

### Parallelizable wave-1 doc plans, dependent README in wave 2
Phase 34 split into four plans: 34-01 (CONTRIBUTING/CHANGELOG), 34-02 (GIFs), 34-03 (screenshots) all ran in wave 1 with `depends_on: []`, while 34-04 (README) ran in wave 2 depending on all three.

**Rationale:** README embeds the GIFs and screenshots and links to CONTRIBUTING/CHANGELOG, so its inputs must exist first; the text and asset generation are independent and can run concurrently.
**Source:** 34-04-PLAN.md

### Keep-a-Changelog version bumped 1.0.0 → 1.1.0
The CHANGELOG header reference was updated from Keep-a-Changelog 1.0.0 to 1.1.0 while still referencing Semantic Versioning 2.0.0. The `[0.5.0]` entry uses Added / Changed / Fixed subsections in that fixed order.

**Rationale:** Project the v0.5.0 release notes against the current Keep-a-Changelog spec and a consistent subsection ordering.
**Source:** 34-01-PLAN.md

### Demo GIFs captured from headless rgb_array frames via imageio, with ffmpeg fallback
GIFs were produced by running the Phase 32 demos headlessly and collecting `rgb_array` frames written through `imageio.mimsave()`, with a documented ffmpeg fallback for environments lacking imageio. The capture script imports `_omp_compat` and `_platform_guard` before MuJoCo/PyBullet to preserve the Phase 32 macOS mjpython contract.

**Rationale:** Avoid external screen-capture tools; reuse already-narration-compliant demos; keep the macOS mjpython compatibility guarantee intact.
**Source:** 34-02-PLAN.md

### GUI screenshots copied (not moved) from tests/gui/screenshots/ to docs/gui/
Phase 33 smoke-test screenshots were copied to `docs/gui/` rather than moved, so the Phase 33 test suite continues to find the originals.

**Rationale:** Keep the test fixtures in place as test evidence while publishing copies for README embedding; avoid breaking a passing test suite to produce docs.
**Source:** 34-03-PLAN.md

### imageio added to the [gui] extra in pyproject.toml
`imageio>=2.31.0` was added under the `[gui]` optional dependency group so the capture dependency is installable alongside the GUI tooling.

**Rationale:** The GIF capture dependency belongs with the gui tooling group since both are visual-output concerns.
**Source:** 34-02-SUMMARY.md

---

## Lessons

### MuJoCo offscreen rgb_array can return None on macOS runners
On the macOS runner used for capture, MuJoCo offscreen `rgb_array` returned `None`, so `knot_tying.gif` had to be captured with `--backend pybullet` instead.

**Context:** Capturing demo GIFs headlessly on macOS; the fallback to PyBullet was a deviation recorded in 34-02-SUMMARY.md.
**Source:** 34-02-SUMMARY.md

### Deterministic zero actions produce tiny GIFs that fail size assertions
A deterministic zero-action policy produced an 11 KB GIF for knot_tying that failed the 100 KB minimum. The final 300-frame capture used `--stochastic --max-episode-steps 50` to introduce enough variation to clear the threshold.

**Context:** First capture attempt for knot_tying.gif fell below the plan's 100 KB–15 MB size bound; re-capture was needed.
**Source:** 34-02-SUMMARY.md

### GUI panel screenshots are intentionally narrow; width thresholds must be relaxed
The Phase 33 smoke-test captures have uneven dimensions (viewport 1088x480, tree_form 90x463, llm_panel 1280x277). The original plan required every screenshot to be >= 200x200 px, but the tree/form panel is intentionally narrow, so the requirement was relaxed to height >= 200 px only.

**Context:** Publishing GUI screenshots; the tree_form panel is a narrow vertical panel by design.
**Source:** 34-03-SUMMARY.md

### GIF frame count should be validated as a range, not an exact target
Frame count was validated against the 240–450 range in `tests/test_doc_assets.py` instead of an exact 300, matching the plan's acceptance range. This accommodates stochastic capture variation.

**Context:** Regression test design for doc assets; exact-frame assertions would be brittle.
**Source:** 34-02-SUMMARY.md

---

## Patterns

### Grep/Python-assert verification gates for doc content
Each plan specifies concrete `grep -E` and `python -c "..."` one-liners as acceptance criteria and verify steps (e.g. `grep -E 'Keep-a-Changelog 1\.1.0' CHANGELOG.md`, a Python assertion that all embedded README image paths resolve to existing files).

**When to use:** Doc-heavy phases where content must contain specific strings/links without writing a full test suite up front.
**Source:** 34-01-PLAN.md, 34-04-PLAN.md

### Regression tests for doc assets in tests/test_doc_assets.py
A single `tests/test_doc_assets.py` file accumulates regression tests across plans: GIF existence/size/frame-count, PNG validity/dimensions, README structure, CHANGELOG `[0.5.0]` entry, and CONTRIBUTING workflow. Plan 34-04 added 15 such tests.

**When to use:** Whenever user-facing docs embed assets that must remain present and well-formed across releases; guard the docs/ tree with a dedicated test module.
**Source:** 34-04-SUMMARY.md, 34-02-SUMMARY.md

### Copy-don't-move when publishing test artifacts as docs
Test-produced assets (screenshots, fixtures) are copied to a public docs/ location rather than moved, leaving the originals as test evidence.

**When to use:** Publishing artifacts that also serve as test fixtures; preserves test-suite integrity while enabling public embedding.
**Source:** 34-03-PLAN.md

### Capture-script ordering: platform guards before simulator imports
The capture script imports `_omp_compat` and `_platform_guard` first, before any MuJoCo/PyBullet import, to preserve the macOS mjpython compatibility contract.

**When to use:** Any script that touches MuJoCo/PyBullet on macOS headless runners.
**Source:** 34-02-PLAN.md

---

## Surprises

### knot_tying.gif first capture was only 11 KB and failed size bounds
The initial deterministic capture produced an 11 KB GIF well under the 100 KB minimum; a second stochastic capture (300 frames, ~30s, 107 KB) was required.

**Impact:** Required a re-capture and a `--stochastic --max-episode-steps 50` flag; added a deviation to 34-02-SUMMARY.md.
**Source:** 34-02-SUMMARY.md

### tree_form screenshot is 90 px wide, not 200 px
The Phase 33 tree/form panel capture is 90x463 — far narrower than the plan's 200x200 minimum — because the panel is intentionally narrow.

**Impact:** The 200 px width requirement was relaxed to height >= 200 px; documented as a deviation in 34-03-SUMMARY.md.
**Source:** 34-03-SUMMARY.md

### Plan 34-01 reported zero lines added/removed despite a full CONTRIBUTING.md rewrite
The summary metrics show `lines_added: 0` / `lines_removed: 0` and `tests_added: 0` even though CONTRIBUTING.md was rewritten and CHANGELOG was updated.

**Impact:** The metrics field appears under-populated for markdown-only doc work; rely on the narrative "What was done" rather than the metrics counters for doc phases.
**Source:** 34-01-SUMMARY.md

### No automated tests were added in plans 34-01/34-02/34-03 by design
Plans 34-01, 34-02, and 34-03 all report `tests_added: 0`; the doc-asset regression tests were deferred to plan 34-04, which added 15 tests in `tests/test_doc_assets.py`.

**Impact:** Test coverage for the phase is concentrated in the final wave-2 plan rather than each producing plan; a single test module guards all doc assets.
**Source:** 34-01-SUMMARY.md, 34-04-SUMMARY.md