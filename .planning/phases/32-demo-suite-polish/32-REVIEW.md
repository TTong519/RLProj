---
status: minor_issues
reviewed-by: gsd-code-reviewer
date: 2026-06-19
phase: 32-demo-suite-polish
files-reviewed: 10
findings-count: 5
severity-breakdown:
  critical: 0
  high: 0
  medium: 2
  low: 3
---

# Phase 32: Demo Suite Polish — Code Review

## Summary

Phase 32 polished the demo suite to a uniform 5-stage narration template by extracting `demos/_common.py` helpers, applying them across the renamed `suturing_demo.py` + 2 new demos (`knot_tying_demo.py`, `needle_passing_demo.py`), adding a dual-arm `MultiAgentConfig` scene, and introducing a 6-test regression suite. The shared `resolve_scene` traversal guard is well-implemented (regex pre-check + authoritative `Path.relative_to`), `format_narration_step` enforces ≤25-word + valid-stage invariants at runtime, and all 6 new tests + 7 OMP-shim tests pass on this host. The change set has no critical bugs or security vulnerabilities; remaining issues are minor code-quality items (unused `pytest` import + missing trailing newline + import-sort order in `tests/test_demos.py`, an inconsistency between `suturing_demo.py` and its sister demos around `DEFAULT_TRAINING_CONFIG` argparse defaults, and a deliberately-simplified test that omits the `task.task_type` assertion).

## Findings

### [MEDIUM-1] `tests/test_demos.py::TestNeedlePassingFixture` omits the `task.task_type == "needle_insertion"` assertion

- **File:** `tests/test_demos.py:177-194`
- **Issue:** The plan called for asserting `scene.task.task_type == "needle_insertion"` (the closest valid Pydantic Literal — `needle_passing` is NOT a valid `TaskConfig.task_type` value per `schema.py:1106-1107`). Per the `32-03-SUMMARY.md` "Deviations from Plan" section, this assertion was deliberately trimmed to keep the test surface minimal. The regression gap is real: Pydantic v2 catches an *invalid* Literal at load time (verified — `model_validate` with `"INVALID_TYPE"` raises `ValidationError`), but a *valid-but-wrong* Literal (e.g., someone changing `needle_insertion` → `suturing`) would silently pass load + the existing test. The point of DEMO-03 was specifically that "needle_passing" was not a valid Literal — losing this assertion removes the guardrail that prevents accidental drift back to an invalid value or migration to a semantically-wrong one.
- **Recommendation:** Re-add the assertion at line ~184:
  ```python
  assert scene.task is not None
  assert scene.task.task_type == "needle_insertion", (
      f"Expected task_type='needle_insertion' (closest valid Pydantic Literal — "
      f"needle_passing is NOT a valid TaskConfig.task_type value), got {scene.task.task_type!r}"
  )
  ```
  This restores the DEMO-03 guardrail without expanding test scope.

### [MEDIUM-2] `demos/suturing_demo.py` argparse defaults remain hardcoded instead of using `DEFAULT_TRAINING_CONFIG`

- **File:** `demos/suturing_demo.py:308-349`
- **Issue:** The plan (`32-01-PLAN.md` Edit 5 area) and the established pattern from `knot_tying_demo.py` / `needle_passing_demo.py` is to source `--algo`, `--steps`, `--max-episode-steps`, `--seed` defaults from `DEFAULT_TRAINING_CONFIG["..."]` dict lookups. `knot_tying_demo.py` and `needle_passing_demo.py` correctly do this (4 lookups each). However, `suturing_demo.py` still uses hardcoded literals (`default="PPO"`, `default=50000`, `default=2000`, `default=42`). The `32-01-SUMMARY.md` is silent on this. If `DEFAULT_TRAINING_CONFIG` is ever evolved (e.g., `total_timesteps: 100_000`), the suturing demo will silently keep the old defaults, causing inconsistency between the three demos in the same suite. The shared `algo_kwargs = {**DEFAULT_TRAINING_CONFIG, "name": args.algo}` at line 134 *does* use the dict for the `AlgorithmConfig` constructor — so the inconsistency is specifically in the argparse default layer.
- **Recommendation:** Replace the 4 hardcoded argparse defaults with `DEFAULT_TRAINING_CONFIG["..."]` lookups to match the sister demos. Example:
  ```python
  parser.add_argument(
      "--algo", "-a",
      type=str, choices=["PPO", "SAC", "A2C"],
      default=DEFAULT_TRAINING_CONFIG["algorithm"],
      help=f"RL algorithm (default: {DEFAULT_TRAINING_CONFIG['algorithm']})",
  )
  # (same pattern for --steps, --max-episode-steps, --seed)
  ```

### [LOW-1] `tests/test_demos.py` has 3 ruff lint errors

- **File:** `tests/test_demos.py:14-24, 22, 194`
- **Issue:** `ruff check tests/test_demos.py` reports 3 errors that are auto-fixable with `ruff check --fix`:
  1. **I001** (line 14) — Import block ordering: `from __future__ import annotations` should come before stdlib (`hashlib`, `os`, etc.). `pytest.ini` runs `ruff` as part of the lint pipeline, and `tests/` is in the lint scope (only `demos/*.py` is exempt).
  2. **F401** (line 22) — `pytest` is imported but never used (no `@pytest.fixture`, `@pytest.mark`, etc.). Either remove the import or convert `TestDemoRegression` etc. to use pytest features.
  3. **W292** (line 194) — Missing trailing newline at end of file.
