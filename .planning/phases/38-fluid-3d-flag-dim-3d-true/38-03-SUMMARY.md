---
phase: 38-fluid-3d-flag-dim-3d-true
plan: 03
subsystem: fluids
tags: [fluid, visualization, 3d, refactor, tdd, additive]
requires:
  - "render_fluid_2d (pre-existing 2D renderer, visualizer.py)"
  - "Phase 38 Plan 01 (FluidConfig.dim_3d / grid_size surface)"
provides:
  - "surg_rl.fluids.visualizer._render_np_2d (private helper shared by 2D + 3D renderers)"
  - "surg_rl.fluids.visualizer.render_fluid_3d (2D z-layer slice-of-3D fallback renderer, D-18)"
  - "surg_rl.fluids.__init__.__all__ entry render_fluid_3d"
affects:
  - "Future env/CLI 3D fluid visualization consumers (render_fluid_3d export)"
tech-stack:
  added: []
  patterns:
    - "Private helper extraction (_render_np_2d) guarded by a 2D image-array-equality regression test (SC#1 byte-identical)"
    - "Explicit dim-order .numpy('x,y,z') on 3D PhiFlow tensors (Pitfall 1)"
    - "z_layer argument clamping to [0, nz-1] (T-38-07 tampering mitigation)"
    - "TDD RED/GREEN gate: RED commit (failing import) then GREEN commit (implementation)"
key-files:
  created:
    - tests/test_fluids/test_render_fluid_3d.py
  modified:
    - src/surg_rl/fluids/visualizer.py
    - src/surg_rl/fluids/__init__.py
decisions:
  - "render_fluid_3d is a slice-of-3D fallback (D-18), NOT a true volume renderer; deferred per CONTEXT.md"
  - "_render_np_2d extracted verbatim from render_fluid_2d's rendering body; 2D extraction try/except (np.asarray fallback) preserved unchanged so the 2D path stays byte-identical"
  - "2D byte-identical guard pins the exact pre-refactor output array (hardcoded _EXPECTED_2D_IMG) rather than a before/after runtime comparison, so the guard is deterministic and independent of refactor timing"
  - "render_fluid_3d config arg is kept for API symmetry with render_fluid_2d but unused by the slice renderer (slice extraction needs only the pressure field)"
metrics:
  duration: ~3m
  tasks: 2
  files: 3
  started: "2026-06-27T05:16:00Z"
  completed: "2026-06-27T05:19:25Z"
status: complete
---

# Phase 38 Plan 03: render_fluid_3d z-layer slice renderer Summary

Added `render_fluid_3d` — a 2D z-layer slice renderer that extracts an xy-plane slice from a 3D pressure field and delegates to a shared private `_render_np_2d` helper extracted from `render_fluid_2d`'s rendering body. The refactor is guarded by a 2D image-array-equality test (SC#1) that pins `render_fluid_2d`'s output against a hardcoded pre-refactor expected array, so the 2D public behavior stays byte-identical.

## Commits

| # | Task | Type | Commit | Message |
|---|------|------|--------|---------|
| 1 | RED — failing render_fluid_3d + 2D refactor guard tests | test | 9d81382 | `test(38-03): add failing render_fluid_3d + 2D refactor guard tests` |
| 2 | GREEN — extract _render_np_2d + add render_fluid_3d + export | feat | d2855ea | `feat(38-03): add render_fluid_3d z-layer slice + extract _render_np_2d` |

## Tasks Completed

### Task 1: RED — render_fluid_3d tests + 2D refactor guard

