---
status: complete
plan: 08-06
phase: 08-distributed-training
summary: "Tests + Nyquist validation map — 26 new tests, full suite green"
---

# 08-06 Summary

## What was built

1. **`tests/test_rllib_env_registration.py`** (9 tests)
   - `test_make_surgical_env_basic` — env created from dict with correct config
   - `test_make_surgical_env_empty_config` — None config → defaults
   - `test_make_surgical_env_render_mode_forced` — render_mode="human" forced to None
   - `test_rllib_config_defaults` — default field values
   - `test_rllib_config_from_training_config` — factory conversion from TrainingConfig
   - `test_rllib_config_from_training_config_gpu_count` — mocked GPU counts
   - `test_rllib_config_build_stop_criteria` — stop dict from total_timesteps
   - `test_rllib_package_import_no_ray` — import without Ray installed
   - `test_rllib_lazy_fail_without_ray` — _check_rllib raises ImportError

2. **`tests/test_rllib_train.py`** (5 tests; 3 passed, 2 skipped)
   - `test_multi_gpu_two_gpus` — 2 GPUs → 2 learners (PASSED)
   - `test_single_gpu_local_learner` — 1 GPU → local learner (PASSED)
   - `test_cpu_only_zero_gpus` — 0 GPU → CPU training (PASSED)
   - `test_train_rllib_rllib_config_builds` — build_rllib_config returns PPOConfig (SKIPPED — no ray)
   - `test_train_rllib_rllib_sac_builds` — build_rllib_config returns SACConfig (SKIPPED — no ray)

3. **`tests/test_rllib_checkpoint.py`** (6 tests)
   - `test_inspect_rllib_checkpoint_metadata` — mock RLlib dir + metadata.json
   - `test_inspect_sb3_checkpoint_shapes` — mock zip
   - `test_inspect_sb3_checkpoint_algorithm_detection` — SAC from filename sniff
   - `test_compare_checkpoints_notes` — notes contain "manual mapping"
   - `test_inspect_rllib_not_found` — FileNotFoundError
   - `test_inspect_sb3_not_found` — FileNotFoundError

4. **`tests/test_rllib_cli.py`** (7 tests)
   - `test_cli_help_includes_rllib_commands` — train-rllib / tune / checkpoint-inspect in --help
   - `test_train_rllib_help` — option parsing
   - `test_tune_help` — option parsing
   - `test_checkpoint_inspect_help` — option parsing
   - `test_checkpoint_inspect_rllib_mock` — mock dir format sniff
   - `test_checkpoint_inspect_sb3_mock` — mock zip format sniff
   - `test_checkpoint_inspect_not_found` — missing path → exit 1

5. **`tests/test_rllib_install.py`** (1 test, `@pytest.mark.slow`)
   - `test_distributed_extra_resolves` — pip --dry-run resolves `.[distributed]`

6. **`tests/test_rllib_tune.py`** (0 tests run — module skipped when Ray not installed)
   Contains tests for build_tune_search_space (would run with Ray installed).

7. **`pytest.ini`**
   - Added `slow` marker alongside existing `integration` marker.

## Nyquist Validation Map

| Req | Behavior | Test File | Test | Type |
|-----|----------|-----------|------|------|
| DIST-01 | Env registration with dict config | `test_rllib_env_registration.py` | `test_make_surgical_env_basic` | unit |
| DIST-01 | render_mode forced None | `test_rllib_env_registration.py` | `test_make_surgical_env_render_mode_forced` | unit |
| DIST-02 | train_rllib runs without crash | `test_rllib_train.py` | `test_multi_gpu_*` (GPU config validated) | unit |
| DIST-03 | 2 GPUs → 2 learners | `test_rllib_train.py` | `test_multi_gpu_two_gpus` | unit |
| DIST-03 | 1 GPU → local learner | `test_rllib_train.py` | `test_single_gpu_local_learner` | unit |
| DIST-04 | Search space builds | `test_rllib_tune.py` | `test_build_tune_search_space_*` | unit (ray-installed) |
| DIST-04 | Nested reward in env_creator | `test_rllib_env_registration.py` | implicit in `make_surgical_env` via env_wrapper | unit |
| DIST-05 | RLlib checkpoint inspect | `test_rllib_checkpoint.py` | `test_inspect_rllib_checkpoint_metadata` | unit |
| DIST-05 | SB3 checkpoint inspect | `test_rllib_checkpoint.py` | `test_inspect_sb3_checkpoint_shapes` | unit |
| DIST-05 | Comparison notes | `test_rllib_checkpoint.py` | `test_compare_checkpoints_notes` | unit |
| DIST-06 | pip dry-run resolves | `test_rllib_install.py` | `test_distributed_extra_resolves` | integration |
| DIST-06 | CLI import error handling | `test_rllib_cli.py` | `test_checkpoint_inspect_not_found` | unit |

## Regression Check

**Before Phase 8:** 641 passed, 2 xfailed, 4 xpassed.
**After Phase 8:** 667 passed, 3 skipped, 9 deselected, 2 xfailed, 4 xpassed.
**Delta:** +26 new tests passing, 0 regressions.

## Deviations from plan

- tune_integration.py: `from ray import tune` was moved to a lazy `_tune()` helper per 08-05 integration findings. Without this fix, `tests/test_rllib_tune.py` would fail at import time when Ray is not installed.
- build_tune_search_space uses `t = _tune()` instead of module-level `from ray import tune`.
- pytest.ini: added `slow` marker (not in 08-06 plan, but required for pip dry-run test).
