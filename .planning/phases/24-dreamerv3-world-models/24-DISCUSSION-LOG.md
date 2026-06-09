# Phase 24: DreamerV3 World Models - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 24-dreamerv3-world-models
**Areas discussed:** Feasibility spike design, Process isolation architecture, GymToEmbodiedWrapper design, Pixel vs low-dim observations, Benchmark integration

---

## Feasibility spike design

| Option | Description | Selected |
|--------|-------------|----------|
| Suturing scene (forceps + liver tet mesh) | Single instrument (forceps) + deformable tissue (liver tet mesh), suturing task from Phase 21 — most representative of surgical dynamics | ✓ |
| Grasping scene (forceps + kidney/organ mesh) | Single instrument + organ from Phase 20, grasping task from Phase 21 — simpler contact dynamics, easier for RSSM to learn | |
| Cutting scene (scalpel + liver tet mesh) | Single instrument + tissue from Phase 16, cutting task from Phase 21 — tests RSSM on discontinuous cutting dynamics | |
| Custom combination | Let me specify a different scene/task combination | |

**User's choice:** Suturing scene (forceps + liver tet mesh)
**Notes:** Most representative of surgical continuous-contact dynamics; uses infrastructure from Phases 16, 20, 21

---

## Feasibility spike metrics and thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Quantitative: MSE < 0.01, reward MAE < 0.5 | Reconstruction MSE < 0.01 on held-out frames + reward prediction MAE < 0.5 — quantitative thresholds from DreamerV3 literature | ✓ |
| Episode-based: 100k steps, 10 eval episodes | Train for 100k steps, evaluate on 10 held-out episodes — pass if RSSM learns meaningful latent dynamics | |
| Qualitative: Visual rollout fidelity | RSSM can rollout 50-step imaginary trajectories that visually match real episodes — qualitative assessment | |
| Custom metrics | Let me define custom metrics and pass/fail criteria | |

**User's choice:** Quantitative: MSE < 0.01, reward MAE < 0.5
**Notes:** Concrete thresholds matching DreamerV3 literature; enables clear pass/fail for DMV3-01

---

## Process isolation architecture

| Option | Description | Selected |
|--------|-------------|----------|
| multiprocessing + stdin/stdout | Separate Python process with multiprocessing, stdin/stdout for communication, XLA_PYTHON_CLIENT_MEM_FRACTION=0.4 | ✓ |
| multiprocessing + Unix sockets | Separate Python process, Unix domain sockets for fast bidirectional communication | |
| subprocess + file-based | Separate process using subprocess.Popen with file-based communication (JSON config in, metrics out) | |
| Custom approach | Let me specify a different approach | |

**User's choice:** multiprocessing + stdin/stdout
**Notes:** Simple, robust, cross-platform; XLA_PYTHON_CLIENT_MEM_FRACTION=0.4 set in subprocess environment

---

## GymToEmbodiedWrapper design

| Option | Description | Selected |
|--------|-------------|----------|
| Standard embodied.Env protocol (reset in action) | Reset embedded in action['reset'] = True; observations returned as flat dict with is_first, is_last, is_terminal keys per embodied.Env spec | ✓ |
| Reset-as-separate-call variant | Separate reset() and step() calls but convert to dict format expected by DreamerV3 | |
| Custom protocol | Let me define the exact protocol mapping | |

**User's choice:** Standard embodied.Env protocol (reset in action)
**Notes:** Matches DreamerV3 expectations exactly; minimal friction for integration

---

## Pixel vs low-dim observations — Pixel mode

| Option | Description | Selected |
|--------|-------------|----------|
| Standard rgb_array render, 64x64, normalized | render_mode='rgb_array' from SurgicalEnv/MuJoCo/PyBullet at pixel_resolution (e.g., 64x64), returned as (H,W,3) RGB tensor normalized to [0,1] | |
| RGB + depth from simulator | Same but include depth/semantic channels if available from simulator | ✓ |
| Low-dim state (~50-100 dims) | (This was a separate question for low-dim) | |

**User's choice:** RGB + depth from simulator
**Notes:** Includes depth channel where simulator supports it → (H, W, 4) RGBA tensor

---

## Pixel vs low-dim observations — Low-dim state mode

| Option | Description | Selected |
|--------|-------------|----------|
| Full surgical state (~50-100 dims) | joint positions (qpos), joint velocities (qvel), gripper state (open/closed, force), task target position, tissue deformation metrics (max displacement, volume change, contact forces) | ✓ |
| Minimal robot state (~10-20 dims) | Only joint positions + gripper state + task target (~10-20 dims) — simpler, may lose tissue deformation info | |
| Custom low-dim state | Let me define exact composition | |

**User's choice:** Full surgical state (~50-100 dims)
**Notes:** Comprehensive state including tissue deformation metrics for surgical dynamics modeling

---

## Benchmark integration

| Option | Description | Selected |
|--------|-------------|----------|
| CLI flag for DreamerV3 checkpoint path | Add --dreamer-checkpoint flag to surg-rl benchmark pointing to DreamerV3 model checkpoint; ExperimentRunner loads it, runs eval, adds to aggregated results | |
| Scene config references DreamerV3 checkpoint | DreamerConfig in scene YAML specifies dreamer model path; benchmark reads it automatically when dreamer_comparison=True | |
| Auto-discovery from standard checkpoint location | Separate surg-rl dreamer-train command produces checkpoints in standard location; benchmark auto-discovers them | ✓ |
| Custom integration | Let me define the integration approach | |

**User's choice:** Auto-discovery from standard checkpoint location
**Notes:** Checkpoints in `models/dreamerv3/{task}_{obs_type}/`; benchmark auto-discovers latest per task/obs_type/backend

---

## OpenCode's Discretion

- Exact RSSM configuration for feasibility spike (hidden size, layers, discrete/continuous latent, kl_scale)
- JAX subprocess communication protocol details (JSON schema, message types, error handling)
- GymToEmbodiedWrapper exact observation/action dict key names and array shapes
- Low-dim state observation exact concatenation order and normalization
- DreamerV3 training hyperparameters for full integration (batch size, sequence length, learning rate, horizon, etc.)
- Checkpoint file format and `dreamer-train` CLI flags for resume, logging, evaluation
- How to run DreamerV3 evaluation without training (load checkpoint → act → compute metrics)

---

## Deferred Ideas

- DreamerV3 offline training from demonstrations (DMV3-06) — deferred to v0.5.0 per REQUIREMENTS.md
- 3D DreamerV3 video prediction — 2D pixel reconstruction sufficient for feasibility assessment per Out of Scope
- RLlib-backed centralized critic for MARL (MARL-05) — independent SB3 policies sufficient for dual-arm
- Task chains (grasp → cut → suture) (TASK-05) — composite scheduling deferred to v0.5.0
- COOLLADA/glTF mesh formats — OBJ is universal baseline for both backends
- Helm chart for K8s — Kustomize overlays sufficient for v0.3.0+