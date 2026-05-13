# Domain Pitfalls — v0.4.0: Training Infrastructure & Realism

**Domain:** Surgical robotics RL training system
**Researched:** 2026-05-13
**Confidence:** HIGH
**Source coverage:** Context7 (PettingZoo, DreamerV3) + codebase audit + existing research

## Executive Summary

Five new feature areas are being added to a 910-test, dual-backend system. The core integration hazards are: (1) PettingZoo's API is **fundamentally incompatible** with the existing Gymnasium-based `SurgicalEnv` — it uses dict-based step/reset returns, per-agent method-based spaces, and agent-key semantics instead of positional tuples; (2) DreamerV3 uses `embodied.env.Env`, not Gymnasium, with a completely different step protocol that bakes reset into the action dict; (3) real mesh assets will collide with the primitive-fallback architecture that 910 tests assume; (4) the existing curriculum system must be extended (not replaced) to avoid regressing the already-fixed `apply_parameters` flow; (5) cross-backend determinism is impossible — benchmarking must treat MuJoCo and PyBullet as separate "hardware" targets.

Each feature section below maps specific code-level gotchas, warning signs, and prevention strategies.

---

## Feature 1: Real Surgical Assets (Instrument Meshes + Organ Geometries)

### Critical Pitfalls

#### Pitfall 1.1: Mesh Format Incompatibility Across Backends

**What goes wrong:** Real surgical meshes arrive as `.stl`, `.dae`, `.glTF`, or `.fbx`. MuJoCo's MJCF only loads `.obj` and `.stl` via `<mesh>`, while PyBullet only loads `.obj` and `.urdf`-embedded meshes. Loading a `.glTF` liver model silently falls back to a primitive box in one backend while partially working in the other.

**Why it happens:** `SceneBuilder.resolve_asset_path()` checks file existence but not format compatibility. `get_mesh_or_primitive()` falls back to primitives on any mesh load failure — format errors and missing files are indistinguishable.

**Consequences:** Different backends see different geometries. Training results are non-comparable. The `_missing_assets` deduplication set (line 119) masks format errors as "missing file" warnings.

**Prevention:**
1. Add a `MeshAsset.supported_formats` validator that rejects unsupported extensions before load
2. Add a `build_mesh_asset()` method to `SceneBuilder` that converts between formats (`.stl` → `.obj` via trimesh)
3. Distinguish "file missing" from "format unsupported" in warning messages
4. Add cross-backend integration test: assert both backends load the same mesh with the same vertex count

**Detection:** Warnings contain "Asset missing" but file exists on disk. One backend shows detailed geometry, the other shows primitive box.

**Phase:** Real Assets (Phase 2 recommended — after schema changes, before curriculum)

---

#### Pitfall 1.2: High-Poly Meshes Blow Up `reset()` Time

**What goes wrong:** Medical-grade organ meshes (e.g., segmented liver from CT) can have 200K+ triangles. The existing soft-body pipeline already has O(n) scene reload in PyBullet (Pitfall 5 from v0.1.0 research). Adding real meshes makes `reset()` take seconds per episode.

**Why it happens:** `PyBulletSimulator.reset()` reloads the full scene when `_soft_body_ids` is non-empty (line ~680). High-poly meshes multiply simulation time (PyBullet soft body is CPU-bound, quadratic in vertex count).

**Consequences:** Training throughput drops from 50+ FPS to 5-10 FPS. `reset()` dominates profiling output. Curriculum advancement becomes painful (100 episodes × 2s reset = 200s overhead).

**Prevention:**
1. Add mesh decimation pipeline (trimesh `simplify_quadratic_decimation`) that auto-generates LOD versions
2. Add `max_faces` validation in `SceneBuilder` — reject meshes > 50K faces with actionable error
3. Cache decimated meshes in `self._primitive_meshes` (like box/sphere/cylinder are already cached)
4. Add performance benchmark test: `reset()` must complete in < 500ms with up to 10K vertex soft body

**Detection:** `git status` shows large `.obj` files (>5MB). `reset()` time measured in seconds. Training progress bar stalls at episode boundaries.

**Phase:** Real Assets (Phase 2)

---

#### Pitfall 1.3: Breaking the Primitive Fallback Contract in 910 Tests

**What goes wrong:** 910 tests across 53 files build `SceneDefinition` objects with `TissueMeshDefinition(primitive="box", dimensions=(...))` and no `mesh` field. Adding mandatory mesh fields or changing `TissueMeshDefinition` validation could break all of them at once.

**Why it happens:** `TissueMeshDefinition.validate_geometry()` (schema.py:641-648) currently requires "either mesh or primitive." If real asset support adds a "mesh is required when assets_dir is set" validator, every existing test scene becomes invalid.

**Consequences:** Mass test failures. Potentially 500+ tests need updating. CI goes red for days.

**Prevention:**
1. Never make `mesh` required — keep `TissueMeshDefinition.mesh` optional
2. Add `prefer_mesh: bool = True` config field that controls resolution priority, not validation
3. Write migration test: assert all 53 test files still pass after schema changes
4. Use `model_construct()` in test factories to avoid triggering new validators early

**Detection:** PR CI failure with > 100 test failures. `pydantic.ValidationError` in `SceneDefinition` construction.

**Phase:** Real Assets (Phase 1 schema prep)

---

#### Pitfall 1.4: Asset Path Fragility in Docker/K8s

**What goes wrong:** Real meshes stored as relative paths (`assets/liver.obj`) resolve correctly on developer machines but fail in Docker containers (`/app/assets/` vs `/workspace/assets/`) and K8s pods (PVC mount points vary).

**Why it happens:** `SceneBuilder.resolve_asset_path()` (line 133) searches relative to `assets_dir`, CWD, and absolute — but none of these survive containerization. The `assets_dir` constructor param defaults to `None` — no default search path.

**Consequences:** All real meshes become primitive fallbacks in production deployments. Training silently uses simpler geometry.

**Prevention:**
1. Add `ASSETS_DIR` environment variable (pydantic-settings)
2. Add asset checksum verification at `load_scene()` time — fail early if mesh doesn't match expected hash
3. Generate a manifest file (`assets_manifest.json`) with expected checksums during build
4. In Dockerfile, bake mesh files into the image (not mounted at runtime) with a fixed `/app/assets` path

**Detection:** `_missing_assets` set grows in production but not locally. Hash mismatches in logs.

**Phase:** Real Assets (Phase 2), with Infrastructure tie-in

---

### Moderate Pitfalls

#### Pitfall 1.5: Color/Material Mismatch After Mesh Replacement

**What goes wrong:** Real instrument meshes come with embedded materials (Phong, PBR). Replacing primitives (which use `DEFAULT_COLORS` dict, line 91) with real meshes changes rendering appearance silently. The RL agent trained on primitive colors may fail on real-color mesh scenes.

**Why it happens:** MuJoCo `<geom type="mesh">` inherits material from the mesh file if present, ignoring the `rgba` attribute. PyBullet `createMultiBody` uses visual shape color.

**Consequences:** Visual domain gap. Agent trained with blue boxes fails on silver-metallic instruments. Observation distributions shift.

**Prevention:**
1. Force material override: set `rgba` on `<geom>` in MJCF regardless of mesh material
2. Add visual consistency test: render both backends, assert pixel similarity within tolerance
3. Document that real meshes may change visual observations

**Detection:** Side-by-side rendering shows different colors. Pixel difference test fails.

**Phase:** Real Assets (Phase 2)

---

## Feature 2: Surgical Task Curriculum (Progressive Difficulty + Task Chains)

### Critical Pitfalls

#### Pitfall 2.1: Regressing the `apply_parameters` Fix

**What goes wrong:** The existing `CurriculumScheduler.apply_parameters()` was a no-op (returned `True` without applying overrides) until Phase 3 fixed it. Adding `difficulty_level` to `TaskConfig` risks creating a second parameter path that bypasses the fixed `apply_parameters()` — or worse, introducing a similar bug where difficulty advances but parameters don't change.

**Why it happens:** Two parameter systems will exist: (1) `CurriculumStageConfig.parameter_overrides` (existing, now working), (2) new `TaskConfig.difficulty_level` + `difficulty_params`. If the v0.4.0 curriculum reads from the new field, the existing curriculum tests won't catch regressions in the old system.

**Consequences:** Curriculum silently stops working. Agent trains at same difficulty forever. Success rate plateaus.

**Prevention:**
1. Extend `CurriculumStageConfig` — do NOT create a parallel difficulty system
2. Add `task_chain: list[str]` to `CurriculumStageConfig` for task composition
3. Write regression test: `apply_parameters()` must change observable values after `advance_stage()`
4. Keep existing curriculum tests, extend with new assertion patterns

**Detection:** `surg-rl train --use-curriculum` shows same difficulty metrics across stages. Regression test fails: parameter values unchanged after curriculum advance.

**Phase:** Curriculum (Phase 3 — must come after Real Assets since tasks reference asset names)

---

#### Pitfall 2.2: Task Chain State Bleed Between Subtasks

**What goes wrong:** A procedure chain like "grasp → cut → suture" shares the same simulator instance across subtasks. If `reset()` between subtasks doesn't fully clear state, the needle from suturing is still embedded in the tissue from the cutting phase — the simulator is in an impossible state.

**Why it happens:** `SurgicalEnv.reset()` (line 474) does `simulator.reset()` + controller reset, but `get_state()`/`set_state()` are backend-specific and incomplete (Pitfall 7 in v0.1.0 research: "PyBullet state restore stores less than MuJoCo").

**Consequences:** Subtask 3 starts with phantom forces, embedded objects, or collision state from subtask 2. Agent learns to exploit state leakage.

**Prevention:**
1. Task chain transitions must call `simulator.reset()` (full reload), NOT `set_state()` (partial restore)
2. Add `assert env.simulator._simulation_time == 0.0` after chain transition
3. Add integration test: run chain 3 times, assert same initial observation on each run
4. For PyBullet, chain transition = full `load_scene()` + `reset()` (same as soft-body reset pattern)

**Detection:** Observations differ between chain runs. Episodic reward varies by chain position.

**Phase:** Curriculum (Phase 3)

---

#### Pitfall 2.3: Cross-Backend Difficulty Semantics Diverge

**What goes wrong:** "Easy" means different things in MuJoCo vs PyBullet. MuJoCo flex FEM uses `youngs_modulus` for stiffness; PyBullet Neo-Hookean uses `mu`/`lambda`. A difficulty level that sets `stiffness=500` on both backends produces drastically different tissue behavior.

**Why it happens:** `CurriculumStageConfig.parameter_overrides` is a flat dict — values are backend-agnostic strings. There's no per-backend parameter mapping.

**Consequences:** "Hard" in MuJoCo may be "Medium" in PyBullet. Cross-backend benchmark comparison is meaningless.

**Prevention:**
1. Add `mujoco_overrides` and `pybullet_overrides` sub-dicts to `CurriculumStageConfig`
2. Write difficulty calibration test: same difficulty level must produce similar deformation magnitude (within 20%) across backends
3. Document which parameters are backend-specific

**Detection:** Tissue deforms 3x more in PyBullet than MuJoCo at same difficulty. Agent success rate diverges by backend at same curriculum stage.

**Phase:** Curriculum (Phase 3)

---

### Moderate Pitfalls

#### Pitfall 2.4: `TaskConfig` Schema Bloat Breaking Scene Files

**What goes wrong:** Adding `difficulty`, `chain`, `prerequisites` fields to `TaskConfig` (schema.py:1047) requires updating all existing scene JSON/YAML files and all test scenes. Old scene files silently get default values — which may not be sensible (e.g., `difficulty=0.0` meaning "trivial").

**Why it happens:** Pydantic v2 provides defaults, so old files parse successfully — but the behavior changes.

**Consequences:** Existing demo scenes (`scenes/simple_suturing.json`) behave differently. Users report "my scene worked before, now it's too easy."

**Prevention:**
1. Use `Field(default=None)` for new optional fields — explicitly check for `None` at runtime
2. Add `@model_validator(mode="after")` that warns when new fields are missing (opt-in migration messaging)
3. Version scenes: add `schema_version` to `Metadata`, validate compatibility

**Detection:** Old scene files parse successfully but produce different simulation behavior. Success rate jumps.

**Phase:** Real Assets schema prep (Phase 1)

---

## Feature 3: Reproducible Benchmarking (Experiment Runner + Reports)

### Critical Pitfalls

#### Pitfall 3.1: Cross-Backend Nondeterminism Makes "Reproducible" Impossible

**What goes wrong:** Setting `seed=42` on both MuJoCo and PyBullet produces different trajectories. MuJoCo's constraint solver is deterministic for a given seed; PyBullet's soft-body solver is nondeterministic due to internal threading. Benchmarking "reproducibility" across backends is a false promise.

**Why it happens:** Physics engines are not identical — different contact models, integrators, solver tolerances. PyBullet `setTimeStep()` and `setRealTimeSimulation()` interact with thread scheduling.

**Consequences:** Reports claiming "reproducible results" are misleading. Users compare MuJoCo vs PyBullet benchmarks expecting identical behavior.

**Prevention:**
1. Treat MuJoCo and PyBullet as separate benchmark targets — never compare them directly
2. Within a single backend, guarantee determinism: set `PYTHONHASHSEED`, `OMP_NUM_THREADS=1`, `CUBLAS_WORKSPACE_CONFIG`
3. Run each benchmark 3+ times, report mean ± std (not single-run results)
4. Add seed reproducibility test: 3 runs with `seed=42` must produce identical cumulative reward (within float tolerance)

**Detection:** Same seed, same backend produces different benchmark results across runs.

**Phase:** Benchmarking (Phase 4 — after curriculum, since tasks drive benchmarks)

---

#### Pitfall 3.2: Hardware-Dependent Metrics Poisoning Comparisons

**What goes wrong:** Training speed (FPS) depends on GPU, Metal, or CPU. A benchmark showing "PPO converges in 100K steps" on an A100 is meaningless on an M1 Mac. Users compare numbers without understanding hardware context.

**Why it happens:** `TrainingConfig.device` defaults to `"auto"` (line 108). Metal, CUDA, CPU produce different wall-clock times for identical algorithm configurations.

**Consequences:** GitHub README benchmarks are misleading. "SAC is faster than PPO" depends entirely on hardware.

**Prevention:**
1. Benchmarks must report wall-clock time, NOT just step counts
2. Report hardware in benchmark output (GPU model, CPU model, RAM)
3. Add `--benchmark-tag hardware=<id>` to CLI for categorizing results
4. Never publish single-hardware benchmarks as general claims

**Detection:** Benchmark report doesn't mention hardware. Two users with different machines report contradictory findings.

**Phase:** Benchmarking (Phase 4)

---

#### Pitfall 3.3: Breaking Existing Training Config Save/Load

