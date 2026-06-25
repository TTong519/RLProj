# Technology Stack — v0.6.0 Carried-Forward Debt Closure

**Project:** surg-rl
**Milestone:** v0.6.0 (Real DreamerV3, TASK-02 per-level schema, K8s PVC e2e, 3D fluid flag)
**Researched:** 2026-06-24
**Scope:** Stack additions/changes needed to close the four carried-forward debt items only. The existing validated stack (Python >=3.10, MuJoCo 3.x, PyBullet >=3.2.5, Gymnasium >=0.29, Stable-Baselines3 >=2.0, Pydantic v2, PhiFlow 3.4.0, tetgen, trimesh, JAX, K8s/Kustomize manifests) is NOT re-researched.

## Headline Finding

**Three of the four debt items need ZERO new packages.** The existing pins are already current and capable:

- `dreamerv3~=1.5.0` + `jax~=0.4.20` -- v1.5.0 is the latest and only PyPI release; the programmatic `embodied.run.train` / `dreamerv3.Agent` API is already available inside the vendored `embodied` framework.
- `phiflow>=3.4.0` -- 3D Eulerian grids are natively supported; the `dim_3d=True` path is a constructor/validator change, not a library change.
- Pydantic v2 -- `DifficultyLevelConfig` is pure schema work reusing the v0.4.2 forward-ref + `model_rebuild()` pattern.

**One new dev-only extra is needed:** `pytest-kind` for the K8s PVC e2e test (replaces the raw-subprocess stub with a session-scoped `kind_cluster` fixture).

---

## Recommended Stack Changes

### (a) Real DreamerV3 Integration -- `_build_agent` stub flip

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `dreamerv3` | `~=1.5.0` (UNCHANGED) | World-model RL agent | v1.5.0 (Feb 22 2023) is the latest + only PyPI release -- no newer version exists. The existing pin is correct. |
| `jax` | `~=0.4.20` (UNCHANGED) | DreamerV3 backend | Compatible with dreamerv3 v1.5.0; already pinned. |
| `optax` | `>=0.1.7` (UNCHANGED) | DreamerV3 optimizer | Already in `[dreamer]` extra. |
| `embodied` (vendored) | bundled in `dreamerv3` | Training orchestration | NOT a separate PyPI install. `embodied.run.train(...)` and `embodied.jax.Agent` ship inside the `dreamerv3` package (same monorepo, `embodied/` subdir). |

**Programmatic API to wire into `_build_agent` / `_run_subprocess_loop`:**

```python
# Inside the JAX subprocess (after XLA_PYTHON_CLIENT_MEM_FRACTION is set):
import dreamerv3
from dreamerv3 import Agent  # inherits embodied.jax.Agent

# obs_space / act_space probed from one env instance (the GymToEmbodiedWrapper)
agent = Agent(obs_space, act_space, config)   # config = embodied.Config(dreamerv3.Config)

carry = agent.init_train(batch_size)                # -> carry state
carry, outs, metrics = agent.train(carry, batch)    # one gradient step on replay batch
carry, act, out = agent.policy(carry, obs, mode='train')  # env rollout action
metrics = agent.report(carry, data)                 # periodic diagnostics
data = agent.save()                                 # checkpoint serialize
agent.load(data)                                    # checkpoint restore
```

**Two viable wiring strategies (pick during phase planning, not here):**

1. **Reuse `embodied.run.train(make_agent, make_replay, make_env, make_stream, make_logger, args)`** as the orchestration inside the subprocess. Our existing `GymToEmbodiedWrapper` already produces the `embodied.Env`-compatible dict obs (`is_first`/`is_last`/`is_terminal`). This is the lowest-code path: supply `make_env=lambda: GymToEmbodiedWrapper(SurgicalEnv(...))`, `make_agent=lambda: Agent(obs_space, act_space, cfg)`, and let `embodied.run.train` drive replay/driver/logger/checkpoints. The existing `CONFIG/TRAIN/EVAL/CHECKPOINT` stdin/stdout JSON protocol then wraps `embodied.run.train`'s lifecycle (start/stop/metrics-forward).
2. **Hand-roll the loop** by instantiating `Agent` directly in `_build_agent` and calling `agent.policy()` / `agent.train()` from the existing `_run_subprocess_loop` branches. More control, more code, re-implements replay buffering and driver logic that `embodied.run.train` already provides.

**Recommendation:** strategy 1 unless the team needs fine-grained control over replay composition. The existing `_JsonStdout` wrapper + `DreamerSubprocess` parent class stay; only `_build_agent`, `_train_loop`, `_evaluate`, `_save_checkpoint`, `_load_checkpoint` get real implementations.

**Sentinel flip:** the Phase 30 E2E test currently asserts `RuntimeError("Agent not configured")` from the stub. Flipping `_build_agent` will make that test START FAILING -- that is the intended signal. The test must be updated in the same phase to assert positive completion (real agent constructed + >=1 train step + checkpoint save/load round-trip) gated on the existing `pytest.mark.skipif(GPU + dreamerv3 + jax)`.

**Do NOT add:** `dreamer` (PyPI v3.3.1, a *different* project -- `rafarodsa/dreamer-v3-purejax`, a pure-JAX reimplementation), `stable-baselines3` DreamerV3 port (does not exist), or a separate `embodied` PyPI install (it is vendored).

### (b) 3D PhiFlow Grid Fluids -- `dim_3d=True`

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `phiflow` | `>=3.4.0` (UNCHANGED) | 3D Eulerian grid fluid solver | 3D is natively supported in 3.4.0; no version bump. |

**Key API fact:** PhiFlow infers dimensionality from the `Box` + axis kwargs passed to `StaggeredGrid`, NOT from a `dim_3d` library flag. There is no `phi.flow.dim_3d` symbol. The `dim_3d=True` we are implementing is OUR config flag (`FluidConfig`), mapped to a 3D constructor at the `FluidSimulator` level.

**2D -> 3D constructor diff:**

```python
# Current 2D (fluid_simulator.py):
domain = Box(x=float(dims[0]), y=float(dims[2]))           # xz-slice
self._velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain,
                               x=config.resolution[0], y=config.resolution[1])

# 3D path (dim_3d=True):
domain = Box(x=float(dims[0]), y=float(dims[1]), z=float(dims[2]))
self._velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain,
                               x=config.resolution[0], y=config.resolution[1], z=config.resolution[2])
```

