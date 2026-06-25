# Architecture Patterns: v0.6.0 Carried-Forward Debt Closure

**Domain:** Surgical-robotics RL training system — 4 tech-debt closure items integrating with an existing mature architecture
**Researched:** 2026-06-24
**Overall confidence:** HIGH (codebase-grounded integration points; DreamerV3 API at MEDIUM — official example.py unreachable, factory signatures from DeepWiki + PyPI docs)

## Scope

This document maps **only** the 4 v0.6.0 closure items onto the existing Surg-RL architecture. It is NOT a greenfield architecture survey. The existing architecture (BaseSimulator ABC, SurgicalEnv, CurriculumScheduler, TaskRewardRouter, DreamerSubprocess, FluidSimulator, K8s Kustomize) is treated as fixed substrate; each item is located at a precise integration point with new-vs-modified components explicit.

The 4 items:
- (a) Real DreamerV3 integration — replace `_build_agent` stub
- (b) TASK-02 per-level difficulty schema — DifficultyLevelConfig + discrete curriculum + scene blocks
- (c) 3D fluid flag — `dim_3d=True` path in PhiFlow solver
- (d) K8s PVC e2e — de-stub checkpoint-persistence test + organ-mesh licensing decision

## Existing Architecture Substrate (fixed)

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI (Typer) → training.py / dreamer training.py / marl-train       │
├─────────────────────────────────────────────────────────────────────┤
│  SurgicalEnv (Gymnasium) ── MultiAgentSurgicalEnv (PettingZoo)      │
│   ├─ BaseSimulator (ABC: MuJoCoSimulator | PyBulletSimulator)       │
│   ├─ TaskRewardRouter → 6 task reward classes                       │
│   │    └─ get_params_for_difficulty() / apply_difficulty()          │
│   ├─ CurriculumScheduler (additive; difficulty: float|DifficultyLevel) │
│   ├─ EnvironmentController / ParameterRandomizer / AdaptiveDifficulty│
│   ├─ FluidSimulator (PhiFlow 2D) — env-driven via env.step()        │
│   └─ BaseSimulator.fluid_step(dt) hook — no-op for MuJoCo/PyBullet  │
├─────────────────────────────────────────────────────────────────────┤
│  DreamerSubprocess (multiprocessing.Process, spawn ctx)             │
│   ├─ Parent: DreamerSubprocess (Pipe JSON protocol)                 │
│   └─ Child:  _subprocess_main → _run_subprocess_loop (JAX)          │
│        ├─ _build_agent(config)  ← STUB returns None  [CLOSURE (a)]  │
│        ├─ _train_loop / _evaluate / _save_checkpoint  ← STUBS       │
│        └─ _JsonStdout wrapper (PyTorch Pipe compatibility)          │
├─────────────────────────────────────────────────────────────────────┤
│  SceneDefinition (Pydantic v2, single source of truth)              │
│   ├─ TaskConfig.difficulty_level: DifficultyLevel | None  (v0.4.2)  │
│   ├─ FluidConfig (2D: Box(x,y), resolution (nx,ny))  [CLOSURE (c)]  │
│   └─ DreamerConfig (obs_type, pixel_resolution, mem_fraction)       │
├─────────────────────────────────────────────────────────────────────┤
│  K8s Kustomize: base/ (pvc.yaml, training-job.yaml, ...)            │
│   ├─ overlays/cpu/  ── overlays/gpu/                                │
│   └─ tests/k8s/test_pvc_e2e.py  ← STUB  [CLOSURE (d)]              │
└─────────────────────────────────────────────────────────────────────┘
```

## Invariants That MUST Be Preserved

These are non-negotiable architectural rules established in prior milestones. Every closure item must respect them.

| # | Invariant | Source | Threat from closures |
|---|-----------|--------|----------------------|
| INV-1 | **CurriculumScheduler extension is additive — never replaces Phase 3 fix** | D-v0.4.0, STATE.md | (b) discrete progression must extend, not rewrite, sample_parameters/advance_stage |
| INV-2 | **DreamerV3 process isolation via JAX subprocess (XLA_PYTHON_CLIENT_MEM_FRACTION=0.4)** | D-v0.4.0 Phase 24 | (a) real agent must live inside subprocess; no JAX in parent |
| INV-3 | **`_JsonStdout` wrapper replaces `os.fdopen` on PyTorch's non-blocking Pipe** | Phase 26 fix | (a) real `_train_loop` must still `print(json.dumps(...), flush=True)` through `_JsonStdout` |
| INV-4 | **Pydantic v2 + cross-package cycle-resolution pattern** (forward-ref + late import + model_rebuild) | Phase 29 D-SCHEMA-01 | (b) DifficultyLevelConfig must reuse this pattern if it references DifficultyLevel |
| INV-5 | **DifficultyLevel is `_FloatMixin(float, Enum)` — scalar `.value` is canonical downstream** | Phase 29 | (b) DifficultyLevelConfig keys/indexes use DifficultyLevel but downstream reads float |
| INV-6 | **Schema-first: new Pydantic v2 models with `None` defaults; existing models unchanged** | D-v0.4.0 | (b)(c) new fields optional with None defaults; no breaking changes |
| INV-7 | **PhiFlow CPU-first; env-driven fluid (env.step calls `self._fluid_simulator.step()`)** | Phase 31 DEBT-03 | (c) 3D path extends FluidSimulator; `fluid_step()` hook stays no-op for MuJoCo/PyBullet |
| INV-8 | **Phase 30 E2E test sentinel: asserts EXPECTED `RuntimeError("Agent not configured")` — STARTS FAILING when real dreamerv3 integrated** | Phase 30 D-30-01..05 | (a) test must FLIP to positive assertions (this is the closure signal) |
| INV-9 | **`difficulty` is the single source of truth — no separate `task_difficulty` field** | D-08 Phase 21 | (b) discrete levels feed into the same `difficulty` scalar path |
| INV-10 | **Benchmarking treats MuJoCo and PyBullet as separate targets — never cross-backend aggregate** | D-v0.4.0 | (a) DreamerV3 comparison reports stay per-backend |

---

## (a) Real DreamerV3 Integration

### Integration Point

`src/surg_rl/dreamer/subprocess.py:125-129` — the `_build_agent(config)` stub:

```python
def _build_agent(config: dict[str, Any]) -> Any:
    """Build DreamerV3 agent from config."""
    # This will be implemented when dreamerv3 is available
    # For now, return a mock that can be replaced
    return None
