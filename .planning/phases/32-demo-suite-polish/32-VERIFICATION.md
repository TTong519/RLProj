---
phase: 32-demo-suite-polish
status: passed
verified-by: gsd-verifier
verified-at: 2026-06-19T10:25:00Z
requirements-verified: [DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05]
score: 5/5 requirements verified
---

# Phase 32: Demo Suite Polish — Verification

## Goal

Polish the demo suite (suturing, knot-tying, needle-passing) to follow a consistent 5-stage narration template via shared `demos/_common.py`, plus add regression tests.

## Verification Result: **passed**

All 5 DEMO requirements verified against the actual codebase. Phase goal achieved.

## Requirement Coverage

### DEMO-01: Suturing demo polished ✓ VERIFIED
- **`demos/suturing_demo.py` exists:** Yes (renamed from `demos/demo.py` via `git mv` — `git log --follow` confirms history preservation: `96cad1d → 9e11c3f → 7dac6aa`)
- **Imports from `demos._common`:** Yes (`from demos._common import (DEFAULT_TRAINING_CONFIG, format_narration_step, print_banner, print_scene_info, resolve_scene)` at line 48)
- **Prints 5-stage narration via `_common` helpers:** Yes — verified by running the demo; all 5 stage markers `[Setup]`, `[Action]`, `[Critical Moment]`, `[Outcome]`, `[Takeaway]` present in output (word counts: 17, 19, 25, 18, 20 — all ≤25)
- **Prints scene info via `_common.print_scene_info`:** Yes — "Scene: Suturing Training Demo, Robots: 1, Tissues: 2, Instruments: 1, Task: multi_stage_suturing" with 4 objectives listed
- **Exits 0 with `--headless --steps 0`:** Yes — verified; exit code 0
- **Evidence:**
  ```
  $ PYTHONPATH=src python demos/suturing_demo.py --headless --steps 0
  ────────────────────────── Suturing RL Training Demo ──────────────────────────
  Phase 32 — Demo Suite Polish
  ...
  [bold cyan][Setup][/bold cyan] The agent operates the surgical_arm_1 gripper inside a suturing scene...
  [bold cyan][Action][/bold cyan] The policy approaches the curved_suturing_needle from above...
  [bold cyan][Critical Moment][/bold cyan] The needle's arc must clear both skin_patch edges simultaneously...
  [bold cyan][Outcome][/bold cyan] The needle passes through skin_patch_left and skin_patch_right...
  [bold cyan][Takeaway][/bold cyan] Suturing rewards dense distance shaping plus a sparse success bonus...
  EXIT: 0
  ```
- **Verdict:** PASS

### DEMO-02: Knot-tying demo polished ✓ VERIFIED
- **`demos/knot_tying_demo.py` exists:** Yes (472 lines; created in plan 02 task 2)
- **`tests/fixtures/scenes/knot_tying.json` exists:** Yes (344 lines; byte-identical to `scenes/knot_tying.json` — `diff -q` exit 0; SHA-256 matches)
- **Imports from `demos._common`:** Yes (5 imports at line 46)
- **Prints 5-stage narration covering 3 sub-steps with KNOT_TIER:** Yes — narration covers needle insertion → knot formation → knot tightening; `knot_driver` mentioned in 3 of 5 stages (Setup, Action, Critical Moment) per vocabulary rule
- **Loads from `tests/fixtures/scenes/knot_tying.json`:** Yes — `--scene` default points to fixture path; `load_scene()` succeeds
- **Exits 0 with `--headless --steps 0`:** Yes — verified
- **Evidence:**
  ```
  $ PYTHONPATH=src python demos/knot_tying_demo.py --headless --steps 0
  ──────────────────────── Knot-Tying RL Training Demo ────────────────────────
  Phase 32 — Demo Suite Polish
  ...
  Scene: Knot Tying Scene, Robots: 1, Tissues: 1, Instruments: 1, Task: knot_tying_task
    - knot_throw (weight=2.0)
    - knot_tighten (weight=3.0)
  [Setup] ... suture_pad tissue and one knot_driver instrument.
  [Action] ... wraps the thread around the knot_driver twice ...
  [Critical Moment] ... 2N pull force on the knot_driver for 200 ms.
  [Outcome] ... knot_throw and knot_tighten objectives both succeed.
  [Takeaway] ... training in roughly 80k PPO timesteps ...
  EXIT: 0
  ```
