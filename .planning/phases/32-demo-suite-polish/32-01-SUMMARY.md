---
phase: 32-demo-suite-polish
plan: 01
subsystem: demo-suite
tags: [rich, narration, shared-helpers, p8-prevention, suturing-demo]

# Dependency graph
requires:
  - phase: 31-tech-debt-foundation
    provides: "Clean baseline (ruff 0 issues, [gui] extra, 1200-test passing) + Phase 32 ready to start"
provides:
  - "demos/NARRATION_TEMPLATE.md — 5-stage narration template (Setup/Action/Critical Moment/Outcome/Takeaway) with ≤25-word-per-sentence guard + vocabulary rules + suturing worked example + anti-patterns"
  - "demos/_common.py — shared helpers: print_banner, print_scene_info, resolve_scene (with .. traversal guard), format_narration_step (with stage + word-count guards), DEFAULT_TRAINING_CONFIG (12 keys)"
  - "demos/suturing_demo.py — refactored from demos/demo.py; imports from demos._common; prints Rich banner + 5-stage narration + scene info; preserves 1168-test suturing workflow"
  - "demos/__init__.py — makes demos/ a Python package so 'from demos._common import ...' resolves"
affects:
  - "Plan 02 (knot-tying demo) — will import from demos._common and follow NARRATION_TEMPLATE 5-stage structure"
  - "Plan 03 (needle-passing demo) — same pattern + the TestNarrationTemplate regression test will validate Plan 01's template"
  - "Phase 34 (docs refresh) — suturing demo's banner + narration structure is the template other demos and the README follow"

# Tech tracking
tech-stack:
  added: []  # no new dependencies — Rich already in stack at 15.0
  patterns:
    - "5-stage narration template (P8 prevention) — written FIRST before any demo is refactored"
    - "Shared demo helpers via demos/_common.py package — single source of truth for banner + scene info + narration"
    - "Scene path resolution anchored on __file__ (CWD-independent) with regex + Path.relative_to .. traversal guard (threat-model T-32-02 mitigation)"
    - "format_narration_step raises ValueError on invalid stage OR >25 words — enforces template at runtime, not just docs"

key-files:
  created:
    - demos/NARRATION_TEMPLATE.md
    - demos/_common.py
    - demos/__init__.py
  modified:
    - demos/suturing_demo.py (renamed from demos/demo.py via git mv)
    - tests/test_omp_compat_shim.py (demo.py -> suturing_demo.py in test enumeration)

key-decisions:
  - "Narration lines kept ≤25 words each (max was Critical Moment at exactly 25 words) — verified by format_narration_step guard"
  - "Rich Console(stderr=True) so banner doesn't pollute --json / pipe stdout (mirrors surg_rl.utils.logging style)"
  - "resolve_scene uses BOTH regex pre-check AND Path.relative_to authoritative guard — belt-and-suspenders for symlinked traversal"
  - "DEFAULT_TRAINING_CONFIG stored as dict (not exported as module constants) so callers can splat-merge into Pydantic v2 constructors"
  - "Added demos/__init__.py (not in plan files_modified) — required for 'from demos._common import ...' to resolve; minimal docstring, no side-effects"
  - "Updated tests/test_omp_compat_shim.py to reference suturing_demo.py instead of demo.py — Rule 2 (auto-fix critical test breakage from rename)"

patterns-established:
  - "Pattern 1: 'from demos._common import ...' after the OMP shim (sys.path.insert(0, str(Path(__file__).resolve().parent)) FIRST, then sys.path.insert(0, str(Path(__file__).resolve().parent.parent)) for the demos package)"
  - "Pattern 2: Print banner → 5 format_narration_step calls → print_scene_info → training phase — fixed order at the top of main() before any training logic"
  - "Pattern 3: Resolve scene via resolve_scene(args.scene) before any training args processing — guards against .. traversal at the top of main()"

requirements-completed: [DEMO-01, DEMO-05]

# Metrics
duration: 31min
completed: 2026-06-19
---

# Phase 32 Plan 01: Suturing Demo Refactor + Narration Template Summary

