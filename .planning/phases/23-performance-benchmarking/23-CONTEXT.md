# Phase 23: Performance Benchmarking - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Reproducible experiment runner comparing SB3 algorithms across surgical tasks, producing publication-quality plots (learning curves, bar charts), tables, and per-backend reports. MuJoCo and PyBullet are treated as separate hardware targets — cross-backend comparison is never performed. DreamerV3 comparison is a conditional integration point reporting "pending — Phase 24" when checkpoints are unavailable.
</domain>

<decisions>
## Implementation Decisions

### Experiment specification
- **D-01:** CLI flags + YAML config — `surg-rl benchmark --task suturing --algorithms PPO,SAC --seeds 5` for quick runs; `surg-rl benchmark --config experiments/run.yaml` for reproducible formal experiments
- **D-02:** CLI flags override YAML fields — `--config experiments/base.yaml --seeds 10` runs the base config with 10 seeds overriding the YAML value
- **D-03:** `ExperimentConfig` is a Pydantic v2 model (extends `BenchmarkConfig` from Phase 19) with deterministic YAML round-trip via `model_dump()`/YAML serialization — `surg-rl benchmark --config foo.yaml` reproduces the exact same run
- **D-04:** Full config with explicit defaults — every field in the YAML is present (task, algorithms, seeds, backend, timesteps, hyperparameters, render settings), making configs self-documenting

### Metrics & visualization pipeline
- **D-05:** 5 core metrics computed per experiment sweep: mean reward (cumulative, smoothed), success rate (% episodes), episode length (mean ± std), wall-clock time (per run, per step), sample efficiency (reward vs env steps)
- **D-06:** Visualization stack: matplotlib for learning curves + bar charts, seaborn for styling, rliable for IQM/stratified bootstrap CIs — matches the Phase 19 [benchmark] optional dependency group
- **D-07:** Three visualization types in the report: learning curves (mean reward vs timestep per algorithm, shaded region), bar charts (success rate by algorithm with rliable statistical significance), and structured result tables
- **D-08:** Dual statistical aggregation on learning curves: rliable IQM (interquartile mean) with stratified bootstrap CIs (Agarwal et al. 2021) AND mean ± 1σ — IQM for publication figures, mean ± 1σ for quick inspection

### Results storage & output format
- **D-09:** Three output formats per benchmark run: JSON raw data (programmatic use), PNG plots (publication figures), and an HTML summary page (browser viewing)
- **D-10:** Directory structure: `results/{experiment_name}_{timestamp}/{task}/{backend}/` — experiment → task subfolder → per-backend subdirectory. Backend results are always separate as required by ROADMAP (BENCH-04)
- **D-11:** Raw metrics storage: one `metrics.json` summary per experiment run (all seeds aggregated) + one `.csv` per seed-run (`seed_{N}_metrics.csv`) for detailed introspection

### Execution orchestration
- **D-12:** Parallel seed sweep internally — `surg-rl benchmark` spawns all seed runs within a single process tree, aggregates results, and produces the unified report. No external scripting needed
- **D-13:** `multiprocessing` for parallelism — one process per seed with its own SB3 training loop. True parallelism avoids GIL contention
- **D-14:** Single run handles both backends sequentially — `surg-rl benchmark --backend all` runs MuJoCo sweep first, then PyBullet sweep, producing one unified report with separate per-backend sections
- **D-15:** Configurable parallelism with `--max-parallel N` flag defaulting to `cpu_count() - 1`. `--max-parallel 1` enables sequential debug mode with clear per-seed output