- **Recommendation:** Run `ruff check tests/test_demos.py --fix` to auto-resolve all 3. Also run `black tests/test_demos.py` — `black --check tests/test_demos.py` fails on 3 multi-line f-strings in the assertion messages (black wants `f"..." f"..."` collapsed onto one line — purely cosmetic).

### [LOW-2] `_count_words` in `_common.py` is inconsistent with itself on hyphenated tokens

- **File:** `demos/_common.py:167-169`
- **Issue:** `_count_words` uses `re.findall(r"\b\w+\b", text)` which splits on word boundaries. For inputs like `"needle-passing"`, this counts as 2 tokens (`needle` + `passing`); for `"needle_passing"`, it counts as 1 token. The 32-02 + 32-03 narration lines intentionally use `"needle-passing"` (hyphen) and `"knot-tying"` (hyphen) in places, while the actual scene bodies use underscores (`needle_passing` is mentioned via `curved_passing_needle`). This isn't a bug (the guards all pass on current text — verified all narration lines ≤25 words), but it's a subtle inconsistency: if a future demo author writes `"knot-tying-scene"` thinking it's one token, the count will surprise them. The template documents "≤25 words per sentence" but doesn't define how to count compound words.
- **Recommendation:** Add a one-line note to `NARRATION_TEMPLATE.md`'s "Per-Stage Constraints" section clarifying that compound words split on hyphens (so `knot-tying-scene` = 3 words), and that `re.findall(r"\b\w+\b", ...)` is the canonical counter.

### [LOW-3] `print_scene_info` does not guard `scene.task.objectives` against empty list

- **File:** `demos/_common.py:110-113`
- **Issue:** `_common.print_scene_info` correctly guards `if scene.task is not None` but then unconditionally iterates `for obj in scene.task.objectives:`. If a scene has `task` set with `objectives=[]` (an empty list, which is valid per `TaskConfig.objectives: list[TaskObjective] = Field(default_factory=list)`), the loop silently emits nothing — not a bug, but the printed output ("Task: foo" with no objective bullets) looks like the scene has no objectives when in fact it has an explicitly-empty list. Minor: the test fixtures and current scenes all have ≥2 objectives, so this isn't currently triggered, but the guard would future-proof it.
- **Recommendation:** Either add an explicit `if scene.task.objectives:` branch that prints "  (no objectives)" when empty, or leave as-is and document the implicit behavior. Lowest-priority item — flagging for completeness.

---

## Files Reviewed (10)
- `demos/NARRATION_TEMPLATE.md` — clean 64-line template, 5 stage headings + vocabulary rules + worked example; lint-clean.
- `demos/__init__.py` — minimal 14-line package docstring; clean.
- `demos/_common.py` — well-implemented helpers; `resolve_scene` traversal guard verified via `resolve_scene("../etc/passwd")` raising `ValueError`; `format_narration_step` word + stage guards verified; `DEFAULT_TRAINING_CONFIG` has 12 keys as documented; lint-clean.
- `demos/suturing_demo.py` — renamed + refactored; imports from `demos._common`; narration follows template; minor inconsistency: argparse defaults remain hardcoded instead of using `DEFAULT_TRAINING_CONFIG` lookups (see MEDIUM-2).
- `demos/knot_tying_demo.py` — clean; correctly sources argparse defaults from `DEFAULT_TRAINING_CONFIG`; KNOT_TIER instrument vocabulary rule satisfied (3 mentions of `knot_driver` in narration).
- `demos/needle_passing_demo.py` — clean; correctly sources argparse defaults from `DEFAULT_TRAINING_CONFIG`; dual-arm vocabulary rule satisfied (both `surgeon_arm` and `assistant_arm` named in Setup narration).
- `scenes/needle_passing.json` — dual-arm `MultiAgentConfig` with `surgeon` + `assistant` roles; `task.task_type='needle_insertion'` (closest valid Pydantic Literal); loads cleanly via `load_scene()` (verified — `s.task.task_type == 'needle_insertion'`, `len(s.robots) == 2`, `len(s.multi_agent.arm_configs) == 2`, roles = `['surgeon', 'assistant']`).
- `tests/fixtures/scenes/knot_tying.json` — byte-identical copy of `scenes/knot_tying.json` (verified `diff -q` exit 0; SHA-256 matches).
- `tests/test_demos.py` — 6-test regression suite across 4 classes; all 6 tests pass on this host; missing 3 ruff lint fixes + missing `task.task_type` assertion (see MEDIUM-1, LOW-1).
- `tests/test_omp_compat_shim.py` — updated to reference `suturing_demo.py` instead of `demo.py`; all 7 tests pass; OMP shim contract preserved.

---

_Reviewed: 2026-06-19T17:10:00Z_
_Reviewer: OpenCode (gsd-code-reviewer)_
_Depth: deep (cross-file analysis + trace call chains across the demo suite)_