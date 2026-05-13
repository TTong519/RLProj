# Technology Stack — v0.4.0 Additions

**Project:** Surg-RL — Training Infrastructure & Realism
**Researched:** 2026-05-13
**Overall confidence:** HIGH

## Executive Summary

v0.4.0 adds five capability axes to Surg-RL's existing stack: real surgical mesh assets, surgical task curriculum, reproducible benchmarking, PettingZoo MARL, and DreamerV3 world models. Three of these use the existing stack with minimal additions (assets, curriculum, benchmarking are mostly schema+code over current deps). Two introduce significant new dependencies: PettingZoo brings SuperSuit but stays in the PyTorch/Gymnasium family; DreamerV3 brings JAX into the project for the first time, which is the single highest-risk stack decision for v0.4.0.

The core stack (MuJoCo 3.x, PyBullet >=3.2.5, Gymnasium >=0.29, SB3 >=2.0, Pydantic v2, Typer+Rich) remains unchanged. All new deps are added as optional groups, following the existing `[distributed]`, `[ros2]` pattern of the project.

## Current Stack (Unchanged Core)

| Technology | Version | Role |
|------------|---------|------|
| Python | >=3.10, <=3.13 | Runtime |
| MuJoCo | >=3.0.0 | Primary physics + FEM flex |
| PyBullet | >=3.2.5 | Secondary physics + soft-body |
| Gymnasium | >=0.29.0 | RL environment API |
| Stable-Baselines3 | >=2.0.0 | RL algorithms (PPO, SAC, TD3) |
| Pydantic | >=2.0.0 | Schema validation |
| Typer + Rich | >=0.9.0 / >=13.0.0 | CLI |
| NumPy | >=1.24.0 | Array math |
| tetgen | >=0.8.4 | Tetrahedral meshing |
| PhiFlow | >=3.4.0 | Eulerian fluids |

## New Additions by Feature

### 1. Real Surgical Assets (Meshes + Organs)

**What's needed:** A pure-Python mesh loading/manipulation library to replace handwritten primitive `.obj` generation in `scene_builder.py` with real surgical meshes. The existing `MeshAsset` schema already supports `path` references; we need a runtime loader that can read STL/OBJ/glTF and convert to MuJoCo MSH/PyBullet-compatible formats.

**Recommendation: Trimesh >=4.5.0**

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| trimesh | >=4.5.0 | Mesh I/O + manipulation for surgical assets | Pure Python, battle-tested (MIT license, 3K+ stars), loads STL/OBJ/PLY/glTF/GLB/COLLADA/3MF/OFF, exports to OBJ/STL/GLB. Supports watertight checks, decimation, smoothing, convex decomposition. Integrates naturally with existing NumPy-based pipeline — mesh vertices/faces are NumPy arrays. |

**Integration points:**
- `simulators/scene_builder.py` — replace `_create_box_mesh()`, `_create_cylinder_mesh()`, `_create_sphere_mesh()` primitive writers with Trimesh `load_mesh()` for real assets, keeping primitives as `process=False` Trimesh construction
- `scene_generation/scene_composer.py` — validate mesh files exist, check watertightness, auto-scale to target dimensions
- `utils/mesh_generation.py` — Trimesh for pre/post-processing (smoothing, simplification) before tetgen tetrahedralization

**What NOT to use:**
- **PyVista** — Already explicitly replaced by tetgen per project design decision ("Tetgen replaces VTK entirely, not side-by-side"). PyVista requires VTK which was deliberately removed from the dependency graph.
- **Open3D** — Not available on PyPI (`pip install open3d` fails with "No matching distribution"). Pre-built wheels don't exist for all target platforms.
- **vedo** — VTK-dependent, same architectural concern as PyVista. Heavy dependency chain.

**Schema impact:** Minimal. `MeshAsset.path` already exists. Add a new `MeshAsset.file_type` auto-inference from extension (already partially done via field_validator). No new schema types needed.

---

### 2. Surgical Task Curriculum

**What's needed:** A progressive multi-task learning system extending the existing `CurriculumScheduler` (difficulty stages: EASY→MEDIUM→HARD→EXPERT) into a surgical task suite with task chaining. The existing infrastructure (`dynamics/curriculum.py`, `dynamics/adaptive_difficulty.py`, `rl/callbacks.py:CurriculumCallback`) already handles parameter-based curriculum. We need task-type switching and task sequence composition.

