---
phase: 36-difficulty-schema-discrete-curriculum
plan: 01
subsystem: rl/difficulty
tags: [difficulty, pydantic, leaf, tdd, schema]
requires:
  - src/surg_rl/rl/difficulty.py (existing DifficultyLevel leaf)
  - .planning/phases/36-difficulty-schema-discrete-curriculum/36-CONTEXT.md (D-07, D-08, SC#1, SC#5)
provides:
  - "src/surg_rl/rl/difficulty.py :: DifficultyLevelConfig Pydantic v2 leaf model with 4 Optional[float] override fields + 4 field_validator range checks"
  - "tests/test_difficulty_config.py :: TDD RED->GREEN gate for DifficultyLevelConfig validation + SC#5 leaf import audit"
affects:
  - "Plan 02 (wiring module / truth-table test) composes DifficultyLevelConfig with the 4-source override chain"
  - "Plan 03 (CurriculumScheduler discrete progression) consumes per-level configs"
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 BaseModel + @field_validator + @classmethod range checks (D-07 global union bounds)"
    - "Leaf module: zero in-project imports enforced by SC#5 substring grep audit"
    - "TDD RED->GREEN: failing-import RED commit, then GREEN implementation commit"
key-files:
  created:
    - tests/test_difficulty_config.py
  modified:
    - src/surg_rl/rl/difficulty.py
decisions:
  - "DifficultyLevelConfig is a Pydantic v2 BaseModel (not a dataclass) — field_validator + @classmethod idiom per CLAUDE.md"
  - "D-07 bounds treated as min/max over all endpoints (global union), NOT 'min lo / max hi'"
  - "Leaf contract preserved: only stdlib (enum, typing) + pydantic imported; no surg_rl.* imports"
  - "Module docstring rephrased to drop the literal substring 'surg_rl.' so the SC#5 substring audit holds without weakening the leaf contract"
metrics:
  duration: ~6 min
  tasks: 2
  files: 2
  tests_added: 11
  completed: 2026-06-25
status: complete
---

# Phase 36 Plan 01: DifficultyLevelConfig Leaf Schema Summary

Implemented the `DifficultyLevelConfig` Pydantic v2 leaf model — the dependency root of the phase's difficulty-override vocabulary — via TDD RED→GREEN, with four `Optional[float]` override fields range-checked against the verified D-07 global union bounds and a zero-in-project-import leaf contract (SC#5).

## What Was Built

### Task 1 (RED): `tests/test_difficulty_config.py`
- `TestDifficultyLevelConfig` — 4 tests covering default-None construction, in-range round-trip, parametrized out-of-range rejection (7 D-07 boundary cases), and type rejection.
- `TestLeafImportAudit.test_leaf_no_inproject_imports` — SC#5 substring audit: reads the leaf source, strips comment-only lines, asserts `"surg_rl."` not present in remaining source.
- RED confirmed: collection failed with `ImportError: cannot import name 'DifficultyLevelConfig'`.
- Commit: `9434da1` — `test(36-01): add failing RED tests for DifficultyLevelConfig + leaf audit`.

### Task 2 (GREEN): `src/surg_rl/rl/difficulty.py`
- Appended `from typing import Optional` and `from pydantic import BaseModel, field_validator` after the existing `from enum import Enum` (no `surg_rl.*` imports added).
- Added `DifficultyLevelConfig(BaseModel)` with four `Optional[float] = None` fields: `tissue_stiffness`, `target_precision_tolerance`, `tool_position_noise`, `time_limit`.
- Added four `@field_validator(...) + @classmethod` methods enforcing the verified D-07 global union bounds:
  - `tissue_stiffness`: `[50.0, 300.0]`
  - `target_precision_tolerance`: `[0.002, 0.3]`
  - `tool_position_noise`: `[0.01, 0.08]`
  - `time_limit`: `[30.0, 180.0]`
- `DifficultyLevel` enum left untouched.
- Commit: `166a52b` — `feat(36-01): implement DifficultyLevelConfig leaf model with D-07 range validators`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Rephrased module docstring to satisfy SC#5 substring audit**
- **Found during:** Task 2 (GREEN) — `TestLeafImportAudit.test_leaf_no_inproject_imports` failed on first GREEN run.
- **Issue:** The pre-existing module docstring contained the literal substring `surg_rl.` in the phrase "no imports from `surg_rl.*`". The plan's SC#5 test design uses substring matching on non-comment lines, which catches docstring mentions even though they are not imports. The acceptance criterion `grep -v '^\s*#' src/surg_rl/rl/difficulty.py | grep -c 'surg_rl\.'` returns 0 would also fail.
- **Fix:** Rephrased the docstring from "no imports from `surg_rl.*`" to "no in-project imports" + an explicit reference to "SC#5 enforces this via a substring audit on the source." The leaf-contract documentation meaning is preserved; only the literal substring that the audit greps for was removed.
- **Files modified:** `src/surg_rl/rl/difficulty.py` (docstring only, within the same GREEN commit).
- **Commit:** `166a52b`

No other deviations. The plan executed as written apart from this docstring rephrase.

## Verification Results

- `PYTHONPATH=src pytest tests/test_difficulty_config.py -v` → **11 passed** (GREEN).
- `grep -v '^\s*#' src/surg_rl/rl/difficulty.py | grep -c 'surg_rl\.'` → **0** (SC#5 leaf audit holds).
- `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py -v` → **111 passed** (additive-regression gate; no existing test edited).
- Acceptance greps: `class DifficultyLevelConfig(BaseModel):` = 1; each of the four bounds checks = 1.

## TDD Gate Compliance

- RED gate: `test(36-01):` commit `9434da1` exists, tests failed at collection (ImportError) before implementation.
- GREEN gate: `feat(36-01):` commit `166a52b` exists after RED, all tests pass.
- No REFACTOR commit needed — implementation was minimal and clean.

## Threat Model

- **T-36-01 (Tampering / out-of-range authoring):** Mitigated — four `field_validator` range checks raise `ValidationError` at schema time against D-07 global bounds.
- **T-36-02 (DoS / Pydantic cross-package cycle):** Mitigated — leaf stays zero-in-project-import; SC#5 audit enforces it.
- **T-36-SC (Tampering / package installs):** N/A — no package installs; only stdlib + already-pinned pydantic v2 used.

## Known Stubs

None. The model is fully wired with validation; no placeholder data flows.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or trust-boundary schema changes beyond the planned override-field validation.

## Self-Check: PASSED

- `tests/test_difficulty_config.py` — FOUND
- `src/surg_rl/rl/difficulty.py` — FOUND (modified)
- Commit `9434da1` (RED) — FOUND
- Commit `166a52b` (GREEN) — FOUND