```

This is the single seam. The subprocess JSON protocol (CONFIG → CONFIG_ACK → TRAIN → METRICS → TRAIN_COMPLETE → EVAL → CHECKPOINT → SHUTDOWN) is already correct and stays unchanged. The `_JsonStdout` wrapper (INV-3) stays. Only the 5 stub functions get real implementations:

| Stub function | Line | Current | Real implementation |
|---------------|------|---------|---------------------|
| `_build_agent(config)` | 125-129 | `return None` | Construct dreamerv3 agent + env + replay + stream + logger from config |
| `_train_loop(agent, total_steps, eval_every)` | 132-134 | yields 1 zero-metric | Run dreamerv3 train driver, yield METRICS dicts |
| `_evaluate(agent, checkpoint, n_episodes)` | 137-139 | returns zeroed dict | Load checkpoint, run eval driver, return real metrics |
| `_save_checkpoint(agent, path)` | 142-144 | `pass` | `agent.save(path)` + write `final.pt` sentinel |
| `_load_checkpoint(agent, path)` | 147-149 | `pass` | `agent.load(path)` |

### Real `_build_agent` Wiring (inside JAX subprocess)

The subprocess is a JAX-only process (INV-2). `SurgicalEnv` itself does NOT import torch — torch is only for SB3, and `surg_rl.rl.__init__` uses PEP-562 lazy `__getattr__` so importing `SurgicalEnv` does not pull `stable_baselines3`/`torch`. This means the subprocess can safely construct a `SurgicalEnv` + `GymToEmbodiedWrapper` without GPU memory conflict, as long as `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` is set (already done at subprocess.py:19-21).

**New vs modified components:**

| Component | Status | Change |
|-----------|--------|--------|
| `subprocess.py::_build_agent` | **Modified** | Real dreamerv3 factory composition (see below) |
| `subprocess.py::_train_loop` | **Modified** | Real training driver loop |
| `subprocess.py::_evaluate` | **Modified** | Real eval driver |
| `subprocess.py::_save_checkpoint` / `_load_checkpoint` | **Modified** | Real checkpoint I/O |
| `wrapper.py::GymToEmbodiedWrapper` | **Unchanged** (reuse) | Already implements embodied.Env protocol; subprocess constructs its own instance |
| `training.py::run_dreamer_training` | **Unchanged** (parent orchestrator) | Already sends CONFIG + TRAIN + handles METRICS; the pipe protocol is correct |
| `tests/dreamer/test_dreamerv3_subprocess_e2e.py` | **Modified — FLIP sentinel** | INV-8: negative assertions → positive assertions |
| `DreamerConfig` (schema.py:1222) | **Modified — additive** | Add `encoder_keys`/`decoder_keys` fields for custom obs key config |

**`_build_agent` internal structure (recommended):**

```python
def _build_agent(config: dict[str, Any]) -> Any:
    """Build DreamerV3 agent + env bundle from config dict.

    Runs entirely inside the JAX subprocess. Constructs its own SurgicalEnv
    + GymToEmbodiedWrapper from the scene JSON passed via config, so no
    cross-process env interaction is needed (preserves INV-2).
    """
    import dreamerv3.main as d3_main
    from embodied.envs.from_gym import FromGym

    from surg_rl.dreamer.wrapper import GymToEmbodiedWrapper
    from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
    from surg_rl.scene_definition.loader import load_scene

    # 1. Construct env inside subprocess (no torch import — safe)
    scene = load_scene(config["scene_path"])
    env = SurgicalEnv(SurgicalEnvConfig(...), scene=scene)
    embodied_env = GymToEmbodiedWrapper(
        env, obs_type=config.get("obs_type", "state"),
        pixel_resolution=config.get("pixel_resolution", (64, 64)),
    )
    # 2. Wrap in FromGym for dreamerv3's embodied.Env contract
    wrapped = FromGym(
        embodied_env,
        obs_key="state" if config.get("obs_type") == "state" else "image",
    )
    # 3. Apply standard dreamerv3 wrappers (NormalizeAction, ClipAction, etc.)
    wrapped = d3_main.wrap_env(wrapped, **config.get("env_wrappers", {}))
    # 4. Build agent via factory: make_agent(obs_space, act_space, config.agent)
    agent = d3_main.make_agent(wrapped.obs_space, wrapped.act_space, ...)
    # 5. Build replay + stream + logger (needed by train driver)
    replay = d3_main.make_replay(...)
    stream = d3_main.make_stream(...)
    logger = d3_main.make_logger(...)
    return {"agent": agent, "env": wrapped, "replay": replay,
            "stream": stream, "logger": logger}
