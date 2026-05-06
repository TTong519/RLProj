<!-- generated-by: gsd-doc-writer -->
# Architecture Overview

Surg-RL is a layered surgical robotics RL training system. It follows a **strict data-flow pipeline** from scene definition through physics simulation to RL training, using the **Strategy pattern** for swappable simulator backends. Version 0.3.2 adds **volumetric cutting** (tetrahedral mesh subdivision) and **grid-based fluid simulation** (PhiFlow 2D Eulerian), integrated as optional modules driven from the schema layer. Every layer consumes the same `SceneDefinition` Pydantic v2 schema, ensuring a single source of truth.

## System Layers

```
┌──────────────────────────────────────────────────────────────────┐
│                   USER INTERFACE                                  │
│    CLI (Typer: surg-rl)  │  Python API  │  Demos (demos/)        │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│                   SCENE GENERATION (optional)                     │
│  TextParser (LLM)  │  VisionParser (VLM)  │  TEMPLATE_REGISTRY   │
│  ──────────────────────────────────────────────────────────────  │
│  OpenAI / Anthropic / Ollama  │  scene_composer.py              │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│                   SCENE DEFINITION                                │
│  SceneDefinition (Pydantic v2)  │  SceneLoader (JSON/YAML +      │
│  robots / tissues / instruments / physics / tasks / DR config    │
│  + DeformableConfig / CutAction / FluidConfig / fluid field      │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│                   SIMULATOR ABSTRACTION (Strategy)                │
│  BaseSimulator (ABC)                                              │
│  ├── MuJoCoSimulator  ──  SceneBuilder → MJCF XML → MuJoCo 3.x  │
│  │    + &lt;flex&gt; FEM mesh gen + _apply_cut(action)              │
│  └── PyBulletSimulator ──  direct primitive API + soft-body       │
│                                                                   │
│  Data carriers: Observation, State, StepResult                   │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│                   EXTENDED PHYSICS MODULES (optional)             │
│  Cutting Engine (src/surg_rl/cutting/)                            │
│  ├── Intersection  ──  signed distances, edge-plane crossing     │
│  └── Engine         ──  cut_tetrahedral_mesh() + subdivision     │
│                                                                   │
│  Fluid Simulation (src/surg_rl/fluids/)                           │
│  ├── FluidSimulator  ──  PhiFlow StaggeredGrid (2D xz-plane)     │
│  ├── ForceComp       ──  pressure gradient → obstacle forces     │
│  └── Visualizer      ──  2D colormesh rendering                  │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│                   DYNAMICS CONTROL                                │
│  EnvironmentController (orchestrator)                             │
│  ├── ParameterRandomizer   (domain randomization)                 │
│  ├── CurriculumScheduler   (Easy → Medium → Hard → Expert)       │
│  └── AdaptiveDifficultyController  (performance-driven scaling)  │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│                   RL LAYER                                        │
│  SurgicalEnv (Gymnasium)                                         │
│  ├── ObservationBuilder  (Dict / Box spaces, 20+ observation      │
│  │                       types, normalization, noise injection)   │
│  ├── ActionBuilder       (joint pos/vel/torque, EE pose/delta,    │
│  │                       gripper, discrete; scaling modes)        │
│  ├── BaseRewardFunction  (9 built-in reward types + composite)    │
│  ├── trigger_cut()       discrete cut plane action + cooldown     │
│  ├── _init_fluid()       lazy FluidSimulator hook                 │
│  └── task_termination    (backend-agnostic success detection)     │
│                                                                   │
│  TrainingManager → SB3 (PPO, SAC, TD3, DDPG, A2C) + callbacks    │
│                                                                   │
│  Optional: Ray/RLlib distributed training                         │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Scene creation**: User provides text/image/template → `TextParser` / `VisionParser` / `get_template()` → `SceneDefinition` → saved as JSON or YAML.
2. **Scene loading**: `SceneLoader.load(path)` validates against Pydantic v2 schema, caches with LRU, checks asset references.
3. **Simulator loading**: `simulator.load_scene(scene)` → `SceneBuilder` generates MJCF XML (MuJoCo) or calls `createMultiBody` / `createSoftBody` (PyBullet) with primitive `.obj` fallbacks. For deformable tissues, `_add_flex_body_to_mjcf()` emits a `<flex>` element with vertex/element data — supporting tetgen mesh, in-memory numpy arrays, and file-based sources.
4. **Optional physics init** (during `SurgicalEnv.__init__`):
   - `_init_fluid()` checks `SceneDefinition.fluid` → instantiates `FluidSimulator` (PhiFlow `StaggeredGrid` on 2D xz-plane) if `FluidConfig.enabled=True`.
5. **Environment reset**: `SurgicalEnv.reset()` → `EnvironmentController.reset()` samples domain-randomized parameters → applies to simulator → `simulator.reset()` → builds initial observation.
6. **Step loop** (per timestep):
   ```
   Agent action
     → ActionBuilder.process_action()           (scale, convert, apply noise)
     → EnvironmentController.step_update()      (apply curriculum/adaptive changes)
     → Simulator.step(action)                   (execute physics)
     → ObservationBuilder.extract()             (map to gym space)
     → RewardFunction.compute()                 (task-specific reward)
     → check_task_success()                     (termination condition)
   → (obs, reward, terminated, truncated, info)
   ```
7. **Cutting event** (discrete; not every step):
   ```
   Agent calls env.trigger_cut(tissue, point, dir, depth)
     → cooldown check (~500ms)
     → build CutAction (Pydantic v2, normalized direction)
     → simulator._apply_cut(cut_action)
       → MuJoCo: query flex verts + tetrahedra, call cut_tetrahedral_mesh(),
         rewrite MJCF XML inline, reload model+data preserving qpos/qvel
   ```
8. **Training**: `TrainingManager.train()` creates SB3 model + callbacks → `model.learn(total_timesteps)`.

## Entry Points

| Entry point | Location | Description |
|---|---|---|
| CLI | `surg-rl` (pyproject.toml `[project.scripts]`) | Typer app: `version`, `config`, `setup`, `generate`, `train`, `evaluate`, `train-rllib`, `tune`, `checkpoint-inspect`, `test-cli`, `scene-validate`, `convert`, `inspect-scene`, `ros2-bridge`, `profile`, `list-templates` |
| Python module | `python -m surg_rl.cli` | Same as CLI, no `__main__.py` needed |
| Library API | `from surg_rl.rl import SurgicalEnv, TrainingManager` | Direct Python import |
| Demos | `demos/demo.py`, `demos/train_demo.py`, `demos/eval_demo.py` | Runnable example scripts |
| Examples | `examples/basic_usage.py`, `examples/rl_training.py`, `examples/rl_evaluation.py`, `examples/visualize_scene.py` | Code examples |

## Key Abstractions

### BaseSimulator (ABC)
**File**: `src/surg_rl/simulators/base_simulator.py` (481 lines)

Defines the unified simulator interface. All backends must implement:

| Method | Purpose |
|---|---|
| `load_scene(scene_definition)` | Parse `SceneDefinition` → internal representation |
| `reset(seed)` | Reset simulation to initial state, return `Observation` |
| `step(action)` | Execute one step, return `StepResult` |
| `render(mode, width, height, camera_name)` | Render current state as image |
| `get_state()` / `set_state(state)` | Save/restore full simulation state |
| `close()` | Clean up resources |
| `start_viewer(target_fps)` / `stop_viewer()` | Non-blocking 3D viewer lifecycle |
| `get_joint_states()` | Per-robot joint positions and velocities |
| `apply_action(action)` → `_apply_action(action)` | Apply control input (templated method) |

**Data carriers** (dataclasses in `base_simulator.py`):
- `Observation` — 20+ fields: `rgb_image`, `depth_image`, `segmentation`, `robot_state`, `end_effector_pos`, `end_effector_quat`, `force_torque`, `tissue_state`, `collision_detected`, `needle_pos`, `entry_point`, `exit_point`, `incision_progress`, `thread_tension`, `cut_force`, `receiver_pos`, `tool_positions`, `custom`
- `State` — snapshot for save/restore: `time`, `qpos`, `qvel`, `mocap_pos`, `mocap_quat`, body positions/orientations, `custom`
- `StepResult` — Gymnasium-style transition tuple: `observation`, `reward`, `terminated`, `truncated`, `info`
- `SimulationStatus` — enum: `RUNNING`, `SUCCESS`, `FAILURE`, `TIMEOUT`

### SurgicalEnv (Gymnasium)
**File**: `src/surg_rl/rl/environment.py` (1100 lines)

A `gym.Env` subclass that wraps simulator + dynamics controller + observation/action builders. Key configuration via `SurgicalEnvConfig`:
- `scene_path` / `scene` — which scene to load
- `simulator_type` — `"mujoco"` (default) or `"pybullet"`
- `timestep` (default: `0.002` s), `frame_skip` (default: `1`), `max_episode_steps` (default: `1000`)
- `render_mode` — `"human"`, `"rgb_array"`, or `None`
- `use_curriculum` / `use_adaptive_difficulty` — toggle dynamics features
- Supports vectorized envs via `make_vec_env()` (SB3 `DummyVecEnv` / `SubprocVecEnv`)

**v0.3.2 hooks**:
- `trigger_cut(tissue_name, surface_point, direction, depth)` — discrete cutting event with cooldown enforcement (~500ms). Constructs a `CutAction`, then calls `simulator._apply_cut()`.
- `_init_fluid()` — called during `__init__`; checks `SceneDefinition.fluid`, lazily imports and instantiates `FluidSimulator` when `FluidConfig.enabled=True`.

### EnvironmentController
**File**: `src/surg_rl/dynamics/environment_controller.py` (578 lines)

Orchestrates three sub-controllers (composition, not inheritance):

| Sub-controller | File | Role |
|---|---|---|
| `ParameterRandomizer` | `parameter_randomizer.py` (645 lines) | Domain randomization: physics (mass, friction, gravity), visual (color, lighting), dynamics (action/observation noise). Uses `weakref.WeakKeyDictionary` for baseline storage per simulator. |
| `CurriculumScheduler` | `curriculum.py` (517 lines) | 4-stage curriculum: Easy → Medium → Hard → Expert. Auto-advances based on success-rate windows. |
| `AdaptiveDifficultyController` | `adaptive_difficulty.py` (492 lines) | Performance-driven scaling with strategies: linear, exponential, proportional, threshold. |

Base class: `BaseController` (ABC) in `base_controller.py` — defines lifecycle: `start`, `stop`, `reset`, `step_update`, `episode_end`, parameter sampling, and callback system.

### Cutting Engine (v0.3.2)
**Package**: `src/surg_rl/cutting/` (241 lines total)

Pure NumPy tetrahedral mesh cutting pipeline. No runtime dependencies beyond NumPy.

| Module | Lines | Purpose |
|---|---|---|
| `intersection.py` | 81 | `compute_signed_distances()` — point-to-plane distances; `edge_intersection()` — crossing point via weighted interpolation; `classify_tet_case()` — 5-case classification (0=no-cut, 1=3-1, 2=2-2, 3=1-3, 4=degenerate) |
| `engine.py` | 160 | `cut_tetrahedral_mesh(verts, tets, origin, normal)` — iterates straddling tets, subdivides via `_subdivide_3_1()` (4 child tets) or `_subdivide_2_2()` (6 child tets), returns new vertices, tetrahedra, and cut-surface faces |

**Integration**: `MuJoCoSimulator._apply_cut(cut_action)` extracts flex vertex data from `flexvert_xpos`, passes tetrahedra from `flex_elem`, calls `cut_tetrahedral_mesh()`, then `_rewrite_flex_mesh_in_mjcf()` replaces the XML `<flex>` element's vertex/element text inline and reloads `MjModel` + `MjData`, preserving existing `qpos`/`qvel` where lengths match.

### Fluid Simulation (v0.3.2)
**Package**: `src/surg_rl/fluids/` (214 lines total)

Wraps PhiFlow (optional: `pip install "surg-rl[fluids]"`) for 2D grid-based Eulerian fluid simulation on the xz-plane. Suitable for surgical bleeding/irrigation scenarios.

| Module | Lines | Purpose |
|---|---|---|
| `fluid_simulator.py` | 97 | `FluidSimulator(config: FluidConfig)` — `StaggeredGrid` velocity field, MAC advection, pressure projection (`fluid.make_incompressible`), obstacle management via `add_obstacle()` / `clear_obstacles()`. Substeps at `config.substep_dt` (default 0.02s). |
| `force_computation.py` | 63 | `compute_obstacle_forces(velocity, pressure, names, config)` — pressure gradient integration `F = -∫Ω ∇p dV` via central difference, returns per-obstacle force vectors with magnitude clamping (max 1e4 N). |
| `visualizer.py` | 54 | `render_fluid_2d(pressure, config, width, height)` — normalizes pressure field to [0,1], resizes via `skimage.transform.resize`, returns (H,W,3) uint8 RGB image. |

**Integration**: `SurgicalEnv._init_fluid()` reads `SceneDefinition.fluid: FluidConfig | None`, instantiates `FluidSimulator` if enabled. The RL agent interacts with fluid indirectly through the `Observation` data carrier (fluid forces appear in `custom` fields) and through obstacle registration in the simulator.

## Backend Strategy Pattern

Both simulator backends consume the same `SceneDefinition` schema but translate it through completely different paths:

| Aspect | MuJoCoSimulator | PyBulletSimulator |
|---|---|---|
| File | `mujoco_simulator.py` (1235 lines) | `pybullet_simulator.py` (1282+ lines) |
| Model format | MJCF XML (via `SceneBuilder.create_mjcf()`) | Direct API calls (`createMultiBody`, `createCollisionShape`) |
| Physics engine | MuJoCo 3.x (`mujoco.MjModel.from_xml_path()`) | PyBullet (`p.connect()`) |
| Rendering | `mujoco.Renderer` (MuJoCo 3.x API) | `p.getCameraImage()` |
| Control mapping | `mjOBJ_ACTUATOR` lookups | `POSITION_CONTROL` / `TORQUE_CONTROL` mode switching |
| Deformable bodies | `<flex>` FEM via tetgen/flexcomp, cuttable | `loadSoftBody()` with procedural `.vtk` meshes |
| Detection (duck typing) | `hasattr(sim, "_model")` | `hasattr(sim, "_physics_client")` |
| Cutting support | Yes (`_apply_cut(cut_action)` + MJCF rewrite) | Not implemented |

**Backend-specific quirks**:
- **MuJoCo**: Stores model as private `_model`. Must call `load_scene()` before `reset()` or `step()`. Deformable tissues use `<flex>` elements in the MJCF XML; the `SceneBuilder` generates these via `_add_flex_body_to_mjcf()` from tetgen meshes, in-memory numpy arrays, or file sources. Cutting rewrites the XML and reloads the model.
- **PyBullet**: Must call `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` before any soft-body load, even on a fresh connect. `removeBody()` is unsafe for soft bodies; `reset()` performs full scene reload when `_soft_body_ids` is non-empty.
- **Scene assets**: `assets/` directory contains no real mesh files. `SceneBuilder` generates primitive `.obj` / `.vtk` fallbacks on the fly (box, sphere, cylinder via pure NumPy in `utils/mesh_generation.py`). Deformable meshes are procedurally tetrahedralized.

## v0.3.2 Schema Additions

Three new Pydantic v2 models extend the scene definition for cutting and fluids:

| Model | File line | Purpose |
|---|---|---|
| `DeformableConfig` | `schema.py:403` | Attached to `TissueConfig` when `soft_body=True`. Controls mesh source (`tetgen`, `flexcomp_grid`, `file`), resolution, max vertices, and backend-specific overrides (`MuJoCoFlexConfig` / `PyBulletFlexConfig`). Includes `BoundaryCondition` attachments and observation flags for vertex positions, strain, and stress. |
| `CutAction` | `schema.py:730` | Volumetric cut as a plane: `tissue_name`, `surface_point` (entry point), `direction` (auto-normalized), `depth` (0.001–0.05m). Discrete event — not a continuous action dimension. |
| `FluidConfig` | `schema.py:1255` | Eulerian grid config: `enabled`, `bounds` (BoundingBox), `resolution` (capped at 128), `density`, `viscosity`, `substep_dt`, `boundary_type` (OPEN/WALL), `initial_velocity`. |
| `SceneDefinition.fluid` | `schema.py:1206` | `FluidConfig | None` field on the root schema — triggers `_init_fluid()` in the env. |

## Optional Modules

### Ray/RLlib Distributed Training
**Package**: `src/surg_rl/rl/rllib/` | **Extra**: `pip install "surg-rl[distributed]"`

Provides `RllibConfig`, `train_rllib()`, and Ray Tune hyperparameter search integration. Registered via `register_env()` and import-guarded (`ImportError` → helpful message). CLI commands: `surg-rl train-rllib`, `surg-rl tune`.

### ROS2 Bridge
**Package**: `src/surg_rl/ros2/` | **Extra**: `pip install "surg-rl[ros2]"` (apt deps required)

Bridge between simulation and real hardware via ROS2 (Humble). Components:
- `Ros2BridgeConfig` — Pydantic v2 configuration
- `Ros2BridgeNode` — state publishing / command subscribing
- `TrajectoryReplay` — self-contained SB3 checkpoint replay to ROS2 topics
- `ControllerBridge` (`hardware_bridge.py`) — manages ros2_control lifecycle from Python, wrapping C++ `controller_manager` via `spawner`/`unspawner` subprocess calls
- Launch files: `bridge.launch.py`, `replay.launch.py` — compose controller_manager + bridge/replay nodes with configurable arguments

Degrades gracefully: `HAS_ROS2 = False` on macOS or when `rclpy` is not installed.

### Kubernetes Deployment
**Directory**: `k8s/` | **Operator**: KubeRay v1.6+

Production K8s manifests for RL training and ROS2 bridge:
- `k8s/base/training-job.yaml` — SB3 training as `batch/v1` Job with GPU node selectors
- `k8s/base/raycluster.yaml` / `rayjob.yaml` — KubeRay RayCluster and RayJob for RLlib
- `k8s/base/` — ConfigMap, Secret, PVC, RBAC infrastructure manifests
- `k8s/overlays/{cpu,gpu}/` — Kustomize overlays for environment variants
- ROS2 bridge runs as sidecar container with `SURGRL_BRIDGE_SIDECAR` detection
- Images pushed to GHCR on `v*` tags via release workflow

### Multi-platform Docker
**Dockerfiles**: `Dockerfile` (CPU amd64+arm64), `Dockerfile.cuda` (CUDA amd64), `Dockerfile.rocm` (ROCm amd64), `Dockerfile.jetson` (Jetson arm64), `Dockerfile.ros2` (ROS2 bridge)
- Cross-arch builds via `docker buildx` + QEMU emulation
- CI docker-ci job validates all 4 Dockerfiles per PR
- Release workflow pushes multi-arch manifest to GHCR

### Other Optional Extras
| Extra | Contents |
|---|---|
| `meshing` | `pyvista>=0.43` — advanced mesh visualization |
| `vision` | `torch`, `torchvision`, `transformers` — VLM inference |
| `tracking` | `wandb`, `mlflow` — experiment tracking |
| `docs` | `sphinx`, `sphinx-rtd-theme`, `myst-parser` — documentation build |
| `fluids` | `phiflow` — 2D Eulerian fluid simulation (v0.3.2) |

## Inheritance Hierarchies

```
Scene Parsers:
  BaseParser (ABC)
  ├── TextParser
  └── VisionParser