**What goes wrong:** `TrainingConfig.save()` (line 140) serializes the dataclass to JSON. Adding `algorithm` fields for DreamerV3 (which doesn't use SB3-style hyperparams) breaks `TrainingConfig.load()` because the AlgorithmConfig schema doesn't know about `world_model`, `imagination_horizon`, etc.

**Why it happens:** `AlgorithmConfig` is SB3-specific (learning_rate, gamma, gae_lambda, etc.). DreamerV3 has a completely different hyperparameter schema.

**Consequences:** Old config files fail to load. Training runs crash on startup.

**Prevention:**
1. Make `AlgorithmConfig` a base class with SB3-specific and Dreamer-specific subclasses
2. Use discriminated union via a `framework: Literal["sb3", "dreamerv3"]` field
3. Add `version` field to serialized configs, implement migration logic
4. Test: round-trip save/load for both SB3 and DreamerV3 configs

**Detection:** `json.JSONDecodeError` or `KeyError` when loading old config files.

**Phase:** Benchmarking (Phase 4) — needs DreamerV3 integration completed first

---

### Moderate Pitfalls

#### Pitfall 3.4: Metric Name Collisions Between SB3 and DreamerV3

**What goes wrong:** SB3 logs `rollout/ep_rew_mean`; DreamerV3 logs `episode/return`. The benchmark report generator must normalize these, or comparison tables show N/A for half the fields.

**Why it happens:** No shared metric ontology exists. Each framework names things differently.

**Consequences:** Benchmark reports are inconsistent. "Mean return" column has mixed sources.

**Prevention:**
1. Define a `BenchmarkMetric` enum with canonical names (RETURN_MEAN, RETURN_STD, WALL_TIME, STEPS)
2. Add `MetricNormalizer` that maps SB3 and DreamerV3 names to canonical names
3. Test: run PPO and DreamerV3, assert both produce `RETURN_MEAN` in report

**Detection:** Benchmark CSV has NaN columns. Report plot has only one line when two should exist.

**Phase:** Benchmarking (Phase 4)

---

## Feature 4: Full MARL Framework (PettingZoo, Dual-Arm Coordination)

### Critical Pitfalls

#### Pitfall 4.1: PettingZoo ParallelEnv Has an Incompatible API

**What goes wrong:** The single most dangerous pitfall. PettingZoo `ParallelEnv.step(actions)` returns `(observations: dict, rewards: dict, terminations: dict, truncations: dict, infos: dict)` — FIVE dictionaries keyed by agent ID. Gymnasium `Env.step(action)` returns `(obs, reward, terminated, truncated, info)` — FIVE values in a tuple.

Directly expecting Gymnasium-style tuple unpacking on PettingZoo steps will silently assign dictionaries to tuple positions, producing bizarre bugs.

**Specific code-level incompatibilities:**

| Concern | Gymnasium Env | PettingZoo ParallelEnv |
|---------|---------------|------------------------|
| `reset()` return | `(obs, info)` | `(observations: dict, infos: dict)` |
| `step()` return | `(obs, rew, term, trunc, info)` tuple | `(obs, rew, term, trunc, info)` dicts |
| Observation space | `self.observation_space` (property) | `env.observation_space(agent)` (method) |
| Action space | `self.action_space` (property) | `env.action_space(agent)` (method) |
| Agents | Single implicit agent | `env.agents` list, can change at runtime |
| Action shape | `np.ndarray` | `{agent_id: np.ndarray}` |
| Observation shape | `np.ndarray` or `dict` | `{agent_id: np.ndarray}` |

**Consequences:** `obs.shape` fails because `obs` is actually a dict keyed by "robot_left". Training loop silently trains on wrong data. 910 existing Gymnasium-based tests are irrelevant for MARL — need completely new test suite.

**Prevention:**
1. Never subclass `SurgicalEnv` for MARL — create a NEW class: `MultiAgentSurgicalEnv(ParallelEnv)`
2. Use `parallel_to_aec()` / `aec_to_parallel()` wrappers for SB3 compatibility
3. Add a `SurgicalEnv.to_pettingzoo()` conversion method that builds the PettingZoo environment from a Gymnasium environment config
4. Write MARL-specific tests from scratch — do not try to adapt existing single-agent tests

**Detection:** `AttributeError: 'dict' object has no attribute 'shape'`. Code does `obs, reward, done, _, info = env.step(action)` with PettingZoo env.

**Phase:** MARL (Phase 5 — last, due to API incompatibility risk)

---

#### Pitfall 4.2: Asymmetric Action/Observation Spaces Break Current Builders

**What goes wrong:** Dual-arm surgery needs different action spaces for each arm (left arm: 7-DOF joint positions + gripper, right arm: 7-DOF joint positions + scalpel). The existing `ActionBuilder` (action.py) and `ObservationBuilder` (observation.py) are single-agent — they assume one `ActionConfig`, one `ObservationConfig`.

**Why it happens:** `ActionBuilder.__init__()` takes one `ActionConfig`. `ObservationBuilder.extract_observation()` takes one `target_pos`. The builders have no concept of per-agent configuration.

**Consequences:** Both arms get identical action/observation spaces. Left arm gets scalpel action space even though it's holding forceps. Agent never learns coordinated behavior.

**Prevention:**
1. Add `AgentActionConfig` and `AgentObservationConfig` that wrap per-agent configs
2. `MultiAgentSurgicalEnv` instantiates one `(ActionBuilder, ObservationBuilder)` per agent
3. `action_space(agent)` method returns the appropriate space for that agent
4. Test: assert left and right action spaces differ when configured differently

**Detection:** Both arms have identical action dimension. Training reward never exceeds single-arm baseline.

**Phase:** MARL (Phase 5)

---

#### Pitfall 4.3: Agent Death/Removal Handling Missing

**What goes wrong:** In a dual-arm procedure, one arm completes its subtask (e.g., grasping) and should be "done." PettingZoo expects you to set `terminations[agent] = True` and remove the agent from `self.agents`. If the "done" arm keeps receiving actions and producing observations, the replay buffer fills with dead-agent noise.

**Why it happens:** The current system has no concept of partial completion — `terminated` is a single boolean for the whole episode. `TaskConfig.objectives` are per-task, not per-agent.

**Consequences:** Dead agent's policy keeps training on meaningless transitions. Replay buffer is contaminated. Learning slows.

**Prevention:**
1. Map objectives to agents: `TaskObjective.responsible_agent: str`
2. When an agent's objectives are complete, set `terminations[agent] = True` and remove from `env.agents`
3. Only the remaining agent's observations/rewards are produced
4. Add test: two-agent episode where agent 0 finishes first, assert only agent 1 transitions after that point

**Detection:** Both agents active for full episode even when one clearly finished. Replay buffer has transitions with `reward=0, done=False` for completed agent.

**Phase:** MARL (Phase 5)

---

### Moderate Pitfalls

#### Pitfall 4.4: `__getattr__` on ParallelEnv Causing Silent Bugs

**What goes wrong:** PettingZoo ParallelEnv implements `__getattr__` that falls through to the underlying AEC environment. Code that does `if hasattr(env, 'observation_space')` gets `True` but the value is a dict `{agent: space}`, not a flat `Space` — breaking SB3 compatibility wrappers.

**Consequences:** SB3's `check_env()` passes but `model.learn()` crashes on first batch.

**Prevention:** Always use `observation_space(agent)` method, never `env.observation_space` property. Add type-checking assertions before passing to SB3.

**Detection:** `TypeError: 'dict' is not a valid gym.Space`. SB3 internal `preprocess_obs()` fails.

**Phase:** MARL (Phase 5)

---

## Feature 5: DreamerV3 World Models

### Critical Pitfalls

#### Pitfall 5.1: DreamerV3 Uses `embodied.env.Env` — Not Gymnasium

**What goes wrong:** DreamerV3's environment interface (`embodied.env.Env`) is completely different from Gymnasium. `env.step(action)` returns a DICT with keys `('image', 'reward', 'is_first', 'is_last', 'is_terminal', ...)` — not a tuple. The action dict itself contains a `'reset': bool` key that controls episode reset inline. There is no separate `reset()` method.

**The DreamerV3 step protocol:**

```python
# Reset (is baked into action dict)
action = {'action': np.array(0, dtype=np.int32), 'reset': np.array(True)}
obs = env.step(action)  # Returns dict, not tuple
# obs = {'image': np.ndarray, 'reward': np.float32(0), 'is_first': True, ...}

# Normal step
action = {'action': np.array(5, dtype=np.int32), 'reset': np.array(False)}
obs = env.step(action)
# obs = {'image': ndarray, 'reward': float, 'is_first': False, 'is_last': False, ...}
```

**Consequences:** `SurgicalEnv` cannot be wrapped for DreamerV3 without a full adapter. Wrapping Gymnasium → embodied requires translating tuple returns to dict returns and implementing the reset-in-action protocol.

**Prevention:**
1. Build a `GymToEmbodiedWrapper` class that translates Gymnasium Env → embodied Env
2. Handle frame stacking, action repeat, and reset signal in the wrapper
3. Test the wrapper against DreamerV3's `wrap_env()` pipeline
4. NEVER try to make DreamerV3 talk Gymnasium natively — always go through the adapter

**Detection:** DreamerV3 crashes on first `env.step()`. `KeyError: 'reset'` in action dict.

**Phase:** DreamerV3 (Phase 6 — after benchmarking, which needs it for comparison)

---

#### Pitfall 5.2: JAX + PyTorch GPU Memory Conflict

**What goes wrong:** DreamerV3 uses JAX internally (world model, RSSM, policy). SB3 uses PyTorch. On the same process, JAX pre-allocates 90% of GPU memory by default (`XLA_PYTHON_CLIENT_MEM_FRACTION=0.9`), leaving nothing for PyTorch SB3 models. Running both frameworks' benchmarks sequentially crashes the second framework.

**Why it happens:** JAX and PyTorch both allocate GPU memory eagerly but don't coordinate. JAX's allocator doesn't release memory until process exit.

**Consequences:** Benchmark comparing SB3 PPO to DreamerV3 on the same script crashes on GPU out-of-memory after the first run.

**Prevention:**
1. Set `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` before importing DreamerV3
2. Run SB3 and DreamerV3 benchmarks in separate subprocesses (multiprocessing)
3. Use CPU mode for DreamerV3 benchmarks when GPU is shared (`--jax.platform cpu`)
4. Detect GPU memory pressure and warn before launching second framework

**Detection:** `RuntimeError: CUDA out of memory` when running both SB3 and DreamerV3 benchmarks. Second benchmark crashes.

**Phase:** DreamerV3 (Phase 6) — but prevention code needs to go into Phase 4 (Benchmarking)

---

#### Pitfall 5.3: Image Observation Encoding Mismatch

**What goes wrong:** DreamerV3 expects uint8 images in [0, 255] range, shape `(H, W, 3)`. `SurgicalEnv` produces float32 normalized observations (`normalize=True` in `ObservationConfig`, line ~305). Feeding normalized float images to DreamerV3's CNN encoder produces garbage latents.

**Why it happens:** `ObservationBuilder` normalizes by default. DreamerV3's world model encoder expects raw pixels.

**Consequences:** World model reconstructions are meaningless. DreamerV3 training diverges. Latent space is degenerate.

**Prevention:**
1. Add `raw_pixels` output mode to `ObservationConfig` (uint8, 0-255)
2. `GymToEmbodiedWrapper` must convert observation dtypes to DreamerV3 expectations
3. Add assertion in wrapper: image observations must be `uint8` dtype
4. Test: DreamerV3 reconstructs image within 0.05 MSE after 10K training steps

**Detection:** DreamerV3 reconstruction loss is 100x higher than expected. Image latent stddev → 0.

**Phase:** DreamerV3 (Phase 6)

---

#### Pitfall 5.4: DreamerV3 Config Complexity = Integration Minefield

**What goes wrong:** DreamerV3's config is enormous — RSSM with 8K deter units, 32 stoch × 64 classes, encoder/decoder with multiple resolutions, symexp_twohot value network, 15-step imagination horizon, etc. Default configs are tuned for Atari/DMC. Surgical robot control with 7-DOF continuous actions + tissue interaction is a completely different domain that needs careful hyperparameter selection.

**Why it happens:** DreamerV3's "fixed hyperparameters" claim applies to the training procedure (learning rate, loss scales), NOT to model architecture. Architecture choices (RSSM size, encoder capacity) massively impact performance.

**Consequences:** Default DreamerV3 config fails to learn surgical tasks. "DreamerV3 doesn't work" becomes the takeaway — but the config was wrong.

**Prevention:**
1. Start with `dmc_vision` config (continuous control + images), NOT `atari` (discrete actions)
2. Reduce RSSM size for surgical domains (fewer degrees of freedom than Atari)
3. Increase `imag_length` for long-horizon surgical procedures (default 15 → 30)
4. Document which config parameters were tuned and why
5. Run hyperparameter sweep on a simple reaching task before attempting full surgical procedure

**Detection:** DreamerV3 reward curve flatlines. World model prediction error doesn't decrease. Policy entropy collapses to zero.

**Phase:** DreamerV3 (Phase 6)

---

### Moderate Pitfalls

#### Pitfall 5.5: Throughput Gap Between DreamerV3 and SB3

**What goes wrong:** DreamerV3 trains on trajectories of length `batch_length=64` with `train_ratio=32` (32 model updates per env step). This requires much higher data throughput than SB3's `n_steps=2048` rollout buffer. If `SurgicalEnv.step()` takes 20ms (physics + rendering), DreamerV3 needs 100+ parallel environments to saturate the learner.

**Consequences:** DreamerV3 training is 10x slower than SB3 on the same hardware. "DreamerV3 is slow" becomes user perception.

**Prevention:**
1. Implement `AsyncPettingZooVecEnv` or DreamerV3's parallel runner
2. Disable rendering during world model training
3. Use frame-skip > 1 for DreamerV3 (action repeat = 2-4)
4. Benchmark throughput (env steps/second) before and after integration
5. Document realistic training time expectations

**Detection:** DreamerV3 GPU utilization < 20%. Training progress bar slow. Learner idle waiting for data.

**Phase:** DreamerV3 (Phase 6)

---

## Cross-Cutting Pitfalls (All Features)

### Critical

#### Pitfall X.1: Dependency Hell

**What goes wrong:** Adding PettingZoo, DreamerV3, trimesh (mesh decimation), and gymnasium-robotics triggers dependency conflicts. PettingZoo requires Gymnasium >= 0.29 (already satisfied). DreamerV3 requires `embodied`, `elements`, JAX — all new. JAX may require specific CUDA/cuDNN versions that conflict with PyTorch's requirements.

**Expected dependency explosion:**

| New Package | Minimum | Conflicts With |
|-------------|---------|----------------|
| `pettingzoo` | >=1.24 | Nothing (Gymnasium ≥0.29 already satisfied) |
| `dreamerv3` | git | `embodied`, `elements`, `jax`, `jaxlib`, `optax`, `tensorflow` (for TF datasets) |
| `trimesh` | >=4.0 | Nothing (pure Python + numpy) |
| `jax` / `jaxlib` | >=0.4 | PyTorch GPU memory (see 5.2); cuDNN version lock |
| `embodied` | git | Nothing (pure Python) |
| `elements` | git | Nothing (pure Python) |

**Consequences:** `pip install` failures. CUDA version mismatch at runtime. "It works on my machine" syndrome.

**Prevention:**
1. Add `[marl]` optional dep group: `pettingzoo>=1.24`
2. Add `[world_model]` optional dep group: `dreamerv3` (via git), `jax`, `jaxlib`
3. Both groups are OPTIONAL — core install still works without them
4. Test installation matrix: `pip install -e ".[marl]"`, `pip install -e ".[world_model]"`, `pip install -e ".[marl,world_model]"`
5. Pin exact versions in CI requirements lock file

**Detection:** `pip install` fails with version conflict. `import jax` crashes. CI failure on dependency resolution.

**Phase:** All phases — dependency groups defined in Phase 1 (schema prep), installed per-phase

---

#### Pitfall X.2: Test Explosion (910 → 1500+ Tests)

**What goes wrong:** Each new feature adds 100+ tests. MARL alone needs parallel env tests, dual-agent tests, coordination tests, agent-death tests. DreamerV3 needs wrapper tests, image encoding tests, config tests, integration tests. CI runtime grows from ~2 minutes to 8-10 minutes.

**Consequences:** Developer iteration slows. CI becomes a bottleneck. `pre-commit` hooks time out.

**Prevention:**
1. Mark MARL tests with `@pytest.mark.marl`
2. Mark DreamerV3 tests with `@pytest.mark.world_model`
3. Default CI (`pytest -m "not integration and not marl and not world_model"`) stays fast
4. Full suite only on PR merge or nightly
5. Use test parallelization: `pytest -n auto` (pytest-xdist)

**Detection:** `time pytest` grows from 2s to 60s. CI pipeline duration doubles.

**Phase:** All phases — test organization in Phase 1, per-feature tests in respective phases

---

#### Pitfall X.3: Cross-Backend Test Coverage Gap

**What goes wrong:** 80 tests in `test_simulators.py` test both backends. New MARL and DreamerV3 features will likely be developed and tested against MuJoCo first (it's simpler). PyBullet testing for these features will be incomplete, creating a coverage gap that's invisible until users hit it.

**Consequences:** MARL works on MuJoCo but silently fails on PyBullet. DreamerV3 image observations work with MuJoCo renderer but not PyBullet renderer.

**Prevention:**
1. Require at least ONE PyBullet integration test per feature before phase completion
2. Add `@pytest.mark.parametrize("backend", ["mujoco", "pybullet"])` to all new integration tests
3. CI matrix must include both backends
4. Flag tests that are MuJoCo-only with explicit `@pytest.mark.skip(reason=...)`

**Detection:** `test_simulators.py:80` tests but `test_marl.py` has 0 PyBullet tests. `pytest --backend=pybullet tests/test_marl.py` returns 0 collected.

**Phase:** All phases — enforcement in code review, not a specific phase

---

### Moderate

#### Pitfall X.4: `model_dump()` Enum Serialization in MARL/DreamerV3 Configs

**What goes wrong:** Pydantic v2 `model_dump()` returns Enum objects, not `.value` strings (documented in AGENTS.md). New configs for PettingZoo agents and DreamerV3 will hit this when serializing to YAML/JSON for checkpointing and benchmarking.

**Consequences:** `yaml.dump` raises `RepresenterError`. Config save/load round-trips fail.

**Prevention:**
1. Always use `model_dump(mode="json")` before YAML serialization
2. Add `ConfigBase` mixin with `to_dict()` that handles enum conversion
3. Test: serialize + deserialize every new config class

**Detection:** `RepresenterError: cannot represent ... Enum`. Config load produces dict instead of typed object.

**Phase:** All phases with new config classes

---

#### Pitfall X.5: Mypy Explosion with PettingZoo Generics

**What goes wrong:** PettingZoo uses `AgentID`, `ObsType`, `ActionType` type variables heavily. When combined with the existing `Observation`, `ActionConfig` types, mypy will produce hundreds of new errors — especially around dict typing (`dict[AgentID, ObsType]` vs `dict[str, np.ndarray]`).

**Consequences:** `pre-commit run mypy` fails with 50+ new errors. Type checking becomes a blocker.

**Prevention:**
1. Add `# type: ignore[assignment]` strategically on PettingZoo API boundaries
2. Create typed wrapper methods that resolve generic types to concrete types
3. Run mypy incrementally: add PettingZoo, fix types, THEN add DreamerV3

**Detection:** `mypy src/surg_rl` output grows from 0 errors to 50+. CI fails on type check step.

**Phase:** MARL (Phase 5) and DreamerV3 (Phase 6)

---

## Phase-Specific Warnings

| Phase | Topic | Most Likely Pitfall | Mitigation |
|-------|-------|---------------------|------------|
| Phase 1 | Schema prep (all features) | `TissueMeshDefinition` changes breaking 910 tests (1.3) | Keep `mesh` optional; add `model_construct()` factories in tests |
| Phase 1 | Schema prep | `TaskConfig` schema bloat (2.4) | All new fields default `None`; add `schema_version` |
| Phase 2 | Real Assets | High-poly meshes exploding `reset()` time (1.2) | Mesh decimation pipeline + `max_faces` validation |
| Phase 2 | Real Assets | Asset path fragility in Docker/K8s (1.4) | `ASSETS_DIR` env var + checksum manifest |
| Phase 3 | Task Curriculum | Regressing `apply_parameters` (2.1) | Extend, don't replace; add regression test |
| Phase 3 | Task Curriculum | Task chain state bleed (2.2) | Full `load_scene()` between chain transitions |
| Phase 4 | Benchmarking | Cross-backend nondeterminism (3.1) | Treat backends as separate targets; run 3+ trials |
| Phase 4 | Benchmarking | Metric name collisions (3.4) | Canonical `BenchmarkMetric` enum |
| Phase 5 | MARL | PettingZoo API incompatibility (4.1) | New `MultiAgentSurgicalEnv`; never subclass `SurgicalEnv` |
| Phase 5 | MARL | Asymmetric spaces not supported (4.2) | Per-agent `(ActionBuilder, ObservationBuilder)` |
| Phase 6 | DreamerV3 | Embodied Env vs Gymnasium (5.1) | `GymToEmbodiedWrapper` adapter layer |
| Phase 6 | DreamerV3 | JAX + PyTorch GPU conflict (5.2) | Subprocess isolation; `XLA_PYTHON_CLIENT_MEM_FRACTION` |
| Phase 6 | DreamerV3 | Image dtype mismatch (5.3) | `raw_pixels` output mode; wrapper dtype conversion |

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Mesh format incompatibility (1.1) | MEDIUM | Add format validator + trimesh conversion; existing asset tests still pass |
| High-poly reset time (1.2) | HIGH | Must add decimation pipeline; affects all real-mesh users |
| Breaking 910 tests (1.3) | HIGH | Roll back schema change; redesign as optional fields |
| Asset path fragility (1.4) | MEDIUM | Add env var + manifest; re-test Docker images |
| Regressing curriculum (2.1) | LOW | Extend test assertions; fix is local to `curriculum.py` |
| Task chain state bleed (2.2) | MEDIUM | Add `load_scene()` call at chain boundaries; test coverage needed |
| PettingZoo API mismatch (4.1) | VERY HIGH | Potential rewrite of `SurgicalEnv` for MARL; must be architecturally separate |
| Asymmetric spaces (4.2) | MEDIUM | Refactor builders to support per-agent config |
| Embodied Env vs Gymnasium (5.1) | HIGH | Must write adapter from scratch; no off-the-shelf solution exists |
| JAX+PyTorch conflict (5.2) | MEDIUM | Subprocess isolation is reliable but adds complexity |
| Image dtype mismatch (5.3) | LOW | Add `raw_pixels` config flag; wrapper converts dtype |
| Dependency hell (X.1) | MEDIUM | Define optional groups early; test install matrix |
| Test explosion (X.2) | MEDIUM | Add marker-based test selection; CI parallelization |

---

## "Looks Done But Isn't" Checklist for v0.4.0

- [ ] **Real assets:** Both backends render the same mesh (not primitive fallback on one)
- [ ] **Real assets:** `reset()` with 10K-vertex organ completes in < 500ms
- [ ] **Real assets:** Docker container resolves mesh paths without developer's filesystem
- [ ] **Curriculum:** `apply_parameters()` still changes simulation state (regression test passes)
- [ ] **Curriculum:** Task chain "grasp → cut → suture" produces identical initial state on each chain run
- [ ] **Benchmarking:** Same seed × 3 runs produces identical cumulative reward
- [ ] **Benchmarking:** SB3 and DreamerV3 metrics appear in same comparison table
- [ ] **MARL:** `env.step(actions)` returns dicts (not tuples) — agent code doesn't unpack tuple-style
- [ ] **MARL:** Left and right arm action spaces differ when configured differently
- [ ] **MARL:** Dead agent removed from `env.agents` after completing its objectives
- [ ] **DreamerV3:** `GymToEmbodiedWrapper` handles reset-in-action protocol correctly
- [ ] **DreamerV3:** Image observations are uint8 [0, 255] before entering world model encoder
- [ ] **DreamerV3:** JAX and PyTorch coexist without GPU OOM (subprocess or memory limit)
- [ ] **Dependencies:** `pip install -e ".[marl]"` and `pip install -e ".[world_model]"` both succeed independently
- [ ] **Tests:** `pytest -m "not marl and not world_model"` runs existing 910 tests and passes
- [ ] **Type check:** `mypy src/surg_rl` passes with PettingZoo imports present

---

## Sources

### High confidence (Context7 + official docs)
- `Context7: /farama-foundation/pettingzoo` — ParallelEnv API, AECEnv, SB3 wrapper, `__getattr__` behavior
- `Context7: /danijar/dreamerv3` — embodied Env interface, Agent API, config structure, step protocol
- `AGENTS.md` — Pydantic v2 quirks, simulator backend conventions, field guard notes
- `CONCERNS.md` (v0.1.0 codebase map) — 39 documented gaps, historical pitfalls

### Medium confidence (codebase audit)
- `src/surg_rl/scene_definition/schema.py` — `TissueMeshDefinition`, `TaskConfig`, `MeshAsset`, `AssetReference`
- `src/surg_rl/simulators/scene_builder.py` — `get_mesh_or_primitive()`, `resolve_asset_path()`, primitive cache
- `src/surg_rl/simulators/base_simulator.py` — `Observation` dataclass, `State` dataclass
- `src/surg_rl/rl/environment.py` — `SurgicalEnv.reset()`, `step()`, action mode propagation
- `src/surg_rl/rl/training.py` — `TrainingConfig`, `AlgorithmConfig`, save/load
- `src/surg_rl/rl/observation.py` — `ObservationConfig`, `ObservationBuilder`
- `src/surg_rl/rl/action.py` — `ActionConfig`, `ActionBuilder`
- `src/surg_rl/dynamics/curriculum.py` — `CurriculumStageConfig`, `apply_parameters()`
- `tests/` — 53 test files, 910 tests, test structure and patterns

### Community/ecosystem knowledge
- PettingZoo GitHub issues — SB3 MARL wrappers, `__getattr__` behavior
- DreamerV3 GitHub issues — GPU memory, image normalization
- PyBullet forum — soft-body performance, mesh loading limitations
- MuJoCo documentation — MJCF `<mesh>` format support

---

*Pitfalls research for: Surg-RL v0.4.0 Training Infrastructure & Realism*
*Researched: 2026-05-13*
*Previous pitfalls (v0.1.0-v0.3.2): All 8 original pitfalls shipped & fixed; 3 accepted tech-debt items still open*