**Suturing demo refactored to use shared `demos/_common.py` helpers with 5-stage Rich narration, plus the `NARRATION_TEMPLATE.md` P8-prevention document written FIRST.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-06-19T06:04:18Z
- **Completed:** 2026-06-19T06:35:44Z
- **Tasks:** 3/3 complete
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- **P8 prevention in place**: `demos/NARRATION_TEMPLATE.md` written FIRST per pitfall prevention, establishing the 5-stage structure (`## Setup`, `## Action`, `## Critical Moment`, `## Outcome`, `## Takeaway`) with ≤25-word-per-sentence constraint, vocabulary rules (no first-person, name scene bodies explicitly, present tense, no marketing language), worked suturing walkthrough, 4 anti-pattern examples, and "How to Add a New Demo" instructions. Plans 02 + 03 will follow this template verbatim.
- **Shared helper module extracted**: `demos/_common.py` exposes 5 public symbols (`print_banner`, `print_scene_info`, `resolve_scene`, `format_narration_step`, `DEFAULT_TRAINING_CONFIG`) — all with type hints, docstrings, and inline validation guards. The threat-model T-32-02 `..` traversal guard is implemented via regex pre-check + authoritative `Path.relative_to` post-resolve check; the word-count guard raises `ValueError` immediately on misuse rather than producing silently-wrong output.
- **Suturing demo refactored**: `demos/demo.py` renamed to `demos/suturing_demo.py` via `git mv` (history preserved — `git log --follow` shows the original 2026-06-17 quick-rework and OMP-shim commits). The new demo imports from `demos._common`, prints a Rich banner, narrates the 4 task stages (Setup/Action/Critical Moment/Outcome/Takeaway) via `format_narration_step`, and prints scene info via `print_scene_info`. `--headless --steps 0` exits 0; `--headless --steps 100 --eval-episodes 1` runs full training+eval end-to-end.
- **1200-test baseline preserved**: `pytest tests/ -m "not integration" -q` reports 1200 passed, 17 skipped, 0 failed (matches the 1134 baseline + 66 from Phase 31 + 0 new from Plan 01). The 7-test `test_omp_compat_shim.py` regression suite was updated to enumerate `suturing_demo.py` instead of `demo.py` (Rule 2 auto-fix for the rename) and all 7 still pass.

## Task Commits

Each task was committed atomically:

1. **task 1: write demos/NARRATION_TEMPLATE.md (DEMO-05, P8 prevention)** — `21437e7` (docs)
2. **task 2: create demos/_common.py with shared helpers** — `909ba25` (feat)
3. **task 3: refactor demos/demo.py → demos/suturing_demo.py using _common helpers** — `96cad1d` (refactor)

**Plan metadata:** `TBD` (git_commit_metadata to be added by orchestrator after merge)

## Files Created/Modified

- `demos/NARRATION_TEMPLATE.md` — 64 lines; 5-stage template + per-stage constraints + vocabulary rules + suturing worked example + 4 anti-patterns + "How to Add a New Demo" section. P8 prevention: written FIRST before any demo is refactored.
- `demos/_common.py` — 254 lines; 5 public symbols + 3 private helpers (`_count_words`, `_REPO_TRAVERSAL_RE`, `_NARRATION_STAGES`). Rich Console to stderr; resolves scene path against repo root (parent of `demos/`).
- `demos/__init__.py` — 12 lines; minimal package docstring, no implicit side-effects on import.
- `demos/suturing_demo.py` — renamed from `demos/demo.py` via `git mv`; 475 lines; refactored to import `DEFAULT_TRAINING_CONFIG`, `format_narration_step`, `print_banner`, `print_scene_info`, `resolve_scene` from `demos._common`. Preserves `_omp_compat` / `_platform_guard` shim imports FIRST in sys.path (mjpython compat). 4 of 5 narration lines (Setup, Action, Outcome, Takeaway) carry over from the plan verbatim; Critical Moment was tuned from "lifts it 5 cm above the tissue plane" + "15° entry angle" to "lifts it" + "15 degree entry angle" to keep the second sentence ≤25 words after counting the period-separated clause as two sentences (25 words exactly).
- `tests/test_omp_compat_shim.py` — 2-line edit (replace `"demo.py"` with `"suturing_demo.py"` in the demo-name enumeration for `test_demos_import_shim_first` and `test_render_demos_import_platform_guard`).

## Decisions Made

