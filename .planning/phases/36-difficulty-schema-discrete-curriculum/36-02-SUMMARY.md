---
phase: 36-difficulty-schema-discrete-curriculum
plan: 02
subsystem: dynamics/difficulty_wiring
tags: [difficulty, wiring, pydantic, tdd, curriculum, additive-composition]
requires:
  - src/surg_rl/rl/difficulty.py (DifficultyLevel + DifficultyLevelConfig leaf from Plan 01)
  - src/surg_rl/rl/rewards.py (interpolate_params classmethod — read-only baseline, NOT edited)
  - src/surg_rl/rl/task_reward_router.py (TASK_REWARD_REGISTRY — used in tests to resolve reward_cls)
  - .planning/phases/36-difficulty-schema-discrete-curriculum/36-CONTEXT.md (D-04/D-05/D-06/D-08)
  - .planning/phases/36-difficulty-schema-discrete-curriculum/36-RESEARCH.md (D-05 mapping table, Open Q3)
provides:
  - "src/surg_rl/dynamics/difficulty_wiring.py :: ABSTRACT_TO_CONCRETE registry (D-05, task_type-keyed) + DiscreteCurriculumConfig Pydantic wrapper (D-08) + compose_difficulty_overrides additive helper (D-06)"
  - "tests/test_difficulty_config.py :: TestComposeDifficultyOverrides — SC#2 truth table (54 cases) + D-04 unmapped-warns + D-08 empty-levels + D-05 oracle"
affects:
  - "Plan 03 (CurriculumScheduler discrete progression) consumes DiscreteCurriculumConfig + compose_difficulty_overrides to apply per-level overrides"
tech-stack:
  added: []
  patterns:
    - "Additive composition: interpolate_params(level.value) FIRST, then ABSOLUTE replacement on mapped override keys (D-06)"
    - "Wiring module receives reward_cls as a parameter — no task_reward_router import (RESEARCH.md Open Q3 one-way edge)"
    - "Test-oracle mirror dict (_D05_ORACLE) + parametrized truth table — programmatic D-05 verification stronger than literal grep"
    - "TDD RED->GREEN: RED via ModuleNotFoundError at import, GREEN restores full collection"
key-files:
  created:
    - src/surg_rl/dynamics/difficulty_wiring.py
  modified:
    - tests/test_difficulty_config.py
decisions:
  - "ABSTRACT_TO_CONCRETE keyed by task_type (corrected D-03), NOT TaskConfig.name — matches TASK_REWARD_REGISTRY keys"
  - "compose_difficulty_overrides uses ABSOLUTE replacement (D-06), not delta/multiplier; unoverridden keys retain interpolated value"
  - "Unmapped override (D-04) logs via logger.warning and keeps interpolated value — never raises KeyError"
  - "DiscreteCurriculumConfig is a Pydantic BaseModel (not dataclass) with levels: dict[DifficultyLevel, DifficultyLevelConfig] defaulting to empty (D-08)"
  - "reward_cls typed as Any (stdlib typing) to satisfy mypy disallow_untyped_defs without importing rl.rewards — preserves the one-way edge (only rl.difficulty in-project import)"
  - "D-04 warning captured via caplog (project logger uses logging.getLogger, not warnings.warn) — verified against task_reward_router.py:93-94 idiom"
metrics:
  duration: ~8 min
  tasks: 2
  files: 2
  tests_added: 76 (54 truth-table + 18 empty-levels + 1 D-04 warns + 1 D-05 oracle + 2 D-08 wrapper)
  completed: 2026-06-25
status: complete
---

# Phase 36 Plan 02: Difficulty Wiring Layer Summary

Landed the one-way wiring layer (`dynamics/difficulty_wiring.py`) that turns `DifficultyLevelConfig` from a passive leaf schema into an additive composition over `interpolate_params()`: the D-05 `ABSTRACT_TO_CONCRETE` registry (task_type-keyed), the `DiscreteCurriculumConfig` Pydantic wrapper (D-08), and the `compose_difficulty_overrides` helper (D-06). Verified by a 54-case parametrized SC#2 truth table, the D-04 unmapped-override-warns test, and a programmatic D-05 oracle — all GREEN via TDD RED->GREEN.

## What Was Built

### Task 1 (RED): `tests/test_difficulty_config.py` — TestComposeDifficultyOverrides appended
- `test_abstract_to_concrete_matches_d05_oracle` — programmatic oracle: `ABSTRACT_TO_CONCRETE == _D05_ORACLE` (cell-for-cell D-05 verification, task_type keying per corrected D-03).
- `test_compose_truth_table` — `@pytest.mark.parametrize` over 54 `(task_type, level, abstract_field, override_value)` tuples covering all 6 task_types x {EASY, MEDIUM, HARD} x each D-05-mapped abstract field. Asserts the composed dict differs from `reward_cls.interpolate_params(level.value)` ONLY on the mapped concrete key (absolute override value, D-06); every other key retains the interpolated baseline; key set unchanged.
- `test_compose_empty_levels_equals_interpolation` — 18 cases: an all-None `DifficultyLevelConfig()` yields pure `interpolate_params(level.value)` (D-08).
- `test_discrete_curriculum_config_default_empty` / `_holds_levels` — D-08 wrapper defaults to empty dict; round-trips a per-level config.
- `test_unmapped_override_warns` — D-04: `tissue_stiffness=120.0` on `suturing` (no tissue_stiffness mapping per D-05) logs a WARNING via `caplog` and the composed dict equals pure interpolation (no raise, no KeyError).
- Override values inside verified D-07 bounds: `tissue_stiffness=120.0`, `target_precision_tolerance=0.02`, `tool_position_noise=0.04`, `time_limit=90.0`.
- RED confirmed: collection failed with `ModuleNotFoundError: No module named 'surg_rl.dynamics.difficulty_wiring'`.
- Commit: `a4355b2` — `test(36-02): add failing RED truth-table + D-04 tests for compose_difficulty_overrides`.

### Task 2 (GREEN): `src/surg_rl/dynamics/difficulty_wiring.py` created
- Module docstring documents the one-way edge architecture (dynamics.difficulty_wiring -> rl.difficulty only; no curriculum/schema/task_reward_router import).
- `ABSTRACT_TO_CONCRETE: dict[str, dict[str, str]]` — exactly the 6 D-05 task_type keys with cell-for-cell concrete PARAM_BOUNDS keys (verified against rewards.py PARAM_BOUNDS at execution time).
- `DiscreteCurriculumConfig(BaseModel)` — `levels: dict[DifficultyLevel, DifficultyLevelConfig] = Field(default_factory=dict)`; default empty == pure interpolation baseline (D-08).
- `compose_difficulty_overrides(task_type, level, config, reward_cls) -> dict[str, float]` — computes `reward_cls.interpolate_params(level.value)` FIRST (D-06), then for each SET (non-None) abstract field: looks up `concrete_key = ABSTRACT_TO_CONCRETE.get(task_type, {}).get(abstract_field)`; if None -> `logger.warning(...)` (D-04) + continue; else `composed[concrete_key] = override_value` (ABSOLUTE replacement, D-06). Returns the composed dict.
- Imports: `from typing import Any`, `from pydantic import BaseModel, Field`, `from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig`, `from surg_rl.utils.logging import get_logger`. No curriculum/schema/task_reward_router import (one-way edge; reward_cls passed as parameter per RESEARCH.md Open Q3).
- Commit: `42ee64c` — `feat(36-02): implement difficulty_wiring module (ABSTRACT_TO_CONCRETE + DiscreteCurriculumConfig + compose_difficulty_overrides)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] D-04 warning captured via `caplog` instead of `pytest.warns(UserWarning)`**
- **Found during:** Task 1 (RED) — test design.
- **Issue:** The plan suggested `pytest.warns(UserWarning)` for the D-04 unmapped-override test, with the parenthetical "or the project logger's warning category — verify against task_reward_router.py:93-94". Verification: `task_reward_router.py` and `utils/logging.py` use `logging.getLogger(...)` + `logger.warning(...)` (standard logging), NOT `warnings.warn(...)`. `pytest.warns` only captures Python `warnings` module emissions, so it would NOT capture `logger.warning`.
- **Fix:** Used `caplog.at_level("WARNING", logger="surg_rl.dynamics.difficulty_wiring")` to capture the log record, then asserted the WARNING record exists and mentions the field + task_type. This matches the project's logger.warning idiom.
- **Files modified:** `tests/test_difficulty_config.py` (test only).
- **Commit:** `a4355b2`.

**2. [Rule 1 - Bug] `reward_cls` typed as `Any` instead of `type` for mypy compliance**
- **Found during:** Task 2 (GREEN) — `mypy src/surg_rl/dynamics/difficulty_wiring.py` reported `"type" has no attribute "interpolate_params" [attr-defined]`.
- **Issue:** The plan signature `reward_cls: type` is too generic for mypy (CLAUDE.md mandates `mypy disallow_untyped_defs = true`). Importing `BaseRewardFunction` from `rl.rewards` to type it as `type[BaseRewardFunction]` would violate the must_have "imports only DifficultyLevel + DifficultyLevelConfig from rl.difficulty" (would add an rl.rewards in-project import).
- **Fix:** Annotated `reward_cls: Any` (stdlib `typing.Any`). mypy passes; the one-way edge is preserved (only rl.difficulty in-project import); the structural contract is documented in the docstring. The composer is a thin wiring helper where `Any` is acceptable.
- **Files modified:** `src/surg_rl/dynamics/difficulty_wiring.py`.
- **Commit:** `42ee64c`.

**3. [Rule 3 - Blocking] `black` reformats suturing D-05 dict to multi-line — literal acceptance grep returns 0**
- **Found during:** Task 2 (GREEN) — acceptance grep check.
- **Issue:** The plan's acceptance criterion `grep -c '"suturing": {"target_precision_tolerance": "needle_position_tolerance"' ... returns 1` requires the suturing dict on a single line. `black` (authoritative per CLAUDE.md) explodes the nested dict literal across multiple lines because the outer `ABSTRACT_TO_CONCRETE` dict is multi-line. Manually forcing single-line with `# fmt: skip` would fight the formatter.
- **Fix:** Kept black's formatting (CLAUDE.md mandates `black --check`). The literal grep returns 0, but the D-05 cell content is verified authoritatively by the programmatic oracle test `test_abstract_to_concrete_matches_d05_oracle` (`ABSTRACT_TO_CONCRETE == _D05_ORACLE`, GREEN), which is strictly stronger than a substring grep.
- **Files modified:** none (formatting left as black produced).
- **Commit:** `42ee64c`.

