# Project Research Summary

**Project:** Surg-RL v0.4.0 — Training Infrastructure & Realism
**Domain:** Surgical robotics RL training platform upgrade
**Researched:** 2026-05-13
**Confidence:** HIGH

## Executive Summary

Surg-RL v0.4.0 adds five capability axes to an existing 910-test, dual-backend (MuJoCo+PyBullet) RL system: real surgical mesh assets, a surgical task curriculum, reproducible benchmarking, PettingZoo multi-agent RL, and DreamerV3 world models. Three of these are straightforward extensions of existing infrastructure (assets uses trimesh over the current primitive pipeline; curriculum extends the existing CurriculumScheduler; benchmarking wraps TrainingManager). Two introduce fundamentally incompatible environment interfaces: PettingZoo `ParallelEnv` returns dict-based step/reset with per-agent method-based spaces, and DreamerV3's `embodied.Env` bakes reset into the action dict and returns observation dicts — neither matches the Gymnasium tuple protocol the codebase assumes everywhere.

The core recommendation is to keep `SurgicalEnv` as the canonical single-agent Gymnasium contract and build thin adapter wrappers (`PettingZooSurgicalEnv`, `DreamerEnvBridge`) that delegate to it. The single highest-risk stack decision is adding JAX (for DreamerV3) into a PyTorch codebase — it must be process-isolated with its own optional dependency group. Cross-backend determinism is impossible; MuJoCo and PyBullet must be treated as separate benchmark targets. The existing 910-test suite must be protected by making all new schema fields optional with `None` defaults and using marker-based test selection (`@pytest.mark.marl`, `@pytest.mark.dreamer`) to keep CI fast.

## Key Findings

### Recommended Stack Additions

**Two new libraries, one bumped version, zero core changes:**

| Addition | Version | Group | Purpose |
|----------|---------|-------|---------|
| trimesh | >=4.5.0 | `[assets]` | Mesh I/O for surgical instruments/organs; replaces primitive .obj fallbacks |
| pettingzoo | >=1.24.0 | `[marl]` | Multi-agent RL (ParallelEnv API, dual-arm coordination) |
| supersuit | >=3.9.0 | `[marl]` | MARL env wrappers (vectorization, frame stacking for SB3 integration) |
| wandb (bumped) | >=0.18.0 | `[benchmark]` | Stabilized `wandb.Table`/`wandb.plot.*` APIs; already in `[tracking]` |
| matplotlib/seaborn/pandas/rliable | latest | `[benchmark]` | Publication-quality plots, statistical benchmarking (IQM, stratified bootstrap) |
| dreamerv3 + jax + optax + elements | >=1.5.0 (PyPI) | `[dreamer]` | World model RL; JAX-based, **process-isolated** from PyTorch stack |

**Critical constraint:** JAX (DreamerV3) must NOT share a process with PyTorch (SB3). DreamerV3 runs subprocess-isolated with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`. No TensorFlow — the PyPI `dreamerv3` package uses JAX, not TF.

### Expected Features — Prioritized by Research

**P1 (v0.4.0 is incomplete without these):**
- 4 real OBJ instrument meshes (forceps, scalpel, needle driver, retractor) replacing primitive boxes
- 2 deformable organ meshes (liver, stomach) via tetgen pipeline
- 3 trainable tasks (suturing, grasping, cutting) with reward functions + SB3 training
- Progressive difficulty (easy/medium/hard) for all tasks
- Reproducible experiment runner with seed propagation + training curves
- Dual-arm PettingZoo `ParallelEnv` (independent PPO policies, shared observation)

**P2 (defer to v0.4.1 if schedule slips):**
- Knot-tying, needle insertion tasks
- Task chain system (grasp → cut → suture)
- DreamerV3 pixel-mode for single surgical task
- SB3 algorithm comparison reports

**P3 (v0.5.0+):**
- Asymmetric obs/action spaces per arm
- SB3 vs DreamerV3 benchmark comparison
- Hyperparameter sweeps, dissection task, multi-organ suite

### Architecture Approach

All five features are additive — no existing module is rewritten. The pattern is: schema extensions (Pydantic v2 models with `None` defaults) → new modules under `src/surg_rl/{assets,task,benchmarking,marl,dreamer}/` → CLI subcommands. `PettingZooSurgicalEnv` is a thin adapter over `SurgicalEnv` (Owns one instance, routes observations/actions per agent via `ObservationRouter`/`ActionAggregator`). `DreamerEnvBridge` translates Gymnasium → `embodied.Env` protocol (dict-based returns, reset-in-action). Task chain executor is a state machine inside `SurgicalEnv` that composes with the existing `CurriculumScheduler` (physical difficulty) to provide task difficulty + procedural complexity.

### Critical Pitfalls (Top 5)

1. **PettingZoo API incompatibility** — `step()` returns dicts, not tuples; agent code must never unpack tuple-style. Build a completely separate `MultiAgentSurgicalEnv(ParallelEnv)`, never subclass `SurgicalEnv`. Recovery cost: VERY HIGH.
2. **DreamerV3 embodied.Env protocol** — no separate `reset()` method; reset is baked into action dict. Must write `GymToEmbodiedWrapper` from scratch. Recovery cost: HIGH.
3. **JAX + PyTorch GPU memory conflict** — JAX pre-allocates 90% GPU memory, leaving nothing for SB3. Run in separate subprocesses with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`. Recovery cost: MEDIUM.
4. **Breaking 910 existing tests** — making mesh fields mandatory invalidates all existing test scenes. All new schema fields default to `None`; use `model_construct()` in test factories. Recovery cost: HIGH.
5. **Cross-backend nondeterminism** — MuJoCo and PyBullet are fundamentally different physics engines. Treat them as separate benchmark targets; never claim cross-backend reproducibility. Recovery cost: MEDIUM.

