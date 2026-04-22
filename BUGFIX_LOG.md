# Bug-Finding-and-Fixing Log

## Initial State
- All 262 tests pass, 2 skipped
- Date: 2026-04-22

## Bugs Identified & Fixed

### Critical
1. `training.py:294` — NameError: `algo_name` undefined in `_create_model`. Should use `algo_config.name.upper()`.
   - **Commit:** ec29c56
2. `callbacks.py` — SB3 callbacks use `__call__(**kwargs)` but SB3's `CallbackList` passes positional args via `ConvertCallback`, causing TypeError.
   - **Commit:** a950b9e
3. `rewards.py:577-586` — Collision penalties pass negative weights; `CollisionPenalty.compute()` subtracts weight, turning penalties into positive rewards. Also ignored `RewardConfig.scale` for DistanceReward.
   - **Commit:** 850b1cd
4. `pybullet_simulator.py` — Orientation stored as `[w,x,y,z]` but PyBullet `resetBasePositionAndOrientation` expects `[x,y,z,w]`.
   - **Commit:** d749ab4
5. `pybullet_simulator.py` — Robot initial poses never stored in `_initial_positions`/`_initial_orientations`, so `reset()` doesn't restore robots.
   - **Commit:** d749ab4
6. `pybullet_simulator.py` — `tissue_state` stores dict-of-dicts but `Observation.tissue_state` typed as `Dict[str, np.ndarray]`.
   - **Commit:** 1646ce5
7. `pybullet_simulator.py` — `load_scene` on re-load didn't clear old bodies, causing duplicates.
   - **Commit:** 134602d

### Moderate
8. `scene_builder.py:520-524` — Cylinder height uses `dims[2]` but `dims` only has 2 elements; height at index 1 is ignored.
   - **Commit:** f23d4d7
9. `environment.py` — Redundant global `np.random.seed(seed)` after `super().reset(seed=seed)`.
   - **Commit:** 4f0e592
10. `action.py:308-310` — `clip_actions` clips to action-space bounds before NORMALIZE scaling, destroying negative actions for positive-bounded dims.
    - **Commit:** 93599ad
11. `environment.py` — `get_state`/`set_state` broken for PyBullet (only saves qpos/qvel, not body_positions).
    - **Commit:** cbdab10
12. `simulators/` — `time_limit=0` treated as no limit due to truthiness check.
    - **Commit:** b1ec56e
13. `pybullet_simulator.py` — `_load_environment` crashes when `pybullet_data` not installed.
    - **Commit:** 7c45dff
14. `scene_builder.py` — `cleanup()` only cleared mesh cache when `temp_dir` exists.
    - **Commit:** a18437d
15. `observation.py` — Depth image fallback dtype was float32 instead of spec.dtype.
    - **Commit:** ad0b976
16. `environment.py` — Silent fallback on simulator `reset()` failure masked real errors.
    - **Commit:** 3dc8547

### Dynamics
17. `base_controller.py` — Off-by-one: `_episode` incremented before warmup check, so `warmup_episodes=1` doesn't skip first episode.
    - **Commit:** 6352023
18. `base_controller.py` — `step_update` compared `_step` against `warmup_episodes` (step count vs episode count).
    - **Commit:** 6352023
19. `base_controller.py` — `_emit` silently swallowed all callback exceptions.
    - **Commit:** 6352023
20. `parameter_randomizer.py` — `noise_scale or abs(...)` treated `0.0` as falsy, ignoring explicit zero noise.
    - **Commit:** 092c6c0, 03cd429
21. `curriculum.py` — `reset_curriculum` didn't deep-copy `DEFAULT_STAGES`, so mutations persisted across resets.
    - **Commit:** f5c831f
22. `curriculum.py` — Stage advancement used total episodes instead of per-stage episodes.
    - **Commit:** 62e8a80
23. `environment_controller.py` — `__repr__` produced malformed string with space before `)`.
    - **Commit:** 07a488e
24. `environment_controller.py` — RNG not synchronized with per-subsystem seeds; stale snapshot in `step_update`.
    - **Commit:** 79ff041
25. `adaptive_difficulty.py` — PROPORTIONAL delta could be negative; `performance_history` was shallow-copied.
    - **Commit:** 24640f8
26. `base_controller.py` — `log_uniform` could receive non-positive bounds, causing math domain error.
    - **Commit:** eb4ee93

## Final State
- All 262 tests pass, 2 skipped
- 24 commits applied
- No new critical bugs found in final review pass
- Minor remaining issues (non-critical): missing `Optional[str]` type hints in `cli.py`, redundant inline imports in scene generation parsers, edge-case shape validation in `observation.py`.