```

**Critical detail — `encoder.mlp_keys` / `encoder.cnn_keys`:** DreamerV3 requires explicit observation key configuration for custom envs (per PyPI docs + DeepWiki). The config dict must set `encoder.mlp_keys=["state"]` (state obs) or `encoder.cnn_keys=["image"]` (pixel obs), plus matching `decoder.mlp_keys`/`decoder.cnn_keys`. The existing `GymToEmbodiedWrapper` already produces `{"state": ...}` or `{"image": ...}` keys (wrapper.py:188-193, 259-264), so the key names are stable. This config must flow from `DreamerConfig` (schema.py:1222-1240) through `training.py::run_dreamer_training` → `DreamerSubprocess.send_config` → subprocess CONFIG message.

### Phase 30 Sentinel Test Flip (INV-8)

`tests/dreamer/test_dreamerv3_subprocess_e2e.py` currently asserts the **stub failure** (lines 61-104):

```python
# CURRENT (stub state):
with pytest.raises(RuntimeError, match="Agent not configured"):
    run_dreamer_training(task="suturing", obs_type="state", ...)
assert not (ckpt_dir / "final.pt").exists()
assert not (ckpt_dir / "training_metrics.json").exists()
```

**After real integration, FLIP to positive assertions:**

```python
# AFTER (real agent state):
metrics = run_dreamer_training(task="suturing", obs_type="state",
                               total_steps=1000, eval_every=500,
                               checkpoint_dir=str(tmp_path / "checkpoints"))
assert metrics is not None
assert (ckpt_dir / "final.pt").exists()  # checkpoint written
assert (ckpt_dir / "training_metrics.json").exists()
assert "reconstruction_mse" in metrics  # real eval metrics returned
```

The `pytestmark` skipif gate (lines 42-49: GPU + dreamerv3 + jax) stays unchanged — macOS local still skips, CI GPU host now runs the positive path. The docstrings that say "will START FAILING when real dreamerv3 is integrated" must be rewritten to describe the positive contract.

### Data Flow (unchanged pipe protocol, real agent)

```
Parent (training.py)                    Subprocess (JAX)
  │                                       │
  ├─ DreamerSubprocess(config) ──────────►│ _subprocess_main: set XLA mem fraction
  │                                       │ import jax; print READY
  │◄─── {"type":"READY"} ─────────────────┤
  ├─ send_config({scene_path, obs_type,   │
  │               encoder_keys, ...}) ───►│ _build_agent: load_scene → SurgicalEnv
  │                                       │ → GymToEmbodiedWrapper → FromGym
  │                                       │ → make_agent/make_replay/make_stream
  │◄─── {"type":"CONFIG_ACK"} ────────────┤
  ├─ train(total_steps=1000) ───────────►│ _train_loop: dreamerv3 driver
  │                                       │   for metrics in driver: print METRICS
  │◄─── {"type":"METRICS", step, loss,…}──┤  (via _JsonStdout → pipe.send)
  │◄─── {"type":"TRAIN_COMPLETE"} ────────┤
  ├─ save_checkpoint(path) ─────────────►│ _save_checkpoint: agent.save → final.pt
  │◄─── {"type":"CHECKPOINT_SAVED"} ──────┤
  ├─ shutdown() ───────────────────────►│ agent.close(); print SHUTDOWN_ACK
  │                                       │ exit
```

**Key invariant preserved:** every `print(json.dumps(...), flush=True)` inside the subprocess still routes through `_JsonStdout.write()` → `pipe.send(payload)` (INV-3). The real dreamerv3 driver's logging must be redirected to stderr or captured, NOT printed to stdout (which would corrupt the JSON pipe). This is the highest-risk pitfall (see PITFALLS).

---

## (b) TASK-02 Per-Level Difficulty Schema + Discrete Curriculum + Scene Blocks

This is a 3-part chain with strict internal dependency: schema → curriculum → scene blocks.

### Part 1: DifficultyLevelConfig (Pydantic v2 schema)

**Integration point:** `src/surg_rl/scene_definition/schema.py` — new model + new field on `TaskConfig` (lines 1087-1121).

**New component:**

```python
class DifficultyLevelConfig(BaseModel):
    """Per-difficulty-level parameter overrides (TASK-02 closure).

    None fields = inherit defaults from the task reward class's
    PARAM_BOUNDS + interpolate_params(level.value). Non-None fields
    override the interpolated value for this level.
    """
    tissue_stiffness: float | None = Field(default=None, ge=0.0, description="Override tissue stiffness (Pa)")
    target_precision_tolerance: float | None = Field(default=None, ge=0.0, description="Override target tolerance (m)")
    tool_position_noise: float | None = Field(default=None, ge=0.0, description="Override tool position noise std (m)")
    time_limit: float | None = Field(default=None, ge=0.1, description="Override episode time limit (s)")
```

**Modified component — `TaskConfig` gets a new optional field (INV-6: None default, existing fields unchanged):**

```python
class TaskConfig(BaseModel):
    # ... existing fields unchanged ...
    difficulty_level: "DifficultyLevel | None" = Field(default=None, ...)  # existing v0.4.2
    difficulty_overrides: dict["DifficultyLevel", DifficultyLevelConfig] | None = Field(
        default=None,
        description="Per-level parameter overrides. Keys are DifficultyLevel "
                    "members (EASY/MEDIUM/HARD). None = use interpolated defaults.",
    )
