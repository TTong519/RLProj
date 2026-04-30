# Requirements: Surg-RL

**Defined:** 2026-04-29
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## v1 Requirements

### Critical Bugs

- [ ] **BUG-01**: PyBullet primitive robot quaternion order matches PyBullet convention `[x, y, z, w]`, producing correct orientation
- [ ] **BUG-02**: PyBullet `reset()` clears all joint positions and velocities to initial values, preventing state leakage between episodes
- [ ] **BUG-03**: `load_scene()` does not crash when `scene_definition.physics` is `None`
- [ ] **BUG-04**: `RewardConfig` validates that penalty values are non-negative; collision penalty sign contract is enforced without `abs()` patch
- [ ] **BUG-05**: Vision prompts produce valid JSON strings (not Python `repr()`) when passed to LLM APIs
- [ ] **BUG-06**: `CurriculumScheduler.apply_parameters()` applies stage-specific parameter overrides instead of returning `True` as a no-op
- [ ] **BUG-07**: `LightConfig` validator uses `model_copy(update=...)` instead of in-place `data` mutation
- [ ] **BUG-08**: `TrainingManager.evaluate()` handles both Gymnasium 5-tuple and SB3 `VecEnv` 4-tuple APIs without crashing

### Action Space

- [ ] **ACT-01**: `JOINT_TORQUES` action type is fully implemented and tested in both simulators
- [ ] **ACT-02**: `ENDEFFECTOR_POSE` action type is fully implemented and tested in both simulators
- [ ] **ACT-03**: `ENDEFFECTOR_DELTA` action type is fully implemented and tested in both simulators
- [ ] **ACT-04**: Gripper actuation (open/close) works in both MuJoCo and PyBullet backends
- [ ] **ACT-05**: Invalid or unimplemented `ActionType` values are rejected at scene load time with a clear error message

### Simulator Robustness

- [ ] **PERF-01**: Soft-body mesh data is cached between `reset()` calls, avoiding redundant file I/O
- [ ] **PERF-02**: Procedural mesh generation uses vectorized NumPy operations instead of nested Python loops
- [ ] **PERF-03**: `get_state()` and `set_state()` are behaviorally equivalent across MuJoCo and PyBullet backends
- [ ] **PERF-04**: `TrainingManager.evaluate()` reuses existing vectorized environments instead of creating fresh instances

### Task Geometry & Assets

- [ ] **TASK-01**: Needle position is extracted from task objectives and available in `Observation.needle_pos`
- [ ] **TASK-02**: Entry point and exit point geometry is available in `Observation` when task objectives specify them
- [ ] **TASK-03**: External mesh files (URDF / DAE / OBJ) can be referenced in `SceneDefinition` and loaded by `SceneBuilder`
- [ ] **TASK-04**: `SceneBuilder` logs a warning when a mesh fallback is used instead of a real asset file

### Security & Config

- [ ] **SEC-01**: `.env.example` does not contain a placeholder API key; `Settings.llm_api_key` rejects placeholder values
- [ ] **SEC-02**: LLM API keys are masked in log output (only last 4 characters shown)

## v2 Requirements

### Notifications

- **NOTF-01**: Multi-agent scenes support two or more cooperating surgical robots in the same simulation
- **NOTF-02**: ROS2 integration publishes simulator state to ROS topics for real-hardware validation
- **NOTF-03**: Cloud training experiments can be launched on Kubernetes with Ray/RLlib backend

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real patient data support | HIPAA/GDPR compliance burden; tool is for synthetic simulation only |
| Web dashboard for training monitoring | TensorBoard already provides this; web stack adds complexity |
| Mobile app | Surgical RL training is desktop/server-bound; no mobile use case |
| Real-time video chat between surgeons | Out of scope for an RL training framework |
| FDA certification / medical-device validation | Research tool, not a clinical product |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-01 | Phase 1 | Pending |
| BUG-02 | Phase 1 | Pending |
| BUG-03 | Phase 1 | Pending |
| BUG-04 | Phase 1 | Pending |
| BUG-05 | Phase 1 | Pending |
| BUG-06 | Phase 1 | Pending |
| BUG-07 | Phase 1 | Pending |
| BUG-08 | Phase 1 | Pending |
| ACT-01 | Phase 2 | Pending |
| ACT-02 | Phase 2 | Pending |
| ACT-03 | Phase 2 | Pending |
| ACT-04 | Phase 2 | Pending |
| ACT-05 | Phase 2 | Pending |
| PERF-01 | Phase 3 | Pending |
| PERF-02 | Phase 3 | Pending |
| PERF-03 | Phase 3 | Pending |
| PERF-04 | Phase 3 | Pending |
| TASK-01 | Phase 4 | Pending |
| TASK-02 | Phase 4 | Pending |
| TASK-03 | Phase 4 | Pending |
| TASK-04 | Phase 4 | Pending |
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-29*
*Last updated: 2026-04-29 after initial definition*
