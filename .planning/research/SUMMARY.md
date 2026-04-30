# Project Research Summary

**Project:** Surg-RL
**Domain:** Surgical robotics reinforcement learning training system
**Researched:** 2026-04-29
**Confidence:** HIGH

## Executive Summary

Surg-RL is a well-architected surgical-robotics RL training system with a dual-backend simulator abstraction (MuJoCo/PyBullet), Pydantic-driven scene definitions, LLM-based scene generation, and Stable-Baselines3 training. The codebase is at v0.1.0 with 487 passing tests (~92% coverage) and a clean layered architecture.

However, the project carries significant residual technical debt from a rapid alpha build: 8 critical bugs with unexecuted fix plans, 3 unimplemented action types, placeholder gripper actuation, and soft-body fragility on macOS/CI. The core value (end-to-end text -> trained policy) is working, but the simulation layer needs stabilization before it can reliably train policies.

The recommended approach is a stabilization-first roadmap: fix critical bugs in Phase 1, complete the action space and gripper in Phase 2, harden the simulator in Phase 3, and then extend task geometry and real asset support in Phase 4+.

## Key Findings

### Recommended Stack

The existing stack is essentially correct and well-matched to the domain:
- **MuJoCo >=3.0.0** for primary rigid-body simulation (superior rendering and contact dynamics)
- **PyBullet >=3.2.5** for soft-body/deformable tissue (only viable open-source option)
- **Gymnasium >=0.29.0 + Stable-Baselines3 >=2.0.0** for RL training
- **Pydantic v2** for schema validation and settings
- **Python >=3.10** with `setuptools` + `pip` (no Poetry/Pipenv)

No stack changes are recommended. Alternative backends (Isaac Sim, RLlib, ROS2) are deferred to v2+.

### Must-Have Features (v1)

All table-stakes features are already implemented:
- Scene definition, loader, generation, simulation, RL environment, training pipeline, domain randomization, curriculum, CLI, demos, tests.

The gaps are **correctness**, not **coverage**:
- Gripper actuation (TODO stub)
- 3 unimplemented action types (`JOINT_TORQUES`, `ENDEFFECTOR_POSE`, `ENDEFFECTOR_DELTA`)
- 8 critical bugs documented but not yet fixed
- Joint control in demos (objects remain static)

### Architecture

Layered pipeline with Strategy pattern for simulators. Clean separation of concerns:
`scene_generation` -> `scene_definition` -> `simulators` -> `dynamics` -> `rl`

Key strength: `SceneDefinition` is the single source of truth. Any backend or RL algorithm change flows through the schema.

Key risk: Backend detection via duck typing (`hasattr`) is fragile. PyBullet-specific bugs (quaternion order, joint reset, soft-body reload) suggest the abstraction is leaking.

### Critical Pitfalls

Top 5 risks:
1. **PyBullet quaternion order bug** — all primitive robots mis-oriented (silent failure)
2. **State leakage between episodes** — joint state not reset, corrupting training data
3. **Collision penalty sign inversion** — `abs()` patches root cause; agent learns to collide
4. **VecEnv API mismatch in evaluation** — crashes with `n_envs > 1`
5. **API key exposure** — `.env.example` leaks placeholder to provider logs

## Implications for Roadmap

### Phase 1: Critical Bug Fixes
**Rationale:** 8 documented bugs silently corrupt simulation correctness, training data, reward semantics, and security. Must fix before any new features.
**Delivers:** Correct PyBullet primitives, clean episode resets, valid reward signs, multi-env evaluation, secure key handling.
**Addresses:** All 5 critical pitfalls above.
**Avoids:** Training on corrupted data, security exposure, incorrect robot kinematics.

### Phase 2: Action Space + Gripper Completion
**Rationale:** The action space is the primary interface between RL agent and simulator. 3 of 6 types are unimplemented; gripper is TODO.
**Delivers:** Full action type matrix, working gripper actuation in both backends, animated demos.
**Uses:** Existing `ActionBuilder`, `BaseSimulator` interface, `scene_builder.py` actuators.
**Implements:** Complete agent -> simulation control path.