```

**Why `dict[DifficultyLevel, DifficultyLevelConfig]` not `list[3]`:** The milestone context says "scene-level `difficulty_blocks: list[3]`" but a dict keyed by enum is safer (no positional indexing errors, validates key membership via Pydantic, matches the `DifficultyLevel` scalar-is-canonical invariant INV-5). The scene JSON form is `{"EASY": {...}, "MEDIUM": {...}, "HARD": {...}}` — Pydantic v2 coerces string keys to the enum by float value (0.0/0.5/1.0) per the established v0.4.2 pattern. If the roadmap prefers `list[3]`, a `field_validator` can map `[easy_cfg, med_cfg, hard_cfg]` → dict internally; the dict is the recommended internal representation.

**Cycle-resolution (INV-4):** `DifficultyLevelConfig` is a pure schema model with no `surg_rl.*` imports — no cycle. The `dict[DifficultyLevel, ...]` annotation reuses the already-resolved `DifficultyLevel` forward ref (schema.py:1501-1506). Add `TaskConfig.model_rebuild()` again at the bottom if the new annotation introduces a new forward ref (it does not, since `DifficultyLevelConfig` is defined above `TaskConfig` in the same file — but if ordering changes, follow the pattern).

### Part 2: Discrete Curriculum Progression (additive — INV-1)

**Integration point:** `src/surg_rl/dynamics/curriculum.py` — `CurriculumScheduler` (lines 89-617).

The existing scheduler uses continuous `difficulty: float` (0.0→1.0) with 4 ordered stages (EASY/MEDIUM/HARD/EXPERT) and `advance_stage()`/`regress_stage()`. The discrete-level progression adds a **level-aware path** that maps `DifficultyLevel` enum members onto stages and consults `DifficultyLevelConfig` overrides during parameter sampling.

**New vs modified components:**

| Component | Status | Change |
|-----------|--------|--------|
| `CurriculumScheduler` | **Modified — additive** | New methods `set_difficulty_level(level)` / `advance_level()` / `current_level` property; `sample_parameters()` consults per-level overrides |
| `CurriculumStageConfig` | **Unchanged** | Already accepts `difficulty: float \| DifficultyLevel` (v0.4.2) |
| `CurriculumConfig` | **Modified — additive** | New optional `discrete_levels: bool = False` flag (opt-in; preserves existing continuous behavior) |
| `EnvironmentController` | **Unchanged** | Already delegates to scheduler |

**Additive methods (do NOT touch existing `advance_stage`/`sample_parameters`/`_should_advance`):**

```python
class CurriculumScheduler(BaseController):
    # ... existing code unchanged ...

    @property
    def current_level(self) -> DifficultyLevel | None:
        """Current discrete level, or None if continuous mode."""
        if not self.curriculum_config.discrete_levels:
            return None
        return DifficultyLevel(self.current_difficulty)  # 0.0/0.5/1.0 → EASY/MEDIUM/HARD

    def set_difficulty_level(self, level: DifficultyLevel) -> None:
        """Set the discrete difficulty level (additive; does not replace set_stage).

        Maps the 3-level enum onto the existing 4-stage machinery:
        EASY→CurriculumStage.EASY, MEDIUM→CurriculumStage.MEDIUM,
        HARD→CurriculumStage.HARD. EXPERT is unreachable via discrete levels
        (by design — discrete progression is 3-level).
        """
        stage_map = {DifficultyLevel.EASY: CurriculumStage.EASY,
                     DifficultyLevel.MEDIUM: CurriculumStage.MEDIUM,
                     DifficultyLevel.HARD: CurriculumStage.HARD}
        self.set_stage(stage_map[level])

    def advance_level(self) -> bool:
        """Advance to the next discrete level (EASY→MEDIUM→HARD). Returns False at HARD."""
        if not self.curriculum_config.discrete_levels:
            return False
        order = [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]
        current = self.current_level
        if current is None or current == order[-1]:
            return False
        self.set_difficulty_level(order[order.index(current) + 1])
        return True
```

**`sample_parameters` extension (additive — consult overrides when present):**

The existing `sample_parameters()` (lines 260-312) samples from `stage_cfg.parameter_overrides` + `task_param_bounds`. The extension adds: after building `merged_overrides`, if a `DifficultyLevelConfig` is attached to the current stage/level, apply its non-None fields as overrides on top. This is a **post-processing step**, not a rewrite:

```python
# After existing merged_overrides construction (line 275):
level_overrides = getattr(stage_cfg, "level_config", None)
if level_overrides is not None:
    if level_overrides.tissue_stiffness is not None:
        physics_params["stiffness"] = level_overrides.tissue_stiffness
    if level_overrides.tool_position_noise is not None:
        dynamics_params["action_noise"] = level_overrides.tool_position_noise
    # ... etc for target_precision_tolerance, time_limit
```

The `time_limit` override flows to `TaskConfig.time_limit` via the env-construction path (environment.py:498-514 already reads `task.difficulty_level` → this extends to read `task.difficulty_overrides[level].time_limit` when present).

### Part 3: Scene-Level difficulty_blocks Parsing

**Integration point:** `src/surg_rl/scene_definition/loader.py` — `SceneLoader` / `load_scene()`.

No loader change needed — Pydantic v2 validates the new `TaskConfig.difficulty_overrides` field automatically when parsing scene JSON. The "scene-level difficulty_blocks" are just the `difficulty_overrides` dict on the task block:

```json
{
  "task": {
    "name": "suturing",
    "task_type": "suturing",
    "difficulty_level": "MEDIUM",
    "difficulty_overrides": {
      "EASY":   {"tissue_stiffness": 8000, "target_precision_tolerance": 0.01, "time_limit": 90.0},
      "MEDIUM": {"tissue_stiffness": 12000, "target_precision_tolerance": 0.005, "time_limit": 60.0},
      "HARD":   {"tissue_stiffness": 16000, "target_precision_tolerance": 0.002, "time_limit": 45.0}
    }
  }
}
```

**New fixtures needed:** `tests/fixtures/scenes/suturing_difficulty_overrides.json` — a scene with all 3 levels of overrides, for end-to-end parsing + env-construction + curriculum-sampling tests.

### Data Flow (difficulty overrides)

```
Scene JSON (difficulty_overrides dict)
  │
  ▼
