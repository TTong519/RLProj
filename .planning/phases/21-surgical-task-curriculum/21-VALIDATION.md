---
phase: 21
slug: surgical-task-curriculum
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-17
promoted_to_complete: 2026-06-10
promoted_by: phase 28-audit-gap-closure-retroactive
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — pytest.ini with `pythonpath = src`) |
| **Config file** | pytest.ini (existing) |
| **Quick run command** | `PYTHONPATH=src pytest tests/test_rewards.py tests/test_task_results.py tests/test_task_reward_router.py -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=src pytest tests/test_rewards.py tests/test_task_results.py tests/test_task_reward_router.py -v`
- **After every plan wave:** Run `PYTHONPATH=src pytest tests/ -m "not integration" -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-task Verification Map

| task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | TASK-04 | T-21-01 | Pydantic validates TaskResult fields | unit | `pytest tests/test_task_results.py -v` | ❌ W0 | ⬜ pending |
| 21-02-01 | 02 | 2 | TASK-01 | T-21-02 | NaN/inf guarded in compute() | unit | `pytest tests/test_rewards.py -v -k "KnotTying or Grasping or Cutting"` | ❌ W0 | ⬜ pending |
| 21-02-02 | 02 | 2 | TASK-04 | T-21-02 | check_success returns TaskResult | unit | `pytest tests/test_rewards.py -v -k "check_success"` | ❌ W0 | ⬜ pending |
| 21-02-03 | 02 | 2 | TASK-01,TASK-02 | — | Registry dispatch, interpolation | unit | `pytest tests/test_task_reward_router.py -v` | ❌ W0 | ⬜ pending |
| 21-03-01 | 03 | 3 | TASK-03 | — | Additive to existing curriculum | integration | `pytest tests/test_dynamics.py -v -k "curriculum"` | ✅ | ⬜ pending |
| 21-03-02 | 03 | 3 | TASK-01 | — | Router wired into env reward fn | integration | `pytest tests/test_environment.py -v -k "task_type"` | ❌ W0 | ⬜ pending |
| 21-03-03 | 03 | 3 | TASK-04 | — | Per-task check wired into episode end | unit | `pytest tests/test_task_termination.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_task_results.py` — stubs for TASK-04 (TaskResult hierarchy validation, model_dump, field constraints, per-task sub-models)
- [ ] `tests/test_rewards.py` — add test classes for 3 new reward subclasses (KnotTyingReward, GraspingReward, CuttingReward), covering compute(), check_success(), check_failure(), interpolate_params()
- [ ] `tests/test_task_reward_router.py` — covers TASK-01 routing logic (known task_type, None task_type, unknown task_type, registry completeness, generic-only fallback)
- [ ] `tests/test_environment.py` — extend with task_type routing integration test
- [ ] `tests/test_task_termination.py` — per-task check delegation test

*Test conftest: none needed — existing fixtures (dummy observation dicts, zero actions) are sufficient.*

---

## Manual-Only Verifications

None — all phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
