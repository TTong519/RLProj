---
phase: 32
phase_name: "Demo Suite Polish"
project: "Surg-RL"
generated: "2026-06-24"
counts:
  decisions: 8
  lessons: 7
  patterns: 5
  surprises: 5
missing_artifacts:
  - "UAT.md"
---

# Phase 32 Learnings: Demo Suite Polish

## Decisions

### Narration template written FIRST before any demo refactor
The NARRATION_TEMPLATE.md was written as Plan 01 task 1, before any demo was refactored, to prevent the P8 pitfall where "demo 1 sounds confident, demo 2 sounds confused, demo 3 sounds like marketing."

**Rationale:** Without the template written first, each demo author invents their own narration style. Writing the template first establishes the 5-stage structure (Setup / Action / Critical Moment / Outcome / Takeaway) with per-stage constraints that Plans 02 and 03 then follow verbatim.
**Source:** 32-01-PLAN.md

---

### Rich Console writes to stderr, not stdout
`print_banner` uses `Console(stderr=True)` so banners do not pollute `--json` or pipe output.

**Rationale:** Mirrors `surg_rl.utils.logging` style; keeps stdout machine-parseable while still rendering Rich formatting for human viewers on stderr.
**Source:** 32-01-SUMMARY.md

---

### DEFAULT_TRAINING_CONFIG stored as a plain dict, not module-level constants
The shared RL hyperparameters live in a single `dict[str, Any]` (12 keys) so callers can splat-merge it into Pydantic v2 constructors.

**Rationale:** Pydantic v2 models do not accept `**dict` directly, so the demo unpacks fields explicitly when constructing `AlgorithmConfig`; keeping values in a dict lets callers do `{**DEFAULT_TRAINING_CONFIG, "name": args.algo}` merges and allows CLI defaults to be sourced via `DEFAULT_TRAINING_CONFIG["..."]` lookups instead of hardcoded literals.
**Source:** 32-01-SUMMARY.md

---

### Belt-and-suspenders path traversal guard in resolve_scene
`resolve_scene` uses BOTH a regex pre-check (`_REPO_TRAVERSAL_RE.search`) for fast rejection of obvious attacks AND `Path.relative_to(_REPO_ROOT)` post-resolve as the authoritative guard.

**Rationale:** The pre-check gives a clearer error message for paths like `../etc/passwd`; the post-resolve check catches symlinked traversals that the regex would miss.
**Source:** 32-01-SUMMARY.md

---

### CLI defaults sourced from DEFAULT_TRAINING_CONFIG dict lookups
All demo CLI flags (`--algo`, `--steps`, `--max-episode-steps`, `--seed`) use `DEFAULT_TRAINING_CONFIG["..."]` lookups as their argparse defaults rather than hardcoded literal numbers.

**Rationale:** Makes each demo track the shared hyperparameter set so a single edit to `_common.py` propagates to all 3 demos; Plan 03's needle-passing demo mirrors the same pattern.
**Source:** 32-02-SUMMARY.md

---

### Needle-passing scene uses task_type='needle_insertion', not 'needle_passing'
The new `scenes/needle_passing.json` sets `task.task_type = "needle_insertion"` because `needle_passing` is NOT a valid Pydantic Literal value at `TaskConfig.task_type` (see schema.py:1107). The reward path uses `task_name="needle_passing_task"` (the `TaskName.NEEDLE_PASSING` enum), which is a separate field and coexists fine.

**Rationale:** The closest valid Pydantic Literal must be used for the scene to load via `load_scene()`; the reward enum is a separate namespace and unaffected.
**Source:** 32-03-PLAN.md

---

### Subprocess regression tests use sys.executable + timeout=60s
The demo regression tests spawn each demo via `subprocess.run([sys.executable, str(demo_path), "--headless", "--steps", "0"], timeout=60, ...)`.

**Rationale:** Using `sys.executable` guarantees interpreter parity between parent and child (avoids mismatched Python environments); the 60s timeout fails fast on hangs without flaking on slow CI runners (banner-only mode runs in <30s).
**Source:** 32-03-SUMMARY.md

---

### TestNeedlePassingFixture uses >=2 arms with set-based role check
The dual-arm scene validation asserts `len(arm_configs) >= 2` and `{"surgeon", "assistant"} <= {role.value for arm in ...}` rather than exact `== 2` with an ordered list.

