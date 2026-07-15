---
phase: 37-scene-level-difficulty-blocks-env-wiring
plan: 01
subsystem: scene_definition
tags: [schema, pydantic-v2, difficulty-blocks, tdd, naming-audit]
requires:
  - "36-01: DifficultyLevelConfig Pydantic v2 leaf (rl.difficulty)"
  - "35: v0.4.2 string forward-ref + late-import + model_rebuild() canon"
provides:
  - "TaskConfig.difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] | None = None (scene-author input surface)"
  - "TaskConfig._coerce_difficulty_blocks_keys field_validator(mode=before) — JSON enum-name string key coercion"
  - "Extended late-import block binding DifficultyLevelConfig alongside DifficultyLevel"
  - "tests/test_difficulty_blocks.py::TestSceneBlocksRoundTrip + TestNamingAudit (SC#1 + SC#5)"
affects:
  - "src/surg_rl/scene_definition/schema.py (TaskConfig + late-import block)"
  - ".planning/PROJECT.md (lines 23, 82 — naming + shape reconciliation)"
  - ".planning/STATE.md (lines 82, 131 — naming + shape reconciliation)"
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 string forward-ref + late-import + model_rebuild() (v0.4.2 canon, extended)"
    - "field_validator(mode=before) for float-enum dict-key name coercion (new — DifficultyLevel is a _FloatMixin so default value-based coercion rejects name strings)"
    - "function-body lazy local import inside validator (cycle-safe; rl.difficulty is a P36-01 leaf)"
key-files:
  created:
    - "tests/test_difficulty_blocks.py"
  modified:
    - "src/surg_rl/scene_definition/schema.py"
    - ".planning/PROJECT.md"
    - ".planning/STATE.md"
decisions:
  - "Q3 field shape: dict[DifficultyLevel, DifficultyLevelConfig] | None directly on TaskConfig (flat for scene authors; only rl.difficulty symbols; NO dynamics.* import — Pitfall 4)"
  - "Added field_validator(mode=before) to coerce JSON enum-name string keys (EASY/MEDIUM/HARD) to DifficultyLevel members — DifficultyLevel is a float-enum so Pydantic default value-based coercion rejects name strings; plan's A6 assumption that name strings auto-coerce was incorrect (Rule 1 auto-fix)"
  - "STATE.md:82 reworded to avoid the literal drift spelling — plan target text contained `difficulty_levels` in a historical quote which would have made the SC#5 grep audit fail (internal plan contradiction, Rule 1 auto-fix)"
metrics:
  duration: "~25 min"
  completed: 2026-06-24
  tasks: 3
  files: 4
status: complete
---

# Phase 37 Plan 01: Scene-Level difficulty_blocks Schema Field Summary

JWT-style per-level override field on `TaskConfig` via Pydantic v2 string forward-ref + late-import + `model_rebuild()` canon, with a `field_validator(mode=before)` for JSON enum-name key coercion and SC#5 naming-drift reconciliation across PROJECT.md + STATE.md.

## What Was Built

### Task 1 (RED) — `tests/test_difficulty_blocks.py`
Created the shared test file (37-01/02/03) with the 37-01 subset only:
- `TestSceneBlocksRoundTrip.test_scene_with_blocks_round_trips` — authors a scene JSON string with `task.difficulty_blocks` for all 3 levels (EASY/MEDIUM/HARD, `target_precision_tolerance` overrides inside D-07 bounds [0.002, 0.3]), `SceneLoader().load_from_string(json, format="json")` succeeds, asserts DifficultyLevel enum keys + authored values preserved + `model_dump()`/`TaskConfig.model_validate()` re-serialization round-trip.
- `TestSceneBlocksRoundTrip.test_existing_scenes_load_without_blocks` — parametrized over the 6 v0.4.0 task scenes (simple_suturing, knot_tying, needle_insertion, grasping, cutting, dissection); each loads with `scene.task.difficulty_blocks is None`. Canonical SC#1 negative regression name shared with 37-03 Task 2 + 37-VALIDATION.md row 37-SC1-neg.
- `TestSceneBlocksRoundTrip.test_malformed_blocks_rejected` — out-of-range override (`target_precision_tolerance=999.0`) raises `SceneValidationError` (wraps `pydantic.ValidationError`) at load time (ASVS V5 / T-37-01).
- `TestNamingAudit.test_no_drift_spelling_in_canonical_docs` — `subprocess.run(["grep", "-rn", "difficulty_levels", ...])` across PROJECT.md, STATE.md, src/surg_rl/ asserts nonzero exit.

RED confirmed: 9 failed (AttributeError on missing field + drift spelling present).

