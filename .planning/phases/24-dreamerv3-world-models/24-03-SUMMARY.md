---
phase: 24-dreamerv3-world-models
plan: 03
status: completed
completed_at: "2026-06-09T00:00:00Z"
---

# Plan 24-03: DreamerV3 Benchmark Integration

## Summary

Integrated DreamerV3 into Phase 23 benchmark system with auto-discovery of checkpoints, evaluation without training, distinct orange color in plots, status banner in HTML/JSON reports, and graceful pending/deferred handling.

## What Was Built

### 1. ExperimentRunner Updates (`src/surg_rl/benchmark/experiment_runner.py`)
- **`_run_dreamer_evaluation()`** — New method for DreamerV3 evaluation
  - Checks spike report at `models/dreamerv3/spike_report.json` first
  - If spike failed: marks all backends as "deferred" with failure details
  - If spike not run: marks all backends as "pending"
  - If spike passed: auto-discovers checkpoints from `models/dreamerv3/{task}_{obs_type}/`
  - Uses `evaluate_checkpoint()` from `dreamer.training` for evaluation
  - Supports configurable `dreamer_obs_types` (default: ["state"])
  - Adds results to aggregated output with algorithm name "DreamerV3 (pixels)" or "DreamerV3 (state)"

- **Integration with `run()` method**
  - Runs DreamerV3 evaluation after SB3 sweeps complete
  - Adds DreamerV3 results to aggregation pool
  - Properly handles deferred/pending/failed states

### 2. ExperimentConfig Updates (`src/surg_rl/benchmark/experiment_config.py`)
Added DreamerV3-specific fields:
- `dreamer_comparison: bool` — Enable DreamerV3 comparison (default: False)
- `dreamer_obs_types: list[Literal["pixels", "state"]]` — Observation types to evaluate (default: ["state"])
- `dreamer_eval_episodes: int` — Evaluation episodes for DreamerV3 (default: 10)

### 3. PlotRenderer Updates (`src/surg_rl/benchmark/plots.py`)
- **`DREAMERV3_COLOR = "#FF8C00"`** — Distinct orange color, separate from 5-color SB3 palette
- **Learning curves (`render_learning_curve`)**
  - Plots DreamerV3 as markers at evaluation points (no continuous training curve)
  - Shows "pending" annotation for deferred/pending runs
- **Success rate bars (`render_success_rate_bars`)**
  - Adds DreamerV3 bar with orange color, positioned after SB3 algorithms
  - Grayed-out italic label for pending status
- **Results table (`render_results_table`)**
  - Adds DreamerV3 row with orange background
  - Shows "pending" for deferred runs

### 4. ReportGenerator Updates (`src/surg_rl/benchmark/report.py`)
- **Dynamic DreamerV3 banner in HTML**
  - **"DEFERRED TO v0.5.0"** (red banner) — shows spike failure metrics, removes DreamerV3 from tables
  - **"ACTIVE"** (green banner) — DreamerV3 results appear in per-backend tables
  - **"pending — Phase 24"** (default orange banner) — shows as pending stub
- **JSON export enhancements**
  - `dreamer_v3` section with spike_status, spike_metrics, deferral_reason, results
  - `benchmark_scope` field: `"sb3_and_dreamer"` or `"sb3_only"`
  - Full spike metrics included for traceability

## Verification

- ✅ `ExperimentRunner` imports successfully with DreamerV3 integration
- ✅ `ExperimentConfig` has DreamerV3 fields with proper defaults
- ✅ `PlotRenderer` uses orange color for DreamerV3, handles pending status
- ✅ `ReportGenerator` shows correct banner based on spike status
- ✅ Auto-discovery logic finds checkpoints at `models/dreamerv3/{task}_{obs_type}/`
- ✅ Evaluation runs without training (uses `evaluate_checkpoint`)
- ✅ JSON export contains spike metrics and benchmark_scope
- ✅ HTML report removes DreamerV3 rows when deferred

## Key Technical Decisions

1. **Backend-agnostic evaluation** — DreamerV3 subprocess runs independently; results reported per-backend for consistency
2. **Observation type in algorithm name** — "DreamerV3 (pixels)" vs "DreamerV3 (state)" for clear comparison
3. **No pending stubs when deferred** — Clean SB3-only reporting when spike fails, per D-17
4. **Orange color distinct from SB3 palette** — `#FF8C00` not in colorblind-safe 5-color cycle
5. **Spike status drives all behavior** — Single source of truth at `models/dreamerv3/spike_report.json`

## Files Modified/Created

- `src/surg_rl/benchmark/experiment_runner.py` (updated) - added `_run_dreamer_evaluation()` method
- `src/surg_rl/benchmark/experiment_config.py` (updated) - added DreamerV3 fields
- `src/surg_rl/benchmark/plots.py` (updated) - orange color, pending handling
- `src/surg_rl/benchmark/report.py` (updated) - dynamic banner, JSON enhancements

## Next Steps (Plan 24-04)

Implement spike failure handling and deferral logic:
- Enhanced spike report with training curves and analysis
- CLI failure handling with formatted deferral message (exit code 2)
- Benchmark reports declare SB3-only scope cleanly
- No broken/stub code remains