## Implications for Roadmap

Based on dependency analysis that de-risks the two high-risk features (MARL API incompatibility, DreamerV3 integration uncertainty):

### Phase 1: Schema Foundation
**Rationale:** All five features need new Pydantic v2 models. No feature can start before its schema exists. This is a pure-additive phase — existing models unchanged, all new fields optional. **Delivers:** `RealMeshAsset`, `TaskChainConfig`, `MultiAgentConfig`, `DreamerConfig`, `BenchmarkConfig` in `schema.py` + optional dependency groups in `pyproject.toml`. **Avoids:** Pitfalls 1.3 (breaking 910 tests), 2.4 (schema bloat), X.1 (dependency hell).

### Phase 2: Real Assets + Task Curriculum (parallel-capable)
**Assets:** Replace primitive box/cylinder/sphere generation with trimesh-loaded OBJ meshes. Add decimation pipeline, format validation, collision geometry generation. **Curriculum:** Extend `CurriculumScheduler` with task-type awareness, task-specific reward functions, and progressive difficulty. Task chain executor as a state machine in `SurgicalEnv`. **Delivers:** 4 instruments + 2 organs as real meshes; 3 trainable tasks with difficulty levels; task chain infrastructure. **Avoids:** Pitfalls 1.1 (format incompatibility), 1.2 (high-poly reset time), 2.1 (regressing `apply_parameters`), 2.2 (task chain state bleed).

### Phase 3: Multi-Agent RL (PettingZoo)
**Rationale:** MARL needs real instruments (Phase 2) for dual-arm scenes but is architecturally independent of curriculum. Build `MultiAgentSurgicalEnv(ParallelEnv)` as a clean adapter — never touch `SurgicalEnv` internals. **Delivers:** Dual-arm `ParallelEnv`, observation router, action aggregator, independent PPO policies. **Avoids:** Pitfalls 4.1 (API incompatibility — the biggest danger in v0.4.0), 4.2 (asymmetric builders), 4.3 (agent death handling), X.5 (mypy explosion with PettingZoo generics).

### Phase 4: Reproducible Benchmarking
**Rationale:** Must come after tasks exist (Phase 2) to have something to benchmark. Wraps `TrainingManager` in `ExperimentRunner` loop. Includes SB3-only benchmarks first; DreamerV3 comparison added in Phase 5. **Delivers:** `surg-rl benchmark/compare/report` CLI, seed propagation + config hashing, training curves, metric tables, W&B integration. **Avoids:** Pitfalls 3.1 (cross-backend nondeterminism — treat backends as separate targets), 3.2 (hardware-dependent metrics — always report wall-time + hardware spec), 3.4 (metric name collisions — use `BenchmarkMetric` enum).

### Phase 5: DreamerV3 World Models
**Rationale:** Highest risk (JAX + new env protocol + uncertain surgical dynamics modeling). Placed after benchmarking so it can compare against established SB3 baselines. Start with a feasibility spike on a single task (reaching or grasping) before committing to full surgical procedure training. **Delivers:** `GymToEmbodiedWrapper`, `DreamerEnvBridge`, `surg-rl dreamer-train`, pixel and low-dim observation paths. **Avoids:** Pitfalls 5.1 (embodied.Env protocol — wrapper from scratch), 5.2 (JAX+PyTorch GPU conflict — subprocess isolation), 5.3 (image dtype mismatch — uint8 raw pixels), 5.4 (config complexity — start with `dmc_vision` config, tune for surgical domain).