### OpenCode's Discretion
- Exact `ExperimentConfig` Pydantic model fields and validation
- YAML serialization/deserialization implementation (Pydantic v2 model_dump + PyYAML round-trip)
- CLI flag → ExperimentConfig field mapping and override logic
- Metric computation details (smoothing window, sample efficiency formula, wall-clock stop/start points)
- Plot styling (seaborn theme, color palette, figure dimensions, font sizes)
- rliable bootstrap configuration (number of bootstrap samples, confidence level)
- HTML report template and generation (static HTML with embedded JSON + linked PNGs, or inline)
- Per-seed CSV schema (columns, checkpoint frequency)
- multiprocessing pool lifecycle, progress reporting (Rich progress bar), and error handling (failed seeds logged but don't crash the sweep)
- DreamerV3 integration point implementation (conditional `DreamerV3: pending — Phase 24` stub)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 23 — success criteria (BENCH-01..BENCH-05), Phase 23 requirements
- `.planning/REQUIREMENTS.md` — BENCH-01 through BENCH-05 requirements

### Schema contracts (from Phase 19)
- `src/surg_rl/scene_definition/schema.py` — `BenchmarkConfig` (Phase 19 D-06 contract)
- `.planning/phases/19-schema-foundation/19-CONTEXT.md` — D-06 `BenchmarkConfig` model spec, `[benchmark]` dep group

### Task & training infrastructure
- `.planning/phases/21-surgical-task-curriculum/21-CONTEXT.md` — 6 task types, `TaskRewardRouter.build(task_type)`, `check_success()`/`check_failure()`, curriculum difficulty levels
- `src/surg_rl/rl/training.py` — `TrainingManager`, SB3 algorithm mapping (PPO, SAC, TD3, DDPG, A2C)
- `src/surg_rl/rl/task_reward_router.py` — `TaskRewardRouter`, `TASK_REWARD_REGISTRY`
- `src/surg_rl/rl/task_results.py` — `TaskResult` hierarchy for per-task success/failure detection

### Multi-agent (optional MARL benchmarks)
- `.planning/phases/22-multi-agent-rl/22-CONTEXT.md` — `MultiAgentSurgicalEnv`, `MultiAgentConfig.shared_policy`
- `src/surg_rl/rl/marl_env.py` — `MultiAgentSurgicalEnv(ParallelEnv)` for optional dual-arm benchmarks

### Simulator contracts
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator` ABC, `Observation` dataclass, `step()` interface
- `src/surg_rl/rl/environment.py` — `SurgicalEnv` (Gymnasium wrapper), `make_env()`

### CLI infrastructure
- `src/surg_rl/cli.py` — existing Typer CLI, `surg-rl train` subcommand pattern to follow for `surg-rl benchmark`
- `pyproject.toml` — `[benchmark]` optional dependency group (matplotlib, seaborn, pandas, rliable)

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — RL layer, SB3 integration, training manager pattern
- `.planning/codebase/STACK.md` — pyproject.toml optional dep groups, CLI framework
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`TrainingManager`** (`rl/training.py`): Already creates SB3 models, runs `learn()`, saves checkpoints, supports evaluation callbacks — the benchmark runner invokes TrainingManager per seed
- **`ExperimentConfig`** (schema.py): Exists from Phase 19 with `None` defaults — extends this with benchmark-specific fields (task, algorithms, seeds, backend, timesteps, hyperparameters)
- **`TaskRewardRouter.build(task_type)`**: Returns `[BaseRewardFunction, ...]` per task — benchmark runner uses this to construct per-task reward functions without hardcoding
- **`Callbacks`** (`rl/callbacks.py`): `EvaluationCallback`, `CheckpointCallback`, `TrainingProgressCallback` — benchmark runner hooks into SB3 callback system to extract per-timestep metrics
- **`CLI`** (`cli.py`): Typer CLI with existing subcommand patterns — new `surg-rl benchmark` subcommand follows the same structure
- **`SurgicalEnv`** (`rl/environment.py`): Canonical Gymnasium env — benchmark runner creates env per seed via `make_env()`
- **`pyproject.toml` [benchmark] dep group**: matplotlib, seaborn, pandas, rliable already declared — Phase 23 just imports them

### Established Patterns
- **SB3 callback system**: Benchmark runner injects a MetricCollectorCallback that writes per-timestep data to disk — same pattern as existing callbacks
- **Pydantic v2 schema-first**: ExperimentConfig extends BenchmarkConfig, YAML round-trip via model_dump → PyYAML
- **Lazy import guards**: matplotlib, seaborn, rliable are optional deps — lazy import with `[benchmark]` extras check
- **CLI flag → config mapping**: Typer options → ExperimentConfig field assignments with precedence (CLI > YAML > defaults)
- **multiprocessing pool lifecycle**: Spawn → collect → aggregate — same pattern as SubprocVecEnv but simpler (no shared env)

### Integration Points
1. **CLI → ExperimentRunner**: `surg-rl benchmark` parses flags/config → creates ExperimentRunner → orchestrates sweep
2. **ExperimentRunner → TrainingManager**: Per-seed process spawns TrainingManager with algorithm + env config → `model.learn()` with MetricCollectorCallback
3. **MetricCollectorCallback → CSV writer**: SB3 step_callback writes per-timestep metrics (reward, success, episode_count, wall_time) to per-seed CSV
4. **Aggregator → Report generator**: After all seeds complete, aggregator reads all CSVs → computes IQM, mean ± 1σ, success rate → generates PNGs + HTML + JSON
5. **DreamerV3 integration point**: Report has conditional `DreamerV3: pending — Phase 24` row when DMV3 checkpoints unavailable — placeholder that Phase 24 fills
</code_context>

<specifics>
## Specific Ideas

No specific UX/visual references — Phase 23 is infrastructure (experiment runner + report generation), no user-facing UI beyond CLI.

### Key architectural constraints
- Backend separation is mandatory — MuJoCo and PyBullet results are never aggregated together, always separate rows/columns (BENCH-04)
- Cross-backend determinism is never claimed — each backend has its own physics, seed propagation, and timing
- DreamerV3 comparison is a conditional stub — not a hard dependency, Phase 24 fills it in
- The Phase 3 CurriculumScheduler fix is never modified — benchmark runner consumes curriculum output, never changes it
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 23-performance-benchmarking*
*Context gathered: 2026-06-07*
