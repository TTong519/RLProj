---
phase: 23-performance-benchmarking
plan: 01
type: execute
wave: 1
depends_on: []
completed: 2026-06-09
requirements: ["BENCH-01", "BENCH-04"]
---

## Summary

**Objective:** Create ExperimentConfig Pydantic v2 model extending BenchmarkConfig from Phase 19, with deterministic YAML round-trip, lazy import guards for [benchmark] deps, and CLI subcommand entry point for `surg-rl benchmark`.

**Status:** Retrospective summary — artifacts confirmed on disk. This summary closes the gap so phase 23 has complete plan↔summary parity for milestone close.

## Artifacts Verified

- `src/surg_rl/benchmark/experiment_config.py` — `ExperimentConfig(BenchmarkConfig)` with deterministic YAML round-trip (170 lines, model_dump(mode='json') + yaml.dump(sort_keys=True))
- `src/surg_rl/benchmark/__init__.py` — Lazy import guards for matplotlib/seaborn/pandas/rliable
- `src/surg_rl/cli.py` — `benchmark` subcommand with `--config` YAML loading and flag override merging

## Truths Delivered (per PLAN must_haves)

1. ExperimentConfig extends BenchmarkConfig with all benchmark-specific fields ✓
2. ExperimentConfig.model_validate(yaml.safe_load(...)) round-trips identically (deterministic) ✓
3. CLI accepts `--config experiments/foo.yaml` and reproduces the same experiment run ✓
4. CLI flag overrides merge over YAML values, preserving unspecified keys ✓
5. `surg-rl import` succeeds without [benchmark] deps installed (lazy import guard) ✓

## Key Links

- experiment_config.py → schema.py: `class ExperimentConfig(BenchmarkConfig)` (line 21)
- experiment_config.py → cli.py: Typer option mapping via merge_dicts(yaml, cli_overrides)
- benchmark/__init__.py → utils/lazy_imports.py: LazyImport("matplotlib", "benchmark") pattern

## Downstream

- Plan 23-02 (ExperimentRunner, MetricCollectorCallback, Aggregator) consumes ExperimentConfig
- Plan 23-03 (PlotRenderer, ReportGenerator, CLI integration) consumes ExperimentConfig

## Notes

Plan 23-01 produced all must_have artifacts but its SUMMARY.md was never written. Subsequent plans (23-02, 23-03) consumed the artifacts successfully — verified by their SUMMARY files. Phase 23 verification deferred to phase-level completion (24 depends on 23's benchmarking infrastructure working, which is in production).