SceneLoader.load_scene() → Pydantic v2 validates → SceneDefinition.task.difficulty_overrides
  │
  ▼
SurgicalEnv._setup_rewards() (environment.py:485-517)
  ├─ reads task.difficulty_level → DifficultyLevel scalar
  ├─ reads task.difficulty_overrides[level] → DifficultyLevelConfig
  ├─ applies time_limit override to self._max_episode_time
  └─ passes stiffness/tolerance/noise overrides to TaskRewardRouter → reward.apply_difficulty()
  │
  ▼
CurriculumScheduler.sample_parameters() (additive post-processing)
  └─ applies tissue_stiffness / tool_position_noise overrides on top of stage params
  │
  ▼
ParameterRandomizer / EnvironmentController.apply_parameters(snapshot, simulator)
```

---

## (c) 3D Fluid Flag (`dim_3d=True`)

### Integration Point

`src/surg_rl/fluids/fluid_simulator.py` — `FluidSimulator.__init__` (lines 66-87) and `step()` (lines 107-143), plus `src/surg_rl/scene_definition/schema.py` `FluidConfig` (lines 1463-1488).

The `BaseSimulator.fluid_step(dt)` hook (base_simulator.py:336-357) and its MuJoCo/PyBullet no-op overrides stay **unchanged** (INV-7 — fluid is env-driven, not simulator-internal). The env wiring in `environment.py:723-736` already calls `self._fluid_simulator.step()` — no change needed there.

### New vs Modified Components

| Component | Status | Change |
|-----------|--------|--------|
| `FluidConfig` (schema.py:1463) | **Modified — additive** | New `dim_3d: bool = False` field; `resolution` accepts `tuple[int,int] \| tuple[int,int,int]` |
| `FluidSimulator.__init__` (fluid_simulator.py:66) | **Modified — branch** | If `dim_3d`: 3D `Box(x,y,z)` + 3D `StaggeredGrid(x,y,z)`; else current 2D path |
| `FluidSimulator.step` (fluid_simulator.py:107) | **Largely unchanged** | `make_incompressible` + `union(*geoms)` + `advect.mac_cormack` work for both 2D and 3D (verified — PhiFlow API is dimension-agnostic) |
| `force_computation.py` | **Modified — 3D branch** | Pressure-gradient integration currently uses 2D bounding boxes; needs 3D bbox branch |
| `BaseSimulator.fluid_step` | **Unchanged** | Stays no-op (INV-7) |
| `MuJoCoSimulator.fluid_step` / `PyBulletSimulator.fluid_step` | **Unchanged** | Stays no-op |
| `environment.py:723-736` | **Unchanged** | Already calls `self._fluid_simulator.step()` |

### FluidConfig Schema Change (INV-6: additive, default preserves existing)

```python
class FluidConfig(BaseModel):
    # ... existing fields unchanged ...
    dim_3d: bool = Field(default=False, description="True = 3D Eulerian grid (x,y,z); False = 2D xz-slice")
    resolution: tuple[int, int] | tuple[int, int, int] = Field(
        default=(32, 32),
        description="Grid resolution. 2D: (nx, ny). 3D: (nx, ny, nz).",
    )

    @field_validator("resolution")
    @classmethod
    def _validate_resolution(cls, v, info):
        dim_3d = info.data.get("dim_3d", False)
        if dim_3d and len(v) != 3:
            raise ValueError("dim_3d=True requires 3-tuple resolution (nx, ny, nz)")
        if not dim_3d and len(v) != 2:
            raise ValueError("dim_3d=False requires 2-tuple resolution (nx, ny)")
        if any(r < 4 for r in v):
            raise ValueError("Resolution must be >= 4 in each dimension")
        if any(r > 128 for r in v):
            raise ValueError("Resolution capped at 128 per dimension")
        return v
```

### FluidSimulator 3D Branch

```python
class FluidSimulator:
    def __init__(self, config: FluidConfig):
        from phi.flow import Box, StaggeredGrid, extrapolation
        if not config.enabled:
            raise ValueError("FluidConfig.enabled must be True")
        self.config = config
        self.dim_3d = config.dim_3d
        dims = config.bounds.get_dimensions()  # (width, height, depth)
        if self.dim_3d:
            domain = Box(x=float(dims[0]), y=float(dims[1]), z=float(dims[2]))
            self._velocity = StaggeredGrid(
                0.0, extrapolation.ZERO, domain,
                x=config.resolution[0], y=config.resolution[1], z=config.resolution[2],
            )
        else:
            # Existing 2D path (xz-slice) — UNCHANGED
            domain = Box(x=float(dims[0]), y=float(dims[2]))
            self._velocity = StaggeredGrid(
                0.0, extrapolation.ZERO, domain,
                x=config.resolution[0], y=config.resolution[1],
            )
        # ... rest unchanged ...
```

**`step()` requires no structural change** — `advect.mac_cormack`, `fluid.make_incompressible`, and `union(*geoms)` are dimension-agnostic in PhiFlow (verified: the 3D Wake Flow example uses the identical API). The `Solve` tolerances may need tuning for 3D (larger Poisson system → may need higher `max_iterations`); expose `max_iterations` as a config field or bump to 1000 for 3D.

**`force_computation.py` needs a real 3D branch** — the current `compute_obstacle_forces` integrates pressure gradients around 2D bounding boxes. For 3D, the bounding box is 3D and the gradient integration axis set expands. This is the highest-complexity sub-task in this closure item.

### Data Flow (3D fluid — unchanged from 2D except grid dimensionality)

```
FluidConfig(dim_3d=True, resolution=(32,32,32), bounds=BoundingBox(...))
  │
  ▼
