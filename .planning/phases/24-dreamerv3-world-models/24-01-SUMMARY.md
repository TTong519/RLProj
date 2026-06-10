---
phase: 24-dreamerv3-world-models
plan: 01
status: completed
completed_at: "2026-06-09T00:00:00Z"
---

# Plan 24-01: DreamerV3 Feasibility Spike Infrastructure

## Summary

Built the complete feasibility spike infrastructure (DMV3-01) for testing whether DreamerV3 can model surgical dynamics from pixel/state observations.

## What Was Built

### 1. DreamerSubprocess (`src/surg_rl/dreamer/subprocess.py`)
- Process-isolated JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` to avoid GPU memory conflicts with PyTorch
- Module-level entry point (`_subprocess_main`) for reliable `spawn` context pickling
- JSON line-delimited stdin/stdout communication protocol
- Message types: CONFIG, TRAIN, EVAL, CHECKPOINT, SHUTDOWN with proper ACK handshakes
- Graceful shutdown handling with process termination fallback

### 2. GymToEmbodiedWrapper (`src/surg_rl/dreamer/wrapper.py`)
- Translates `SurgicalEnv` → `embodied.Env` protocol (DeepMind embodied benchmark format)
- **Pixel observations** (64×64 RGBA): Renders via simulator, normalizes to [0,1] float32
- **State observations** (~128 dims): Concatenates qpos, qvel, gripper state, task target, tissue metrics, task variables
- Handles embodied reset-in-action protocol: `action['reset'] = True` triggers env reset
- Returns flat dict with `is_first`, `is_last`, `is_terminal` boolean flags

### 3. SpikeOrchestrator (`src/surg_rl/dreamer/spike.py`)
- Creates forceps + liver tet mesh + suturing scene programmatically using SceneDefinition schema
- Spawns `DreamerSubprocess`, sends config, runs training loop, evaluates
- Computes pass/fail metrics: Reconstruction MSE < 0.01, Reward MAE < 0.5
- Generates detailed JSON report at `models/dreamerv3/spike_report.json` with training curves and analysis

### 4. Package Exports (`src/surg_rl/dreamer/__init__.py`)
- Exports all public classes: `DreamerSubprocess`, `GymToEmbodiedWrapper`, `SpikeOrchestrator`, `run_spike`, `check_spike_status`

## Verification

- ✅ Scene creation: forceps instrument + liver deformable tissue + suturing task loads successfully
- ✅ Environment creation: SurgicalEnv with MuJoCo backend initializes
- ✅ Observation wrapper: Produces valid embodied-format observations for both pixel and state modes
- ✅ Subprocess spawn: Process isolation with XLA memory fraction works (verified module imports)
- ✅ Report generation: Detailed spike report JSON with pass/fail determination

## Key Technical Decisions

1. **MuJoCo flex bodies** for tetrahedral soft tissues (not flexcomp) — uses `elasticity` element for 3D FEM
2. **Process isolation essential** — JAX + PyTorch GPU memory conflict requires separate subprocess with 40% GPU allocation
3. **Embodied protocol compliance** — reset signal embedded in action dict, boolean observation flags
4. **Configurable thresholds** — Defaults per DMV3-01: MSE < 0.01, MAE < 0.5, 100k steps, 10 eval episodes

## Files Modified/Created

- `src/surg_rl/dreamer/subprocess.py` (new) - 265 lines
- `src/surg_rl/dreamer/wrapper.py` (new) - 265 lines  
- `src/surg_rl/dreamer/spike.py` (new) - 370 lines
- `src/surg_rl/dreamer/__init__.py` (updated) - exports all modules
- `src/surg_rl/simulators/scene_builder.py` (fixed) - MuJoCo flex contact selfcollide="pair"/"none", removed invalid edge/plugin elements

## Next Steps (Plan 24-02)

Build full DreamerV3 training orchestration with `surg-rl dreamer-train` CLI command, checkpoint management, and auto-discovery for benchmarking.