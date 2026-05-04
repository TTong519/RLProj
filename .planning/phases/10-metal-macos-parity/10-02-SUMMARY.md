# 10-02 Summary: MPS Logging & Fallback

**Plan:** 10-02-PLAN.md
**Status:** Complete
**Depends on:** 10-01
**Commits:** 1

## Accomplishments

- Added `mps_fallback_to_cpu()` to `src/surg_rl/utils/gpu.py` — single-warning utility for unsupported MPS operations. Uses module-level `_mps_fallback_warned` flag to prevent log spam.
- Added 5 Metal-specific tests to `tests/test_gpu_integration.py`:
  - `test_get_torch_device_auto` — auto resolves to valid device string
  - `test_get_torch_device_passthrough` — explicit pass-through works
  - `test_metal_memory_info_on_macos` — memory info available on macOS
  - `test_metal_memory_info_on_non_macos` — None on non-macOS
  - `test_mps_fallback_warns_once` — warns once, silent thereafter

## Files Modified

| File | Change |
|------|--------|
| `src/surg_rl/utils/gpu.py` | +12 lines: `_mps_fallback_warned`, `mps_fallback_to_cpu()` |
| `tests/test_gpu_integration.py` | +62 lines: 5 new Metal tests |

## Self-Check: PASSED

- `mps_fallback_to_cpu("test_op")` emits single WARNING, second call silent
- All 5 new tests pass on macOS (1 skipped on non-macOS)
