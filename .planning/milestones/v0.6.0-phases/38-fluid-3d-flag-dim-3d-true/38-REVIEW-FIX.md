---
phase: 38-fluid-3d-flag-dim-3d-true
status: all_fixed
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
reviewed: 2026-06-27
review_path: .planning/phases/38-fluid-3d-flag-dim-3d-true/38-REVIEW.md
---

# Phase 38: Code Review Fix Report

**Fixed at:** 2026-06-27T00:00:00Z
**Source review:** `.planning/phases/38-fluid-3d-flag-dim-3d-true/38-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 critical + 5 warning; info findings out of scope per `fix_scope: critical_warning`)
- Fixed: 6
- Skipped: 0

## Per-Finding Disposition

| ID | Severity | Title | Disposition | Commit | Rationale |
|-----|----------|-------|-------------|--------|----------|
| CR-01 | Critical | 3D force helper uses cell-index gradient, not physical gradient (wrong units) | fixed | cc117c3 | Moved `dx/dy/dz` computation before the `np.gradient` calls and passed the physical cell spacing as the second positional argument per axis (`np.gradient(p_np, dx, axis=0)` etc.), so the 3D force helper now returns per-meter pressure gradients (Newtons, not Pa·m³/cell). Added a zero-cell-size guard returning zero forces (defensive — also covered by WR-04 at the schema level). 3D-only; the 2D `compute_obstacle_forces` body is byte-identical and untouched. Existing 3D tests still pass: the per-axis clamp tests use synthetic ramps large enough to still saturate the 1e4 cap, and the y-axis-nonzero test only asserts `|fy| > 0`. |
| WR-01 | Warning | `coupling_mode` (ONE_WAY / TWO_WAY) is dead config — never consumed | fixed (documented) | 0bdd4c9 | Implementing real TWO_WAY added-mass coupling would be substantial new behavior risking the verified 3D path and the TWO_WAY xfail semantics. Applied the acceptable minimal fix: added an honest `step()` docstring documenting that TWO_WAY currently aliases ONE_WAY and that the xfail exercises the same stable path (xpass is expected, not a guarantee of TWO_WAY behavior). Field left in place; behavior unchanged. |
| WR-02 | Warning | `coupling_substeps` is dead config — never consumed | fixed (documented) | 0bdd4c9 | A real substep loop (`sub_dt = dt / coupling_substeps`) is substantial new behavior; deferred. Documented in the same `step()` docstring that `coupling_substeps` is reserved for a future substep loop and is not consumed today, so callers who pin it get no effect. Field left in place; behavior unchanged. |
| WR-03 | Warning | `add_instrument` tip Box is geometrically redundant in every test case | fixed (documented) | 0bdd4c9 | Making the shaft finite or adding a `tip_half > shaft_radius` test would change geometry/coverage and risk the verified 3D fixtures. Applied the minimal honest fix: extended the `add_instrument` docstring with a Note explaining that the tip is absorbed by the infinite shaft when `tip_half <= shaft_radius` (the case used by every Phase 38 fixture) and that only `tip_half > shaft_radius` produces a distinct tip (no coverage today). Behavior unchanged. |
| WR-04 | Warning | Schema allows `dim_3d=True` with zero-y-extent `BoundingBox` (degenerate 3D domain) | fixed | 2d47f23 | Extended `_require_grid_size_when_dim_3d` (model_validator mode="after") to also reject `dim_3d=True` when any bounds dimension has zero (or near-zero, `< 1e-12`) extent, raising a `ValidationError` with the offending dims. Verified no existing test constructs `dim_3d=True` with zero-y bounds — all 3D fixtures use `_make_3d_bounds()` (0.3m y extent). 2D path unaffected (it does not sample a 3D grid over y). |
| WR-05 | Warning | `zip(obstacles, obstacle_names)` without `strict=True` silently truncates on length mismatch | fixed | 77a8e71 | Added `strict=True` to the `zip(obstacles, obstacle_names)` call in `_compute_obstacle_forces_3d`. Python 3.10+ supports `strict=True` (project requires `>=3.10`). 3D-only; the 2D `compute_obstacle_forces` only takes `obstacle_names` and is untouched. |

## Files Modified

- `src/surg_rl/fluids/force_computation.py` (CR-01, WR-05)
- `src/surg_rl/scene_definition/schema.py` (WR-04)
- `src/surg_rl/fluids/fluid_simulator.py` (WR-01, WR-02, WR-03 — documentation only)

No new files created. No 2D-path source modified. No 2D test files modified.

## Tests

Post-fix suite (run from the isolated review-fix worktree):

```
PYTHONPATH=src pytest tests/test_fluids/ tests/test_fluid_step.py -q --tb=short
```

Result: **65 passed, 1 xpassed, 0 failed** (the same green baseline as pre-fix; the `xpassed` is the documented `test_two_way_opt_in_documented_unstable` case, which is the expected outcome given the TWO_WAY-aliases-ONE_WAY inertness documented in WR-01).

The 2D byte-identical SC#1/SC#5 regression gates (`tests/test_fluids/test_2d_baseline.py`, `tests/test_fluid_step.py`) remain green — the validated 2D path is preserved.

---

_Fixed: 2026-06-27T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_