### Phase Ordering Rationale
- **Schema first** — unblocks all features, zero risk, Pydantic v2 pattern is well-understood.
- **Assets before curriculum** — curriculum needs real meshes for task-specific instrument assignments.
- **MARL before DreamerV3** — PettingZoo integration is engineering (well-understood API); DreamerV3 is research (uncertain feasibility). Get the known work done first.
- **Benchmarking before** (and after) **DreamerV3** — Phase 4 delivers SB3-only benchmarking while Phase 5 adds the DreamerV3 comparison capability. This decouples the report infrastructure from the risky world-model integration.
- **DreamerV3 last** — if the feasibility spike shows RSSM can't model surgical dynamics, defer to v0.5.0 without blocking the rest of v0.4.0.

### Research Flags

**Needs `/gsd-research-phase` during planning:**
- **Phase 5 (DreamerV3):** JAX `embodied.Env` protocol details, surgical domain config tuning, RSSM capacity for deformable dynamics. This is research-level uncertainty.

**Standard patterns (skip research-phase):**
- **Phase 1 (Schema):** Pydantic v2 is well-documented; existing codebase has strong patterns.
- **Phase 2 (Assets):** trimesh is the standard Python mesh library; additive to existing SceneBuilder.
- **Phase 3 (MARL):** PettingZoo ParallelEnv API is documented; adapter pattern is clean.
- **Phase 4 (Benchmarking):** Well-established pattern from rl-baselines3-zoo; wraps existing TrainingManager.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct PyPI verification for all additions; trimesh/wandb/pettingzoo confirmed working versions. JAX-PyTorch isolation strategy is proven. |
| Features | HIGH | Clear P1/P2/P3 split; surgical task definitions from JIGSAWS literature; MARL capability is bounded (dual-arm only). |
| Architecture | HIGH | All five features are additive; adapter pattern avoids rewriting SurgicalEnv; schema extensions are optional. |
| Pitfalls | HIGH | Direct codebase audit of 910 tests, scene_builder, curriculum, simulators. PettingZoo and DreamerV3 API gotchas verified via Context7 + official docs. |

**Overall confidence: HIGH** — with one caveat: DreamerV3's ability to model deformable surgical dynamics is an open research question. The architecture is correct regardless; the learning performance may not be.

### Gaps to Address

- **DreamerV3 surgery feasibility:** Whether RSSM can learn tet mesh cutting dynamics is unknown. Handle via feasibility spike in Phase 5; have a clear kill switch to defer to v0.5.0.
- **Organ mesh source licensing:** Need MIT/CC0 organ meshes. MuJoCo Menagerie has no surgical instruments. Candidate: surgtoolloc dataset or procedural generation. Resolve in Phase 2 planning.
- **SB3/PettingZoo training loop:** PettingZoo envs don't work directly with SB3's single-agent VecEnv. Need either RLlib multi-agent API (already partially in codebase) or custom training loop. Decide in Phase 3 planning.
- **PyBullet soft-body mesh limits:** Performance degrades quadratically with vertex count. Enforce `max_faces <= 50K` with actionable errors. Calibrate in Phase 2.

## Sources

### Primary (HIGH confidence — verified via Context7 + PyPI)
- Context7 `/mikedh/trimesh` — mesh formats, watertight checks, decimation
- Context7 `/farama-foundation/pettingzoo` — ParallelEnv API, SB3 integration, SuperSuit
- Context7 `/danijar/dreamerv3` — Agent init, JAX config, requirements.txt (`jax[cuda12]==0.4.33`, no TF)
- Context7 `/wandb/wandb` — Table/plot APIs (verified against 0.26.1)
- PyPI: trimesh 4.12.2, pettingzoo 1.26.1, supersuit 3.10.0, dreamerv3 1.5.0, wandb 0.26.1

### Secondary (MEDIUM — codebase audit)
- `src/surg_rl/scene_definition/schema.py` — existing MeshAsset, TaskConfig, TissueMeshDefinition
- `src/surg_rl/simulators/scene_builder.py` — primitive fallback pattern, mesh resolution
- `src/surg_rl/rl/training.py` — TrainingManager, AlgorithmConfig, save/load
- `src/surg_rl/dynamics/curriculum.py` — CurriculumScheduler, apply_parameters (Phase 3 fix)
- `tests/` — 910 tests across 53 files, marker patterns, backend parametrization

### Tertiary (reference)
- JIGSAWS dataset — surgical task definitions (suturing, knot-tying, needle passing)
- rl-baselines3-zoo — benchmark runner pattern, rliable integration
- AGENTS.md — Pydantic v2 quirks, simulator backend conventions, optional field guards

---
*Research completed: 2026-05-13*
*Ready for roadmap: yes*
*Conflicts resolved: STACK.md (authoritative) overrides ARCHITECTURE.md's tensorflow-cpu recommendation — DreamerV3 PyPI package uses JAX, not TF*
