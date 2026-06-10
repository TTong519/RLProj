---
phase: 24-dreamerv3-world-models
plan: 02
status: completed
completed_at: "2026-06-09T00:00:00Z"
---

# Plan 24-02: DreamerV3 Training Orchestration & CLI

## Summary

Built full DreamerV3 training orchestration with CLI command `surg-rl dreamer-train`, checkpoint management, evaluation mode, and auto-discovery for benchmarking integration.

## What Was Built

### 1. Training Module (`src/surg_rl/dreamer/training.py`)
- **`run_dreamer_training()`** — Main entry point for training pipelines
  - Supports all 6 surgical task types: suturing, knot_tying, needle_insertion, grasping, cutting, dissection
  - Creates task-specific scenes programmatically (forceps/instrument + deformable tissue)
  - Both observation modes: **pixels** (64×64 RGBA) and **state** (~128 dims)
  - Process-isolated JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`
  - Periodic evaluation every `eval_every` steps
  - Checkpoint saving to `models/dreamerv3/{task}_{obs_type}/checkpoint_{step}.pt`
  - Metrics logged alongside checkpoints (`metrics_{step}.json`)

- **`evaluate_checkpoint()`** — Standalone evaluation without training
  - Loads checkpoint, runs `n_episodes`, returns benchmark-compatible metrics
  - Returns: success_rate, mean_reward, mean_episode_length, wall_clock_time, sample_efficiency, reconstruction_mse, reward_mae
  - Auto-discovers checkpoints from standard location

- **Resume & eval_only support**
  - `--resume` flag loads latest checkpoint and continues training
  - `--eval-only` flag runs pure evaluation on latest checkpoint

- **Graceful checkpointing on interrupt** — Ctrl+C saves `checkpoint_interrupt_{step}.pt`

### 2. CLI Commands (`src/surg_rl/cli.py`)

#### `dreamer-train`
```bash
surg-rl dreamer-train --task suturing --obs-type pixels --steps 500000
surg-rl dreamer-train --task grasping --obs-type state --eval-only
surg-rl dreamer-train --config experiments/dreamer_suturing.yaml --resume
```

Options: `--task`, `--obs-type`, `--steps`, `--eval-episodes`, `--eval-every`, `--resume`, `--checkpoint-dir`, `--eval-only`, `--config`, `--verbose`

#### `dreamer-spike`
```bash
surg-rl dreamer-spike
surg-rl dreamer-spike --task suturing --obs-type state --steps 50000
surg-rl dreamer-spike --force
```

Standalone feasibility spike runner with pass/fail output, exit codes 0/2

### 3. Package Exports (`src/surg_rl/dreamer/__init__.py`)
Added: `run_dreamer_training`, `evaluate_checkpoint`

### 4. Spike Failure Handling
- `dreamer-train` checks `models/dreamerv3/spike_report.json` at startup
- If spike failed: exits with code 2, prints formatted deferral message with metrics
- If spike not run: warns user to run `dreamer-spike` first

## Verification

- ✅ `surg-rl dreamer-train --help` shows all options correctly
- ✅ `surg-rl dreamer-spike --help` shows all options correctly
- ✅ All dreamer module imports work (subprocess, wrapper, spike, training)
- ✅ Task scene creation for all 6 task types
- ✅ Checkpoint directory structure: `models/dreamerv3/{task}_{obs_type}/`
- ✅ YAML config file support with CLI overrides
- ✅ Spike failure detection and deferral messaging

## Key Technical Decisions

1. **Auto-discovery for benchmarking** — Checkpoints at fixed path `models/dreamerv3/{task}_{obs_type}/` enables Phase 23 benchmark integration
2. **Separate spike command** — Allows CI to run spike independently before training
3. **Exit code 2 for deferral** — Distinct from error (1) and success (0), usable in CI pipelines
4. **Config YAML + CLI overrides** — Consistent with Phase 23 benchmark command pattern
5. **Process isolation in training** — Same XLA memory fraction (0.4) as spike

## Files Modified/Created

- `src/surg_rl/dreamer/training.py` (new) - 380 lines
- `src/surg_rl/cli.py` (updated) - added `dreamer-train` and `dreamer-spike` commands
- `src/surg_rl/dreamer/__init__.py` (updated) - exports training functions

## Next Steps (Plan 24-03)

Integrate DreamerV3 into Phase 23 benchmark system:
- Auto-discover checkpoints in ExperimentRunner
- Add DreamerV3 evaluation without training
- Orange color in plots, status banner in reports
- Graceful pending/deferred handling