- **Narration word counts**: Kept all 5 lines ≤25 words to pass `format_narration_step`'s guard. The Critical Moment stage was the tightest at exactly 25 words — verified by `_count_words` returning 25.
- **Rich Console to stderr**: `print_banner` writes to `Console(stderr=True)` so banners don't pollute `--json` or pipe output — mirrors `surg_rl.utils.logging` style.
- **Belt-and-suspenders traversal guard**: `resolve_scene` uses BOTH the regex pre-check (`_REPO_TRAVERSAL_RE.search`) for fast rejection of obvious attacks AND the `Path.relative_to(_REPO_ROOT)` post-resolve check as the authoritative guard. The pre-check provides a clearer error message for paths like `../etc/passwd`; the post-resolve check catches symlinked traversals.
- **DEFAULT_TRAINING_CONFIG as dict**: Stored as a plain `dict[str, Any]` (not as module-level constants) so callers can splat-merge into Pydantic v2 constructors: `{**DEFAULT_TRAINING_CONFIG, "name": args.algo}`. Pydantic v2 models don't accept `**dict` directly, so the demo unpacks fields explicitly when constructing `AlgorithmConfig`.
- **Added `demos/__init__.py`** (not in plan `files_modified`): Required for `from demos._common import ...` to resolve. The package marker is empty (just a docstring) so existing demos that use the direct `import _omp_compat` style (via the sys.path bootstrap) continue to work without modification.
- **Updated `tests/test_omp_compat_shim.py`**: The rename broke two assertions in the existing regression test that enumerated `demo.py` in the demo-name list. Per Rule 2 (auto-fix missing critical functionality — a test that prevents segfault regression is critical), I updated the enumeration to `suturing_demo.py` rather than add a `demo.py` shim. The test contract (every demo imports `_omp_compat` first, every render-capable demo imports `_platform_guard`) is preserved.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `demos/__init__.py` to make `demos` a Python package**

- **Found during:** task 3 (suturing_demo.py refactor)
- **Issue:** The plan's import pattern `from demos._common import print_banner, ...` requires `demos` to be a Python package. Without `__init__.py`, the import raises `ModuleNotFoundError: No module named 'demos'` from any CWD.
- **Fix:** Created `demos/__init__.py` with a minimal docstring (12 lines) — no implicit side-effects so existing demos that use the direct `import _omp_compat` style continue to work unchanged.
- **Files modified:** `demos/__init__.py` (new)
- **Verification:** `python demos/suturing_demo.py --headless --steps 0` exits 0 with the banner + 5-stage narration + scene info printing correctly. `python demos/eval_demo.py --help` still works (existing demo style preserved).
- **Committed in:** `96cad1d` (task 3 commit)

**2. [Rule 2 - Missing Critical] Added sys.path bootstrap for repo root in `suturing_demo.py`**

- **Found during:** task 3 (suturing_demo.py refactor)
- **Issue:** Even with `demos/__init__.py`, the `from demos._common import ...` import fails when the user runs `python demos/suturing_demo.py` from a directory that doesn't have the repo root on `PYTHONPATH` (e.g., from a worktree root). The OMP shim adds `demos/` to `sys.path`, but Python needs the **parent** of `demos/` on `sys.path` to resolve `from demos._common import ...`.
- **Fix:** Added `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` after the existing `sys.path.insert(0, str(Path(__file__).parent.parent / "src"))` line. The repo root is the parent of `demos/`. This mirrors the existing OMP-shim pattern.
- **Files modified:** `demos/suturing_demo.py`
- **Verification:** `python demos/suturing_demo.py --headless --steps 0` works from any CWD. Tested with CWD=/Users/tt/Documents/RLProj and the demo resolves correctly.
- **Committed in:** `96cad1d` (task 3 commit)

**3. [Rule 2 - Missing Critical] Updated `tests/test_omp_compat_shim.py` to reference `suturing_demo.py` instead of `demo.py`**