### Task 2 (GREEN) — `src/surg_rl/scene_definition/schema.py`
- Added `difficulty_blocks: "dict[DifficultyLevel, DifficultyLevelConfig] | None" = Field(default=None, ...)` inside `TaskConfig` immediately after `difficulty_level` (mirrors the existing field shape verbatim with `# noqa: F821`).
- Added `@field_validator("difficulty_blocks", mode="before")` `_coerce_difficulty_blocks_keys` — converts JSON enum-name string keys (`"EASY"`/`"MEDIUM"`/`"HARD"`) to `DifficultyLevel` members. `DifficultyLevel` is a `_FloatMixin(float, Enum)` with values 0.0/0.5/1.0, so Pydantic's default value-based coercion rejects name strings; scene authors author by level name (RESEARCH.md:558-572). Uses a function-body lazy local import of `DifficultyLevel` (cycle-safe — `rl.difficulty` is a P36-01 leaf with zero in-project imports). Stringified floats (`"0.0"`/`"0.5"`/`"1.0"`) and existing enum members pass through unchanged.
- Extended the existing late-import block at `schema.py:1501` from `from surg_rl.rl.difficulty import (DifficultyLevel,)` to `from surg_rl.rl.difficulty import (DifficultyLevel, DifficultyLevelConfig,)` (preserved `# noqa: E402` / `# noqa: F401`). The single existing `TaskConfig.model_rebuild()` call resolves BOTH forward refs.
- NO `from surg_rl.dynamics.*` import added (Pitfall 4 guard — `grep -c 'from surg_rl.dynamics' schema.py` = 0). No second `model_rebuild()` call. `DifficultyLevelConfig` not edited (P36-01 leaf, read-only).