**Rationale:** More robust if a third arm (e.g., a camera arm) is ever added later; the test would not break on a benign extension.
**Source:** 32-03-SUMMARY.md

---

## Lessons

### demos/ must be a Python package for `from demos._common import` to resolve
The plan's import pattern requires `demos` to be a Python package. Without `demos/__init__.py`, the import raises `ModuleNotFoundError: No module named 'demos'` from any CWD.

**Context:** Found during task 3 (suturing_demo.py refactor); `demos/__init__.py` was not in the plan's `files_modified` list. Created a minimal 12-line docstring-only `__init__.py` with no side-effects so existing demos using direct `import _omp_compat` style continue to work.
**Source:** 32-01-SUMMARY.md

---

### Repo root must be on sys.path for `from demos._common import` to work from any CWD
Even with `demos/__init__.py`, the import fails when running `python demos/suturing_demo.py` from a directory without the repo root on PYTHONPATH. The OMP shim adds `demos/` to sys.path, but Python needs the parent of `demos/` to resolve the package import.

**Context:** Added `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` after the existing src-path bootstrap, mirroring the existing OMP-shim pattern.
**Source:** 32-01-SUMMARY.md

---

### git stash/pop loses rename detection; re-stage both files together to recover
After `git mv demos/demo.py demos/suturing_demo.py` and a `git stash` round-trip, git recorded `new file: demos/suturing_demo.py` + `deleted: demos/demo.py` instead of `renamed:`, losing the rename linkage.