### Phase 3: Simulator Robustness & Performance
**Rationale:** PyBullet soft-body reload is O(n) per episode. Mesh generation uses Python loops. State restore is incomplete. These limit training scale.
**Delivers:** Cached soft-body meshes, vectorized mesh generation, equivalent state save/restore across backends, faster reset.
**Uses:** `mesh_generation.py`, `vtk_io.py`, `PyBulletSimulator.get_state/set_state`.
**Implements:** Simulation performance layer for scaling up.

### Phase 4: Task Geometry + Real Asset Support
**Rationale:** Task observations (`needle_pos`, `entry_point`, `exit_point`) are stubs. All assets are procedural primitives.
**Delivers:** Geometry extraction from task objectives, real URDF/DAE/OBJ mesh loading, improved visual fidelity.
**Uses:** `scene_builder.py`, `base_simulator.py` mesh loading hooks.
**Implements:** Production-grade scene richness.

### Phase 5: Experiment Tracking + Cloud Training
**Rationale:** Currently only TensorBoard. Research teams need W&B/MLflow, distributed training, experiment reproducibility.
**Delivers:** Optional W&B/MLflow callbacks, Ray/RLlib backend, Docker support, CI/CD pipelines.
**Uses:** `rl/callbacks.py`, `rl/training.py`, new `infrastructure/` layer.
**Implements:** Team-scale research workflow.

### Phase Ordering Rationale

- Phase 1 must come first: correctness before features.
- Phase 2 depends on Phase 1: action types need correct joint control from bug fixes.
- Phase 3 is independent of Phase 2 but depends on Phase 1: performance tuning needs correct behavior to measure.
- Phase 4 depends on Phase 3: real assets need efficient loading (cached meshes).
- Phase 5 is optional and depends on Phase 4: cloud training needs rich scenes to be worth the infrastructure cost.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Simulator Robustness):** PyBullet soft-body state reset may require undocumented API calls; needs spike.
- **Phase 4 (Real Assets):** URDF/DAE loading in MuJoCo has subtle coordinate frame issues; needs research.
- **Phase 5 (Cloud Training):** Ray + SB3 integration patterns are evolving; may need to switch to RLlib entirely.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Bug Fixes):** All bugs are documented with specific line numbers and fix plans.
- **Phase 2 (Action Space):** SB3 action space mapping is well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing stack is correct; no changes needed |
| Features | HIGH | Table stakes fully implemented; gaps are correctness, not coverage |
| Architecture | HIGH | Clean layering; only concern is duck-typing fragility |
| Pitfalls | HIGH | 39 documented gaps, 8 with line-specific fix plans |

**Overall confidence:** HIGH

### Gaps to Address

- **PyBullet soft-body performance:** No official documentation on safe soft-body reset. May require upstream PyBullet issue or creative workaround.
- **MuJoCo soft-body maturity:** `mjOBJ_FLEX` is experimental. If surgical tissue simulation becomes critical, may need to invest in MuJoCo flex support or stick with PyBullet.
- **ROS2 integration:** Not yet researched. If real-hardware deployment is a goal, this is a significant gap.

## Sources

### Primary (HIGH confidence)
- `.planning/codebase/ARCHITECTURE.md` — existing system structure
- `.planning/codebase/STACK.md` — dependency inventory
- `.planning/codebase/CONCERNS.md` — 39 documented gaps + 8 critical bugs
- `AGENTS.md` — project-specific conventions and quirks
- `README.md` — feature inventory and test status

### Secondary (MEDIUM confidence)
- MuJoCo 3.x documentation — Renderer API, mjOBJ_FLEX
- PyBullet Quickstart Guide — quaternion conventions, soft-body API
- Stable-Baselines3 docs — VecEnv API, callback system
- dVRK (JHU) documentation — surgical robotics baseline

### Tertiary (LOW confidence)
- PyBullet forums — soft-body reset workarounds (community knowledge)
- MuJoCo Menagerie — surgical robot models (model availability)

---
*Research completed: 2026-04-29*
*Ready for roadmap: yes*
