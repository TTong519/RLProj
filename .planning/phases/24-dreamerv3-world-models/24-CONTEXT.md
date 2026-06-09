# Phase 24: DreamerV3 World Models - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Feasibility spike determines whether DreamerV3's RSSM can model surgical dynamics from pixel/state observations. If viable: process-isolated JAX subprocess training, GymToEmbodiedWrapper for SurgicalEnv protocol adaptation, dual observation modes (pixel + low-dim state). If not: defer to v0.5.0 with documented evidence, Phase 23 benchmarks revert to SB3-only comparison.
</domain>

<decisions>
## Implementation Decisions

### Feasibility spike design
- **D-01:** Test scene: Single forceps instrument + liver deformable tetrahedral mesh with suturing task from Phase 21 — most representative of surgical continuous-contact dynamics
- **D-02:** Quantitative pass/fail thresholds: Reconstruction MSE < 0.01 on held-out frames AND reward prediction MAE < 0.5 after 100k training steps with 10 evaluation episodes
- **D-03:** Feasibility report outputs: pass/fail recommendation, reconstruction MSE, reward prediction MAE, qualitative rollout fidelity assessment — documentation sufficient for v0.5.0 deferral decision

### Process isolation architecture
- **D-04:** JAX subprocess via Python `multiprocessing` with stdin/stdout communication (text/JSON protocol) — XLA_PYTHON_CLIENT_MEM_FRACTION=0.4 set in subprocess environment
- **D-05:** Subprocess lifecycle: spawn on `dreamer-train` command, communicate config via stdin, stream metrics/json via stdout, graceful shutdown on SIGTERM
- **D-06:** Main process never imports JAX/dreamerv3 — all DreamerV3 code isolated in subprocess module(s)

### GymToEmbodiedWrapper design
- **D-07:** Standard embodied.Env protocol — reset signal embedded in action dict (`action['reset'] = True`), observations returned as flat dict with `is_first`, `is_last`, `is_terminal` boolean keys
- **D-08:** Wrapper maps `SurgicalEnv.reset()` → first observation with `is_first=True`, `SurgicalEnv.step()` → observation with `is_last`/`is_terminal` set from terminated/truncated
- **D-09:** Action space conversion: `SurgicalEnv` continuous action → embodied action dict with same array, plus optional `reset` key

### Pixel vs low-dim observations
- **D-10:** Pixel observation: `render_mode='rgb_array'` from MuJoCo/PyBullet at `DreamerConfig.pixel_resolution` (default 64×64), includes depth channel where simulator supports it → (H, W, 4) RGBA tensor normalized to [0, 1]
- **D-11:** Low-dim state observation (~50-100 dims): joint positions (qpos), joint velocities (qvel), gripper state (aperture, force), task target position/config, tissue deformation metrics (max displacement, volume change, contact forces) concatenated flat
- **D-12:** `DreamerConfig.obs_type` selects mode — both must initialize and begin training without errors

### Benchmark integration
- **D-13:** Auto-discovery from standard checkpoint location: `surg-rl dreamer-train` writes checkpoints to `models/dreamerv3/{task}_{obs_type}/` — `surg-rl benchmark --dreamer-comparison` auto-discovers latest checkpoint per task/obs_type/backend
- **D-14:** When checkpoint found, ExperimentRunner evaluates DreamerV3 checkpoint (no training) and adds actual metrics to aggregated results replacing "pending — Phase 24" stub
- **D-15:** DreamerV3 results appear in same per-backend tables/plots as SB3 algorithms with distinct color (orange) and labeling — Phase 23 PlotRenderer/ReportGenerator already handle this

### Kill switch / deferral path
- **D-16:** If feasibility spike fails (MSE ≥ 0.01 OR reward MAE ≥ 0.5): DMV3-02, DMV3-03, DMV3-04 skipped; full DreamerV3 integration deferred to v0.5.0 per DMV3-05
- **D-17:** Failure evidence documented in Phase 24 spike report (metrics, training curves, analysis) — Phase 23 benchmark reports updated to remove DreamerV3 pending stub and declare SB3-only as v0.4.0 scope
- **D-18:** `surg-rl dreamer-train` command still exists but exits with informative message if spike failed, pointing to v0.5.0 roadmap