FluidSimulator.__init__ → 3D StaggeredGrid + Box(x,y,z)
  │
  ▼
SurgicalEnv.step() (environment.py:723-736)
  ├─ every fluid_interval steps: self._fluid_simulator.step()
  │    ├─ advect.mac_cormack (3D velocity field)
  │    ├─ union(*obstacle_geometries) → Obstacle(merged_sdf)
  │    ├─ fluid.make_incompressible → (div-free velocity, pressure)
  │    └─ compute_obstacle_forces (3D bounding boxes) → forces dict
  └─ self._simulator.fluid_step(dt)  ← no-op (INV-7), unchanged
```

---

## (d) K8s PVC e2e + Organ-Mesh Licensing Decision

### Part 1: PVC e2e Test De-Stub

**Integration point:** `tests/k8s/test_pvc_e2e.py` (lines 35-50 — the stubbed `test_pvc_read_write_stub`).

**Recommended approach: kubectl subprocess (not python-client).** The kubernetes python-client adds a heavy dependency and requires kube-config wiring; `kubectl` is already the natural K8s interaction tool and the test is already gated on `kind` availability (lines 17-29). The test uses `subprocess.run(["kubectl", ...])` directly.

**New vs modified components:**

| Component | Status | Change |
|-----------|--------|--------|
| `tests/k8s/test_pvc_e2e.py::test_pvc_read_write_stub` | **Modified — de-stub** | Rename to `test_pvc_read_write_e2e`; implement 4-step cycle |
| `k8s/overlays/e2e/` | **New (optional)** | E2e overlay with small PVC (1Gi) + test Job manifests; or reuse `base/pvc.yaml` with a patched storage request |
| `k8s/base/pvc.yaml` | **Unchanged** | 50Gi PVC for production; e2e overlay patches to 1Gi for fast teardown |
| `pyproject.toml` | **Unchanged** | No `kubernetes` python-client dependency (kubectl subprocess approach) |

**Test body (replaces the TODO at line 44):**

```python
@pytest.mark.k8s
@pytest.mark.integration
@pytest.mark.slow
def test_pvc_read_write_e2e(self) -> None:
    """PVC create → write checkpoint → read checkpoint → verify → cleanup."""
    if not _kind_cluster_available():
        pytest.skip("No local kind cluster available")

    # 1. Apply PVC (e2e overlay with 1Gi)
    subprocess.run(["kubectl", "apply", "-k", "k8s/overlays/e2e/"], check=True)
    _wait_for("pvc", "surg-rl-checkpoints", "Bound", timeout=60)

    # 2. Launch writer Job — writes sentinel checkpoint to PVC
    subprocess.run(["kubectl", "apply", "-f", "k8s/e2e/writer-job.yaml"], check=True)
    _wait_for("job", "pvc-writer", "Complete", timeout=120)

    # 3. Launch reader Job — reads sentinel back, exits 0 if content matches
    subprocess.run(["kubectl", "apply", "-f", "k8s/e2e/reader-job.yaml"], check=True)
    _wait_for("job", "pvc-reader", "Complete", timeout=120)

    # 4. Cleanup
    subprocess.run(["kubectl", "delete", "-k", "k8s/overlays/e2e/"], check=False)
    subprocess.run(["kubectl", "delete", "job", "pvc-writer", "pvc-reader"], check=False)
```

**`_wait_for` helper** — polls `kubectl get <resource> -o jsonpath='{.status.phase}'` until desired state or timeout. This is the standard e2e polling pattern; no new dependency.

**New e2e manifests (small, focused):**
- `k8s/overlays/e2e/kustomization.yaml` — references `../../base`, patches PVC to 1Gi
- `k8s/e2e/writer-job.yaml` — Job that mounts `surg-rl-checkpoints` PVC, writes `/mnt/checkpoints/sentinel.txt` with known content, exits 0
- `k8s/e2e/reader-job.yaml` — Job that mounts PVC, reads `/mnt/checkpoints/sentinel.txt`, asserts content matches, exits 0 (or non-zero on mismatch — test checks Job status)

**Skipif gate stays:** the `@pytest.mark.k8s` + `@pytest.mark.integration` + `@pytest.mark.slow` marks + `_kind_cluster_available()` check (lines 32-42) ensure this only runs when a local `kind` cluster is present. CI without K8s skips; CI with `kind` runs the real cycle.

### Part 2: Organ-Mesh Licensing Decision

**This is a decision artifact, not code.** The research spike was already done in v0.5.0 Phase 35 (STATE.md: "Organ mesh licensing research spike (decision deferred to v0.6.0)"). The closure is the **decision** between:

| Option | License | Pros | Cons |
|--------|---------|------|------|
| **Procedural generation** (tetgen primitives) | MIT (project-owned) | No license risk; already have fallback pipeline (scene_builder OBJ primitives); works offline | Less anatomically realistic; requires param tuning per organ |
| **surgtoolloc dataset** | Research-only / CC-BY-NC? (must verify) | Real organ geometries; publication-quality | License may restrict redistribution; dataset download + conversion pipeline; network dependency |

**Recommended:** Procedural generation as default (ship in `assets/`), with surgtoolloc as an optional `[assets-surgtoolloc]` extra that downloads + converts at install time (lazy import pattern, INV-consistent). This keeps the core package MIT-clean and lets researchers opt into the dataset.

**Deliverable:** A `.planning/decisions/organ-mesh-licensing.md` ADR (Architecture Decision Record) documenting the choice, license verification, and the optional-extra integration plan. No `src/` code change required for the decision itself; if procedural generation is chosen, the existing `scene_builder.py` fallback path becomes the default and the `assets/` README documents it.

---

## Suggested Build Order (Considering Dependencies)

### Dependency Graph

```
(b1) DifficultyLevelConfig schema ──► (b2) discrete curriculum ──► (b3) scene blocks + fixtures
                                         │
                                         └─ (b2) depends on (b1) for DifficultyLevelConfig type
                                              (b3) depends on (b2) for scheduler.advance_level()