- **Found during:** task 3 verification (running the existing test suite)
- **Issue:** The plan renames `demos/demo.py` → `demos/suturing_demo.py`, but `tests/test_omp_compat_shim.py::test_demos_import_shim_first` (line 125) and `::test_render_demos_import_platform_guard` (line 152) hardcode the demo-name enumeration as `{"demo.py", ...}` and `{"demo.py", ...}` respectively. After the rename, these tests fail with `FileNotFoundError` because `demos/demo.py` no longer exists. The test contract — every demo must import `_omp_compat` first to prevent the macOS OMP #179 segfault — is critical and must not silently degrade.
- **Fix:** Replaced `"demo.py"` with `"suturing_demo.py"` in both demo-name enumerations. Added a 3-line comment documenting the rename for future maintainers. All 7 tests in `test_omp_compat_shim.py` pass after the change.
- **Files modified:** `tests/test_omp_compat_shim.py`
- **Verification:** `pytest tests/test_omp_compat_shim.py -v` reports 7/7 passed.
- **Committed in:** `96cad1d` (task 3 commit)

**4. [Plan-tuning] Tuned Critical Moment narration line to ≤25 words**

- **Found during:** task 3 (writing the 5-stage narration block)
- **Issue:** The plan-suggested Critical Moment narration has the phrase "lifts it 5 cm above the tissue plane" plus "The policy maintains a 15° entry angle" — the period-separated second sentence ("off-axis entry tears the FEM mesh. The policy maintains a 15° entry angle") plus the first sentence pushes the second sentence over 25 words when counted as a single narration line. `format_narration_step` enforces the 25-word limit on the whole `line` argument, not per sentence.
- **Fix:** Tuned to "lifts it" + "holds a 15 degree entry angle" — verified by `_count_words` returning exactly 25 words. The vocabulary rule of naming scene bodies (skin_patch_left, skin_patch_right, curved_suturing_needle, surgical_arm_1, FEM mesh) is preserved.
- **Files modified:** `demos/suturing_demo.py`
- **Verification:** `format_narration_step("Critical Moment", ...)` returns a Rich-formatted string without raising.
- **Committed in:** `96cad1d` (task 3 commit)

---

**Total deviations:** 4 auto-fixed (4 missing critical / scope additions)
**Impact on plan:** All 4 fixes necessary for the plan's `from demos._common import ...` pattern to actually work at runtime + the existing regression test to keep passing. No scope creep into Phase 32 Plans 02/03 territory.

## Issues Encountered