- `fluid.make_incompressible(velocity, obstacles, Solve(...))` works identically in 3D (pressure Poisson solve generalizes; `rel_tol`/`abs_tol`/`max_iterations` unchanged).
- The `union(*geoms)` multi-obstacle workaround (DEBT-05) is dimension-agnostic -- carries over unchanged.
- `compute_obstacle_forces` (force_computation.py) must handle a 3D pressure gradient; verify the per-obstacle bounding-box integration generalizes to a z-axis slice.
- Reference example: [PhiFlow Wake_Flow](https://tum-pbs.github.io/PhiFlow/examples/grids/Wake_Flow.html) -- full 3D cylinder wake with `Box(x=200, y=100, z=5)`, `infinite_cylinder(inf_dim='z')`, `iterate(step, batch(time=200), ...)`.

**Schema change required:** `FluidConfig.resolution: tuple[int, int]` must accept `tuple[int, int, int]` when `dim_3d=True`. Recommended form:

```python
dim_3d: bool = Field(default=False, description="Enable 3D Eulerian grid (vs 2D xz-slice)")
resolution: tuple[int, int] | tuple[int, int, int] = Field(
    default=(32, 32), description="Grid resolution (nx, ny) or (nx, ny, nz) when dim_3d=True"
)

@field_validator("resolution")
@classmethod
def _validate_resolution(cls, v, info):
    dim_3d = info.data.get("dim_3d", False)
    expected_len = 3 if dim_3d else 2
    if len(v) != expected_len:
        raise ValueError(f"Resolution must have {expected_len} dims when dim_3d={dim_3d}")
    if any(d < 4 for d in v):
        raise ValueError("Resolution must be >= 4 per dimension")
    if any(d > 128 for d in v):
        raise ValueError("Resolution capped at 128 per dimension")
    return v
```

**Do NOT add:** `mantaflow` (abandoned since 2022), `pyvista`/`vtk` (removed in v0.3.2 for tetgen), a GPU-fluid backend (CPU-first is the established decision; GPU fluids explicitly out of scope).

### (c) DifficultyLevelConfig -- Pydantic v2 Schema

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pydantic` | v2 (UNCHANGED) | Schema for per-level difficulty overrides + scene-level blocks | Pure schema work; reuses the v0.4.2 cycle-resolution pattern. |

**No new packages.** The established pattern (PROJECT.md Key Architecture Decisions) applies directly:

```python
class DifficultyLevelConfig(BaseModel):
    """Per-level difficulty overrides (TASK-02)."""
    tissue_stiffness: float | None = Field(default=None, ge=0.0, description="Override FEM stiffness")
    target_precision_tolerance: float | None = Field(default=None, ge=0.0, description="Success radius override")
    tool_position_noise: float | None = Field(default=None, ge=0.0, description="Observation noise std")
    time_limit: float | None = Field(default=None, gt=0.0, description="Episode time cap override (s)")
```

**Scene-level `difficulty_blocks: list[3]`:**

```python
# On SceneDefinition or TaskConfig (decide in phase planning):
difficulty_blocks: list[DifficultyLevelConfig] = Field(
    default_factory=list, description="Exactly 3 entries: [easy, medium, hard]"
)

@field_validator("difficulty_blocks")
@classmethod
def _exactly_three(cls, v):
    if len(v) != 0 and len(v) != 3:
        raise ValueError("difficulty_blocks must have exactly 3 entries [easy, medium, hard] or be empty")
    return v
```

**Discrete `CurriculumScheduler` level progression:** indexes into the 3-block list (0=EASY, 1=MEDIUM, 2=HARD) instead of the continuous `current_difficulty: float`. The existing `DifficultyLevel` `_FloatMixin(float, Enum)` stays for the scalar path; the discrete path adds a `current_level: int` (0..2) that selects `difficulty_blocks[current_level]` and feeds `apply_difficulty()` per reward class.

**Cross-package cycle resolution (reuse v0.4.2 pattern):** `from __future__ import annotations` + string forward-ref + late import at module bottom + `Model.model_rebuild()` + lazy local imports inside function bodies. The existing `TaskConfig.model_rebuild()` call at schema.py bottom already handles the `DifficultyLevel` forward ref; add `DifficultyLevelConfig` to the same late-import + rebuild block.

**Do NOT add:** `enum-tools`, a separate `difficulty_schema` package, or a JSON-schema generator (Pydantic v2 native validation is sufficient).

### (d) K8s PVC e2e Test -- `pytest-kind`

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pytest-kind` | `>=22.11.1` (**NEW, dev-only**) | Session-scoped `kind_cluster` fixture for PVC e2e | Battle-tested (stable since 2019), lightweight, matches the existing stub's `kind`-detection + `@pytest.mark.k8s` marker. |
| `pykube-ng` | transitive (via pytest-kind) | Lightweight K8s API client for PVC state polling | Bundled with pytest-kind; avoids the 30+ MB official `kubernetes` client. |
| `kind` (binary) | external prerequisite | Local Kubernetes cluster | Already detected by the existing stub's `_kind_cluster_available()`. |

**Why `pytest-kind` over alternatives:**

| Framework | Python client | Providers | Scope | Verdict |
|-----------|--------------|-----------|-------|---------|
| **pytest-kind** (hjacobs) | `pykube-ng` (lightweight) | kind only | session | **RECOMMENDED** -- stable since 2019, `kubectl(*args)` subprocess helper matches the declarative `kustomize apply` workflow, `load_docker_image` + `port_forward` + `kubeconfig_path` for debugging. |
| pytest-kubernetes (Blueshoe) | dict/kubectl | k3d/kind/minikube | per-test | More providers than needed; per-test cluster recreation is wasteful for a single PVC test. |
| pytest-k8s (v1.0.0, Jul 2025) | official `kubernetes>=33.1.0` (30+ MB) | kind only | session/module/class/function | Cleanest official-client integration but adds a heavy runtime dep for a dev-only test. |

**Integration with existing stub (`tests/k8s/test_pvc_e2e.py`):**

```python
# Add to pyproject.toml [project.optional-dependencies]
k8s-test = ["pytest-kind>=22.11.1"]

# Test body (replaces the TODO):
def test_pvc_read_write_cycle(kind_cluster):
    # kind_cluster fixture is session-scoped, skips if kind unavailable
    kind_cluster.kubectl("apply", "-f", "k8s/base/pvc.yaml")
    kind_cluster.kubectl("wait", "--for=condition=Bound",
                         "pvc/surg-rl-checkpoints", "--timeout=60s")
    # Launch Job that writes a checkpoint to the PVC mount
    kind_cluster.kubectl("apply", "-f", "tests/k8s/write-job.yaml")
    kind_cluster.kubectl("wait", "--for=condition=Complete",
                         "job/surg-rl-write", "--timeout=120s")
    # Launch Job that reads the checkpoint back and verifies
    kind_cluster.kubectl("apply", "-f", "tests/k8s/read-job.yaml")
    kind_cluster.kubectl("wait", "--for=condition=Complete",
                         "job/surg-rl-read", "--timeout=120s")
    # Assert via logs
    logs = kind_cluster.kubectl("logs", "job/surg-rl-read")
    assert "CHECKPOINT_OK" in logs
    # Cleanup
    kind_cluster.kubectl("delete", "-f", "tests/k8s/write-job.yaml")
    kind_cluster.kubectl("delete", "-f", "tests/k8s/read-job.yaml")
```

**Keep `kubectl` subprocess as the primary apply mechanism** (declarative, consistent with the existing `k8s/base/*.yaml` Kustomize workflow). Use the `kind_cluster.api` (pykube) only if polling PVC `.status.phase` programmatically is needed beyond `kubectl wait`.

**Organ-mesh licensing decision (same debt item, no stack impact):** this is a licensing/process decision (procedural generation vs surgtoolloc dataset), NOT a stack addition. Procedural generation reuses the existing `trimesh` + `tetgen` pipeline; surgtoolloc would add a data-download step (no new runtime dep). The decision is deferred to phase planning -- no library research needed here.

**Do NOT add:** the official `kubernetes` Python client (heavy, unnecessary for a PVC round-trip test), `helm` (Kustomize overlays are the established decision; Helm explicitly out of scope), `k3d`/`minikube` providers (`kind` is already the detected cluster).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| DreamerV3 agent | `dreamerv3~=1.5.0` (vendored `embodied.run.train`) | `dreamer` PyPI v3.3.1 (pure-JAX reimpl) | Different project, not a successor; would fork the codebase from the danijar reference implementation. |
| DreamerV3 orchestration | `embodied.run.train(...)` reuse | Hand-rolled `agent.train()` loop in `_run_subprocess_loop` | Hand-roll re-implements replay/driver/logger; only choose if fine-grained control is required. |
| 3D fluids | `phiflow>=3.4.0` 3D `StaggeredGrid` | Mantaflow / pyvista | Mantaflow abandoned since 2022; pyvista/VTK removed in v0.3.2. PhiFlow 3D is built-in. |
| 3D fluid flag | `FluidConfig.dim_3d: bool` + `resolution` union | Separate `FluidConfig3D` model | Union + validator is less code and keeps the config single-model; matches Pydantic v2 idiom. |
| K8s e2e framework | `pytest-kind>=22.11.1` | `pytest-k8s` (official kubernetes client) | Adds 30+ MB dev dep for one PVC test; pykube-ng is sufficient. |
| K8s e2e framework | `pytest-kind>=22.11.1` | Raw `subprocess.run(["kubectl", ...])` (status quo stub) | Loses fixture lifecycle (session cluster, kubeconfig, load_docker_image, port_forward); the stub already hand-rolls `_kind_cluster_available()` which pytest-kind provides correctly. |
| Difficulty schema | Pydantic v2 `DifficultyLevelConfig` model | JSON Schema + `jsonschema` validator | Project standard is Pydantic v2; reuses `model_rebuild()` cycle pattern. |

---

## Installation

```bash
# NEW dev-only extra for K8s PVC e2e (add to pyproject.toml)
pip install -e ".[k8s-test]"

# Existing extras (UNCHANGED, no re-install needed unless upgrading):
#   [dreamer]  -> dreamerv3~=1.5.0, jax~=0.4.20, optax>=0.1.7
#   [assets]   -> trimesh, tetgen
#   fluids     -> phiflow>=3.4.0 (already a core dep, not optional)

# External prerequisite for the PVC e2e test:
#   kind (Kubernetes in Docker) -- already detected by tests/k8s/test_pvc_e2e.py
```

**pyproject.toml diff (the only dependency change in v0.6.0):**

```toml
[project.optional-dependencies]
# ... existing extras unchanged ...
k8s-test = ["pytest-kind>=22.11.1"]
```

---

## Integration Notes with Existing Stack

1. **DreamerV3 subprocess isolation is unchanged.** `DreamerSubprocess` (multiprocessing spawn context, `_JsonStdout` pipe wrapper, `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`, `XLA_PYTHON_CLIENT_PREALLOCATE=false`) stays. Only `_build_agent` / `_train_loop` / `_evaluate` / `_save_checkpoint` / `_load_checkpoint` get real bodies. The `CONFIG/TRAIN/EVAL/CHECKPOINT/SHUTDOWN` stdin/stdout JSON protocol stays.

2. **`GymToEmbodiedWrapper` is already `embodied.Env`-compatible** (`is_first`/`is_last`/`is_terminal` dict obs, reset-in-action protocol). No wrapper change needed for the real agent wiring.

3. **3D fluids are additive.** `dim_3d=False` (default) preserves the existing 2D xz-slice path bit-for-bit. The `FluidSimulator.step()` body branches on `config.dim_3d` for the `Box`/`StaggeredGrid` construction only; `make_incompressible` + `union(*geoms)` + `compute_obstacle_forces` are shared. Existing 2D tests stay green.

4. **`DifficultyLevelConfig` is additive to the schema.** Existing `TaskConfig.difficulty_level: DifficultyLevel | None` (scalar enum) stays for backwards compat; `difficulty_blocks: list[DifficultyLevelConfig]` is a new optional field defaulting to empty. Existing scenes without `difficulty_blocks` load unchanged.

5. **K8s PVC e2e is dev-only.** `pytest-kind` is in `[k8s-test]` extra, never imported at runtime. The `@pytest.mark.k8s` + `@pytest.mark.integration` + `@pytest.mark.slow` markers already exist in `pytest.ini`. The test stays skipped locally (no `kind` cluster) and runs in CI with a `kind` provisioner.

6. **GPU gating preserved.** The DreamerV3 real-integration E2E (flipped Phase 30 test) keeps the existing `pytest.mark.skipif` on (GPU + `dreamerv3` + `jax`); macOS local skips, CI GPU host validates. The 3D fluid test and K8s PVC test are NOT GPU-gated.

---

## Sources

- [dreamerv3 v1.5.0 on PyPI](https://pypi.org/project/dreamerv3/) -- latest + only release (Feb 22 2023); confidence MEDIUM (web).
- [danijar/dreamerv3 README](https://github.com/danijar/dreamerv3/blob/main/README.md) -- CLI entrypoint `python -m dreamerv3.main`, YAML config, `--jax.platform` flag; confidence MEDIUM (web).
- [danijar/dreamerv3 agent.py](https://github.com/danijar/dreamerv3/blob/b65cf81a/dreamerv3/agent.py) -- `Agent(embodied.jax.Agent)` with `init_train/train/policy/report/save/load`; confidence MEDIUM (web).
- [danijar/dreamerv3 embodied/run/train.py](https://github.com/danijar/dreamerv3/blob/b65cf81a/embodied/run/train.py) -- `train(make_agent, make_replay, make_env, make_stream, make_logger, args)` orchestration; confidence MEDIUM (web).
- [danijar/dreamerv3 embodied/core/base.py](https://github.com/danijar/dreamerv3/blob/b65cf81a/embodied/core/base.py) -- abstract `Agent` interface contract; confidence MEDIUM (web).
- [DeepWiki: DreamerV3 Agent Architecture](https://deepwiki.com/danijar/dreamerv3/4-agent-architecture) -- component breakdown (enc/dyn/dec/rew/con/pol/val/slowval); confidence MEDIUM (web).
- [DeepWiki: DreamerV3 Agent Interface](https://deepwiki.com/danijar/dreamerv3/7.1-agent-interface) -- `train(carry,data)->(carry,out,metrics)` lifecycle; confidence MEDIUM (web).
- [PhiFlow Wake_Flow 3D example](https://tum-pbs.github.io/PhiFlow/examples/grids/Wake_Flow.html) -- `Box(x=,y=,z=)`, `StaggeredGrid(x=,y=,z=)`, `make_incompressible` in 3D; confidence MEDIUM (web).
- [PhiFlow Staggered Grids docs](https://tum-pbs.github.io/PhiFlow/Staggered_Grids.html) -- MAC grid, 2D + 3D support; confidence MEDIUM (web).
- [PhiFlow fluid API](https://tum-pbs.github.io/PhiFlow/phi/physics/fluid.html) -- `make_incompressible(velocity, obstacles, Solve())` signature; confidence MEDIUM (web).
- [pytest-kind v22.11.1 on PyPI](https://pypi.org/project/pytest-kind/) -- session-scoped `kind_cluster` fixture, `kubectl(*args)`, `load_docker_image`, `port_forward`; confidence MEDIUM (web).
- [pytest-k8s v1.0.0 on PyPI](https://pypi.org/project/pytest-k8s/) -- official `kubernetes` client alternative (rejected -- heavy dep); confidence MEDIUM (web).
- [Blueshoe/pytest-kubernetes](https://github.com/blueshoe/pytest-kubernetes) -- k3d/kind/minikube alternative (rejected -- over-provisioned); confidence MEDIUM (web).
- Local codebase: `src/surg_rl/dreamer/subprocess.py` (`_build_agent` stub at L125-129, sentinel at L83/88/98), `src/surg_rl/fluids/fluid_simulator.py` (2D `Box(x=,y=)` constructor), `src/surg_rl/scene_definition/schema.py` (`FluidConfig` L1463-1488, `TaskConfig.model_rebuild()` L1506), `tests/k8s/test_pvc_e2e.py` (stub body), `pyproject.toml` (`[dreamer]` extra L128-133), `pytest.ini` (markers L8-11); confidence HIGH (read directly).