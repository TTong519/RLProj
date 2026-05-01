---
phase: 03-simulator-robustness
plan: 02
subsystem: simulator

tags:
  - state-serialization
  - pybullet
  - mujoco
  - soft-body
  - training-manager
  - vecenv-cache

requires:
  - phase: 03-simulator-robustness
    plan: 01
    provides: mesh-caching + vectorization infrastructure

provides:
  - Cross-backend get_state/set_state round-trip fidelity (PERF-03)
  - PyBullet soft-body node position capture + restore
  - TrainingManager.eval() persistent env caching (PERF-04)

affects:
  - Phase 4 (assets / rendering) -- state fidelity assumed for reproducible episodes

tech-stack:
  added: []
  patterns:
    - "State.custom dict for backend-specific extensions"
    - "Config-keyed env caching with eager invalidation"

key-files:
  created: []
  modified:
    - src/surg_rl/simulators/pybullet_simulator.py
    - src/surg_rl/rl/training.py
    - tests/test_simulators.py
    - tests/test_rl_training.py

key-decisions:
  - "resetMeshData + resetJointState are sufficient for PyBullet state fidelity; no need for soft-body-ID persistence"
  - "Build eval env key from all config fields that affect env construction to minimize false cache hits"
  - "Cached VecEnv reset() on reuse instead of keeping warm -- balances correctness and performance"

requirements-completed: [PERF-03, PERF-04]

# Metrics
duration: 12min
completed: 2026-05-01
---

# Phase 3 Plan 2: State Save/Restore + Eval Env Caching Summary

**Cross-backend state fidelity and persistent evaluation environment caching for RL training.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-01T04:59:04Z
- **Completed:** 2026-05-01T05:11:04Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- **PyBullet `get_state()`** now captures soft-body node positions via `p.getMeshData()` into `State.custom["soft_body_nodes"]`, guarded by try/except per threat model T-03-04.
- **PyBullet `set_state()`** restores:
  - Joint positions/velocities via `resetJointState` using the same iteration order as `get_joint_states()` (sorted robot names, sorted joint names).
  - Soft-body node positions via `resetMeshData()` with flattened vertex arrays, also guarded by try/except.
- **MuJoCo** verified: `get_state() → set_state() → get_state()` yields qpos/qvel identical within 1e-6; observation fidelity within 1e-3.
- **TrainingManager** now caches the evaluation environment on `self._eval_env` and reuses it across `evaluate()` calls when config matches.
- `_build_eval_env_key()` hashes scene path, simulator, algorithm name/hyperparameters, n_envs, max_episode_steps, seed, and curriculum flags.
- Config mismatch triggers disposal of stale env and creation of a new one.
- `close()` properly disposes cached eval env.

## Task Commits

1. **Task 1: Implement soft-body state save/restore in PyBullet and cross-backend equivalence** — `f6f2624` (feat)
2. **Task 2: Implement persistent evaluation environment caching in TrainingManager** — `4efffb1` (feat)

## Files Created/Modified

- `src/surg_rl/simulators/pybullet_simulator.py` — Added soft-body node capture in `get_state()`; added joint state + soft-body node restoration in `set_state()`.
- `src/surg_rl/rl/training.py` — Added `_build_eval_env_key()`; modified `evaluate()` to cache/reuse eval env; updated `close()` to dispose cached env; added `_eval_env_key` state.
- `tests/test_simulators.py` — Added `TestStateSaveRestore` (MuJoCo + PyBullet round-trip) and `TestSoftBodyStateRoundtrip` (soft-body node fidelity).
- `tests/test_rl_training.py` — Added `TestEvalEnvCaching` (creation, reuse, invalidation).

## Decisions Made

- Used `resetMeshData()` (standard PyBullet API) instead of `setSoftBodyData()` (unavailable) for restoring soft-body vertices.
- Eval env key covers all fields passed to `make_vec_env` / `SurgicalEnvConfig` to avoid invisible mismatches.
- Cached env receives `reset()` on reuse to guarantee clean episode start.

## Deviations from Plan

**None — plan executed exactly as written.**

- Small test fixture adjustments (VecEnv mock signatures for 4-tuple step results) were necessary to match existing evaluate() internal unpacking logic; these are test wiring, not behavioral deviations.

## Issues Encountered

- None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced.

## Known Stubs

None — all data sources are wired to actual simulation state or config-derived keys.

## Self-Check: PASSED

- [x] All modified files exist and compile
- [x] All tests pass (579 passed, 2 xfailed, 4 xpassed)
- [x] Both commits present in git log

## Next Phase Readiness

- PERF-03 and PERF-04 complete. Phase 3 (Simulator Robustness) fully delivered.
- No blockers. Ready for Phase 4 (Real Assets + Rendering) or Phase 5 (Training Infrastructure) depending on roadmap priority.

---
*Phase: 03-simulator-robustness*
*Completed: 2026-05-01*
