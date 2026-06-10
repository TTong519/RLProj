---
phase: 24-dreamerv3-world-models
plan: 04
status: completed
completed_at: "2026-06-09T00:00:00Z"
---

# Plan 24-04: Spike Failure Handling & Deferral Logic

## Summary

Implemented comprehensive spike failure handling with detailed failure reporting, CLI deferral messages, benchmark SB3-only mode, and clean deferral paths with no broken stubs.

## What Was Built

### 1. Enhanced Spike Reporting (`src/surg_rl/dreamer/spike.py`)
- **Always writes `spike_report.json`** regardless of pass/fail at `models/dreamerv3/spike_report.json`
- **Detailed failure report schema:**
  ```json
  {
    "timestamp": "2026-06-09T...",
    "status": "passed" | "failed",
    "thresholds": {"reconstruction_mse": 0.01, "reward_mae": 0.5},
    "results": {
      "reconstruction_mse": 0.015,
      "reward_mae": 0.62,
      "training_steps": 100000,
      "eval_episodes": 10
    },
    "training_curves": {
      "reconstruction_loss": [...],
      "reward_loss": [...],
      "total_loss": [...]
    },
    "analysis": "Detailed text analysis...",
    "recommendation": "defer to v0.5.0" | "proceed with integration",
    "deferral_reason": "reconstruction_mse_above_threshold" | "reward_mae_above_threshold" | "both"
  }
  ```
- **`check_spike_status()`** helper for CLI/benchmark to read report

### 2. CLI Deferral Handling (`src/surg_rl/cli.py`)

#### `dreamer-train` command
- Checks spike report at startup
- If failed: prints formatted deferral message with exact metrics and exits code 2:
```
╭─ DreamerV3 Deferred to v0.5.0 ────────────────────────╮
│ Feasibility spike did not meet thresholds:            │
│   Reconstruction MSE: 0.015 (threshold: < 0.01)       │
│   Reward MAE: 0.62 (threshold: < 0.5)                 │
│                                                       │
│ Full DreamerV3 integration is deferred to v0.5.0.     │
│ See models/dreamerv3/spike_report.json for details.   │
╰───────────────────────────────────────────────────────╯
```
- If not run: warns user to run `dreamer-spike` first
- If passed: proceeds with training normally
- `--force` flag available to bypass spike check (development only)

#### `dreamer-spike` command
- Standalone spike runner with `--force` flag
- Prints detailed pass/fail results with exit codes:
  - `0` = passed
  - `2` = failed (deferred)
  - `1` = error

### 3. Benchmark SB3-Only Mode (`src/surg_rl/benchmark/report.py`)
- **Dynamic HTML banner** based on spike status:
  - **Failed (deferred):** Red banner, shows failure metrics, no DreamerV3 rows in tables
  - **Passed (active):** Green banner, DreamerV3 results in per-backend tables
  - **Pending:** Orange banner "pending — Phase 24"

- **JSON export includes:**
  ```json
  {
    "dreamer_v3": {
      "status": "failed",
      "spike_metrics": {"reconstruction_mse": 0.015, "reward_mae": 0.62},
      "deferral_reason": "reconstruction_mse_above_threshold"
    },
    "benchmark_scope": "sb3_only"
  }
  ```
- When deferred: `benchmark_scope: "sb3_only"`, DreamerV3 completely removed from tables/plots
- No "pending — Phase 24" stubs remain when deferred — clean SB3-only reporting

### 4. DreamerV3 Evaluation Integration
- `ExperimentRunner._run_dreamer_evaluation()` checks spike status first
- If failed: marks all backends as "deferred" with error message
- If pending: marks all backends as "pending"
- If passed: auto-discovers and evaluates checkpoints

## Verification

- ✅ `check_spike_status()` returns None when no report exists
- ✅ Spike report JSON structure matches specification
- ✅ `dreamer-train` shows formatted deferral message on failure
- ✅ `dreamer-train` exits with code 2 on deferral (distinct from error=1)
- ✅ `dreamer-spike` prints pass/fail with exit codes 0/2
- ✅ Benchmark HTML banner shows DEFERRED/ACTIVE/PENDING correctly
- ✅ Benchmark JSON has `benchmark_scope: "sb3_only"` when deferred
- ✅ No DreamerV3 rows in tables when deferred
- ✅ All import paths work (subprocess, wrapper, spike, training)
- ✅ CLI help shows all options for both commands

## Key Technical Decisions

1. **Exit code 2 for deferral** — Distinct from error (1) and success (0), CI-friendly
2. **Always write spike report** — Even on failure, provides evidence for deferral decision
3. **Spike status is single source of truth** — CLI, training, benchmark all read same file
4. **Clean SB3-only mode** — When deferred, no trace of DreamerV3 in outputs (per D-17)
5. **Formatted CLI output** — Box-drawing characters for clear deferral presentation

## Files Modified/Created

- `src/surg_rl/dreamer/spike.py` (enhanced) - detailed failure report, check_spike_status
- `src/surg_rl/cli.py` (updated) - dreamer-train deferral handling, dreamer-spike command
- `src/surg_rl/benchmark/report.py` (updated) - SB3-only mode, dynamic banner, JSON scope field
- `src/surg_rl/benchmark/experiment_runner.py` (updated) - deferred/pending status handling

## Phase 24 Complete

All 4 plans in Phase 24 (DreamerV3 World Models) completed:

| Plan | Scope | Status |
|------|-------|--------|
| 24-01 | Feasibility Spike Infrastructure | ✅ Completed |
| 24-02 | Training Orchestration & CLI | ✅ Completed |
| 24-03 | Benchmark Integration | ✅ Completed |
| 24-04 | Failure Handling & Deferral | ✅ Completed |

## Summary of Deliverables

1. **DreamerSubprocess** — Process-isolated JAX training with XLA_PYTHON_CLIENT_MEM_FRACTION=0.4
2. **GymToEmbodiedWrapper** — SurgicalEnv → embodied.Env protocol (pixels 64×64 RGBA, state ~128 dims)
3. **SpikeOrchestrator** — Forceps + liver tet mesh + suturing scene, 100k steps, MSE/MAE thresholds
4. **surg-rl dreamer-train** — Full training with resumes, eval-only, config YAML, checkpoints
5. **surg-rl dreamer-spike** — Standalone spike with pass/fail, formatted output
6. **Benchmark integration** — Auto-discovery, orange plots, dynamic HTML banner
7. **Deferral logic** — Clean SB3-only mode when spike fails, no broken stubs

## Next Steps

Phase 24 is complete. Run phase verification:
```
/gsd-verify-work 24
```

Then advance to next milestone or close project.