Created `tests/test_fluids/test_render_fluid_3d.py` (NEW file) with:
- `TestRenderFluid3D`: `test_render_3d_returns_image` (3D fixture via PhiFlow `Box(x=0.3,y=0.3,z=0.3)` + `StaggeredGrid(x=16,y=16,z=16)` + `make_incompressible` → 3D pressure; `render_fluid_3d(pressure, None, z_layer=8, width=100, height=80)` → `(80,100,3)` uint8), `test_render_3d_default_layer` (`z_layer=None` → middle `nz//2`), `test_render_3d_null_pressure_returns_none`, `test_render_3d_layer_clamp` (T-38-07: out-of-range `z_layer` clamped to `[0, nz-1]`).
- `TestRenderFluid2DByteIdentical::test_render_2d_image_byte_identical_after_refactor` (SC#1): renders a known 4x4 2D fixture via `render_fluid_2d(..., width=8, height=6)` and asserts `np.array_equal(img, _EXPECTED_2D_IMG)` against the hardcoded pre-refactor output array (computed once from the current `render_fluid_2d` before the extraction).
- 3D fixture built directly via PhiFlow (independent of Plan 02's `FluidSimulator` 3D — keeps this plan parallel/independent).
- RED confirmed: `ImportError: cannot import name 'render_fluid_3d' from 'surg_rl.fluids.visualizer'` during collection. Existing `TestFluidVisualization` 2D tests pass unchanged.

### Task 2: GREEN — extract _render_np_2d + add render_fluid_3d + export

**`src/surg_rl/fluids/visualizer.py`:**
- Extracted `_render_np_2d(arr: np.ndarray, width: int, height: int) -> np.ndarray | None` — private shared helper containing the verbatim rendering body (normalize, `skimage.transform.resize`, blue-channel colormap, `return img`; `except Exception: return None`) previously inlined in `render_fluid_2d`.
- `render_fluid_2d` now delegates: after the existing 2D extraction path (`pressure.values.numpy()` / `np.asarray` fallback — UNCHANGED, lines preserved), it calls `return _render_np_2d(p_vals, width, height)`. Public signature and 2D output byte-identical (guarded by the 2D image-array-equality test).
- Added `render_fluid_3d(pressure, config, z_layer=None, width=400, height=400) -> np.ndarray | None` (D-18): `None` pressure returns `None`; extracts `p_np = pressure.values.numpy("x,y,z")` (explicit dim order — Pitfall 1) inside a try/except returning `None` on failure (defensive, mirrors 2D); `nz = p_np.shape[2]`; `layer = z_layer if z_layer is not None else nz // 2`; clamps `layer` to `[0, nz-1]` (T-38-07); `slice_2d = p_np[:, :, layer]`; `return _render_np_2d(slice_2d, width, height)`. Docstring documents it as a slice-of-3D fallback, NOT a true volume renderer.

**`src/surg_rl/fluids/__init__.py`:** `from surg_rl.fluids.visualizer import render_fluid_2d, render_fluid_3d` + `"render_fluid_3d",` added to `__all__` (additive; existing entries preserved).

## Verification Results

- `PYTHONPATH=src pytest tests/test_fluids/test_render_fluid_3d.py -v` → 5 passed (3D returns `(80,100,3)` uint8; default layer; null returns None; layer clamp both ends; 2D byte-identical guard passes).
- `PYTHONPATH=src pytest tests/test_fluids/test_fluid_simulator.py -v` → 26 passed (2D `TestFluidVisualization` unchanged + all 2D/3D simulator tests).
- `PYTHONPATH=src pytest tests/test_fluids/test_render_fluid_3d.py tests/test_fluids/test_fluid_simulator.py -v` → 31 passed.
- `PYTHONPATH=src pytest tests/test_fluid_step.py -v` → 5 passed (SC#5 `fluid_step` hook unchanged).
- Acceptance greps:
  - `grep -c 'def _render_np_2d' src/surg_rl/fluids/visualizer.py` → 1
  - `grep -c 'def render_fluid_3d' src/surg_rl/fluids/visualizer.py` → 1
  - `grep -c 'x,y,z' src/surg_rl/fluids/visualizer.py` → 1 (3D slice extraction with explicit dim order)
  - `grep -c 'render_fluid_3d' src/surg_rl/fluids/__init__.py` → 2 (import + `__all__`)
  - 2D `np.asarray` fallback preserved (line 67, `visualizer.py`); `git diff --stat` shows 74 insertions, 15 deletions — the deletions are the rendering body moved into `_render_np_2d`, NOT the 2D extraction path.
- SC#1 byte-identical: `test_render_2d_image_byte_identical_after_refactor` passes — `render_fluid_2d` output matches the pre-refactor pinned array exactly.

## Deviations from Plan

### Auto-fixed Issues

None — the plan executed exactly as written. The implementation matches D-18, Pitfall 1 (explicit dim order), T-38-06 (defensive try/except → None), and T-38-07 (z_layer clamp) verbatim.

### Minor note on 2D byte-identical guard strategy

The plan offered two options for the 2D guard: "assert `np.array_equal(img_before, img_after)` OR pin against a hardcoded expected array hash." I chose the hardcoded-array pin (`_EXPECTED_2D_IMG`) over a runtime before/after comparison because: (a) it is deterministic and independent of refactor timing — the expected array was computed from the pre-refactor `render_fluid_2d` and embedded directly in the test; (b) a runtime before/after comparison would require keeping a copy of the pre-refactor code path in the test, which is fragile. This is a test-design choice within the plan's allowed options, not a deviation from the plan's requirements.

## TDD Gate Compliance

- RED gate commit `9d81382` (`test(38-03): ...`) exists — tests failed with `ImportError` before any implementation; existing 2D visualization tests passed unchanged.
- GREEN gate commit `d2855ea` (`feat(38-03): ...`) exists after RED — all 5 new tests pass + 2D byte-identical guard passes.
- No REFACTOR needed (implementation is clean as written; `_render_np_2d` body is the verbatim extraction).

## Threat Surface

No new threat surface beyond the plan's `<threat_model>`. Mitigations implemented as specified:
- **T-38-06 (DoS / NaN in image):** `render_fluid_3d` wraps `pressure.values.numpy("x,y,z")` in try/except returning `None` on failure; `_render_np_2d` normalizes with the existing `p_max > 1e-12` guard (zeros if degenerate) and wraps the whole rendering body in try/except returning `None`.
- **T-38-07 (Tampering / z_layer out of range):** `layer = max(0, min(layer, nz - 1))` clamps before slicing; `test_render_3d_layer_clamp` verifies `z_layer=999` and `z_layer=-5` do not raise.

## Known Stubs

None. `render_fluid_3d` is fully wired (slice extraction + delegation to `_render_np_2d`); no placeholder/TODO/empty-default stubs. `render_fluid_3d`'s `config` arg is intentionally unused (slice extraction needs only the pressure field) — documented in the docstring, not a stub.

## Self-Check: PASSED

- `tests/test_fluids/test_render_fluid_3d.py` — FOUND (created, contains `TestRenderFluid3D` + `TestRenderFluid2DByteIdentical`)
- `src/surg_rl/fluids/visualizer.py` — FOUND (modified, contains `_render_np_2d` + `render_fluid_3d`)
- `src/surg_rl/fluids/__init__.py` — FOUND (modified, exports `render_fluid_3d` in import + `__all__`)
- Commit `9d81382` — FOUND (`git log --oneline | grep 9d81382`)
- Commit `d2855ea` — FOUND (`git log --oneline | grep d2855ea`)
- 2D byte-identical regression: `test_render_2d_image_byte_identical_after_refactor` passes; `TestFluidVisualization` 2/2 pass; `test_fluid_step.py` 5/5 pass.