---
phase: 38-fluid-3d-flag-dim-3d-true
verified: 2026-06-27T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 38: 3D Fluid Flag (dim_3d=True) Verification Report

**Phase Goal:** Simulation authors can opt into 3D Eulerian grid fluids via `FluidConfig.dim_3d=True` and get a stable, memory-bounded 3D solver with one-way fluid/solid coupling by default, while the validated 2D xz-slice path stays unchanged for existing scenes.
**Verified:** 2026-06-27T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth (SC) | Status | Evidence |
|---|------------|--------|----------|
| 1 | `FluidConfig.dim_3d=True` constructs a 3D `Box(x,y,z)`+`StaggeredGrid` and runs `make_incompressible`+pressure projection in 3D; `dim_3d=False` (default) produces byte-identical 2D solver output to v0.5.0 (regression gate) | ✓ VERIFIED | `fluid_simulator.py:74-87` builds 3D `Box(x,y,z)`+`StaggeredGrid(x=nx,y=ny,z=nz)`; `step()` line 197 calls `fluid.make_incompressible` (3D path identical mechanism, 3D grid). 2D byte-identical: `tests/test_fluids/test_2d_baseline.py::Test2DBaselineByteIdentical::test_2d_velocity_pressure_pinned_to_baseline` passes with SHA256 hash pins on pressure (9ae73c40…) + velocity x-face/y-face (12525d30…); `tests/test_fluids/test_render_fluid_3d.py::TestRenderFluid2DByteIdentical` pins 2D render output array. `git diff b87fe3e..HEAD -- src/surg_rl/fluids/force_computation.py` shows the 2D `compute_obstacle_forces` body has 0 deletions (only the new 3D helper appended above). |
| 2 | 3D fluid/solid coupling runs stably for a full episode with default `coupling_mode="one_way"` on thin instruments (no NaN, no blow-up); `two_way` is opt-in and documented as unstable on thin instruments | ✓ VERIFIED (behavioral) | `tests/test_fluids/test_3d_coupling.py::Test3DCouplingOneWay::test_one_way_stable_n100` runs N=100 steps via `add_instrument` with thin dims (0.01,0.1,0.01) and asserts `np.isfinite` on every step's pressure + all 3 velocity faces — passes. Behavioral spot-check reproduced: 100-step ONE_WAY run stayed finite. TWO_WAY opt-in: `test_two_way_opt_in_accepted` confirms `FluidConfig(coupling_mode=TWO_WAY)` constructs; `test_two_way_opt_in_documented_unstable` is `@pytest.mark.xfail(strict=False)` documenting instability (docstring + xfail reason cite RESEARCH Pitfall 8). |
| 3 | A separate, smaller 3D default `grid_size` + Pydantic validator prevents the cubic NxNxN memory blow-up when `dim_3d=True` is set without an explicit grid size | ✓ VERIFIED | `schema.py:1580-1588` `_require_grid_size_when_dim_3d` model_validator raises `ValidationError` when `dim_3d=True and grid_size is None`. Spot-check: `FluidConfig(enabled=True, dim_3d=True, grid_size=None, …)` → `ValidationError` raised. `_cap_grid_size` (lines 1565-1578) rejects `len!=3`, any dim<4, any dim>64; accepts anisotropic `(64,32,64)`. Spot-check confirmed all bounds (reject 3, reject 65, reject (24,24), accept anisotropic). Schema recommends `24^3` in error string + description. |
| 4 | The documented `union(*geoms)` multi-obstacle SDF workaround has a NaN-regression test covering BOTH the 2D and 3D paths | ✓ VERIFIED | `tests/test_fluids/test_nan_regression.py::test_nan_regression_parametrized` is a SINGLE `@pytest.mark.parametrize` over `(dim_3d=False/True) × (single/overlapping)` — 4 cases: 2d-single, 2d-overlapping, 3d-single, 3d-overlapping. Overlapping cases add two obstacles whose SDFs overlap and rely on `union(*geoms)` inside `FluidSimulator.step` (line 193). Asserts velocity finite every step + pressure finite-or-None (DEBT-05 graceful-failure contract). All 4 pass. |
| 5 | `BaseSimulator.fluid_step(dt)` hook still fires for both `dim_3d` modes (the v0.5.0 5-test regression suite passes unchanged) | ✓ VERIFIED | `base_simulator.py:336-357` `fluid_step` default no-op preserved. `tests/test_fluid_step.py` 5-test suite passes unchanged (verified: `git log b87fe3e..HEAD -- tests/test_fluid_step.py` shows no phase-38 commit touched it; last touch was phase 31 commit a26200d). Suite run: `test_base_simulator_default_is_noop`, `test_base_simulator_default_with_dt`, `test_mu_joco_simulator_fluid_step_is_noop`, `test_py_bullet_simulator_fluid_step_is_noop`, `test_surgical_env_invokes_simulator_fluid_step_hook` — all 5 pass. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/surg_rl/scene_definition/schema.py` | FluidCouplingMode + FluidConfig 3D fields/validators | ✓ VERIFIED | `FluidCouplingMode` (1507-1511), `dim_3d` (1529), `grid_size` (1530-1536), `coupling_mode` (1537-1543), `coupling_substeps` (1544-1552), `_cap_grid_size` (1565-1578), `_require_grid_size_when_dim_3d` (1580-1588). All verified by direct call + `tests/test_fluids/test_schema.py::TestFluidConfig3D` (9 tests pass). |
| `src/surg_rl/fluids/fluid_simulator.py` | 3D init/step/add_instrument branches | ✓ VERIFIED | 3D `__init__` branch (74-87), 3D step force-call branch (208-220), `add_instrument` (123-180). 2D branches preserved byte-identical in `else` blocks. |
| `src/surg_rl/fluids/force_computation.py` | `_compute_obstacle_forces_3d` helper | ✓ VERIFIED | Lines 12-77. Per-obstacle mask via `phi.field.sample`, per-axis independent clamp `[-1e4,1e4]` (lines 73-75). 2D `compute_obstacle_forces` body byte-identical (git diff: 0 deletions). |
| `src/surg_rl/fluids/visualizer.py` | `render_fluid_3d` + `_render_np_2d` extraction | ✓ VERIFIED | `_render_np_2d` (10-46), `render_fluid_3d` (74-113) with z-layer slice + clamp (T-38-07). `render_fluid_2d` refactored to delegate (49-71); 2D output pinned by `test_render_2d_image_byte_identical_after_refactor`. |
| `src/surg_rl/fluids/__init__.py` | exports `render_fluid_3d` | ✓ VERIFIED | Line 5 imports `render_fluid_2d, render_fluid_3d`; `__all__` includes both (lines 7-11). |
| `tests/test_fluids/test_2d_baseline.py` | SC#1 2D byte-identical baseline | ✓ VERIFIED | SHA256 hash-pin on pressure + velocity faces + per-step finiteness. Passes. |
| `tests/test_fluids/test_3d_coupling.py` | SC#2 ONE_WAY stability + TWO_WAY opt-in | ✓ VERIFIED | `Test3DCouplingOneWay::test_one_way_stable_n100` (N=100 finite every step) + `Test3DCouplingTwoWayOptIn` (accepted + xfail). Pass. |
| `tests/test_fluids/test_nan_regression.py` | SC#4 parametrized NaN regression | ✓ VERIFIED | Single `@pytest.mark.parametrize` over 4 cases (2D/3D × single/overlapping), N=50 steps, finite-or-None every step. All 4 pass. |
| `tests/test_fluids/test_force_computation.py` | 3D obstacle-mask + per-axis clamp tests | ✓ VERIFIED | `TestComputeObstacleForces3D` (4 tests: returns-3tuple, y-axis-nonzero via synthetic y-ramp, per-axis-independent-clamp distinguishes from 2D scalar clamp, finite-no-nan) + `TestComputeObstacleForces2DUnchanged` (2D signature/behavior pin). All pass. |
| `tests/test_fluids/test_render_fluid_3d.py` | 3D z-layer slice + 2D refactor guard | ✓ VERIFIED | `TestRenderFluid3D` (returns-image, default-layer, null-pressure, layer-clamp) + `TestRenderFluid2DByteIdentical` (pinned 2D array). All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `FluidConfig.dim_3d` | `FluidSimulator` 3D branch | `if config.dim_3d:` in `__init__` and `step` | ✓ WIRED | `fluid_simulator.py:74,208` |
| `FluidConfig.grid_size` | 3D `StaggeredGrid` resolution | `nx,ny,nz = config.grid_size` (line 79) → `StaggeredGrid(…, x=nx, y=ny, z=nz)` | ✓ WIRED | `fluid_simulator.py:79-87` |
| `FluidSimulator.step` 3D branch | `_compute_obstacle_forces_3d` | `from surg_rl.fluids.force_computation import _compute_obstacle_forces_3d` + call (lines 210-220) | ✓ WIRED | Imports + 5-arg call matches signature |
| `FluidSimulator.add_instrument` | `add_obstacle` | `merged = union(shaft, tip); self.add_obstacle(merged, name)` (lines 179-180) | ✓ WIRED | Raises `ValueError` when `not dim_3d` or `pose is None` (155-163) |
| `render_fluid_3d` | `_render_np_2d` | `slice_2d = p_np[:,:,layer]; return _render_np_2d(slice_2d, width, height)` (lines 112-113) | ✓ WIRED | |
| `fluids.__init__` | `render_fluid_3d` export | `from …visualizer import render_fluid_2d, render_fluid_3d` + `__all__` | ✓ WIRED | |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `render_fluid_3d` | `slice_2d` (from `p_np[:,:,layer]`) | `pressure.values.numpy("x,y,z")` from a live `make_incompressible` solve | Yes — `test_render_3d_returns_image` builds a 3D pressure via `fluid.make_incompressible` and asserts non-None `(80,100,3)` uint8 image | ✓ FLOWING |
| `_compute_obstacle_forces_3d` | `p_np` (pressure gradient) | `pressure.values.numpy("x,y,z")` from `FluidSimulator.step`'s `make_incompressible` call | Yes — `test_compute_obstacle_forces_3d_returns_3tuple` exercises a real 3D solve and gets finite `(fx,fy,fz)` | ✓ FLOWING |
| 2D `compute_obstacle_forces` | `p_vals` | `pressure.values.numpy()` | Yes — pinned byte-identical by `test_2d_velocity_pressure_pinned_to_baseline` hash | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SC#3 schema rejects `dim_3d=True, grid_size=None` | `python -c "FluidConfig(…)"` | `ValidationError: grid_size is required when dim_3d=True` | ✓ PASS |
| SC#3 anisotropic `(64,32,64)` accepted; `(3,…)/(65,…)/(24,24)` rejected; `coupling_substeps∈{0,17}` rejected, `{1,16}` accepted | direct construction matrix | All 7 expected outcomes match | ✓ PASS |
| SC#2 ONE_WAY N=100 finite on thin instrument | 100-step loop with `add_instrument((0.01,0.1,0.01))` | All pressure + 3 velocity faces finite every step | ✓ PASS |
| Full fluid test suite | `PYTHONPATH=src pytest tests/test_fluids/ tests/test_fluid_step.py -v` | 65 passed, 1 xpassed (the TWO_WAY xfail unexpectedly passed), 0 failed | ✓ PASS |

### Probe Execution

Step 7c SKIPPED — Phase 38 is a library/schema feature phase with no declared `scripts/*/tests/probe-*.sh` probes. The phase's "probes" are the pytest regression gates (SC#1/SC#2/SC#4/SC#5), all run under Behavioral Spot-Checks above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FLUID-01 | 38-01, 38-02, 38-03 | `dim_3d=True` enables 3D Eulerian grid fluids (3D `Box`/`StaggeredGrid` + 3D pressure projection); `dim_3d=False` default preserves the validated 2D xz-slice behavior | ✓ SATISFIED | SC#1 + SC#5 verified (see Truths #1, #5) |
| FLUID-02 | 38-02, 38-04 | 3D fluid/solid coupling runs stably with one-way coupling as the default (two-way opt-in) on thin instruments | ✓ SATISFIED | SC#2 verified (see Truth #2) |
| FLUID-03 | 38-01, 38-04 | 3D solver memory-bounded via separate smaller 3D default `grid_size` + validator; `union(*geoms)` multi-obstacle SDF NaN-regression test covers the 3D path | ✓ SATISFIED | SC#3 + SC#4 verified (see Truths #3, #4) |

No orphaned requirements — `REQUIREMENTS.md` maps exactly FLUID-01/02/03 to Phase 38; all three are claimed by plans and satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/surg_rl/fluids/force_computation.py` | 53-55 | `np.gradient(p_np, axis=…)` without physical cell spacing → forces off by factors of `dx/dy/dz` (3D-only) | ⚠️ WARNING (CR-01) | See Materiality below — not in any SC |
| `src/surg_rl/scene_definition/schema.py` / `fluid_simulator.py` | 1537-1543 / 182-235 | `coupling_mode` (ONE_WAY/TWO_WAY) declared + validated but never consumed by `step()` — both modes run identical code (WR-01) | ⚠️ WARNING | See Materiality below |
| `src/surg_rl/scene_definition/schema.py` / `fluid_simulator.py` | 1544-1552 / 182-235 | `coupling_substeps` declared + validated but never consumed by `step()` — no substep loop (WR-02) | ⚠️ WARNING | Not in any SC; defense-in-depth knob is inert |
| `src/surg_rl/fluids/fluid_simulator.py` | 172-180 | `add_instrument` tip Box geometrically absorbed by infinite-z shaft for the equal-half-size case used by every test (WR-03) | ⚠️ WARNING | Not in any SC; tested morphology is effectively shaft-only |
| `src/surg_rl/scene_definition/schema.py` | 1580-1588 | Schema accepts `dim_3d=True` with zero-y-extent `BoundingBox` → degenerate 3D domain with `dy=0` → silent zero forces (WR-04) | ⚠️ WARNING | Not in any SC; no validator guards bounds extent |
| `src/surg_rl/fluids/force_computation.py` | 66 | `zip(obstacles, obstacle_names)` without `strict=True` silently truncates on length mismatch (WR-05) | ℹ️ INFO | Code-quality; lists are aligned in practice |

No `TBD`/`FIXME`/`XXX` debt markers in any phase-38-modified file. No unreferenced debt markers.

### Code-Review Findings — Materiality Assessment

A deep code review (`38-REVIEW.md`, status: issues_found — 1 BLOCKER, 5 WARNING, 4 INFO) was independently assessed against the literal Phase 38 success criteria and must_haves. The reviewer's "BLOCKER" severity reflects general code-quality aspirations; against the **goal contract** none of the findings block:

- **CR-01 (3D force unit bug — `np.gradient` missing cell spacing):** Real defect. However, no SC and no PLAN `must_haves` truth asserts 3D force **magnitude correctness in physical Newtons**. SC#2 is explicitly a **stability / no-NaN** contract ("no NaN, no simulation blow-up"); the per-axis independent clamp (D-17) is the only force-related `must_have`, and it is verified by `test_3d_force_per_axis_independent_clamp`. The phase goal speaks of "one-way fluid/solid coupling" — coupling is delivered (forces are computed and returned per obstacle per step); their physical *accuracy* is not in the goal contract. **Disposition: WARNING — out-of-scope for Phase 38 SCs; recommend a follow-up issue for force-magnitude correctness.**
- **WR-01 (`coupling_mode` dead config):** The literal SC#2 requires only that "two_way is opt-in and documented as unstable." `FluidConfig(coupling_mode=TWO_WAY)` is accepted (`test_two_way_opt_in_accepted`) and the xfail test + docstring document instability. SC#2 does **not** require TWO_WAY to behave differently from ONE_WAY. The xfail unexpectedly passing (1 xpassed) is consistent with WR-01: with no behavioral divergence, the xfail premise is false. **Disposition: WARNING — the opt-in knob is inert; recommend either implementing TWO_WAY feedback or removing the field.**
- **WR-02 (`coupling_substeps` dead config):** Not referenced by any SC. The `must_have` truth in 38-01 only requires the field exists with `ge=1, le=16` — verified. **Disposition: WARNING.**
- **WR-03 (tip Box absorbed):** Not in any SC. `add_instrument` exists, raises guards, registers an obstacle via `union` — the `must_have` truth is satisfied. **Disposition: WARNING.**
- **WR-04 (zero-y bounds):** Not in any SC. SC#3 is about `grid_size`, not bounds extent. **Disposition: WARNING.**
- **WR-05 (zip strict):** Code quality. **Disposition: INFO.**
- **IN-01..04:** All INFO — dead `velocity` param, unused `config` in renderers, 2D array aliasing (SC#1-locked), bare-except render fallback (SC#1-locked). None impact any SC.

**Conclusion:** No review finding falsifies any SC or `must_haves` truth. The findings are real code-quality issues that warrant follow-up work but do not block the phase goal. The phase goal is achieved as literally specified.

### Human Verification Required

None. All five success criteria are verified by automated tests:
- SC#1/SC#5 byte-identical contracts are hash/array pinned (automated).
- SC#2 stability is exercised by `test_one_way_stable_n100` (behavioral test, N=100 finite-every-step).
- SC#3 schema validation is exercised by `TestFluidConfig3D` + direct construction spot-checks.
- SC#4 NaN regression is exercised by the 4-case parametrized test.

No visual / real-time / external-service checks are required by the SCs. The `render_fluid_3d` output is shape/dtype-pinned (automated); visual fidelity is not in any SC.

### Gaps Summary

No gaps. All 5 roadmap success criteria are verified, all 3 requirements (FLUID-01/02/03) are satisfied, all artifacts exist + are substantive + wired + have flowing data, all key links are wired, all prohibitions honored (2D `compute_obstacle_forces` body has 0 deletions; `test_fluid_step.py` untouched by phase-38 commits; existing 2D test classes in `test_fluid_simulator.py` untouched — phase-38 commit c5e4463 only appended new 3D classes + fixture).

Six advisory code-quality findings from `38-REVIEW.md` are noted as WARNING/INFO but none map to any success criterion or `must_haves` truth, so none block the phase goal. Recommended follow-up (non-blocking): (a) fix CR-01 force unit bug + add a physical-magnitude regression test; (b) either implement or remove `coupling_mode`/`coupling_substeps`; (c) add a zero-y-extent bounds validator; (d) add a `tip_half > shaft_radius` test or make the shaft finite.

---

_Verified: 2026-06-27T00:00:00Z_
_Verifier: Claude (gsd-verifier)_