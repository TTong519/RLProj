---
phase: 37-scene-level-difficulty-blocks-env-wiring
verified: 2026-06-24T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: N/A
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 37: Scene-Level difficulty_blocks + Env Wiring — Verification Report

**Phase Goal:** Scene JSON authors can specify `difficulty_blocks` per level on a task, and `SurgicalEnv` applies them at construction with a single, documented, tested override-precedence chain — so a researcher loading a scene with hard-mode blocks gets a hard-mode environment without code changes.
**Verified:** 2026-06-24
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| #   | Truth (SC) | Status | Evidence (empirical — run, not inferred) |
| --- | ---------- | ------ | ---------------------------------------- |
| 1   | A scene JSON with `difficulty_blocks` for all three levels loads via `SceneLoader` without error and the blocks round-trip through Pydantic v2 validation. | ✓ VERIFIED | `tests/test_difficulty_blocks.py::TestSceneBlocksRoundTrip::test_scene_with_blocks_round_trips` PASSED. Test authors all 3 levels (EASY/MEDIUM/HARD `target_precision_tolerance`), loads via `SceneLoader().load_from_string`, asserts `DifficultyLevel` enum keys present + authored values preserved (0.02/0.005/0.002) + `model_dump()`→`TaskConfig.model_validate()` re-serialization round-trip. Negative cases (6 v0.4.0 scenes load with `difficulty_blocks is None`) + malformed-rejection (out-of-range `target_precision_tolerance=999.0` raises `SceneValidationError`) all PASSED. |
| 2   | `SurgicalEnv._setup_rewards` applies overrides in documented precedence: `difficulty_blocks[level]` > `TaskConfig.difficulty_level` > `config.difficulty` > default 0.5 — verified by a parametrized truth-table test. | ✓ VERIFIED | `TestPrecedenceTruthTable::test_precedence_resolution` — 5 parametrized cases PASSED. The test genuinely distinguishes all 4 levels: `blocks` case asserts `SuturingReward.position_threshold == 0.008` (the composed override, DISTINCT from the HARD interpolated baseline 0.002); `task_difficulty_level` case asserts `interpolate_params(1.0)`; `config_difficulty` asserts `interpolate_params(0.25)`; `default` asserts `interpolate_params(0.5)`. Code at `environment.py:503-562` implements the chain: `task.difficulty_level` → `getattr(config,"difficulty",0.5)` → `difficulty_float` → blocks branch (Q4 `isinstance(difficulty, DifficultyLevel)` guard, lazy-local import of `compose_difficulty_overrides` at line 542). Behavior-dependent (state-transition truth) verified by a passing behavioral test. |
| 3   | Loading all 6 v0.4.0 task scene fixtures with each of the 3 difficulty levels succeeds and produces a stepped environment (regression gate). | ✓ VERIFIED | `TestSixSceneThreeLevelRegression::test_six_scenes_three_levels_construct_and_step` — 18 cases (6 scenes × 3 levels) PASSED. Fixtures confirmed present at `scenes/{simple_suturing,knot_tying,needle_insertion,grasping,cutting,dissection}.json`. Each case loads via `SceneLoader`, mutates `task.difficulty_level`, constructs `SurgicalEnv`, asserts `_reward_fn is not None` + `_task_difficulty == {0.0|0.5|1.0}`, calls `env.reset()`+`env.step()` and asserts a well-formed 5-tuple. Behavior-dependent (env.step 5-tuple) verified by passing tests. |
| 4   | Existing v0.4.2 fixture `suturing_difficulty_hard.json` still loads and produces the same difficulty scalar it did before this phase (back-compat gate). | ✓ VERIFIED | `TestHardFixtureScalarEquivalence::test_hard_fixture_scalar_unchanged` PASSED. Fixture confirmed present at `tests/fixtures/scenes/suturing_difficulty_hard.json`. Test asserts `scene.task.difficulty_level == DifficultyLevel.HARD` (v0.4.2 authored `1.0` coerced to enum), `difficulty_blocks is None` (blocks branch inert), `env._task_difficulty == 1.0` (literal byte-identical scalar, not computed). |
| 5   | Naming drift reconciled: `difficulty_blocks` is the canonical field name across PROJECT.md, schema, and STATE.md (prior `difficulty_levels` spelling is gone). | ✓ VERIFIED | `grep -rn "difficulty_levels" .planning/PROJECT.md .planning/STATE.md src/surg_rl/` → exit 1 (no hits). `TestNamingAudit::test_no_drift_spelling_in_canonical_docs` (subprocess grep audit) PASSED. Schema field `difficulty_blocks` at `schema.py:1122` is the canonical spelling. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/surg_rl/scene_definition/schema.py` | `TaskConfig.difficulty_blocks` field + `field_validator(mode=before)` + late-import + `model_rebuild()` | ✓ VERIFIED | Field at line 1122 (`dict[DifficultyLevel, DifficultyLevelConfig] \| None`), validator `_coerce_difficulty_blocks_keys` at line 1133, extended late-import at line 1545 imports both `DifficultyLevel` + `DifficultyLevelConfig`, single `TaskConfig.model_rebuild()` at line 1553. No `from surg_rl.dynamics.*` import (Pitfall 4 guard). Import-cycle check: `python -c "import surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring, surg_rl.dynamics.curriculum"` → OK. |
| `src/surg_rl/rl/environment.py` | `SurgicalEnvConfig.difficulty: float = 0.5` + additive `_setup_rewards` precedence branch | ✓ VERIFIED | `SurgicalEnvConfig.difficulty` at line 101. Blocks branch at lines 521-562: `getattr(task,"difficulty_blocks",None)` read, `isinstance(difficulty, DifficultyLevel)` Q4 guard, `difficulty in blocks` check, lazy-local import of `compose_difficulty_overrides` + `TASK_REWARD_REGISTRY` inside branch (line 542-543), `reward_list[0].apply_params(params)` override, early return before existing router branch. Existing curriculum/router branches untouched. |
| `src/surg_rl/rl/rewards.py` | `apply_params(params)` on BaseRewardFunction + 6 task rewards; `apply_difficulty` delegates | ✓ VERIFIED | `grep` confirms 7 `def apply_params` (1 base no-op + 6 task) and 6 `self.apply_params(self.interpolate_params(difficulty))` delegates. Pure refactor — observable output unchanged (test_apply_params_delegates_on_suturing PASSED). |
| `src/surg_rl/dynamics/difficulty_wiring.py` | `compose_difficulty_overrides` + `DiscreteCurriculumConfig` + `ABSTRACT_TO_CONCRETE` | ✓ VERIFIED | `compose_difficulty_overrides` at line 85, `DiscreteCurriculumConfig` at line 72, `ABSTRACT_TO_CONCRETE` at line 30. Consumed by environment.py blocks branch. |
| `tests/test_difficulty_blocks.py` | 35-test cumulative regression file covering all 5 SCs | ✓ VERIFIED | 35 tests collected, 35 passed in 1.26s. All 5 SC test classes present. |
| `.planning/PROJECT.md`, `.planning/STATE.md` | Naming reconciliation (SC#5) | ✓ VERIFIED | Drift spelling gone — grep returns exit 1. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `schema.py` `TaskConfig.difficulty_blocks` | `rl.difficulty.DifficultyLevelConfig` | late-import at `schema.py:1545` + `TaskConfig.model_rebuild()` at 1553 | ✓ WIRED | Single `model_rebuild()` resolves both `DifficultyLevel` + `DifficultyLevelConfig` forward refs; import-cycle check OK. |
| `environment.py` `_setup_rewards` blocks branch | `dynamics.difficulty_wiring.compose_difficulty_overrides` | function-body lazy-local import at `environment.py:542` | ✓ WIRED | Lazy-local (not module-level) — Pitfall 4 guard; verified by grep. |
| `environment.py` blocks branch | `rl.task_reward_router.TASK_REWARD_REGISTRY` + `TaskRewardRouter` | lazy-local import at `environment.py:543` + `TaskRewardRouter(difficulty=difficulty_float).build(task_type)` at 553-554 | ✓ WIRED | `reward_list[0].apply_params(params)` at line 560 applies the composed override. |
| `rewards.py` 6 task rewards | `apply_params` (new) + `interpolate_params` (existing) | `apply_difficulty` delegates via `self.apply_params(self.interpolate_params(difficulty))` | ✓ WIRED | 6 delegates confirmed by grep; refactor regression test PASSED. |
| Scene JSON `difficulty_blocks` string keys | `DifficultyLevel` enum members | `field_validator(mode="before")` `_coerce_difficulty_blocks_keys` via `DifficultyLevel[key]` | ✓ WIRED | Round-trip test confirms `"EASY"/"MEDIUM"/"HARD"` string keys → enum members. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `SuturingReward.position_threshold` | `params["needle_position_tolerance"]` | `compose_difficulty_overrides` (P36-02) → `apply_params` | Yes — composed from authored `DifficultyLevelConfig.target_precision_tolerance` (0.008 in blocks case) | ✓ FLOWING |
| `env._task_difficulty` | resolved `difficulty` scalar | `task.difficulty_level` / `config.difficulty` / curriculum / 0.5 default | Yes — varies per truth-table case (1.0/1.0/0.25/0.5) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| SC#2 precedence truth-table (state transition) | `pytest tests/test_difficulty_blocks.py -k "Precedence or Truth"` | 5 passed | ✓ PASS |
| SC#3 6×3 scene construct+step (5-tuple invariant) | `pytest tests/test_difficulty_blocks.py -k "Regression"` | 18 passed | ✓ PASS |
| SC#4 back-compat scalar (byte-identical 1.0) | `pytest tests/test_difficulty_blocks.py -k "HardFixture or Scalar"` | 1 passed | ✓ PASS |
| Additive-regression gate (TASK-09 continuous path unchanged) | `pytest tests/test_difficulty_levels.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_dynamics.py -q` | 204 passed | ✓ PASS |
| Import-cycle invariant | `python -c "import surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring, surg_rl.dynamics.curriculum"` | OK | ✓ PASS |

### Probe Execution

Not applicable — this phase declares no `scripts/*/tests/probe-*.sh` probes and is not a migration/tooling phase. The verification surface is the `tests/test_difficulty_blocks.py` regression file (run in isolation per the macOS pre-existing backend-abort caveat).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TASK-08 | 37-01, 37-02, 37-03 | Scene-level `difficulty_blocks` + env wiring | ✓ SATISFIED | All 5 SCs verified empirically; 35 tests pass. |

No orphaned requirements found for this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `tests/test_difficulty_blocks.py` | 81 | Stale doc comment: "Pydantic v2 coerces JSON string keys by float value" — actual coercion is by name via `field_validator(mode="before")` using `DifficultyLevel[key]` (auto-fixed in 37-01 deviation #1) | ℹ️ Info | Comment-only staleness; functional behavior is correct (test passes). No action required. |
| `src/surg_rl/rl/environment.py` | — | 5 pre-existing ruff errors + pre-existing black reformatting debt (F821 ControllerBridge, SIM105, etc.) | ℹ️ Info | Pre-existing baseline debt, unchanged by this phase (verified via `git stash` per 37-02 SUMMARY). Out of scope. |
| `tests/test_difficulty_blocks.py` | — | 10 pre-existing ruff errors (F401 unused imports, I001, W292) | ℹ️ Info | Pre-existing baseline debt, 0 new errors from this phase (per 37-03 SUMMARY). Out of scope. |

No `TBD`/`FIXME`/`XXX` debt markers in any phase-modified source file. No stub implementations in `schema.py`, `environment.py`, or `rewards.py`.

### Human Verification Required

None. All 5 success criteria are verified empirically by automated tests run in this verification session:
- SC#1, SC#5: deterministic round-trip + grep audits — PASSED.
- SC#2, SC#3: behavior-dependent truths (state-transition + env.step 5-tuple invariant) each exercised by a passing named behavioral test — VERIFIED (not merely present).
- SC#4: byte-identical scalar comparison — PASSED.

The macOS MuJoCo/PyBullet backend abort caveat is documented in 37-03-SUMMARY and handled in SC#3 via a degrade-to-construct-only `pytest.skip` fallback citing the pre-existing 36-03-SUMMARY cause; on this verification host the full-step path ran cleanly (no skips).

### Gaps Summary

No gaps. All 5 roadmap success criteria are verified against the live codebase by running the actual tests. The phase goal — a researcher loading a scene with hard-mode blocks gets a hard-mode environment without code changes — is achieved: the `difficulty_blocks` field round-trips through Pydantic v2, `_setup_rewards` applies the documented 4-level precedence chain (verified by a truth-table test that distinguishes all 4 levels with distinct observables), the 6 v0.4.0 scenes load+construct+step under all 3 levels, the v0.4.2 hard fixture's scalar is byte-identical to pre-phase, and the `difficulty_levels` drift spelling is gone from canonical docs + schema.

---

_Verified: 2026-06-24_
_Verifier: Claude (gsd-verifier)_

## Verification Complete

**Status:** passed
**Score:** 5/5 must-haves verified
**Report:** /Users/tt/Documents/RLProj/.planning/phases/37-scene-level-difficulty-blocks-env-wiring/37-VERIFICATION.md

All 5 roadmap success criteria verified empirically against the live codebase by running `tests/test_difficulty_blocks.py` (35 passed) and the additive-regression gate (204 passed). Phase goal achieved — scene JSON authors can specify `difficulty_blocks` per level and `SurgicalEnv` applies them at construction with the documented, tested 4-level precedence chain. Ready to proceed to the next phase.