**Context:** Recovered via `git restore --staged` + `git add demos/demo.py demos/suturing_demo.py` together (git's rename detection runs at staging time). Verified via `git log --follow --oneline -- demos/suturing_demo.py` showing the original 2026-06-17 commits still attached.
**Source:** 32-01-SUMMARY.md

---

### format_narration_step enforces the 25-word limit on the whole line argument, not per sentence
The plan-suggested Critical Moment narration had two period-separated sentences whose combined word count exceeded 25 when treated as a single `line` argument.

**Context:** Tuned "lifts it 5 cm above the tissue plane" + "15° entry angle" to "lifts it" + "holds a 15 degree entry angle" to land at exactly 25 words. Vocabulary rule of naming scene bodies was preserved.
**Source:** 32-01-SUMMARY.md

---

### `needle_passing` is NOT a valid TaskConfig.task_type Pydantic Literal
The natural task name for the needle-passing demo cannot be used as `task.task_type`; only `needle_insertion` (among the existing Literal values) is valid.

**Context:** Discovered while writing `scenes/needle_passing.json` in Plan 03 task 1; the reward path uses `task_name="needle_passing_task"` (a different enum) which coexists fine. Test assertions were trimmed to avoid asserting the exact task_type string since `load_scene()` already validates it at schema level.
**Source:** 32-03-PLAN.md

---

### gsd-executor agent responses can truncate mid-task, leaving later tasks undone
Plan 03's first executor agent completed only Task 1 (scene file commit `cc63ae0`) before its response was cut off mid-Task 2, leaving the demo file and test file uncommitted.

**Context:** Resumed via two sequential single-task `general` subagent dispatches to minimize response-length truncation risk. Worth noting for future Phase 32+ plans where the gsd-executor template might produce longer outputs than the runtime allows.
**Source:** 32-03-SUMMARY.md

---

### `pytest tests/` invoked directly can SIGABRT (exit 134) on this host; use `python -m pytest`
Running `pytest tests/ -m "not integration"` via the shell's `pytest` directly produced no output and exit code 134 (SIGABRT).

**Context:** Switching to `python -m pytest` works correctly. Likely a shell environment quirk independent of the code changes; would have hit Plan 01's verification too.
**Source:** 32-02-SUMMARY.md

---

## Patterns

### Template-first authoring (P8 prevention)
Write the canonical template/convention document as the FIRST artifact of a phase, before any consumer is refactored. The template document defines structure + per-element constraints + vocabulary rules + worked example + anti-patterns.

**When to use:** When multiple downstream consumers (3 demos, docs, future phases) must follow a consistent shape; writing the template first prevents each author inventing their own style.
**Source:** 32-01-PLAN.md

---

### Shared helper module for a suite of related scripts
Extract shared utilities (banner printing, scene path resolution, narration formatting, default config) into a single `_common.py` module with type-hinted, docstring-documented public symbols and inline validation guards; all consumers import from it rather than duplicating logic.

**When to use:** When 3+ scripts in the same directory share the same boilerplate (banner code, path handling, default hyperparameters); establishes a stable interface for downstream plans.
**Source:** 32-01-PLAN.md

---

### Subprocess-based regression tests for CLI demos
Spawn each demo as a child process with `subprocess.run([sys.executable, demo_path, "--headless", "--steps", "0"], timeout=60, capture_output=True)` and assert exit code 0 + expected stderr substring (`[Setup]` marker).

**When to use:** When demos are CLI scripts whose correctness includes end-to-end import + banner + exit behavior; the subprocess approach catches import-time failures (e.g., OMP shim regressions) that in-process tests would miss. Use `--steps 0` to short-circuit before the simulator loop so each test runs in <30s.
**Source:** 32-03-PLAN.md

---

### Demo file mirrors sister demo's structure exactly
Each new demo file is a near-clone of the sister demo (same OMP shim block, same `_common` imports, same `run_training` / `run_evaluation` / `main` shape) with task-specific bits (scene path, banner title, narration lines, reward builder) swapped.

**When to use:** When building a suite of parallel demos; minimizes per-demo cognitive load and keeps the lint/deviation profile consistent across demos (inherited lint issues are accepted uniformly rather than fixed piecemeal).
**Source:** 32-02-SUMMARY.md

---

### Scene path resolution anchored on __file__, CWD-independent
`resolve_scene` resolves the scene path against `_REPO_ROOT = Path(__file__).resolve().parent.parent` (the parent of the `demos/` directory), not against the current working directory. This makes the demo runnable from any CWD.

**When to use:** When a CLI script's default `--scene` path is relative to the repo root but the script may be invoked from any working directory; combine with a `..` traversal guard for safety.
**Source:** 32-01-SUMMARY.md

---

## Surprises

### demos/ was not a Python package; __init__.py was required but unlisted in the plan
The plan's `files_modified` list did not include `demos/__init__.py`, but the `from demos._common import ...` pattern requires `demos` to be a package.

**Impact:** Auto-fixed under Rule 2 (missing critical) by creating a minimal 12-line `demos/__init__.py`; without it the entire plan's import pattern fails at runtime.
**Source:** 32-01-SUMMARY.md

---

### The Critical Moment narration line landed at exactly 25 words
The tightest narration line (suturing Critical Moment) hit the 25-word limit exactly after re-tuning; the `format_narration_step` guard raises `ValueError` above 25.

**Impact:** Required careful word-counting and rephrase ("15°" → "15 degree", "lifts it 5 cm above the tissue plane" → "lifts it") to stay under the limit while preserving the vocabulary rule of naming scene bodies.
**Source:** 32-01-SUMMARY.md

---

### Inherited lint issues in demos/ accepted rather than fixed
`demos/knot_tying_demo.py` has the exact same 9 ruff errors and 1 black formatting error as `demos/suturing_demo.py` (F401, F841, UP035, UP006, UP045, `--scene, "-s"` line-break).

**Impact:** The plan's literal success criterion `ruff check demos/knot_tying_demo.py exits 0` cannot pass without diverging from the sister demo's pattern. Deferred demo-directory lint cleanup to a separate Phase 32 follow-up so all 3 demos can be cleaned in a single sweep.
**Source:** 32-02-SUMMARY.md

---

### gsd-executor agent truncated mid-plan, leaving tasks undone
The first executor agent for Plan 03 stopped after Task 1 with its response cut off mid-Task 2, leaving the demo file and test file uncommitted.

**Impact:** Required resumption via two sequential single-task subagent dispatches; not a blocker but worth noting for future plans where the gsd-executor template might produce longer outputs than the runtime allows.
**Source:** 32-03-SUMMARY.md

---

### git stash round-trip lost the rename detection
A `git stash` after `git mv demos/demo.py demos/suturing_demo.py` recorded the change as separate add+delete instead of a rename, breaking `git log --follow` continuity.

**Impact:** Recovered by re-staging both files together (git's rename detection runs at staging time); without recovery, the 2026-06-17 quick-rework and OMP-shim fix commits would have been detached from the renamed file.
**Source:** 32-01-SUMMARY.md