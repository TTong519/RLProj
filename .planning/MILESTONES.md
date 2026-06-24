# Milestones: Surg-RL

## v0.5.0 Scene Editor & UX Polish (Shipped: 2026-06-24)

**Phases completed:** 5 phases, 22 plans, 22 tasks

**Key accomplishments:**

- Lint-clean dreamer module (10/10 ruff issues fixed) and multi-arch Dockerfile.ros2 via `$TARGETARCH`
- Cut cooldown regression test parametrized over both backends + PhiFlow `union()` workaround documented
- BaseSimulator `fluid_step(dt)` hook with no-op default + explicit overrides + env wiring + 5-test regression suite
- GUI scaffolding: `[gui]` extra + `surg-rl-gui` console script + editor package (LazyImport + HAS_GUI + mjpython helpers) + 19-test regression suite
- Suturing demo refactored to use shared `demos/_common.py` helpers with 5-stage Rich narration, plus the `NARRATION_TEMPLATE.md` P8-prevention document written FIRST.
- Knot-tying demo (KNOT_TIER instrument) with 5-stage narration and canonical fixture copy at `tests/fixtures/scenes/knot_tying.json`
- Dual-arm needle-passing demo (surgeon + assistant) + 6-test regression suite covering all 3 demos, narration template, and fixtures
- EditorWindow (QMainWindow) + 4-pane QDockWidget layout + safe_error_message redactor + EditorSettings QSettings wrapper + drag-drop + status bar
- SchemaWalker (recursive over 62 schema classes) + FieldRenderer widget-factory registry (vec3-spinbox, enum-combobox, file-picker, color-picker, range-slider)
- ViewportPanel (20 Hz frame loop, mouse orbit/pan/zoom, R-key camera reset) + custom ViewportCanvas + MuJoCo/PyBullet render bridge with framebuffer retry
- SceneTreeView (right-click Add/Remove/Duplicate, drag-reorder, validation icons) + PropertyForm (QFormLayout, 150 ms debounced validation)
- LLMPanel (QThread TextParserWorker) + SceneUndoStack (deep-copy snapshots, 100-level cap) + file operations (New/Open/Save/Save As) + GUI smoke tests
- Fixed --headless path resolution (4-level repo root) and hardened mjpython re-exec against crash (FileNotFoundError) and infinite loop (failed detection)
- Hardened viewport against MuJoCo Renderer __del__ crash, added _running flag to halt QTimer cleanly, and wired closeEvent to stop viewport before Qt teardown — editor no longer freezes on launch
- User-facing docs refresh: README + CONTRIBUTING + CHANGELOG rewritten for v0.5.0 with 3 embedded demo GIFs + 3 GUI screenshots
- Advanced tech debt: HARD-fixture `SurgicalEnv`-construction integration test, `CurriculumStageConfig.difficulty` normalization at env-construction, K8s PVC e2e scaffolding (stubbed, deferred to v0.6.0), organ mesh licensing research spike (decision deferred to v0.6.0)
- Post-close hardening (commit 997ad9d): interactive `ViewportCanvas` replacing `QLabel`, PyBullet `_normalize_pb_rgb()` canonicalization, MuJoCo persistent-renderer-failure short-circuit, viewport framebuffer-size retry

**Known deferred items at close:** 2 (see STATE.md Deferred Items) — Phase 09 ros2-bridge verification gaps, Phase 24 DreamerV3 UAT (GPU-gated). The v0.5.0 `gui-no-render-under-mjpython` debug session was resolved by commit `3031ed9`. No `v0.5.0-MILESTONE-AUDIT.md` was run.

---

## v0.4.0: Training Infrastructure & Realism

**Shipped:** 2026-06-09 | **Phases:** 19-24 | **Plans:** 21 | **Requirements:** 23/23 Complete

Transforms Surg-RL from a simulation framework into a competitive RL research platform with real surgical assets, comprehensive task curriculum, systematic benchmarking, multi-agent support, and a feasibility-driven DreamerV3 world model integration. Schema-first foundation (Pydantic v2 + optional dependency groups) enables clean feature isolation; process-isolated JAX training keeps the DreamerV3 spike from disturbing the SB3 stack.

**Key accomplishments:**