Simulators:
  BaseSimulator (ABC)
  ├── MuJoCoSimulator
  └── PyBulletSimulator

Dynamics Controllers:
  BaseController (ABC)
  ├── ParameterRandomizer
  ├── CurriculumScheduler
  └── AdaptiveDifficultyController
  (EnvironmentController composes the three above)

Reward Functions:
  BaseRewardFunction (ABC)
  ├── DistanceReward
  ├── OrientationReward
  ├── ActionPenalty
  ├── TimePenalty
  ├── SuccessReward
  ├── CollisionPenalty
  ├── SuturingReward
  ├── DissectionReward
  ├── NeedlePassingReward
  └── CompositeReward
```

## Directory Structure Rationale

```
src/surg_rl/
  cli.py                   Typer CLI entrypoint (863 lines, 16+ commands)
  render_thread.py         Off-main-thread render loop
  scene_definition/        Pydantic v2 schema (schema.py, 1282 lines) +
                           JSON/YAML loader with caching (loader.py, 889 lines)
  scene_generation/        LLM/VLM parsers + template registry + composer
  simulators/              ABC + two backends + scene-to-format builder
                           (mujoco_simulator.py: 1235 lines, scene_builder.py: 1061 lines)
  cutting/                 Tetrahedral mesh cutting engine (v0.3.2)
                           intersection (81 lines) + engine (160 lines)
  fluids/                  Grid-based fluid simulation (v0.3.2)
                           FluidSimulator (97 lines) + force computation (63 lines)
                           + 2D visualizer (54 lines)
  dynamics/                Domain randomization, curriculum, adaptive difficulty
  rl/                      Gymnasium env, SB3 training, obs/act/rew builders, callbacks
    rllib/                 Ray/RLlib distributed training (optional)
  ros2/                    ROS2 bridge (optional, Linux-only)
  utils/                   Configuration (pydantic-settings), Rich logging,
                           mesh generation (pure NumPy), VTK I/O, GPU detection