- **Verdict:** PASS

### DEMO-03: Needle-passing demo polished ✓ VERIFIED
- **`demos/needle_passing_demo.py` exists:** Yes (482 lines; created in plan 03 task 2)
- **`scenes/needle_passing.json` exists with dual-arm MultiAgentConfig:** Yes (289 lines; 2 robots named `surgeon_arm` + `assistant_arm`; `multi_agent.arm_configs` has 2 distinct entries with roles `surgeon` + `assistant`; `task.task_type = "needle_insertion"` — closest valid Pydantic Literal)
- **Imports from `demos._common`:** Yes (5 imports at line 48)
- **Prints 5-stage narration covering 4 sub-steps with dual arms:** Yes — Setup explicitly names BOTH `surgeon_arm` AND `assistant_arm` (vocabulary rule for dual-arm); narration covers pick-up → approach → pass-through → withdrawal
- **Loads from `scenes/needle_passing.json`:** Yes — `--scene` default points to canonical scene path
- **Exits 0 with `--headless --steps 0`:** Yes — verified
- **Evidence:**
  ```
  $ PYTHONPATH=src python demos/needle_passing_demo.py --headless --steps 0
  ──────────────────── Needle-Passing RL Training Demo ────────────────────
  Phase 32 — Demo Suite Polish (Dual-Arm)
  ...
  Scene: Needle Passing Scene, Robots: 2, Tissues: 1, Instruments: 1, Task: needle_passing_task
    - needle_pickup (weight=1.0)
    - needle_pass (weight=3.0)
    - assistant_receive (weight=2.0)
  [Setup] ... surgeon_arm and assistant_arm inside a needle-passing scene ...
  [Action] ... surgeon_arm to pick up the curved_passing_needle ...
  [Critical Moment] ... align with the assistant_arm end effector ...
  [Outcome] ... assistant_arm closes its gripper on the shaft ...
  [Takeaway] ... dense cross-arm distance shaping ...
  EXIT: 0
  ```
- **Verdict:** PASS

### DEMO-04: Per-demo regression tests ✓ VERIFIED
- **`tests/test_demos.py` exists:** Yes (194 lines; created in plan 03 task 3)
- **Contains 4 test classes:** Yes — `TestDemoRegression`, `TestNarrationTemplate`, `TestKnotTyingFixture`, `TestNeedlePassingFixture`
- **Contains 6 tests:** Yes — `test_suturing_demo_runs`, `test_knot_tying_demo_runs`, `test_needle_passing_demo_runs`, `test_template_has_5_stage_headings`, `test_knot_tying_fixture_matches_source`, `test_needle_passing_scene_has_multi_agent_config`
- **All 6 tests pass:** Yes — verified
- **Evidence:**
  ```
  $ PYTHONPATH=src python -m pytest tests/test_demos.py -v
  ============================= test session starts ==============================
  collected 6 items

  tests/test_demos.py::TestDemoRegression::test_suturing_demo_runs PASSED        [ 16%]
  tests/test_demos.py::TestDemoRegression::test_knot_tying_demo_runs PASSED       [ 33%]
  tests/test_demos.py::TestDemoRegression::test_needle_passing_demo_runs PASSED   [ 50%]
  tests/test_demos.py::TestNarrationTemplate::test_template_has_5_stage_headings PASSED [ 66%]
  tests/test_demos.py::TestKnotTyingFixture::test_knot_tying_fixture_matches_source PASSED [ 83%]
  tests/test_demos.py::TestNeedlePassingFixture::test_needle_passing_scene_has_multi_agent_config PASSED [100%]

  ============================== 6 passed in 15.49s ==============================
  ```