### Task 3 — `.planning/PROJECT.md` + `.planning/STATE.md` (SC#5)
- `PROJECT.md:82` — drift spelling `difficulty_levels: list[3]` replaced with canonical `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig]`; D-29-03 exclusion lifted (Phase 37 ships).
- `PROJECT.md:23` — old `list[3]` shape reconciled to `dict[DifficultyLevel, DifficultyLevelConfig] | None` (RESEARCH.md Open Q3).
- `STATE.md:82` — naming-drift note updated to past-tense Phase 37 attribution; drift spelling removed (reworded to "prior plural-s spelling" to avoid the literal `difficulty_levels` so the SC#5 grep audit passes).
- `STATE.md:131` — deferred-items row shape updated to `dict[DifficultyLevel, DifficultyLevelConfig] | None`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `field_validator(mode=before)` for JSON enum-name key coercion**
- **Found during:** Task 2 (GREEN)
- **Issue:** The plan/PATTERNS asserted (A6) that "Pydantic v2 coerces JSON string keys (`"EASY"`/`"MEDIUM"`/`"HARD"`) to `DifficultyLevel` enum members by float value." This is incorrect: `DifficultyLevel` is a `_FloatMixin(float, Enum)` with values 0.0/0.5/1.0, so Pydantic's default enum-key coercion attempts value-based matching and rejects the name string `"EASY"` (it is not float-coercible and does not match any enum value). The GREEN gate failed with `SceneValidationError: Input should be 0.0, 0.5 or 1.0`.
- **Fix:** Added a `@field_validator("difficulty_blocks", mode="before")` that looks up enum members by name via `DifficultyLevel[key]` (standard `Enum.__getitem__`), falling back to pass-through for stringified floats. Uses a function-body lazy local import of `DifficultyLevel` (cycle-safe — `rl.difficulty` is a P36-01 leaf). The validator runs at validation time, after the module is fully loaded, so the local import is safe.
- **Files modified:** `src/surg_rl/scene_definition/schema.py`
- **Commit:** `af6f0b5`

**2. [Rule 1 - Bug] STATE.md:82 target text contained the drift literal**
- **Found during:** Task 3
- **Issue:** The plan's target text for `STATE.md:82` was `... vs \`difficulty_levels\` (STATE.md) → ... reconciled in Phase 37 ...`. This still contains the literal string `difficulty_levels`, which would make the SC#5 `grep -rn "difficulty_levels"` audit return exit 0 (hits found) and fail `TestNamingAudit` — an internal plan contradiction.
- **Fix:** Reworded to `... vs prior plural-s spelling (STATE.md) → ...` — preserves the historical drift-note meaning without emitting the literal drift spelling. The grep audit now returns exit 1 (no hits) and `TestNamingAudit` passes.
- **Files modified:** `.planning/STATE.md`
- **Commit:** `8dea934`

**3. [Rule 1 - Bug] `test_malformed_blocks_rejected` catches `SceneValidationError`, not `pydantic.ValidationError`**
- **Found during:** Task 1 (RED)
- **Issue:** The plan specified `assert pytest.raises(pydantic.ValidationError)` around `SceneLoader().load_from_string`. `SceneLoader` wraps `pydantic.ValidationError` as `SceneValidationError` (a `SceneLoaderError` subclass) via `raise SceneValidationError(...) from e` (`loader.py:646`). The raised exception is `SceneValidationError`, not `ValidationError`, so `pytest.raises(ValidationError)` would not catch it.
- **Fix:** The test catches `pytest.raises((SceneValidationError, ValidationError))` — accepts both the wrapped and unwrapped forms. This preserves the plan's intent (validation rejects malformed input at load time) while matching the loader's actual exception contract.
- **Files modified:** `tests/test_difficulty_blocks.py`
- **Commit:** `5f9e156`

**4. [Rule 1 - Bug] Added `# noqa: UP037` to the new field annotation**
- **Found during:** Task 2 (GREEN)
- **Issue:** The new `difficulty_blocks: "dict[DifficultyLevel, DifficultyLevelConfig] | None"` string forward-ref triggers ruff UP037 ("remove quotes from type annotation"). The existing `difficulty_level` field (line 1113) has the same UP037 as pre-existing debt (9 UP037 errors pre-exist in the file from the same v0.4.2 forward-ref canon). The acceptance criterion requires "ruff check clean on touched files" — mirroring the existing field exactly would add a 10th UP037.
- **Fix:** Added `# noqa: UP037` to the new annotation line only. My contribution is lint-clean (9 pre-existing UP037 errors remain, unchanged — out of scope per the scope-boundary rule). `black --check` clean.
- **Files modified:** `src/surg_rl/scene_definition/schema.py`
- **Commit:** `af6f0b5`

## Validation

- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py -v` → 9 passed (SC#1 round-trip + SC#5 naming audit)
- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_levels.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_dynamics.py -v` → 213 passed (additive-regression gate, TASK-09 — no existing test edited)
- `python -c "import surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring, surg_rl.dynamics.curriculum"` → OK (no Pydantic cross-package cycle; T-37-02 mitigated)
- `grep -rn "difficulty_levels" .planning/PROJECT.md .planning/STATE.md src/surg_rl/` → no hits (exit 1; SC#5 naming audit)
- `grep -c 'difficulty_blocks:' src/surg_rl/scene_definition/schema.py` → 1
- `grep -c 'DifficultyLevelConfig' src/surg_rl/scene_definition/schema.py` → 3 (field annotation + validator local import + late-import)
- `grep -c 'from surg_rl.dynamics' src/surg_rl/scene_definition/schema.py` → 0 (Pitfall 4 guard)
- `grep -c 'TaskConfig.model_rebuild' src/surg_rl/scene_definition/schema.py` → 1 (single call, not duplicated)
- `ruff check src/surg_rl/scene_definition/schema.py` → 9 pre-existing UP037 errors (unchanged from pre-phase baseline; my new line suppressed via `# noqa: UP037`)
- `black --check src/surg_rl/scene_definition/schema.py` → clean

## TDD Gate Compliance

- RED gate: `test(37-01):` commit `5f9e156` — 9 tests fail before schema field added (AttributeError on missing `difficulty_blocks` + drift spelling present in canonical docs).
- GREEN gate: `feat(37-01):` commit `af6f0b5` — `TestSceneBlocksRoundTrip` (8 tests) green after field + validator + late-import extension.
- Naming-audit gate: `docs(37-01):` commit `8dea934` — `TestNamingAudit` green after PROJECT.md + STATE.md reconciliation; all 9 `test_difficulty_blocks.py` tests green.

## Known Stubs

None. The `difficulty_blocks` field is fully wired at the schema layer (Pydantic v2 validation + round-trip + malformed rejection). The override-consumption seam (`SurgicalEnv._setup_rewards` precedence branch + `rewards.apply_params`) is Plan 02's responsibility (T-37-03 accepted for this plan; the field is intentionally inert until Plan 02 wires the env branch).

## Threat Flags

None. No new security-relevant surface beyond the plan's `<threat_model>` (T-37-01 input validation mitigated via inherited D-07 range validators + the new field_validator; T-37-02 cross-package cycle mitigated via the extended late-import + single `model_rebuild()`; T-37-03 inert-surface accepted for this plan). The `field_validator(mode=before)` is a name-lookup coercion (`DifficultyLevel[key]`) — invalid names raise `KeyError` and fall through to Pydantic's value-based coercion, which then raises `ValidationError` for unknown strings. No new network/auth/file-access surface.

## Self-Check: PASSED

- `tests/test_difficulty_blocks.py` — FOUND
- `src/surg_rl/scene_definition/schema.py` — FOUND (modified)
- `.planning/PROJECT.md` — FOUND (modified)
- `.planning/STATE.md` — FOUND (modified)
- Commit `5f9e156` (test/RED) — FOUND
- Commit `af6f0b5` (feat/GREEN) — FOUND
- Commit `8dea934` (docs/naming) — FOUND