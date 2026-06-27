---
phase: 38
slug: 3d-fluid-flag-dim-3d-true
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-26
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `38-RESEARCH.md` § Validation Architecture (Nyquist validation enabled).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pytest.ini` (marker registry) |
| **Quick run command** | `PYTHONPATH=src pytest tests/test_fluids/ -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (fluid slice); full suite ~3–5 min |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=src pytest tests/test_fluids/ -v` (finite-output + schema + 2D-baseline)
- **After every plan wave:** Run `PYTHONPATH=src pytest tests/test_fluids/ tests/test_fluid_step.py -v` (all fluid + hook regression)
- **Before `/gsd-verify-work`:** Full suite must be green — `PYTHONPATH=src pytest tests/ -v` (includes the 5-test `test_fluid_step.py` suite UNCHANGED and the 2D `test_fluid_simulator.py` suite UNCHANGED — SC#1/SC#5 byte-identical gate)
- **Max feedback latency:** ~30 seconds
- **Nyquist rationale:** The instability mode of interest is per-step NaN/blow-up in velocity/pressure. The fastest mode is a per-step divergence, so the SC#2/SC#4 regression tests sample `np.all(np.isfinite(...))` EVERY step for the first N steps (not every Nth) — per-step sampling is the minimum rate to catch it.

---

## Per-Task Verification Map

> Populated by the planner/executor once PLAN.md task IDs exist. The requirement → test mapping below is the contract each task's `<verify>`/`<acceptance_criteria>` must satisfy.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-02-T2 | 38-02 | 2 | FLUID-01 | T-38-01 / — | 3D construct+step produces finite 3D pressure | unit/integration | `PYTHONPATH=src pytest tests/test_fluids/test_fluid_simulator.py -k "3d" -v` | ❌ W0 (additive) | ⬜ pending |
| 38-04-T1 | 38-04 | 3 | FLUID-01 (SC#1) | — | 2D byte-identical output | regression | `PYTHONPATH=src pytest tests/test_fluids/test_2d_baseline.py -v` | ❌ W0 | ⬜ pending |
| 38-04-T2 | 38-04 | 3 | FLUID-02 | — | ONE_WAY stable over N=100 steps, no NaN | integration | `PYTHONPATH=src pytest tests/test_fluids/test_3d_coupling.py -k "one_way" -v` | ❌ W0 | ⬜ pending |
| 38-04-T2 | 38-04 | 3 | FLUID-02 | — | TWO_WAY opt-in + documented unstable | integration | `PYTHONPATH=src pytest tests/test_fluids/test_3d_coupling.py -k "two_way" -v` | ❌ W0 | ⬜ pending |
| 38-01-T2 | 38-01 | 1 | FLUID-03 | T-38-02 (OOM DoS) | `grid_size` required when `dim_3d=True` → ValidationError | unit | `PYTHONPATH=src pytest tests/test_fluids/test_schema.py -k "grid_size or dim_3d" -v` | ❌ W0 (extend) | ⬜ pending |
| 38-01-T2 | 38-01 | 1 | FLUID-03 | T-38-02 | `_cap_grid_size` rejects <4, >64, wrong len; anisotropic ok | unit | `PYTHONPATH=src pytest tests/test_fluids/test_schema.py -k "cap_grid_size" -v` | ❌ W0 (extend) | ⬜ pending |
| 38-04-T3 | 38-04 | 3 | FLUID-03 (SC#4) | — | NaN-regression parametrized (2D×3D)×(single×overlap), N=50 finite | regression | `PYTHONPATH=src pytest tests/test_fluids/test_nan_regression.py -v` | ❌ W0 | ⬜ pending |
| 38-04-T3 | 38-04 | 3 | SC#5 | — | `fluid_step` hook unchanged (5-test suite) | regression | `PYTHONPATH=src pytest tests/test_fluid_step.py -v` | ✅ (must pass unchanged) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Validation Dimensions (mapped to the 5 Success Criteria)

| Dimension | SC | Approach |
|-----------|----|----------|
| D1 finite-output correctness | SC#1/SC#4 | Per-step `np.isfinite` on velocity+pressure for both dims. |
| D2 2D byte-identical regression | SC#1 | Array-equality (or hash) of velocity+pressure for `dim_3d=False` vs a v0.5.0 baseline fixture. Existing 2D suite passes unchanged. |
| D3 3D stability over N steps | SC#2/SC#4 | N=100 ONE_WAY steps with thin instruments via `add_instrument`; assert no NaN/blow-up. TWO_WAY variant asserts opt-in + documents instability (NOT stable). |
| D4 memory-bounded grid_size validation | SC#3 | Pydantic `ValidationError` on `dim_3d=True` + `grid_size=None`; `_cap_grid_size` rejects <4, >64, wrong len; anisotropic (64,32,64) accepted. |
| D5 fluid_step hook unchanged | SC#5 | Existing 5-test `test_fluid_step.py` suite passes unchanged. |

---

## Wave 0 Requirements

- [ ] `tests/test_fluids/test_2d_baseline.py` — SC#1 2D byte-identical baseline (velocity+pressure array-equality for the existing 2D fixture)
- [ ] `tests/test_fluids/test_3d_coupling.py` — SC#2 ONE_WAY N-step stability + TWO_WAY opt-in gate
- [ ] `tests/test_fluids/test_nan_regression.py` — SC#4 parametrized `(dim_3d=False, dim_3d=True) × (single, overlapping)` N-step finite-assert
- [ ] Extend `tests/test_fluids/test_schema.py` — `dim_3d`/`grid_size`/`coupling_mode`/`coupling_substeps` validators (required-when, cap, anisotropic, defaults)
- [ ] Extend `tests/test_fluids/test_fluid_simulator.py` — 3D init/step/obstacle tests (additive; do NOT edit existing 2D tests)
- [ ] Extend/new `tests/test_fluids/test_force_computation.py` — 3D obstacle-mask force `(fx,fy,fz)` + per-axis independent clamp
- [ ] `tests/test_fluids/test_render_fluid_3d.py` — z-layer slice delegation
- [ ] Framework install: none (pytest already installed)

*Existing infrastructure (pytest + pytest.ini) covers the framework; Wave 0 is test-file scaffolding only.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification. (No manual-only checks — pure solver/schema phase.)*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planning contract complete — per-task map filled from 38-01..04 PLAN.md task IDs; Nyquist-compliant per RESEARCH § Validation Architecture; Wave 0 test-file enumeration covers every MISSING reference in the map)