(c) 3D fluid flag — INDEPENDENT (no deps on b or d)

(d1) PVC e2e — INDEPENDENT
(d2) organ-mesh licensing decision — INDEPENDENT (documentation only)

(a) Real DreamerV3 — INDEPENDENT but GPU-gated, highest risk, do LAST
      └─ benefits from clean baseline (b)(c)(d) landed first
      └─ GPU-gated: CI GPU host required; macOS local skips (INV-8 sentinel flips)
```

### Recommended Phase Ordering

| Order | Item | Rationale | Can parallelize with |
|-------|------|-----------|----------------------|
| 1 | **(b1) DifficultyLevelConfig schema** | Pure schema, no deps, unblocks (b2)+(b3). Fastest to land. | (c), (d1), (d2) |
| 2 | **(c) 3D fluid flag** | Independent, well-scoped, PhiFlow API verified (HIGH confidence). Medium complexity (force_computation 3D branch). | (d1), (d2) |
| 3 | **(b2) Discrete curriculum progression** | Depends on (b1). Additive methods on CurriculumScheduler (INV-1). | (d1), (d2) |
| 4 | **(b3) Scene-level difficulty_blocks + fixtures** | Depends on (b2). Loader is unchanged (Pydantic validates); work is fixtures + env-construction wiring + tests. | (d1), (d2) |
| 5 | **(d1) PVC e2e + (d2) licensing decision** | Independent; can run any time but low-risk-landing before (a) is good. (d2) is documentation; (d1) is test+manifests. | — |
| 6 | **(a) Real DreamerV3 integration** | LAST. GPU-gated (CI GPU host), highest risk, requires `dreamerv3` + `jax` install. Sentinel test flip (INV-8) is the closure signal. Benefits from clean baseline. | — |

**Parallelization note:** Items (c), (d1), (d2) are fully independent and can run in parallel worktrees with (b1)→(b2)→(b3). The (b) chain is sequential internally. Item (a) is sequential-last due to GPU-gating and risk.

**Phase numbering:** continues from 36 (v0.5.0 ended at Phase 35). Suggested:
- Phase 36: (b1) DifficultyLevelConfig schema + (b2) discrete curriculum (combine — both touch curriculum.py, single worktree)
- Phase 37: (b3) scene blocks + fixtures + env-construction wiring
- Phase 38: (c) 3D fluid flag
- Phase 39: (d1) PVC e2e + (d2) organ-mesh licensing decision (combine — both K8s/asset-adjacent)
- Phase 40: (a) Real DreamerV3 integration + sentinel flip

Or if parallel worktrees are used: 36=(b1+b2), 37=(c)‖(d1+d2)‖(b3), 38=(a).

---

## Component Impact Summary

### New Components

| Component | Location | Closure item |
|-----------|----------|--------------|
| `DifficultyLevelConfig` model | `src/surg_rl/scene_definition/schema.py` | (b1) |
| `k8s/overlays/e2e/` kustomization | `k8s/overlays/e2e/` | (d1) |
| `k8s/e2e/writer-job.yaml` + `reader-job.yaml` | `k8s/e2e/` | (d1) |
| `tests/fixtures/scenes/suturing_difficulty_overrides.json` | `tests/fixtures/scenes/` | (b3) |
| `.planning/decisions/organ-mesh-licensing.md` ADR | `.planning/decisions/` | (d2) |

### Modified Components

| Component | Location | Closure item | Nature |
|-----------|----------|--------------|--------|
| `TaskConfig` | `schema.py:1087` | (b1) | Add `difficulty_overrides` field (None default) |
| `FluidConfig` | `schema.py:1463` | (c) | Add `dim_3d` field + resolution validator |
| `FluidSimulator.__init__` | `fluid_simulator.py:66` | (c) | 3D branch on `dim_3d` |
| `force_computation.py` | `src/surg_rl/fluids/` | (c) | 3D bounding-box branch |
| `CurriculumScheduler` | `curriculum.py:89` | (b2) | Additive: `set_difficulty_level`/`advance_level`/`current_level` + override post-processing |
| `CurriculumConfig` | `curriculum.py:65` | (b2) | Additive: `discrete_levels` flag |
| `SurgicalEnv._setup_rewards` | `environment.py:485-517` | (b3) | Read `difficulty_overrides[level]` for time_limit + reward params |
| `_build_agent` + 4 stubs | `subprocess.py:125-149` | (a) | Real dreamerv3 factory composition |
| `test_dreamerv3_subprocess_e2e.py` | `tests/dreamer/` | (a) | FLIP sentinel: negative → positive assertions |
| `test_pvc_e2e.py` | `tests/k8s/` | (d1) | De-stub: implement 4-step PVC cycle |
| `DreamerConfig` | `schema.py:1222` | (a) | Add `encoder_keys`/`decoder_keys` fields for custom obs key config |

### Unchanged Components (invariants preserved)

| Component | Why unchanged |
|-----------|---------------|
| `BaseSimulator.fluid_step` + MuJoCo/PyBullet overrides | INV-7: fluid is env-driven, hook stays no-op |
| `_JsonStdout` wrapper | INV-3: pipe protocol unchanged |
| `GymToEmbodiedWrapper` | Already implements embodied.Env protocol; subprocess constructs its own |
| `DreamerSubprocess` parent class + pipe protocol | INV-2: process isolation unchanged |
| `TaskRewardRouter` + 6 reward classes | Already have `apply_difficulty()`; (b) feeds overrides through existing path |
| `EnvironmentController` / `ParameterRandomizer` | Delegates to scheduler; scheduler's additive methods handle the rest |
| `k8s/base/pvc.yaml` | Production 50Gi PVC; e2e overlay patches to 1Gi |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Replacing CurriculumScheduler methods instead of adding
**What:** Rewriting `sample_parameters` or `advance_stage` to be level-aware.
**Why bad:** Violates INV-1 (additive — never replaces Phase 3 fix). Breaks existing continuous-difficulty users.
**Instead:** Add `set_difficulty_level`/`advance_level`/`current_level` as new methods; `sample_parameters` gets a post-processing step for overrides, not a rewrite.

### Anti-Pattern 2: Importing torch inside the DreamerV3 subprocess
**What:** Letting `_build_agent` pull in `stable_baselines3` or `torch` via `surg_rl.rl.__init__`.
**Why bad:** Violates INV-2 (JAX+PyTorch GPU memory conflict). Even with XLA_PYTHON_CLIENT_MEM_FRACTION=0.4, torch's CUDA context initialization in the subprocess can fragment GPU memory.
**Instead:** Import `SurgicalEnv` + `GymToEmbodiedWrapper` directly (not via `surg_rl.rl.__init__`); these do not import torch. The PEP-562 lazy `__getattr__` in `surg_rl.rl.__init__` means `from surg_rl.rl.environment import SurgicalEnv` is torch-free.

### Anti-Pattern 3: Letting dreamerv3 driver logs go to stdout in the subprocess
**What:** dreamerv3's `make_logger` writing to stdout.
**Why bad:** Corrupts the JSON pipe protocol (INV-3) — `_JsonStdout` sends every `print` as a pipe message; non-JSON log lines crash `json.loads` in the parent's `_read_message`.
**Instead:** Configure dreamerv3 logger to write to stderr (`sys.stderr` is already `os.fdopen(2, "w")` per subprocess.py:25) or to a log file. Only `print(json.dumps(...), flush=True)` goes to stdout.

### Anti-Pattern 4: Making `difficulty_overrides` a `list[3]` with positional indexing
**What:** `difficulty_overrides: list[DifficultyLevelConfig]` indexed 0/1/2.
**Why bad:** Positional indexing is error-prone (which index is HARD?); no Pydantic key validation; breaks INV-5 (enum is canonical).
**Instead:** `dict[DifficultyLevel, DifficultyLevelConfig]` with enum keys; Pydantic validates key membership; scene JSON uses `{"EASY": {...}, "HARD": {...}}`.

### Anti-Pattern 5: Changing `fluid_step()` hook to do real 3D fluid work
**What:** Implementing 3D fluid inside `MuJoCoSimulator.fluid_step` / `PyBulletSimulator.fluid_step`.
**Why bad:** Violates INV-7 (fluid is env-driven via `FluidSimulator`; hook is no-op for backends without native fluid).
**Instead:** 3D fluid lives in `FluidSimulator` (PhiFlow); the hook stays no-op; `env.step()` calls `self._fluid_simulator.step()` unchanged.

---

## Sources

- Codebase inspection (HIGH confidence): `src/surg_rl/dreamer/subprocess.py`, `wrapper.py`, `training.py`, `rl/difficulty.py`, `dynamics/curriculum.py`, `scene_definition/schema.py`, `fluids/fluid_simulator.py`, `simulators/base_simulator.py`, `rl/environment.py`, `k8s/base/pvc.yaml`, `tests/k8s/test_pvc_e2e.py`, `tests/dreamer/test_dreamerv3_subprocess_e2e.py`
- `.planning/PROJECT.md` Key Architecture Decisions + `.planning/STATE.md` Decisions/Deferred Items (HIGH — primary context)
- DreamerV3 API (MEDIUM): [danijar/dreamerv3 GitHub](https://github.com/danijar/dreamerv3), [PyPI dreamerv3 v1.5.0](https://pypi.org/project/dreamerv3/), [DeepWiki Getting Started](https://deepwiki.com/danijar/dreamerv3/3-getting-started), [DeepWiki Environment Integration](https://deepwiki.com/danijar/dreamerv3/8-environment-integration) — factory functions `make_agent(obs_space, act_space, config.agent)`, `embodied.envs.from_gym:FromGym`, `encoder.mlp_keys`/`cnn_keys` requirement. Official `example.py` unreachable (404) so exact instantiation code inferred from factory signatures + DeepWiki descriptions.
- PhiFlow 3D API (HIGH): [PhiFlow StaggeredGrids](https://tum-pbs.github.io/PhiFlow/Staggered_Grids.html), [PhiFlow fluid API](https://tum-pbs.github.io/PhiFlow/phi/physics/fluid.html), [Wake Flow 3D example](https://tum-pbs.github.io/PhiFlow/examples/grids/Wake_Flow.html) — confirms `StaggeredGrid(x,y,z, bounds=Box(x,y,z))` + `make_incompressible` dimension-agnostic.