- **Verdict:** PASS

### DEMO-05: Narration template ✓ VERIFIED
- **`demos/NARRATION_TEMPLATE.md` exists:** Yes (64 lines; written FIRST per P8 prevention in plan 01 task 1)
- **5-stage structure documented in order:** Yes — `## Setup` (L34), `## Action` (L37), `## Critical Moment` (L40), `## Outcome` (L43), `## Takeaway` (L46) — verified by `grep -nE "^## (Setup|Action|Critical Moment|Outcome|Takeaway)$" demos/NARRATION_TEMPLATE.md`
- **Per-stage constraints documented:** Yes — "1-2 sentences per stage" + "≤25 words per sentence" + Stage headings must match literal markdown
- **Vocabulary rules documented:** Yes — `## Vocabulary Rules` section (L24-29) covering: no first-person, name scene bodies, present tense, no marketing language
- **Worked example (suturing walkthrough):** Yes — L31-48
- **Anti-patterns documented:** Yes — 4 examples in `## Anti-Patterns` section (L50-55)
- **Verdict:** PASS

## Test Suite Results

| Suite | Result | Notes |
|-------|--------|-------|
| `tests/test_demos.py` | 6 passed, 0 failed | All 6 demo regression tests pass in 15.49s |
| `tests/test_omp_compat_shim.py` | 7 passed, 0 failed | OMP shim regression tests pass in 0.01s (updated for rename: `demo.py` → `suturing_demo.py`) |
| Full suite `pytest tests/ -m "not integration"` | 1206 passed, 17 skipped, 0 failed | Baseline 1200 + 6 new = 1206; no regressions |

## Code Review Status

`32-REVIEW.md` reports `status: minor_issues` with 5 findings (0 critical, 0 high, 2 medium, 3 low). All findings are quality improvements, not blockers:

| # | Severity | Finding | Impact on Goal |
|---|----------|---------|----------------|
| MEDIUM-1 | test_demos.py omits `task.task_type == "needle_insertion"` assertion | None — the scene's other assertions (multi_agent.arm_configs ≥ 2, roles contain 'surgeon' + 'assistant') already cover DEMO-03 acceptance; load_scene() would also reject invalid task_type Literal at validation time |
| MEDIUM-2 | suturing_demo.py argparse defaults hardcoded vs `DEFAULT_TRAINING_CONFIG` | None — the literal values match the DEFAULT_TRAINING_CONFIG values exactly (`"PPO"`, `50_000`, `2000`, `42`); suturing_demo.py DOES use `{**DEFAULT_TRAINING_CONFIG, "name": args.algo}` for the AlgorithmConfig constructor at line 134. The inconsistency is at the argparse default layer only |
| LOW-1 | 3 ruff lint errors in test_demos.py (I001 import order, F401 unused pytest, W292 trailing newline) | None — all auto-fixable; don't affect test correctness or demo goal |
| LOW-2 | `_count_words` regex splits on hyphens (e.g., "knot-tying" = 2 tokens) | None — current narration lines all pass ≤25-word guard |
| LOW-3 | `print_scene_info` doesn't guard empty objectives list | None — cosmetic; current scenes have ≥2 objectives |

No finding blocks the phase goal.

## Codebase Evidence (Files Touched)