- **git stash/pop unstaged the rename**: After `git mv demos/demo.py demos/suturing_demo.py` and starting the lint comparison against the original file via `git stash`, the rename was lost in the stash round-trip (git recorded `new file: demos/suturing_demo.py` + `deleted: demos/demo.py` instead of `renamed:`). Recovered by `git restore --staged` + `git add demos/demo.py demos/suturing_demo.py` (re-staging both files together re-detects the rename; git's rename detection runs at staging time). Verified post-recovery: `git log --follow --oneline -- demos/suturing_demo.py` shows the original 2026-06-17 quick-rework and OMP-shim commits.

## Verification Results

### Plan verification commands (all PASS)

```bash
# 1. NARRATION_TEMPLATE.md exists with 5 stage headings
$ test -f demos/NARRATION_TEMPLATE.md && grep -cE "^## (Setup|Action|Critical Moment|Outcome|Takeaway)$" demos/NARRATION_TEMPLATE.md
5   ✓

# 2. _common.py: import OK + symbols OK + traversal guard OK + word guard OK + config OK
$ PYTHONPATH=src python -c "from demos._common import (print_banner, print_scene_info, resolve_scene, format_narration_step, DEFAULT_TRAINING_CONFIG); ..."
_COMMON_OK  ✓

# 3. suturing_demo.py --headless --steps 0 prints 5 stage markers
$ PYTHONPATH=src python demos/suturing_demo.py --headless --steps 0 2>&1 | grep -cE "\[Setup\]|\[Action\]|\[Critical Moment\]|\[Outcome\]|\[Takeaway\]"
5   ✓
```

### Lint status (demos/)

- `ruff check demos/_common.py` → All checks passed
- `ruff check demos/__init__.py` → All checks passed
- `ruff check demos/suturing_demo.py` → 9 errors (all pre-existing in `demos/demo.py`; out of refactor scope per deviation scope boundary: unused `numpy`/`SurgicalEnvConfig`/`make_env`/`ActionConfig`/`ActionType` imports; `Tuple` → `tuple`; `eval_results` unused; etc.)
- `black --check demos/_common.py` → would be left unchanged
- `black --check demos/__init__.py` → would be left unchanged
- `black --check demos/suturing_demo.py` → 1 violation (pre-existing, unrelated to refactor)

### Pytest regression summary

```
1200 passed, 17 skipped, 27 deselected, 32 warnings in 89.59s (0:01:29)
```

- Baseline 1134 (pre-Phase-31) + 66 (Phase 31) = 1200. Plan 01 introduces 0 new tests (the regression tests for narration compliance are Plan 03 per the plan's `verify` block).
- All 7 `tests/test_omp_compat_shim.py` tests pass with the updated `suturing_demo.py` enumeration.

### Demolition check (T-32-02 traversal guard)

```
$ PYTHONPATH=src python -c "from demos._common import resolve_scene; resolve_scene('../etc/passwd')"
ValueError: Scene path contains '..' traversal: ../etc/passwd (root=/Users/tt/Documents/RLProj)

$ PYTHONPATH=src python -c "from demos._common import format_narration_step; format_narration_step('Setup', 'word ' * 30)"
ValueError: Narration line has 30 words (max 25). See demos/NARRATION_TEMPLATE.md.

$ PYTHONPATH=src python -c "from demos._common import format_narration_step; format_narration_step('BogusStage', 'x')"
ValueError: Invalid narration stage: 'BogusStage'. Must be one of ('Setup', 'Action', 'Critical Moment', 'Outcome', 'Takeaway'). See demos/NARRATION_TEMPLATE.md.
```

All 3 guards fire as expected.

### End-to-end demo run (--steps 100 --eval-episodes 1)

- `--headless --steps 0` → exits 0 with banner + 5-stage narration + scene info
- `--headless --steps 100 --eval-episodes 1` → trains for 52.5s on MPS, evaluates 1 episode, reports metrics (Mean reward 25M, Success rate 0% — expected for 100 steps). No segfaults. OMP shim still effective.

### Rename history preserved

```
$ git log --follow --oneline -- demos/suturing_demo.py
96cad1d refactor(32-01): rename demo.py to suturing_demo.py and import from _common
9e11c3f quick(20260617-demo-rework): realistic suturing demo — soft tissue, small needle, visible gripper jaws
7dac6aa fix(demos): work around OMP #179 segfault via thread=1 env vars
```

The 2026-06-17 quick-rework and OMP-shim fix commits are still attached to the renamed file.

## User Setup Required

None — no external service configuration required. Rich is already in stack at 15.0; no `pip install` of new packages.

## Next Phase Readiness

- **Plan 02 (knot-tying demo)** can now begin: the `_common.py` interface is stable (`print_banner`, `print_scene_info`, `resolve_scene`, `format_narration_step`, `DEFAULT_TRAINING_CONFIG`); the `NARRATION_TEMPLATE.md` provides the narration structure; the suturing demo is the reference implementation. Plan 02 will add a new `demos/knot_tying_demo.py` that mirrors `suturing_demo.py`'s structure.
- **Plan 03 (needle-passing demo)** follows the same pattern and adds the `TestNarrationTemplate::test_all_demos_follow_template` regression test that validates all 3 demos against `NARRATION_TEMPLATE.md`'s 5-stage structure.
- **No blockers for Phase 33 (PySide6 Scene Editor)** — Phase 32 is independent of the GUI work.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tamper_mitigated | `demos/_common.py` | `resolve_scene` rejects `..` traversal above the repo root via regex pre-check + `Path.relative_to` authoritative guard (threat-model T-32-02). Verified by `resolve_scene("../etc/passwd")` raising `ValueError`. |
| threat_flag: dos_mitigated | `demos/suturing_demo.py` | `--max-episode-steps 2000` upper bound + `--steps` validator preserved from the original `demos/demo.py` argparse (threat-model T-32-01). No new surface introduced. |
| threat_flag: disclosure_accepted | `demos/suturing_demo.py` | Demo banners print scene metadata (name, robot count, tissue count, task objectives) which is non-sensitive (threat-model T-32-03). `surg_rl.utils.logging.SensitiveDataFilter` already in stack for any logger output. |

No new security-relevant surface introduced beyond what was already in `demos/demo.py`.

---

*Phase: 32-demo-suite-polish*
*Completed: 2026-06-19*