- Pydantic v2 schema foundation: 5 new config models (MeshAsset, TaskConfig, BenchmarkConfig, MultiAgentConfig, DreamerConfig) with `None` defaults; 4 optional dependency groups (`[assets]`, `[benchmark]`, `[marl]`, `[dreamer]`) with lazy import guards
- trimesh-based real instrument and organ meshes: 9 instrument URDFs with V-HACD collision decomposition, 4 organ meshes through the tetgen deformable pipeline, procedural fallback for missing assets
- 6 surgical task types × 3 difficulty levels via TaskResult Pydantic v2 hierarchy + TaskRewardRouter; CurriculumScheduler extended additively with `task_difficulty` field
- PettingZoo ParallelEnv dual-arm training via `MultiAgentSurgicalEnv` (thin adapter over canonical `SurgicalEnv`); SuperSuit wrappers for SB3 compatibility; shared and independent policy modes
- SB3 benchmarking framework: `ExperimentRunner` with multiprocessing seed sweeps, IQM + mean±std aggregation via rliable, publication-quality plots/tables, MuJoCo and PyBullet as separate backend targets
- DreamerV3 feasibility spike + process-isolated training: `GymToEmbodiedWrapper` protocol adapter, JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`, pixel (64×64 RGBA) and state observation modes, auto-discovery checkpoint integration
- 12/12 UAT pass on Phase 24 with gap closure Plan 24-05 adding KNOT_TIER, NEEDLE instrument types and 3 additional task types (knot_tying, needle_insertion, dissection)

**Decisions:**

- Schema-first — all new Pydantic v2 models with `None` defaults; existing models unchanged. Decouples schema from implementation
- trimesh is the sole new mesh library; no glTF/COLLADA complexity
- `MultiAgentSurgicalEnv` MUST be a separate class from `SurgicalEnv` — clean adapter pattern, no shared mutable state
- DreamerV3 needs process isolation via JAX subprocess (XLA_PYTHON_CLIENT_MEM_FRACTION=0.4) to avoid GPU memory conflicts with PyTorch
- CurriculumScheduler extension must be additive — never replace Phase 3 fix
- Benchmarking treats MuJoCo and PyBullet as separate targets — no cross-backend aggregation
- Dual statistical aggregation (mean±1σ + IQM+CI) per D-08; both methods shown for transparency
- Seaborn colorblind-safe palette with fixed algorithm color cycle; DreamerV3 distinct orange (#FF8C00)
- DreamerV3 task type set locked to match Phase 21 curriculum (6 types) via gap closure Plan 24-05

**Issues deferred:** 12 (mostly carry-overs from v0.3.2 and v0.3.1, plus 3 v1 requirements TASK-05/MARL-05/DMV3-06 deferred from v0.4.0 → v2)

---

## v0.3.2: Advanced Simulation

**Shipped:** 2026-05-05 | **Phases:** 15-18 | **Plans:** 9 | **Tests:** 910

Advanced simulation features for the surgical robotics RL training system: platform-agnostic tetgen mesh generation, FEM-based deformable objects, real-time volumetric tetrahedral mesh cutting, and Eulerian grid-based fluid simulation with two-way solid coupling.

**Key accomplishments:**

- Replaced VTK/PyVista with tetgen for tetrahedral mesh generation (200MB dep savings)
- FEM-based deformable objects via MuJoCo `<flex>` with auto-derived Neo-Hookean parameters and PyBullet soft body param mapping
- Real-time tetrahedral mesh cutting engine with signed-distance classification, edge-plane intersection, and remeshing integrated with both backends
- Eulerian grid-based fluid solver (PhiFlow 3.4.0) with MAC grid, pressure projection, and two-way solid coupling for bleeding/irrigation simulation
- In-memory tetgen → MJCF flex bridge enabling arbitrary mesh pipelines without intermediate files

**Decisions:**

- Tetgen replaces VTK entirely (not side-by-side) — removes binary deps
- Cutting is a discrete trigger (not continuous action) with 500ms cooldown; PyBullet cuts use RESET_USE_DEFORMABLE_WORLD + full scene reload
- PhiFlow over Mantaflow for Eulerian fluids; CPU-first, GPU deferred

**Issues deferred:** 3

---

## v0.3.1: Audit Gap Closure

**Shipped:** 2026-05-04 | **Phases:** 14 | **Plans:** 1 | **Tests:** 833

Fixes the 5 integration gaps identified in the v0.3.0 milestone audit, closing the loop between Docker release workflows, Kubernetes manifests, and ROS2 entrypoints.

**Key accomplishments:**

- `release.yml` builds and pushes `Dockerfile.ros2` to GHCR alongside CPU and CUDA images
- Training Job uses CUDA image on GPU nodes with correct image reference
- initContainer health check uses ROS2 topic probe instead of generic HTTP check
- `bridge_node`/`replay_node` console_scripts registered in pyproject.toml
- `_mps_available()` imports from `gpu.py` instead of duplicating detection logic

**Decisions:**

- Single-phase fix for all 5 gaps rather than spreading across phases
- All gaps were wiring/integration issues, not architectural — no schema or API changes needed

**Issues deferred:** 0

---

## v0.3.0: Production & Cross-Platform

**Shipped:** 2026-05-03 | **Phases:** 10-13 | **Plans:** 18

Wire PyTorch MPS backend into the RL training pipeline on Apple Silicon, build multi-architecture Docker images for amd64 and arm64, implement ros2_control hardware interface integration, and provide production-ready Kubernetes manifests for RL training jobs and Ray RLlib clusters.

**Key accomplishments:**

- Metal MPS backend on Apple Silicon with automatic device resolution and cpu fallback for unsupported ops
- macOS CI runner with mjpython auto-detection and zero xfail markers on soft-body tests
- Multi-arch Docker (CPU, CUDA, ROCm, Jetson/JetPack) with buildx verification in CI and GHCR push on release tags
- ros2_control `SystemInterface` subclass + URDF tag injection + launch files composable from both colcon and pip installs
- Kubernetes manifests: Training Jobs, KubeRay RayCluster, ROS2 bridge sidecar, ConfigMap/Secrets/PVC with checkpoint persistence

**Decisions:**

- Phase ordering: Metal → Docker → K8s; ros2_control runs in parallel (Linux-only, independent)
- GHCR as container registry with multi-arch manifest on git tags
- `ROS_PACKAGE_PATH` fallback for pip installs alongside native colcon workspace support

**Issues deferred:** 5 (audit gaps resolved in v0.3.1)

---

## v0.2.0: Scaling, Rendering & Real Robot

**Shipped:** 2026-05-03 | **Phases:** 6-9 | **Plans:** 19

Scale beyond single-GPU SB3 training to distributed RLlib execution with multi-GPU support, add real-time non-blocking 3D rendering, bridge to real hardware via ROS2, and provide universal GPU backend detection across CUDA/ROCm/Metal/Intel.

**Key accomplishments:**

- Universal GPU backend detection across CUDA, Intel oneAPI, AMD ROCm, and Apple Metal with unified `HardwareBackend` enum and auto/CPU fallback
- Real-time non-blocking 3D rendering via `RenderThread` with FPS throttle, headless fallback, and macOS mjpython support
- Ray/RLlib distributed training with multi-GPU auto-config, Ray Tune hyperparameter search, and checkpoint inspection utilities
- ROS2 bridge running as separate `multiprocessing.Process` with IPC via `multiprocessing.Queue` (keep-latest semantics) for real-robot command forwarding
- TrajectoryReplay for offline playback of SB3 checkpoints over ROS2 topics

**Decisions:**

- GPU acceleration as Phase 6 (foundation for rendering and distributed training)
- Ray/RLlib as optional `[distributed]` extra with lazy imports; RLlib 2.55 new API stack (`config.learners()`, `config.env_runners()`)
- ROS2 bridge runs as separate process (not daemon thread) for process-safe IPC; macOS warns + disables, CLI exits gracefully
- Kubernetes and multi-platform Docker deferred to v0.3.0

**Issues deferred:** 3

---

## v0.1.0: Stabilization

**Shipped:** 2026-05-02 | **Phases:** 1-5 | **Plans:** 12 | **Tests:** 607

Stabilizes the Surg-RL surgical-robotics RL training system by fixing 8 critical bugs, completing the action space, hardening simulator performance, and extending task geometry and real asset support. A correctness-first, stabilization-focused milestone: no new features until the foundation is solid.

**Key accomplishments:**

- Fixed 8 critical bugs (quaternion order, joint reset leakage, physics=None crash, reward sign contract, curriculum dynamics, LightConfig mutation, API key exposure, VecEnv evaluate robustness)
- Completed all 7 `ActionTypes` with gripper auto-detection and load-time validation across MuJoCo and PyBullet backends
- Hardened simulator performance with soft-body mesh caching (<100ms reset), vectorized mesh generation (~10x faster), and cross-backend state save/restore (qpos/qvel within 1e-6)
- Extended task geometry via `target_body` observation binding and real URDF/OBJ loading with deduplicated fallback warnings
- Optional W&B/MLflow experiment tracking, multi-stage Docker, GitHub Actions CI (matrix 3.10/3.11/3.12), and PyPI release pipeline

**Decisions:**

- Correctness-first: no new features until foundation is solid
- Gripper auto-detection via joint name heuristics rather than explicit config
- Soft-body mesh caching at simulator level with scene-definition hash key

**Issues deferred:** 3
