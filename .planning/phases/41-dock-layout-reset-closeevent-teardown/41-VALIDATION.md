---
phase: 41
slug: dock-layout-reset-closeevent-teardown
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-15
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `41-RESEARCH.md` §Validation Architecture. Task IDs in the Per-Task
> Verification Map are filled in by the planner (`41-*-PLAN.md`); the test-class
> mapping below is the locked contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode = auto, per pytest.ini / CLAUDE.md) |
| **Config file** | `pytest.ini` (handles `PYTHONPATH=src` for pytest) |
| **Quick run command** | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py -v` (phase GUI test file; offscreen) |
| **Full suite command** | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/ -v` |
| **Estimated runtime** | ~10–20 seconds (offscreen Qt is fast; no real provider call by default) |

**Offscreen GUI convention:** every Qt test sets `QT_QPA_PLATFORM=offscreen` and builds `QApplication` + `EditorWindow` headless — the Phase 31/33 `tests/test_gui_scaffold.py` pattern (per CONTEXT.md D-08, RESEARCH.md §Architecture Patterns). Direct script runs require `PYTHONPATH=src`.

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_dock_state.py -v`
- **After every plan wave:** Run `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

> Task IDs now assigned by the planner (Plan 01: T1→T3; Plan 02: T1→T2). The
> test-class → success-criterion mapping is locked here; the executor must not drop a criterion.

| Task | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Test Class | SC | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------------|----|--------|
| 41-01-01 | 01 | 1 | GUI-18 | — | N/A (local desktop, no auth/network) | unit/introspection | `pytest tests/test_dock_state.py::TestDockObjectNames -v` | `TestDockObjectNames` | SC#4 | ⬜ pending |
| 41-01-02 | 01 | 1 | GUI-18 | — | N/A | unit (round-trip, TDD GREEN) | `pytest tests/test_dock_state.py::TestDockRoundTrip -v` | `TestDockRoundTrip::test_reset_layout_restores_factory_default` | SC#1 | ⬜ pending |
| 41-01-03 | 01 | 1 | GUI-18 | — | N/A | unit (round-trip + update_scene, TDD GREEN) | `pytest tests/test_dock_state.py::TestDockRoundTrip tests/test_dock_state.py::TestUpdateScene -v` | `TestDockRoundTrip::test_rearrange_close_reopen` + `TestUpdateScene` | SC#2 | ⬜ pending |
| 41-02-01 | 02 | 2 | GUI-18 | — | N/A | unit (mock-slow, TDD GREEN) | `pytest tests/test_dock_state.py::TestCloseMidCallMockSlow -v` | `TestCloseMidCallMockSlow` | SC#3 | ⬜ pending |
| 41-02-02 | 02 | 2 | GUI-18 | — | N/A | integration (skipif) + wiring guard | `pytest tests/test_dock_state.py::TestCloseMidCallRealProvider -v` | `TestCloseMidCallRealProvider` + aboutToClose-wiring guard | SC#3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dock_state.py` (name per implementer's discretion; follow `test_gui_scaffold.py` placement) — stubs for the four test classes above covering GUI-18 / SC#1–4
- [ ] Offscreen `QApplication` fixture (reuse the `test_gui_scaffold.py` offscreen-subprocess or in-process pattern — RESEARCH.md §Architecture Patterns)
- [ ] No new framework install needed — pytest + PySide6 `[gui]` extra already present

*Existing `tests/test_gui_scaffold.py` + `pytest.ini` infrastructure covers the harness; Wave 0 adds the phase-specific test file only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| _(none)_ | — | — | — |

*All phase behaviors have automated verification.* SC#3's real-provider path is gated behind `skipif` when no API key is present, but the always-on mock-slow-parser test (D-09b) is the regression backstop that runs unconditionally offscreen — so SC#3 is guarded even without keys (per CONTEXT.md D-09 and RESEARCH.md).

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending