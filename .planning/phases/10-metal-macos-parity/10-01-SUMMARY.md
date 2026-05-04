# 10-01 Summary: MPS Device Resolution

**Plan:** 10-01-PLAN.md
**Status:** Complete
**Commits:** 1

## Accomplishments

- Added `get_torch_device()` to `src/surg_rl/utils/gpu.py` — resolves `"auto"` → `"mps"` on Apple Silicon (CUDA → MPS → CPU priority). Logs unified memory info and speed caveat at INFO.
- Added `get_metal_memory_info()` to `src/surg_rl/utils/gpu.py` — returns `{"unified_memory_gb": float}` on macOS via `sysctl hw.memsize`.
- Wired `get_torch_device()` into `TrainingRunner._create_model()` in `src/surg_rl/rl/training.py` — SB3 models now receive resolved device string instead of raw config value.
- Added `_mps_available()` helper and MPS detection branch to `RllibConfig.from_training_config()` in `src/surg_rl/rl/rllib/config.py` — logs MPS detection with "local learner" note.

## Files Modified

| File | Change |
|------|--------|
| `src/surg_rl/utils/gpu.py` | +80 lines: `get_torch_device()`, `get_metal_memory_info()`, `_MPS_SPEED_CAVEAT` |
| `src/surg_rl/rl/training.py` | +2 lines: import `get_torch_device`, resolve device in `_create_model()` |
| `src/surg_rl/rl/rllib/config.py` | +15 lines: `_mps_available()`, MPS branch in `from_training_config()` |

## Self-Check: PASSED

- `get_torch_device("auto")` → `"mps"` with `unified_memory_gb: 24.0` on macOS
- Passthrough: `get_torch_device("cpu")` → `"cpu"`, `get_torch_device("cuda")` → `"cuda"`, `get_torch_device("mps")` → `"mps"`
- `RllibConfig.from_training_config(TrainingConfig())` → `num_learners=0, num_gpus_per_learner=0.0` on MPS
- Full test suite: 774 passed (775 after wave 2)