No other deviations. The plan executed as written apart from these three Rule 1/3 auto-fixes.

## Verification Results

- `PYTHONPATH=src pytest tests/test_difficulty_config.py -v` -> **87 passed** (Plan 01's 11 + Plan 02's 76; GREEN).
- `PYTHONPATH=src pytest tests/test_difficulty_config.py::TestComposeDifficultyOverrides::test_compose_truth_table -v` -> **54 passed** (SC#2 truth table, 36-T06-02).
- `PYTHONPATH=src pytest tests/test_difficulty_config.py::TestComposeDifficultyOverrides::test_unmapped_override_warns -v` -> **1 passed** (D-04, 36-T06-03).
- `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py -v` -> **111 passed** (additive-regression gate; no reward surface edited).
- `python -c "import surg_rl.dynamics.curriculum, surg_rl.scene_definition.schema, surg_rl.dynamics.difficulty_wiring"` -> **OK** (no Pydantic cross-package cycle, SC#5).
- One-way edge: `grep -c 'from surg_rl.dynamics.curriculum' src/surg_rl/dynamics/difficulty_wiring.py` = **0**; `grep -c 'from surg_rl.scene_definition' ...` = **0**.
- `ruff check` + `black --check` + `mypy` on the new module -> **all clean**.
- Acceptance greps: `ABSTRACT_TO_CONCRETE` = 3; `class DiscreteCurriculumConfig(BaseModel):` = 1; `def compose_difficulty_overrides` = 1; `interpolate_params(level.value)` = 3; `logger.warning` = 1; suturing literal grep = 0 (deviation #3 — oracle test authoritative).

## TDD Gate Compliance

- RED gate: `test(36-02):` commit `a4355b2` exists; tests failed at collection (ModuleNotFoundError) before implementation.
- GREEN gate: `feat(36-02):` commit `42ee64c` exists after RED; all 87 tests pass.
- No REFACTOR commit needed — implementation was minimal and clean.

## Threat Model

- **T-36-03 (Tampering / compose_difficulty_overrides task_type lookup):** Mitigated — `ABSTRACT_TO_CONCRETE.get(task_type, {})` yields empty mapping for unknown task_type; all override fields warn-and-no-op (D-04), never raise KeyError. Verified by `test_unmapped_override_warns`.
- **T-36-04 (Tampering / override value range):** Mitigated at Plan 01 schema time (field_validator D-07 bounds); Plan 02 does not re-validate (additive over already-validated config).
- **T-36-05 (DoS / dynamics.difficulty_wiring -> rl import edge):** Mitigated — one-way import verified by grep (no curriculum/schema import) + cycle-check import test (SC#5).
- **T-36-SC (Tampering / package installs):** N/A — no package installs; only stdlib (typing) + already-pinned pydantic v2.

## Known Stubs

None. The wiring layer is fully functional; `compose_difficulty_overrides` returns real composed dicts; no placeholder data flows.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or trust-boundary schema changes beyond the planned override-field composition. The wiring module reads `interpolate_params` read-only on the passed-in reward class; no reward surface is edited.

## Self-Check: PASSED

- `src/surg_rl/dynamics/difficulty_wiring.py` — FOUND (created)
- `tests/test_difficulty_config.py` — FOUND (modified)
- Commit `a4355b2` (RED) — FOUND
- Commit `42ee64c` (GREEN) — FOUND