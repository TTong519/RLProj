# Phase 23 Discussion Log

**Date:** 2026-06-07
**Phase:** 23 — Performance Benchmarking
**Outcome:** 4 areas discussed, 15 decisions captured

## Areas Discussed

### 1. Experiment Specification

| # | Question | Options Presented | User's Choice |
|---|----------|-------------------|---------------|
| 1 | How should users specify benchmark experiments? | CLI flags + YAML config (Recommended), CLI flags only, YAML config only | CLI flags + YAML config (Recommended) |
| 2 | How should CLI flags interact with YAML config files? | CLI overrides YAML (Recommended), Mutually exclusive, YAML overrides CLI | CLI overrides YAML (Recommended) |
| 3 | What format should the YAML config be — how is it validated? | Pydantic v2 model (Recommended), Raw dict, JSON Schema validation | Pydantic v2 model (Recommended) |
| 4 | What should the ExperimentConfig model look like? Which fields are required vs optional? | Minimal config file (Recommended), Full config with explicit defaults, Config with SB3 override blocks | Full config with explicit defaults |

**Summary:** CLI-first ergonomics with YAML for reproducibility. User chose a Pydantic v2 ExperimentConfig model with every field explicit in the YAML — self-documenting config files. CLI flags override any YAML field for quick tweaks.

### 2. Metrics & Visualization Pipeline

| # | Question | Options Presented | User's Choice |
|---|----------|-------------------|---------------|
| 5 | Which performance metrics should the benchmark compute and report? | All 5 core metrics (Recommended), Mean reward + success rate only, 4 metrics skip sample efficiency | All 5 core metrics (Recommended) |
| 6 | What visualization library stack should the benchmark use? | matplotlib + seaborn + rliable (Recommended), matplotlib only, Plotly interactive | matplotlib + seaborn + rliable (Recommended) |
| 7 | What visualizations should the report generate? | Curves + bars + tables (Recommended), Learning curves only, Curves + bar charts | Curves + bars + tables (Recommended) |
| 8 | For learning curves, what statistical aggregation should be computed across seeds? | IQM + stratified bootstrap (Recommended), Mean ± 1σ only, Both rliable IQM and mean ± 1σ | Both rliable IQM and mean ± 1σ |

**Summary:** Comprehensive RL benchmarking metrics with rliable statistical rigor. User chose dual aggregation (IQM + mean ± 1σ) for maximum flexibility. Three visualization types in the report: learning curves, bar charts, and tables.

### 3. Results Storage & Output Format

| # | Question | Options Presented | User's Choice |
|---|----------|-------------------|---------------|
| 9 | What output formats should the benchmark produce? | JSON + PNG + HTML report (Recommended), JSON only, JSON + PNG plots | JSON + PNG + HTML report (Recommended) |
| 10 | How should benchmark results be organized on disk? | Nested by experiment/task/backend (Recommended), Flat per-experiment directory, Flat single directory | Nested by experiment/task/backend (Recommended) |
| 11 | How should raw metrics data be stored — one file or per-seed? | Summary JSON + per-seed CSV (Recommended), Single JSON with embedded per-seed data, Per-seed CSVs only | Summary JSON + per-seed CSV (Recommended) |

**Summary:** Three output formats with nested directory structure separating backends. Per-seed CSVs for detailed introspection + summary JSON for programmatic aggregation.

### 4. Execution Orchestration

| # | Question | Options Presented | User's Choice |
|---|----------|-------------------|---------------|
| 12 | How should seed sweeps and algorithm comparisons be orchestrated? | Sequential seed sweep internally (Recommended), Parallel seed sweep internally, Single-seed runner + external sweep | Parallel seed sweep internally |
| 13 | What parallelism mechanism should the runner use? | multiprocessing (Recommended), ThreadPoolExecutor, Ray | multiprocessing (Recommended) |
| 14 | How should per-backend benchmarking work? | Single run both backends sequential (Recommended), Separate per-backend invocations, Optional concurrent backends | Single run both backends sequential (Recommended) |
| 15 | How should parallel seed count be controlled? | Configurable auto-default (Recommended), Hardcoded to CPU count, Always sequential | Configurable auto-default (Recommended) |

**Summary:** Parallel seed sweeps via multiprocessing, single command handles both backends sequentially, configurable `--max-parallel` flag with sensible defaults.

## Deferred Ideas

None — discussion stayed within phase scope.

## OpenCode's Discretion

See CONTEXT.md § OpenCode's Discretion for the full list of areas where the planner/researcher has implementation flexibility.
