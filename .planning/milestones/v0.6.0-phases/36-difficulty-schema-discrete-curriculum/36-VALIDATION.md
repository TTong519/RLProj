---
phase: 36
slug: difficulty-schema-discrete-curriculum
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-24
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `36-RESEARCH.md` § Validation Architecture (code-verified, HIGH confidence).
> `workflow.tdd_mode` is **true** — TDD-eligible tasks are flagged in the Test Type column.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via `pytest.ini`; `pythonpath = src`, `asyncio_mode = auto`) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (pure unit/regression; no GPU, no simulator) |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py -v`
- **After every plan wave:** Run `PYTHONPATH=src pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Plan IDs/waves assigned by the planner (Plan 01 = Wave 1, Plan 02 = Wave 2, Plan 03 = Wave 3) and confirmed by the plan-checker (0 blockers). Rows are keyed by requirement + success criterion (SC); every requirement ID (TASK-06, TASK-07, TASK-09) and every SC (#1–#5) is covered. The TASK-09 regression gate (row 36-T09-01) must stay green after every plan, hence Plan 01–03 / Wave 1→3.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 36-T06-01 | 01 | 1 | TASK-06 / SC#1 | — | Pydantic range validators reject out-of-range overrides (ASVS V5 input validation) | unit (TDD) | `PYTHONPATH=src pytest tests/test_difficulty_config.py -v` | ❌ W0 | ⬜ pending |
| 36-T06-02 | 02 | 2 | TASK-06 / SC#2 | — | N/A | unit (TDD, parametrized) | `PYTHONPATH=src pytest tests/test_difficulty_config.py::test_compose_truth_table -v` | ❌ W0 | ⬜ pending |
| 36-T06-03 | 02 | 2 | TASK-06 / SC#2 (D-04) | — | N/A | unit | `PYTHONPATH=src pytest tests/test_difficulty_config.py::test_unmapped_override_warns -v` | ❌ W0 | ⬜ pending |
| 36-T07-01 | 03 | 3 | TASK-07 / SC#3 | — | N/A | unit (TDD) | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py -v` | ❌ W0 | ⬜ pending |
| 36-T07-02 | 03 | 3 | TASK-07 / SC#3 (parity) | — | N/A | unit (regression parity) | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py::test_advance_stage_unchanged tests/test_dynamics.py::TestCurriculumScheduler -v` | ✅ test_dynamics.py exists; parity test new | ⬜ pending |
| 36-T07-03 | 03 | 3 | TASK-07 / SC#3 | — | N/A | unit | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py::test_current_difficulty_mode_branch -v` | ❌ W0 | ⬜ pending |
| 36-T09-01 | 01–03 | 1–3 | TASK-09 / SC#4 | — | N/A | regression (unchanged) | `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py -v` | ✅ existing — must stay green | ⬜ pending |
| 36-SC5-01 | 01 | 1 | SC#5 | — | Leaf placement prevents import-cycle DoS | unit (import audit) | `PYTHONPATH=src pytest tests/test_difficulty_config.py::test_leaf_no_inproject_imports -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_difficulty_config.py` — covers SC#1 (range validation), SC#2 (additive truth table), D-04 (unmapped override warns), SC#5 (leaf import audit). TDD RED gate for the `DifficultyLevelConfig` model + `compose_difficulty_overrides` helper.
- [ ] `tests/test_discrete_curriculum.py` — covers SC#3 (`set_difficulty_level`/`advance_level` EASY→MEDIUM→HARD→False, `advance_stage` parity, `current_difficulty` mode branch). TDD RED gate for the scheduler additions.
- [ ] No framework install needed — pytest + pydantic already installed (`pip install -e ".[dev]"` covers everything).

*Existing infrastructure covers all non-test phase requirements; only the two new test files above are Wave 0.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification. No manual checks required (pure schema + curriculum-internals phase; no GUI, no simulator, no deployment).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (the two new test files)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending