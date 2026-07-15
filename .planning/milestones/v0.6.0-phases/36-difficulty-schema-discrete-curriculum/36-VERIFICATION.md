---
phase: 36-difficulty-schema-discrete-curriculum
verified: 2026-06-24T00:00:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 36: Difficulty Schema + Discrete Curriculum — Verification Report

**Phase Goal:** Researchers can define per-level difficulty overrides (tissue stiffness, precision tolerance, tool noise, time limit) that apply additively over the existing `interpolate_params()` baseline, and the curriculum can advance through discrete EASY→MEDIUM→HARD levels without touching the validated continuous `advance_stage` path.
**Verified:** 2026-06-24
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth (SC) | Status | Evidence (file:line) |
| -- | ---------- | ------ | -------------------- |
| 1  | SC#1 — `DifficultyLevelConfig` Pydantic v2 leaf with 4 Optional[float] override fields + range validators against D-07 global union bounds | ✓ VERIFIED | `src/surg_rl/rl/difficulty.py:56-97` — `class DifficultyLevelConfig(BaseModel)` with `tissue_stiffness`/`target_precision_tolerance`/`tool_position_noise`/`time_limit` all `float \| None = None`; 4 `@field_validator` methods. Bounds recomputed independently from `rewards.py` PARAM_BOUNDS (min/max over all endpoints, Pitfall 1): tissue_stiffness [50.0,300.0], target_precision_tolerance [0.002,0.3], tool_position_noise [0.01,0.08], time_limit [30.0,180.0] — all 4 match the validators exactly. `test_difficulty_config.py::TestDifficultyLevelConfig` (in-range, out-of-range parametrized, type rejection) GREEN. |
| 2  | SC#2 — `compose_difficulty_overrides` ADDITIVE over `interpolate_params(level.value)` (interpolate first, absolute-replace only mapped keys; D-06); unmapped warns + keeps interpolated (D-04, no raise); `ABSTRACT_TO_CONCRETE` 6 keys (D-05) | ✓ VERIFIED | `src/surg_rl/dynamics/difficulty_wiring.py:85-135` — `composed = reward_cls.interpolate_params(level.value)` first (L118); `ABSTRACT_TO_CONCRETE.get(task_type, {})` (L119, no KeyError — T-36-03); `logger.warning` on unmapped (L127-131, D-04); absolute replace `composed[concrete_key] = override_value` (L134, D-06). `ABSTRACT_TO_CONCRETE` (L30-61) has exactly 6 task_type keys; every concrete key verified present in the corresponding reward class `PARAM_BOUNDS` (checked via `rewards.py` import). `test_compose_truth_table` (parametrized over all 6 tasks × 3 levels × mapped fields) + `test_compose_empty_levels_equals_interpolation` + `test_unmapped_override_warns` all GREEN. |
| 3  | SC#3 — `CurriculumScheduler` additive `progression_mode` (continuous/discrete, default continuous) + `set_difficulty_level`/`advance_level` (EASY→MEDIUM→HARD→False, D-12) on separate `_current_level` axis + `current_difficulty` mode branch | ✓ VERIFIED | `src/surg_rl/dynamics/curriculum.py`: `progression_mode: Literal["continuous","discrete"] = "continuous"` (L92) + `discrete_config` (L96); `_current_level`/`_level_entry_episode`/`_level_order` (L200-207); `set_difficulty_level` (L290-303); `advance_level` (L305-331) — HARD terminal returns False (L322), uses `_meets_success_threshold(self.curriculum_config.min_success_rate)` (L327, corrected D-11); `current_difficulty` mode branch (L237-240); `_meets_success_threshold` shared helper (L596-616). `test_discrete_curriculum.py::TestDiscreteProgression` (init defaults, set, advance transitions, mode branch, auto-advance) GREEN. |
| 4  | SC#4 — continuous `advance_stage`/`update_curriculum` byte-identical; full v0.4.0+v0.4.2 suite passes UNCHANGED (additive-regression gate) | ✓ VERIFIED | `git diff 9434da1^..HEAD -- src/surg_rl/dynamics/curriculum.py` shows NO `-` lines touching `advance_stage` (only additive `+` comments + the `_should_advance` pure refactor extracting `_meets_success_threshold`). `update_curriculum` discrete branch is additive (L529-542), continuous branch (L544-559) unchanged. Gate: `228 passed, 33 skipped` (33 skips are GUI-display skips in `test_viewport`). `test_dynamics.py` (full v0.4.0/v0.4.2 curriculum suite) + `test_difficulty_levels.py` + `test_advance_stage_unchanged` parity all GREEN. |
| 5  | SC#5 — `DifficultyLevelConfig` zero-in-project-import leaf; one-way edge curriculum → difficulty_wiring → rl.difficulty; no Pydantic cross-package cycle | ✓ VERIFIED | `grep -v '^\s*#' src/surg_rl/rl/difficulty.py \| grep -c 'surg_rl\.'` = 0 (leaf). `difficulty_wiring.py` imports only `from surg_rl.rl.difficulty import ...` + `from surg_rl.utils.logging` (L21-22); 0 reverse edges to `curriculum`/`scene_definition`/`task_reward_router`. `curriculum.py` late bottom-of-file import (L736) `from surg_rl.dynamics.difficulty_wiring import DiscreteCurriculumConfig` (one-way). `python -c "import surg_rl.dynamics.curriculum, surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring, surg_rl.rl.difficulty"` → OK (no cycle). `test_leaf_no_inproject_imports` GREEN. |
| 6  | TASK-06 — per-level overrides apply additively over `interpolate_params()`, never replace it | ✓ VERIFIED | Covered by Truths 1 + 2 (SC#1 + SC#2). `compose_difficulty_overrides` always starts from `interpolate_params(level.value)` baseline and only absolute-replaces mapped overridden keys. |
| 7  | TASK-07 — `CurriculumScheduler` advances discrete EASY→MEDIUM→HARD via additive `progression_mode`; continuous float `advance_stage` preserved unchanged | ✓ VERIFIED | Covered by Truths 3 + 4 (SC#3 + SC#4). |

**Score:** 7/7 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/surg_rl/rl/difficulty.py` | `DifficultyLevelConfig` Pydantic v2 leaf + 4 field_validator range checks | ✓ VERIFIED | L56-97. Leaf audit: 0 in-project imports. |
| `src/surg_rl/dynamics/difficulty_wiring.py` | `ABSTRACT_TO_CONCRETE` + `DiscreteCurriculumConfig` + `compose_difficulty_overrides` | ✓ VERIFIED | L30-61 (registry, 6 keys), L72-82 (DiscreteCurriculumConfig), L85-135 (composer). |
| `src/surg_rl/dynamics/curriculum.py` | additive `progression_mode` + `discrete_config` + `_current_level` + `set_difficulty_level`/`advance_level`/`_meets_success_threshold` + `current_difficulty` branch | ✓ VERIFIED | L92, L96, L200-207, L290-331, L596-616, L237-240. |
| `tests/test_difficulty_config.py` | SC#1 + SC#2 + D-04 + SC#5 tests | ✓ VERIFIED | 3 classes: TestDifficultyLevelConfig, TestLeafImportAudit, TestComposeDifficultyOverrides. 40+ tests GREEN. |
| `tests/test_discrete_curriculum.py` | SC#3 + SC#4 parity tests | ✓ VERIFIED | 2 classes: TestDiscreteProgression, TestAdvanceStageParity. 6 tests GREEN. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `difficulty_wiring.py` | `rl/difficulty.py` | `from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig` | ✓ WIRED | L21; used at L82, L88. |
| `difficulty_wiring.py` | `rl/rewards.py` | `reward_cls.interpolate_params(level.value)` (passed-in class) | ✓ WIRED | L118; reward_cls is a parameter — no import, no reverse edge (Open Q3). |
| `curriculum.py` | `difficulty_wiring.py` | late bottom-of-file import of `DiscreteCurriculumConfig` | ✓ WIRED | L736 (PEP 563 forward-ref binding). |
| `test_difficulty_config.py` | `difficulty_wiring.py` + `rl/difficulty.py` + `task_reward_router.py` | imports | ✓ WIRED | L9-15. |
| `test_discrete_curriculum.py` | `curriculum.py` + `rl/difficulty.py` | imports | ✓ WIRED | L16-21. |

### Data-Flow Trace (Level 4)

Not applicable — Phase 36 is pure schema + curriculum-internals (no dynamic-data rendering components, no DB/API layers). The "data flow" is the `interpolate_params` → override-replacement pipeline, verified behaviorally by the truth-table test.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| SC#1 range validation (in + out of range) | `pytest tests/test_difficulty_config.py::TestDifficultyLevelConfig -v` | 8 passed | ✓ PASS |
| SC#2 truth table (additive composition) | `pytest tests/test_difficulty_config.py::TestComposeDifficultyOverrides -v` | all parametrized cases passed | ✓ PASS |
| SC#3 discrete progression + parity | `pytest tests/test_discrete_curriculum.py -v` | 6 passed | ✓ PASS |
| SC#4 additive-regression gate | `pytest tests/test_dynamics.py tests/test_difficulty_levels.py -v` | all passed | ✓ PASS |
| SC#5 no import cycle | `python -c "import surg_rl.dynamics.curriculum, surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring, surg_rl.rl.difficulty"` | OK | ✓ PASS |
| D-07 bounds recomputed from PARAM_BOUNDS | `python -c "...endpoints..."` | tissue[50,300] tol[0.002,0.3] noise[0.01,0.08] time[30,180] — match validators | ✓ PASS |

### Probe Execution

No phase-declared probes (`scripts/*/tests/probe-*.sh`). Phase uses pytest gates only (re-run above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TASK-06 | 36-01, 36-02 | Per-level difficulty overrides apply additively over `interpolate_params()` | ✓ SATISFIED | SC#1 + SC#2 (Truths 1, 2, 6) |
| TASK-07 | 36-03 | `CurriculumScheduler` discrete EASY→MEDIUM→HARD via additive `progression_mode`; continuous preserved | ✓ SATISFIED | SC#3 + SC#4 (Truths 3, 4, 7) |
| TASK-09 | 36-01..03 | v0.4.0 + v0.4.2 curriculum suite passes unchanged (additive-regression gate) | ✓ SATISFIED | 228 passed, 33 skipped; `advance_stage` byte-identical (Truth 4) |

No orphaned requirements. REQUIREMENTS.md maps TASK-06, TASK-07, TASK-09 to Phase 36; all three claimed by plans and satisfied.

### Threat-Model Mitigation Verification

| Threat | Mitigation | Status | Evidence |
| ------ | ---------- | ------ | -------- |
| T-36-01 | Pydantic range validators reject out-of-range overrides (ASVS V5) | ✓ PRESENT | `rl/difficulty.py:71-97` — 4 `@field_validator` methods |
| T-36-02 | Leaf stays zero in-project imports (cycle DoS) | ✓ PRESENT | leaf audit = 0; `test_leaf_no_inproject_imports` GREEN |
| T-36-03 | `ABSTRACT_TO_CONCRETE.get(task_type, {})` — no KeyError on unknown task | ✓ PRESENT | `difficulty_wiring.py:119` |
| T-36-04 | Override values range-validated at schema time | ✓ PRESENT | Plan 01 validators (T-36-01) |
| T-36-05 | One-way import edge, no Pydantic cross-package cycle | ✓ PRESENT | `difficulty_wiring.py` imports only leaf; `curriculum.py` late one-way import; import-both OK |
| T-36-08 | `advance_level` uses shared `_meets_success_threshold(min_success_rate)`, no stage-coupling | ✓ PRESENT | `curriculum.py:327, 596-616` |

### Anti-Patterns Found

None. `grep -nE "TBD|FIXME|XXX"` on the 3 touched source files + 2 test files → no matches. No placeholder/stub patterns; no `return None`/`return {}` stubs in the new code paths. No debt markers.

### Gate Results (Independently Re-Confirmed)

| # | Gate | Command | Result | Status |
| - | ---- | ------- | ------ | ------ |
| 1 | Phase suite | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py tests/test_difficulty_config.py tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_file_operations.py tests/test_viewport.py tests/test_environment_controller.py -q` | 228 passed, 33 skipped (GUI-display skips in test_viewport) | ✓ PASS |
| 2 | SC#5 import cycle | `python -c "import surg_rl.dynamics.curriculum, surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring, surg_rl.rl.difficulty"` | OK | ✓ PASS |
| 3 | Lint + format | `ruff check` + `black --check` on 3 source files | All checks passed / 3 files unchanged | ✓ PASS |
| 4 | mypy (delta) | `mypy` on 3 source files | 3 errors, ALL pre-existing in `curriculum.py` (L387 `apply_parameters` untyped pre-existing, L414 `pybullet` stub import, L618 `episode_end_with_task_result` untyped pre-existing from Phase 35). New Plan 03 methods (`set_difficulty_level` L290, `advance_level` L305, `_meets_success_threshold` L596, `current_difficulty` L228) all fully type-annotated. **Phase 36 mypy delta = 0 new errors.** | ✓ PASS |
| 5 | RL test crash (environment) | `PYTHONPATH=src pytest tests/test_rl.py -q` | `Fatal Python error: Aborted` in `libomp.dylib` (`__kmp_unregister_library` / `__kmp_register_library_startup`) — torch/OpenMP incompatibility on Python 3.14.6 at `import torch` time. Crashes BEFORE any difficulty/curriculum code is exercised (test_rl.py imports `surg_rl.rl.training` → torch). Pre-existing on baseline `9434da1^`. | ⚠️ ENVIRONMENT (not a Phase 36 regression) |

### Pre-Existing Environment Note (test_rl.py / test_rl_callbacks.py native crash)

`tests/test_rl.py` and `tests/test_rl_callbacks.py` abort with `Fatal Python error: Aborted` originating in `torch/lib/libomp.dylib` (`__kmp_unregister_library`), a known torch/OpenBLAS/OpenMP incompatibility on macOS Python 3.14.6. The crash occurs at `import torch` (pulled in via `surg_rl.rl.training`), before any Phase 36 surface (`DifficultyLevelConfig`, `compose_difficulty_overrides`, `CurriculumScheduler.progression_mode`) is imported or exercised. Confirmed pre-existing on baseline `9434da1^` (before Phase 36 commits). The RL environment uses `CurriculumScheduler` via the additive DEFAULT-continuous path (byte-identical, SC#4); the discrete path is not on the RL import/call chain. This is an environment limitation, not a phase failure.

### Human Verification Required

None. All phase behaviors have automated verification (pure schema + curriculum-internals phase; no GUI, no simulator, no deployment per 36-VALIDATION.md §Manual-Only Verifications).

### Gaps Summary

No gaps. All 3 requirements (TASK-06, TASK-07, TASK-09) and all 5 Success Criteria (#1–#5) are verified in the live codebase with `file:line` evidence. All 6 threat-model mitigations present. All 4 gates (suite, cycle, lint/format, mypy-delta) re-confirmed independently; the 5th (RL native crash) is a documented pre-existing environment issue unrelated to Phase 36 surfaces.

---

_Verified: 2026-06-24_
_Verifier: Claude (gsd-verifier)_