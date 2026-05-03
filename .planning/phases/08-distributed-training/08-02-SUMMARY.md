---
status: complete
plan: 08-02
phase: 08-distributed-training
summary: "train_rllib() entrypoint + single-node multi-GPU auto-config"
---

# 08-02 Summary

## What was built

1. **`src/surg_rl/rl/rllib/train.py`**
   - `train_rllib(config, stop_criteria, *, local_mode, log_dir, checkpoint_dir, callbacks) -> str`
     - Registers env, `ray.init()` with resource logging, config build, algorithm build.
     - Training loop: `while timesteps_done < target: result = algo.train()`
     - Checkpoint every `checkpoint_freq` steps + final checkpoint.
     - KeyboardInterrupt → save interrupted checkpoint.
     - `finally`: `algo.stop()`, `ray.shutdown()`.
   - `_resolve_algo_class(algorithm)` → PPO or SAC dispatch.

## Deviations

- `_resolve_algo_class` added as helper since `build_algo()` is not available on RLlib 2.x config objects.

## Tests

| Test | Status |
|------|--------|
| `test_multi_gpu_two_gpus` | PASSED (2 learners, 1 GPU each) |
| `test_single_gpu_local_learner` | PASSED (0 learners, 1 GPU) |
| `test_cpu_only_zero_gpus` | PASSED (0 learners, 0 GPU) |
| `test_train_rllib_rllib_config_builds` | SKIPPED (no ray installed) |
| `test_train_rllib_rllib_sac_builds` | SKIPPED (no ray installed) |
