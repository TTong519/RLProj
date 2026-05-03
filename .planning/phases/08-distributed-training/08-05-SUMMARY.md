---
status: complete
plan: 08-05
phase: 08-distributed-training
summary: "CLI commands: train-rllib, tune, checkpoint-inspect"
---

# 08-05 Summary

## What was built

1. **`src/surg_rl/cli.py`** — three new Typer commands appended after existing `evaluate`:
   - `surg-rl train-rllib` — wraps `train_rllib(RllibConfig.from_cli_args(...))`
     - Options: `--scene`, `--algorithm`, `--timesteps`, `--n-envs`, `--lr`, `--gamma`, `--seed`, `--log-dir`, `--checkpoint-freq`, `--local-mode`
   - `surg-rl tune` — wraps `run_tune_experiment(build_tune_search_space(...), ...)`
     - Options: `--scene`, `--algorithm`, `--timesteps`, `--num-samples`, `--max-iters`, `--lr-min/max`, `--gamma-min/max`, `--log-dir`, `--scheduler`, `--local-mode`
   - `surg-rl checkpoint-inspect` — wraps `inspect_rllib_checkpoint` / `inspect_sb3_checkpoint` / `compare_checkpoints`
     - Args: `path`; flags: `--compare-with`
     - Sniffs format by `Path.is_dir()`
   - All three commands catch `ImportError` and print helpful install message with `typer.Exit(1)`.

2. **`tests/test_rllib_cli.py`** — 7 tests:
   - Help text presence for all three commands
   - Mock checkpoint inspect (RLlib dir + SB3 zip)
   - Not-found error handling

## Deviations from plan

- None.

## Tests

| Test | Status |
|------|-------- |
| `test_cli_help_includes_rllib_commands` | PASSED |
| `test_train_rllib_help` | PASSED |
| `test_tune_help` | PASSED |
| `test_checkpoint_inspect_help` | PASSED |
| `test_checkpoint_inspect_rllib_mock` | PASSED |
| `test_checkpoint_inspect_sb3_mock` | PASSED |
| `test_checkpoint_inspect_not_found` | PASSED |
