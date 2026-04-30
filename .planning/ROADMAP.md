# Roadmap: Surg-RL

## Overview

This roadmap stabilizes the Surg-RL surgical-robotics RL training system (v0.1.0) by fixing 8 critical bugs, completing the action space, hardening simulator performance, and extending task geometry and real asset support. It is a correctness-first, stabilization-focused plan: no new features until the foundation is solid.

## Phases

- [ ] **Phase 1: Critical Bug Fixes** — Fix 8 documented critical bugs before any new features
- [ ] **Phase 2: Action Space + Gripper** — Complete unimplemented action types and gripper actuation
- [ ] **Phase 3: Simulator Robustness** — Performance optimization, state management, and caching
- [ ] **Phase 4: Task Geometry + Real Assets** — Bind task geometry to observations and load real mesh files
- [ ] **Phase 5: Experiment Tracking + Infrastructure** — W&B/MLflow, Docker, CI/CD pipelines

## Phase Details

### Phase 1: Critical Bug Fixes
**Goal**: All 8 documented critical bugs are fixed, tested, and committed. The simulation layer is correct before any feature work proceeds.
**Depends on**: Nothing (first phase)
**Requirements**: [BUG-01, BUG-02, BUG-03, BUG-04, BUG-05, BUG-06, BUG-07, BUG-08, SEC-01, SEC-02]
**Success Criteria** (what must be TRUE):
  1. Primitive robots in PyBullet have correct orientation (verified by test)
  2. Episode reset leaves all joint states at initial values (verified by test)
  3. Scene loads without crashing when `physics` is `None` (verified by test)
  4. Negative penalty configs are rejected at validation time; collision penalty rewards are always non-positive (verified by test)
  5. Vision prompts produce valid JSON strings when logged (verified by test)
  6. Curriculum stage parameter overrides actually change simulation parameters (verified by test)
  7. `LightConfig` validator does not mutate `data` dict in place (verified by test)
  8. `evaluate()` succeeds with both `DummyVecEnv(n_envs=1)` and `SubprocVecEnv(n_envs=2)` (verified by test)
  9. `.env.example` contains no placeholder key; `Settings` rejects placeholder values (verified by test)
  10. API key is masked in all log output (verified by test)
**Plans**: 3 plans

Plans:
- [x] 01-01: Fix simulator correctness bugs (quaternion order, joint reset, physics=None crash)
- [x] 01-02: Fix reward, curriculum, and config bugs (sign contract, apply_parameters, LightConfig, vision prompts)
- [x] 01-03: Fix evaluation and security bugs (VecEnv API, API key exposure)

### Phase 2: Action Space + Gripper
**Goal**: All action types are implemented and the gripper works in both backends. Demos show animated robot movement.
**Depends on**: Phase 1
**Requirements**: [ACT-01, ACT-02, ACT-03, ACT-04, ACT-05]
**Success Criteria** (what must be TRUE):
  1. `surg-rl train` can train with `JOINT_TORQUES`, `ENDEFFECTOR_POSE`, and `ENDEFFECTOR_DELTA` action types
  2. Gripper opens and closes in demos for both MuJoCo and PyBullet
  3. Invalid `ActionType` values are rejected at `SceneLoader.load()` time with a helpful error message
  4. Training callbacks show gripper state in TensorBoard logs
**Plans**: 3 plans

Plans:
- [ ] 02-01: Implement `JOINT_TORQUES` action type in both backends
- [ ] 02-02: Implement `ENDEFFECTOR_POSE` and `ENDEFFECTOR_DELTA` action types in both backends
- [ ] 02-03: Implement gripper actuation and add config-time action validation

### Phase 3: Simulator Robustness
**Goal**: Simulator reset is fast, state restore is equivalent across backends, and mesh generation is vectorized.
**Depends on**: Phase 1
**Requirements**: [PERF-01, PERF-02, PERF-03, PERF-04]
**Success Criteria** (what must be TRUE):
  1. Soft-body episode reset is <100ms (measured on suturing scene)
  2. Procedural mesh generation for 64³ cells completes in <1s
  3. `get_state()` → `set_state()` produces identical observation as initial `reset()` in both backends
  4. `evaluate()` reuses existing vectorized envs; no new env creation per call
**Plans**: 2 plans

Plans:
- [ ] 03-01: Optimize soft-body reset and mesh performance
- [ ] 03-02: Unify state save/restore across backends and fix VecEnv evaluation reuse

### Phase 4: Task Geometry + Real Assets
**Goal**: Task observations are populated from scene objectives and real mesh files can be loaded.
**Depends on**: Phase 2, Phase 3
**Requirements**: [TASK-01, TASK-02, TASK-03, TASK-04]
**Success Criteria** (what must be TRUE):
  1. Suturing scene observation contains `needle_pos` within 1e-3 of objective-specified geometry
  2. Entry/exit point observations match task objective geometry when specified
  3. Scene with external URDF/DAE/OBJ loads successfully (test with sample URDF)
  4. Fallback warning is logged once per missing asset, not per frame
**Plans**: 2 plans

Plans:
- [ ] 04-01: Bind task geometry (needle, entry, exit, incision) to observation pipeline
- [ ] 04-02: Add real mesh/URDF loading to SceneBuilder with fallback logging

### Phase 5: Experiment Tracking + Infrastructure
**Goal**: Research teams can track experiments, reproduce runs, and deploy training to cloud infrastructure.
**Depends on**: Phase 4
**Requirements**: [NOTF-01, NOTF-02, NOTF-03]
**Success Criteria** (what must be TRUE):
  1. `TrainingManager` supports optional Weights & Biases/MLflow callback
  2. Dockerfile builds the package with all optional extras
  3. GitHub Actions workflow runs `pytest`, `ruff`, `black --check`, and `mypy` on every PR
**Plans**: 2 plans

Plans:
- [ ] 05-01: Add W&B/MLflow callbacks and Docker support
- [ ] 05-02: Set up GitHub Actions CI/CD with lint, test, and type-check gates

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Critical Bug Fixes | 0/3 | Not started | - |
| 2. Action Space + Gripper | 0/3 | Not started | - |
| 3. Simulator Robustness | 0/2 | Not started | - |
| 4. Task Geometry + Assets | 0/2 | Not started | - |
| 5. Infrastructure | 0/2 | Not started | - |
