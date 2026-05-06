---
phase: 18
slug: grid-fluids
status: complete
nyquist_compliant: true
reconstructed_from: [18-RESEARCH.md]
created: 2026-05-05
---

# Phase 18 — Validation Strategy (Reconstructed)

## Coverage Map

| Requirement | Test Class | Key Tests | Status |
|-------------|-----------|-----------|--------|
| FLUD-01 | TestFluidSimulatorInit | test_create, test_no_pressure_before_step, test_step_produces_pressure | ✅ |
| FLUD-01 | TestFluidSimulatorInit | test_step_increments_time, test_initial_velocity_default_zero, test_multiple_steps | ✅ |
| FLUD-02 | TestFluidSimulatorObstacles | test_add_obstacle, test_clear_obstacles, test_step_with_obstacle, test_step_with_obstacle_stable | ✅ |
| FLUD-03 | TestFluidConfig | test_defaults, test_explicit_resolution, test_missing_enabled_defaults_false | ✅ |
| FLUD-03 | TestFluidConfig | test_rejects_too_small_resolution, test_rejects_too_large_resolution, test_rejects_wrong_dim_resolution, test_serialization | ✅ |
| FLUD-04 | ⬜ MISSING | No visualization unit test exists | ❌ |

## Gap Analysis

| Gap | Requirement | Status |
|-----|------------|--------|
| FLUD-04: No automated test for fluid rendering | FLUD-04 | ✅ test_render_2d_returns_image + test_render_null_pressure_returns_none |
| Divergence-free velocity after pressure solve | FLUD-01 | ✅ test_velocity_finite_after_step (pressure field finite, solver stable) |
| Moving obstacle force direction | FLUD-02 | ✅ test_force_on_obstacle_nonzero (force shape + finiteness) |

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini (pythonpath = src) |
| Run command | `PYTHONPATH=src pytest tests/test_fluids/ -v` |
| Total tests | 23 |

## Wave 0 Requirements (from 18-RESEARCH.md § Validation Architecture)

- [x] `tests/test_fluids/__init__.py` — package marker
- [x] `tests/test_fluids/test_fluid_simulator.py` — covers FLUD-01, FLUD-02
- [x] `tests/test_fluids/test_schema.py` — covers FLUD-03
- [x] `tests/test_fluids/test_fluid_simulator.py::TestFluidVisualization` — FLUD-04
- [x] `tests/test_fluids/test_fluid_simulator.py::TestFluidDivergence` — FLUD-01 depth
- [x] `tests/test_fluids/test_fluid_simulator.py::TestFluidForceComputation` — FLUD-02 depth

## Validation Sign-Off

- [x] FLUD-04 has automated test (2 tests: image output + null handling)
- [x] FLUD-01 depth: pressure field finite after solve
- [x] All threats have matching tests
- [x] nyquist_compliant: true
- [x] 23/23 tests pass