| File | Status | Verified |
|------|--------|----------|
| `demos/NARRATION_TEMPLATE.md` | created (64 lines) | ✓ exists, has 5 stage headings + vocabulary rules + worked example + anti-patterns |
| `demos/_common.py` | created (255 lines) | ✓ has all 5 public symbols; traversal + word-count guards verified |
| `demos/__init__.py` | created (12 lines) | ✓ makes `demos` importable as a package |
| `demos/suturing_demo.py` | renamed from `demos/demo.py` via `git mv` (475 lines) | ✓ imports from `demos._common`; prints 5-stage narration; exits 0 |
| `demos/knot_tying_demo.py` | created (472 lines) | ✓ imports from `demos._common`; KNOT_TIER vocabulary satisfied; exits 0 |
| `demos/needle_passing_demo.py` | created (482 lines) | ✓ imports from `demos._common`; dual-arm vocabulary satisfied; exits 0 |
| `scenes/needle_passing.json` | created (289 lines) | ✓ dual-arm MultiAgentConfig; loads via `load_scene()` |
| `tests/fixtures/scenes/knot_tying.json` | created (344 lines; byte-identical to `scenes/knot_tying.json`) | ✓ `diff -q` exit 0; SHA-256 matches |
| `tests/test_demos.py` | created (194 lines; 4 classes, 6 tests) | ✓ all 6 tests pass |
| `tests/test_omp_compat_shim.py` | modified (2 lines: `demo.py` → `suturing_demo.py` enumeration) | ✓ all 7 tests pass |

## Anti-Pattern Scan

Searched for stub/anti-pattern markers in new/modified files:
- `TODO|FIXME|XXX|HACK|PLACEHOLDER`: 0 matches
- `return null|return {}|return []`: 0 matches in the demo/test files (the `return {}` in `resolve_scene` is inside `except` block raising `ValueError`, not a stub)
- Empty implementations: None found
- Hardcoded empty data props: None found
- The `pytest` import in `tests/test_demos.py:22` is flagged as F401 (unused) by ruff — noted in LOW-1 review finding, doesn't affect behavior since the file uses `assert` only (no pytest features)

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| suturing demo `--headless --steps 0` exits 0 | `PYTHONPATH=src python demos/suturing_demo.py --headless --steps 0` | exit 0; all 5 stage markers + scene info printed | ✓ PASS |
| knot_tying demo `--headless --steps 0` exits 0 | `PYTHONPATH=src python demos/knot_tying_demo.py --headless --steps 0` | exit 0; all 5 stage markers + scene info printed | ✓ PASS |
| needle_passing demo `--headless --steps 0` exits 0 | `PYTHONPATH=src python demos/needle_passing_demo.py --headless --steps 0` | exit 0; all 5 stage markers + scene info printed | ✓ PASS |
| `tests/test_demos.py` 6 tests pass | `PYTHONPATH=src python -m pytest tests/test_demos.py -v` | 6 passed in 15.49s | ✓ PASS |
| `tests/test_omp_compat_shim.py` 7 tests pass | `PYTHONPATH=src python -m pytest tests/test_omp_compat_shim.py -v` | 7 passed in 0.01s | ✓ PASS |
| Fixture byte-identical | `diff -q scenes/knot_tying.json tests/fixtures/scenes/knot_tying.json` | exit 0 (no output, identical) | ✓ PASS |
| Dual-arm scene loads | `load_scene('scenes/needle_passing.json')` | multi_agent.arm_configs=2, roles=['surgeon','assistant'], task.task_type='needle_insertion' | ✓ PASS |
| All narration lines ≤25 words | regex `\b\w+\b` counter | Max is 25 (suturing Critical Moment); all others 17-23 | ✓ PASS |

## Gaps

None. All 5 requirements verified.

## Human Verification Required

None. All verification is programmatic.

## Recommendation

**Status: passed → update_roadmap**

The phase goal is fully achieved. All 5 DEMO requirements (DEMO-01..05) verified by direct execution and code inspection. The 6 regression tests pass; full test suite grows from 1200 → 1206 passed with 0 regressions. Code review surfaced 5 minor issues (2 medium, 3 low) — none block the phase goal. They can be addressed in a Phase 32 follow-up plan if desired, but are not gating.