### OpenCode's Discretion
- Exact RSSM configuration for feasibility spike (hidden size, layers, discrete/continuous latent, kl_scale)
- JAX subprocess communication protocol details (JSON schema, message types, error handling)
- GymToEmbodiedWrapper exact observation/action dict key names and array shapes
- Low-dim state observation exact concatenation order and normalization
- DreamerV3 training hyperparameters for full integration (batch size, sequence length, learning rate, horizon, etc.)
- Checkpoint file format and `dreamer-train` CLI flags for resume, logging, evaluation
- How to run DreamerV3 evaluation without training (load checkpoint → act → compute metrics)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 24 — success criteria, DMV3-01..DMV3-05 requirements
- `.planning/REQUIREMENTS.md` — DMV3-01 through DMV3-05 requirements, v2 DMV3-06

### Schema contracts (from Phase 19)
- `src/surg_rl/scene_definition/schema.py` — `DreamerConfig` (line 1194), `BenchmarkConfig.dreamer_comparison` (line 752)
- `.planning/phases/19-schema-foundation/19-CONTEXT.md` — D-02 `DreamerConfig` spec, `[dreamer]` dep group, `DREAMER` lazy import

### Phase 23 Benchmarking (integration target)
- `.planning/phases/23-performance-benchmarking/23-CONTEXT.md` — D-11 DreamerV3 integration point, D-08 dual aggregation, D-10 per-backend structure
- `src/surg_rl/benchmark/experiment_config.py` — `ExperimentConfig.dreamer_comparison`, `DreamerConfig` fields
- `src/surg_rl/benchmark/plots.py` — DreamerV3 color handling, pending status rendering
- `src/surg_rl/benchmark/report.py` — DreamerV3 status banner, metrics.json schema
- `src/surg_rl/benchmark/experiment_runner.py` — DreamerV3 conditional stub logic

### Phase 21 Surgical Task Curriculum (training targets)
- `.planning/phases/21-surgical-task-curriculum/21-CONTEXT.md` — 6 task types, TaskRewardRouter, TaskResult hierarchy, curriculum difficulty
- `src/surg_rl/rl/task_reward_router.py` — `TASK_REWARD_REGISTRY` for task-specific reward functions
- `src/surg_rl/rl/task_results.py` — `TaskResult` base + 6 sub-models for success/failure detection

### Phase 22 Multi-Agent RL (optional MARL benchmarks)
- `.planning/phases/22-multi-agent-rl/22-CONTEXT.md` — `MultiAgentSurgicalEnv`, `MultiAgentConfig.shared_policy`