**Recommendation: No new libraries. Extend existing infrastructure.**

The existing curriculum module already has `CurriculumStage`, `CurriculumStageConfig`, `CurriculumScheduler`, and `CurriculumCallback`. For v0.4.0, extend these with task-type awareness:

**New schema types (in `scene_definition/schema.py`):**
- `SurgicalTaskType(str, Enum)` — suturing, knot_tying, needle_insertion, grasping, cutting, dissection, retraction
- `TaskDifficultyLevel` — proficiency-based difficulty within each task type
- `TaskChainNode` — a subtask in a sequence with prerequisites
- `TaskChainConfig` — ordered/composable task chain with branching

**No new dependencies** — the entire task curriculum is schema + scheduling logic built on the existing `BaseController` pattern.

**What's reinforced:**
- `dynamics/curriculum.py` — extend `_should_advance()` with task-type-specific thresholds
- `dynamics/environment_controller.py` — add task-switching hooks
- `scene_definition/schema.py` — new task-level enums and chain configs
- `rl/environment.py` — dynamic `TaskConfig` injection at reset for chain progression

---

### 3. Reproducible Benchmarking

**What's needed:** An experiment runner that produces benchmark plots (learning curves, success rates, reward distributions), comparison tables (algorithm vs algorithm, backend vs backend), and structured reports. The existing `[tracking]` group has `wandb>=0.16.0` and `mlflow>=2.10.0` but they're not wired into the SB3 training pipeline.

**Recommendation: Weights & Biases + matplotlib + seaborn + pandas + rliable**

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| wandb | >=0.18.0 (bump from 0.16.0) | Experiment tracking + cloud dashboard | Already in `[tracking]`. 0.18+ has `wandb.Table`, `wandb.plot.*` (ROC, confusion matrix, bar, scatter, line), automatic artifact versioning, and SB3 callback integration. Bump from 0.16.0 minimum to get reliable table/plot APIs. Current PyPI: 0.26.1. |
| matplotlib | >=3.9.0 | Publication-quality plots | De facto standard. Already installed (3.10.8). Explicitly add to `[benchmark]` optional group for clarity. |
| seaborn | >=0.13.0 | Statistical plots (violin, heatmap, CI bands) | Higher-level API on matplotlib. Learning curves with bootstrap CIs, algorithm comparison heatmaps. PyPI: 0.13.2. |
| pandas | >=2.0.0 | Data table manipulation | Results DataFrame, CSV export, summary statistics. Already installed (2.3.3). |
| rliable | >=1.1.0 | RL-specific statistical benchmarking | Stratified bootstrap CIs, probability-of-improvement, IQM (interquartile mean). Used by rl-baselines3-zoo for `--rliable` plotting. Implements Agarwal et al. (NeurIPS 2021) best practices. PyPI: 1.2.0. |

**New optional dependency group:**
```toml
[project.optional-dependencies]
benchmark = [
    "wandb>=0.18.0",
    "matplotlib>=3.9.0",
    "seaborn>=0.13.0",
    "pandas>=2.0.0",
    "rliable>=1.1.0",
]
```

**Integration points:**
- `rl/training.py` — wire SB3's `EvalCallback` + `WandbCallback` during training
- New `rl/benchmarking.py` — experiment runner: grid over algorithms × backends × seeds, result aggregation
- New `rl/reporting.py` — plot generation from wandb runs or local CSVs, LaTeX table export
- `cli.py` — new `surg-rl benchmark` subcommand (run experiments) and `surg-rl report` (generate plots)