```

Each directory maps to one layer of the pipeline. Dependencies flow in one direction only: `scene_definition` ← `scene_generation`, `simulators`, `dynamics`, `rl`, `cutting`, `fluids`. Circular imports are avoided; cross-layer communication goes through `SceneDefinition` (data), `Observation` (data carrier), and `CutAction`/`FluidConfig` (discrete event payloads).

## Key Design Decisions

1. **Pydantic v2 as system schema**: All runtime configuration flows through `SceneDefinition`. Strong typing, validation, and JSON serialization. Caveats: enum values must be converted before YAML dump; `model_construct()` must be used to skip validation (not `Model(**data)`).

2. **No real asset files**: `SceneBuilder` generates primitive `.obj` / `.vtk` fallbacks on the fly. Keeps the repo lightweight but limits visual fidelity. No file in `assets/` is guaranteed to exist. Deformable meshes are procedurally tetrahedralized via `mesh_generation._try_external_tetrahedralization()`.

3. **Backend detection via duck typing**: `hasattr(sim, "_model")` → MuJoCo; `hasattr(sim, "_physics_client")` → PyBullet. Used throughout dynamics controllers and parameter randomizers rather than `isinstance()` checks. `trigger_cut()` also uses `hasattr(sim, "_apply_cut")` to gate cutting support.

4. **Observation dataclass as cross-backend contract**: `BaseSimulator.Observation` is the only data structure shared between simulators and the RL layer. This ensures backend-agnostic task termination and reward computation. Fluid forces and cut events flow through the `custom` field.

5. **Optional extras pattern**: Heavy dependencies (Ray/RLlib, ROS2, PyTorch, W&B, PhiFlow) are opt-in via `pip install "surg-rl[extra]"`. Each optional package has import guards with helpful error messages.

6. **Composition over inheritance in dynamics**: `EnvironmentController` composes three independent controllers rather than inheriting from them. Each sub-controller has its own ABC (`BaseController`) with a standard lifecycle.

7. **Discrete cutting events (not continuous actions)**: Cutting is a sparse, discrete event triggered by the agent calling `env.trigger_cut()` — not a continuous action dimension. This avoids the combinatorial explosion of learning a cut-vs-control policy and allows a 500ms cooldown to prevent mesh instability from repeated reloads.

8. **Model reload on cut**: MuJoCo does not support runtime mesh topology changes. After tetrahedral subdivision, the MJCF XML is rewritten and `MjModel` is reconstructed — preserving `qpos`/`qvel` where shapes match. This is an expensive operation (~10–50ms), reinforcing the discrete, cooldown-gated design.

<!-- VERIFY: Documentation site at https://surg-rl.readthedocs.io -->
<!-- VERIFY: GitHub repository at https://github.com/surg-rl/surg-rl -->