### Simulator contracts
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator` ABC, `Observation` dataclass, `render()` method
- `src/surg_rl/simulators/mujoco_simulator.py` — `MuJoCoSimulator.render()` for rgb_array
- `src/surg_rl/simulators/pybullet_simulator.py` — `PyBulletSimulator.render()` for rgb_array

### RL environment
- `src/surg_rl/rl/environment.py` — `SurgicalEnv` (reset, step, observation, action, reward), `make_env()`

### CLI infrastructure
- `src/surg_rl/cli.py` — `benchmark` command with `--dreamer-comparison` flag, pattern for new `dreamer-train` subcommand
- `pyproject.toml` — `[dreamer]` optional dependency group (dreamerv3~=1.5.0, jax~=0.4.20, optax>=0.1.7)

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — RL layer, simulator abstraction, environment controller
- `.planning/codebase/STACK.md` — optional dependency groups, CLI framework

### External docs
- DreamerV3 GitHub: https://github.com/danijar/dreamerv3
- embodied.Env protocol: https://github.com/danijar/embodied
- JAX GPU memory fraction: https://jax.readthedocs.io/en/latest/environment_variables.html

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`DreamerConfig`** (schema.py): Skeletal model with `obs_type`, `pixel_resolution`, `process_isolation`, `memory_fraction`, `dreamer_variant`, `reconstruction_metric` — Phase 24 extends/uses
- **`DREAMER`** lazy import (`src/surg_rl/dreamer/__init__.py`): `LazyImport("dreamerv3", "dreamer")` — no import-time dependency
- **`SurgicalEnv`**: Full RL environment with simulator + controller + observation/action/reward — GymToEmbodiedWrapper adapts this
- **`Observation` dataclass** (`base_simulator.py`): Cross-backend observation contract — low-dim state extraction can use this
- **`ExperimentConfig.dreamer_comparison`** flag + `DreamerConfig` in experiment config — benchmark integration point
- **`surg-rl benchmark` CLI**: Typer command pattern — `surg-rl dreamer-train` follows same structure
- **`pyproject.toml` `[dreamer]` group**: dreamerv3, jax, optax already declared with lazy import guard

### Established Patterns
- **Pydantic v2 schema-first**: All config models in `schema.py`, optional fields default to `None`
- **Lazy import guards**: Optional deps loaded via `LazyImport` in package `__init__.py` — no crash on missing packages
- **Subprocess isolation**: Phase 22 uses threading; Phase 24 uses multiprocessing for JAX/PyTorch GPU separation
- **CLI command pattern**: Typer subcommands with config file + flag overrides, Rich console output
- **Per-backend directory structure**: `results/{exp}_{timestamp}/{task}/{backend}/` — DreamerV3 results follow this
- **Additive extensions**: Never rewrite Phase 3 CurriculumScheduler, never duplicate sim logic (MARL pattern)

### Integration Points
1. **`surg-rl dreamer-train` → JAX subprocess**: CLI spawns subprocess with XLA_PYTHON_CLIENT_MEM_FRACTION=0.4, passes config, streams metrics
2. **GymToEmbodiedWrapper → `SurgicalEnv`**: Adapter wraps SurgicalEnv, maps reset/step to embodied.Env protocol
3. **JAX subprocess → DreamerV3 library**: Subprocess imports dreamerv3/jax, runs training/eval, outputs JSON metrics
4. **DreamerV3 checkpoint → `surg-rl benchmark`**: Auto-discovery from `models/dreamerv3/{task}_{obs_type}/` replaces "pending" stub
5. **`DreamerConfig` → ExperimentConfig**: `dreamer_comparison=True` + `DreamerConfig` fields drive benchmark DreamerV3 eval

</code_context>

<specifics>
## Specific Ideas

- **Feasibility spike scene**: Forceps + liver tet mesh from Phase 20/16, suturing task from Phase 21 — representative continuous-contact surgical dynamics
- **Quantitative thresholds**: MSE < 0.01, reward MAE < 0.5 after 100k steps — concrete pass/fail for DMV3-01
- **Process isolation**: multiprocessing + stdin/stdout JSON protocol — simple, robust, works cross-platform
- **embodied.Env protocol**: Standard reset-in-action, flat dict with is_first/is_last/is_terminal — matches DreamerV3 expectations exactly
- **Pixel obs**: rgb_array + depth at 64×64 normalized [0,1] — standard vision input for DreamerV3
- **Low-dim obs**: qpos + qvel + gripper + task target + tissue deformation (~50-100 dims) — comprehensive surgical state
- **Auto-discovery**: Checkpoints in `models/dreamerv3/{task}_{obs_type}/` — benchmark picks up without manual config
- **Kill switch**: Clear deferral to v0.5.0 with documented evidence — no ambiguity if spike fails

</specifics>

<deferred>
## Deferred Ideas

- **DreamerV3 offline training from demonstrations** (DMV3-06) — deferred to v0.5.0 per REQUIREMENTS.md
- **3D DreamerV3 video prediction** — 2D pixel reconstruction sufficient for feasibility assessment per Out of Scope
- **RLlib-backed centralized critic for MARL** (MARL-05) — independent SB3 policies sufficient for dual-arm
- **Task chains (grasp → cut → suture)** (TASK-05) — composite scheduling deferred to v0.5.0
- **COOLLADA/glTF mesh formats** — OBJ is universal baseline for both backends
- **Helm chart for K8s** — Kustomize overlays sufficient for v0.3.0+

</deferred>

---

*Phase: 24-dreamerv3-world-models*
*Context gathered: 2026-06-08*