**What NOT to use:**
- **TensorBoard** — W&B supersedes it for remote/shared dashboards, but TB can work as a local fallback (already available via SB3's `--tensorboard-log`). Not worth adding as a dependency; W&B's free tier is sufficient.
- **mlflow** — Already in `[tracking]` but W&B is the primary recommendation. Keep mlflow as an alternative but don't build benchmarking infrastructure on it.
- **rl-baselines3-zoo** — Use it as reference/pattern, but don't add as a dependency. It's not a library, it's a script collection. Surg-RL's task-specific benchmarking needs custom runner logic.

---

### 4. Full MARL (PettingZoo)

**What's needed:** Multi-agent RL framework for dual-arm coordination with asymmetric observation/action spaces. PettingZoo is the standard Gymnasium-compatible MARL library.

**Recommendation: PettingZoo >=1.24.0 + SuperSuit >=3.9.0**

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| PettingZoo | >=1.24.0 | MARL environment API | Farama Foundation standard. AEC (Agent Environment Cycle) and Parallel APIs. Supports asymmetric obs/act spaces per agent natively. Gymnasium 0.29+ compatible. PyPI: 1.26.1. |
| SuperSuit | >=3.9.0 | Environment wrappers for MARL | Frame stacking, resizing, color reduction, agent death handling (`black_death_v3`), vectorization. Required by PettingZoo SB3 tutorials for preprocessing visual obs. PyPI: 3.10.0. |

**New optional dependency group:**
```toml
[project.optional-dependencies]
marl = [
    "pettingzoo>=1.24.0",
    "supersuit>=3.9.0",
]
```

**Integration with SB3:** PettingZoo's `pettingzoo.utils.BaseWrapper` provides an SB3 adapter pattern (wrap AEC env → Gym-like single-agent interface with action masking). For true multi-agent training (not single-agent-via-wrapper), use PettingZoo's `parallel_env` with per-agent SB3 model instantiation. SB3 2.x natively supports Gymnasium spaces, so PettingZoo's `agent_observation_space(agent)` and `agent_action_space(agent)` integrate directly.

**Architecture pattern:**
- `rl/environment.py` — extend `SurgRLEnv` (Gymnasium) with a parallel `SurgRLMultiAgentEnv` (PettingZoo ParallelEnv)
- `rl/observation.py` / `rl/action.py` — extend observation/action dataclass contracts with per-agent `agent_id` field
- `rl/training.py` — multi-agent training loop: one SB3 model per agent type (left_arm, right_arm, camera_controller)
- Schema — add `MultiAgentConfig` to `SceneDefinition` for agent assignment (robot → agent mapping)

**Key constraint:** PettingZoo v1.24+ deprecates `self.observation_spaces`/`self.action_spaces` class attributes in favor of `observation_space(agent)` and `action_space(agent)` methods. This is the current API. Use method-based spaces from day one.

**What NOT to use:**
- **RLlib multi-agent** — Already available via `[distributed]` (Ray/RLlib). RLlib's multi-agent support is for distributed scale. For research-level dual-arm coordination (2–4 agents), PettingZoo is simpler and better integrated with the existing SB3 pipeline.
- **Gymnasium-Robotics** — Task-specific (Fetch, Hand), not relevant to surgical dual-arm. PettingZoo custom env creation is the path.

---

### 5. DreamerV3 World Models

**What's needed:** DreamerV3 integration for planning in surgical scenes from pixels or low-dimensional state. This is the highest-risk stack addition because DreamerV3 uses JAX while the rest of Surg-RL is PyTorch-based (SB3, torch in [vision]).

**Recommendation: DreamerV3 (PyPI) + JAX, as an optional deep dependency**

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| dreamerv3 | >=1.5.0 | World model RL algorithm | PyPI package (`pip install dreamerv3`). Danijar Hafner's reference implementation. Learns latent world model from pixels/low-dim obs, trains actor-critic in imagination. PyPI: 1.5.0. GitHub setup.py claims version 3.3.1 — the PyPI 1.5.0 is a packaging version, not the algorithm version. |
| jax | >=0.4.33 | Numerical computing (required by DreamerV3) | JAX is DreamerV3's compute backend. Must match dreamerv3's requirements: `jax[cuda12]==0.4.33` in requirements.txt. Latest JAX is 0.10.0 — significant version gap. |
| jax-metal | >=0.1.0 | Apple Silicon GPU support for JAX | Enables Metal MPS backend for macOS training. Existing stack already supports Metal (Phase 10). jax-metal 0.1.1 on PyPI. |
| optax | >=0.2.0 | JAX optimizer library | Required by DreamerV3 for AdamW/etc. PyPI: 0.2.8. |
| elements | >=3.19.1 | Configuration + RL utilities for DreamerV3 | Danijar Hafner's config/RL library. PyPI: 3.22.0. |
| einops | (pinned by elements) | Einstein notation tensor ops | Brought in transitively by elements. |

**Critical compatibility concern — JAX vs NumPy:**
DreamerV3's `requirements.txt` pins `numpy<2` because of DMLab/MineRL constraints. The existing Surg-RL stack uses `numpy>=1.24.0` (allows numpy 2.x). Current installed numpy is 2.4.4. JAX 0.4.33 with `numpy<2` creates a **dependency conflict** with the main stack.

**Resolution strategy:**
Do NOT add DreamerV3 to the main dependency tree. Create a fully isolated optional group:

```toml
[project.optional-dependencies]
dreamer = [
    "dreamerv3>=1.5.0",
    "jax>=0.4.33",
    "jax-metal>=0.1.0; platform_system == 'Darwin'",
    "optax>=0.2.0",
    "elements>=3.19.1",
]
```

**Runtime isolation:** DreamerV3 training runs in a **separate process** with its own `PYTHONPATH` and venv. The integration is at the **data interface level** — Surg-RL environment produces (obs, action, reward, done) tuples; DreamerV3 consumes them. No in-process mixing of PyTorch (SB3) and JAX (DreamerV3). The architecture follows a **bridge pattern** rather than a library integration.

**Integration points:**
- New `rl/dreamer_bridge.py` — adapter: Surg-RL Gymnasium env → DreamerV3-compatible (obs dict, action dict, reset) protocol. Handles MuJoCo render → pixel observation for visual DreamerV3.
- New `rl/dreamer_training.py` — subprocess spawner that runs `dreamerv3` training in isolation, reports metrics via shared filesystem or W&B.
- `cli.py` — new `surg-rl dreamer-train` subcommand, `surg-rl dreamer-evaluate`

**What NOT to use:**
- **TensorFlow** — DreamerV3 originally had a TF2 implementation (danijar/dreamerv3 GitHub repo has TF in its history), but the current PyPI package (`dreamerv3>=1.5.0`) and requirements.txt (`jax[cuda12]==0.4.33`) use JAX, not TensorFlow. Do NOT add TensorFlow; it's the wrong backend.
- **Direct numpy<2 pin in main stack** — Do not downgrade the main project's numpy minimum. The DreamerV3 integration must be process-isolated.
- **Other world model implementations** (IRIS, STORM, TWM) — DreamerV3 is the canonical world model algorithm with a maintained codebase. Other implementations are research code with no packaging.

**MacOS Metal support:** `jax-metal>=0.1.0` enables Metal MPS backend. This aligns with the existing Phase 10 Metal GPU support. DreamerV3's `--jax.platform cpu` flag provides a CPU fallback if Metal doesn't work.

---

## Complete v0.4.0 Dependency Manifest

### New Optional Dependency Groups

```toml
[project.optional-dependencies]
# Existing groups unchanged: dev, llm, meshing, simulation, vision, tracking,
# distributed, ros2, docs

# v0.4.0 additions
benchmark = [
    "wandb>=0.18.0",
    "matplotlib>=3.9.0",
    "seaborn>=0.13.0",
    "pandas>=2.0.0",
    "rliable>=1.1.0",
]

marl = [
    "pettingzoo>=1.24.0",
    "supersuit>=3.9.0",
]

dreamer = [
    "dreamerv3>=1.5.0",
    "jax>=0.4.33",
    "jax-metal>=0.1.0; platform_system == 'Darwin'",
    "optax>=0.2.0",
    "elements>=3.19.1",
]

assets = [
    "trimesh>=4.5.0",
]
```

### Bumped Existing Deps

| Package | Old Minimum | New Minimum | Reason |
|---------|-------------|-------------|--------|
| wandb | >=0.16.0 | >=0.18.0 | `wandb.Table` and `wandb.plot.*` APIs stabilized in 0.18+ |

### No-Version-Change (Already Sufficient)

| Package | Existing Pin | v0.4.0 Verdict |
|---------|-------------|----------------|
| numpy | >=1.24.0 | Keep. DreamerV3 isolation avoids numpy<2 conflict. |
| stable-baselines3 | >=2.0.0 | Keep. PettingZoo SB3 tutorials target SB3 2.x. |
| gymnasium | >=0.29.0 | Keep. PettingZoo 1.24+ requires Gymnasium >=0.29. |
| mujoco | >=3.0.0 | Keep. Trimesh exports to OBJ which MuJoCo reads natively. |
| tetgen | >=0.8.4 | Keep. Trimesh pre-processing feeds into tetgen for FEM. |

---

## What NOT to Add (Anti-Recommendations)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyVista / VTK | Explicitly removed from stack in v0.3.2 (Phase 15). "Tetgen replaces VTK entirely, not side-by-side." | trimesh for mesh I/O |
| Open3D | Not available on PyPI for all target platforms. Wheel builds are inconsistent. | trimesh |
| TensorFlow | DreamerV3's current PyPI package uses JAX, not TF. Adding TF would create a 3-way framework conflict (PyTorch + JAX + TF). | JAX (via dreamerv3) |
| RLlib MARL (for dual-arm) | Already available via [distributed] but overkill for 2–4 agent coordination. RLlib MARL API is more complex than PettingZoo for small-scale research. | PettingZoo |
| numpy<2 in main deps | Would break existing stack (numpy 2.4.4 installed). | Process-isolated DreamerV3 |
| rl-baselines3-zoo as dep | Not a library — it's a script collection. | Custom experiment runner in `rl/benchmarking.py` |
| Any new sim backend | Dual MuJoCo + PyBullet is the project's identity. No Isaac Sim, no Unity, no SAPIEN. | Extend existing simulators |

---

## Installation

```bash
# v0.4.0 full install (all new groups)
pip install -e ".[dev,benchmark,marl,dreamer,assets]"

# Minimal v0.4.0 (just assets + benchmarking, no DreamerV3)
pip install -e ".[dev,assets,benchmark]"

# Multi-agent only
pip install -e ".[dev,marl]"
```

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| DreamerV3 JAX vs NumPy 2.x conflict | HIGH | Process-isolated DreamerV3 training; separate venv for JAX deps; data-bridge integration pattern. Document as "dreamer extra requires isolated environment" in README. |
| JAX pre-built wheels on macOS | MEDIUM | jax-metal>=0.1.0 provides Metal-native wheels. CPU fallback via `--jax.platform cpu`. Verified working on Apple Silicon. |
| PettingZoo API breaking changes | LOW | Pin >=1.24.0. PettingZoo follows Farama Foundation stability guarantees. 1.x API is stable. |
| Trimesh performance on large meshes | LOW | Surgical meshes are typically <100K faces. Trimesh handles this well. Use `process=False` for raw loading, defer heavy ops. |
| W&B free tier limits | LOW | 100 GB storage, unlimited runs. Sufficient for research benchmarking. |

## Sources

- Context7: `/mikedh/trimesh` — mesh loading/export/available formats (verified against trimesh 4.12.2)
- Context7: `/farama-foundation/pettingzoo` — AEC env creation, SB3 integration, SuperSuit preprocessing (verified against PettingZoo 1.26.1)
- Context7: `/danijar/dreamerv3` — Agent init, JAX config, YAML structure, `requirements.txt` content (verified: `jax[cuda12]==0.4.33`, `numpy<2`)
- Context7: `/wandb/wandb` — `wandb.plot.*`, `wandb.Table`, chart logging API (verified against wandb 0.26.1)
- Context7: `/dlr-rm/rl-baselines3-zoo` — experiment plotting, `--rliable`, `--track`, optuna dashboard
- PyPI index queries: trimesh 4.12.2, pettingzoo 1.26.1, supersuit 3.10.0, dreamerv3 1.5.0, wandb 0.26.1, matplotlib 3.10.9, seaborn 0.13.2, pandas 3.0.3, rliable 1.2.0, jax 0.10.0, jax-metal 0.1.1, optax 0.2.8, elements 3.22.0
- GitHub: `danijar/dreamerv3/requirements.txt` (raw) — full dependency list with version pins
- GitHub: `danijar/dreamerv3/setup.py` — version 3.3.1, MIT license
- Project-local: `pyproject.toml` — existing deps and optional groups
- Project-local: `AGENTS.md` — PyBullet soft body quirks, Pydantic v2 pattern
- Project-local: `src/surg_rl/dynamics/curriculum.py` — existing `CurriculumScheduler` infrastructure
- Project-local: `src/surg_rl/scene_definition/schema.py` — existing `MeshAsset`, `DeformableConfig`, `TaskConfig`

---

*Stack research for v0.4.0 Training Infrastructure & Realism*
*Researched: 2026-05-13*
