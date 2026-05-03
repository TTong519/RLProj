# Phase 8: Distributed Training with Ray/RLlib - Research

**Researched:** 2026-05-02
**Domain:** Distributed RL training with Ray RLlib 2.55+ on a Gymnasium surgical environment
**Confidence:** MEDIUM

## Summary

Phase 8 adds distributed training support to the surg-rl project via Ray RLlib. The current training stack (Stable-Baselines3, single-node CPU/GPU, Dummy/SubprocVecEnv) must remain untouched while a parallel RLlib training path is introduced.

The primary challenge is gymnasium version alignment: the project currently uses gymnasium 1.2.3, while RLlib 2.55.1 also depends on gymnasium 1.2.2 (as of the latest dry-run). There is no known conflict, but the version must be verified during installation.

Key integration points:
1. `SurgicalEnv` must accept a `config` dict for RLlib's env-creator pattern.
2. `surg_rl.rl.rllib` module must provide `train_rllib(config)` that maps the existing `TrainingConfig`/`AlgorithmConfig` into RLlib's `PPOConfig`/`SACConfig` and runs `config.build_algo().train()`.
3. Multi-GPU on a single node should use `config.learners(num_learners=N, num_gpus_per_learner=1)` with `ray.init()` auto-detecting the local cluster.
4. Ray Tune integration requires wrapping `train_rllib()` as a `tune.Tuner` trainable, exposing search-space dimensions (scene definitions, reward weights, learning rate, etc.).
5. Checkpoint compatibility between SB3 and RLlib is **not automatic**; RLlib checkpoints are directory-based (`Checkpointable` API with `metadata.json`, `state.pkl`, `class_and_ctor_args.pkl`), while SB3 checkpoints are single `.zip` files with PyTorch `state_dict`. The requirement asks for an *inspection* utility and a *documented migration path*, not a universal converter.

**Primary recommendation:** Use RLlib's new API stack (default since Ray 2.10+), register `SurgicalEnv` via `tune.register_env`, build `PPOConfig` with `env_runners(num_env_runners=...)` and `learners(num_gpus_per_learner=...)`, and keep all Ray/RLlib code behind an optional `[distributed]` extra.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Environment registration (RLlib) | API / Backend | — | `register_env` lives in the RLlib config layer; no browser/client involvement |
| Single-node multi-GPU training | API / Backend | — | `LearnerGroup` + `ray.init()` are backend compute |
| Hyperparameter search (Tune) | API / Backend | — | `tune.Tuner` orchestrates trials on the Ray cluster |
| Checkpoint inspection / migration | API / Backend | — | Utility functions that read both checkpoint formats |
| SB3 training preservation | API / Backend | — | Existing `TrainingManager` stays unchanged; parallel path only |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ray[rllib]` | `>=2.10` (latest verified 2.55.1) | Distributed RL framework, PPO/SAC/DQN algorithms | Industry standard for scalable RL; new API stack simplifies multi-GPU |
| `gymnasium` | `>=0.29.0` (project already on 1.2.3; RLlib resolves to 1.2.2) | Environment API | Both SB3 and RLlib require gymnasium; Farama standard |
| `torch` | `>=2.0.0` | Deep-learning backend for RLlib learners | RLlib new stack is PyTorch-only; project already uses torch for vision extra |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tune-sklearn` | latest (dry-run resolves via `ray[tune]`) | Hyperparameter search integration with scikit-learn-style APIs | Required by DIST-06; not directly used if we use raw `ray.tune` |
| `tensorboardX` | resolved by `ray[rllib]` | Metrics logging for RLlib | RLlib already pulls this in; optional explicit dep if needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ray[rllib]` | `cleanrl` + `torch.distributed` | CleanRL is lightweight but lacks built-in distributed env sampling, hyperparameter tuning, and checkpointing. RLlib is the right choice for the project's scale goals. |
| `tune-sklearn` | `optuna` + `ray` | `optuna` is excellent, but `tune-sklearn` is explicitly required by DIST-06. Keep it as an optional dependency even if we primarily use `ray.tune` directly. |

**Installation:**
```bash
pip install "ray[rllib]>=2.10" "torch>=2.0.0" "tune-sklearn"
```

**Version verification:**
- `ray` latest on PyPI: **2.55.1** (published 2025-ish) — verified via `pip index versions ray`.
- `gymnasium` project version: **1.2.3**; `ray[rllib]` resolves to **1.2.2** — no conflict detected in dry-run (`pip install --dry-run`), but this must be re-verified on the target machine.

## Architecture Patterns

### System Architecture Diagram

```
User CLI / Script
       |
       v
+-------------------+
|  TrainingConfig   |
|  (dataclass)      |
|  SB3 path OR      |
|  RLlib path       |
+---------+---------+
          |
    +-----+-----+
    |           |
    v           v
+--------+  +------------------+
|Training|  |  RllibConfig     |
|Manager |  |  (converter)     |
|(SB3)   |  +--------+---------+
+--------+           |
                     v
            +------------------+
            | ray.init()       |
            | (auto-detect)    |
            +--------+---------+
                     |
        +------------+------------+
        |                         |
        v                         v
+---------------+      +------------------+
| EnvRunner     |      | LearnerGroup     |
| (sample       |      | (multi-GPU DDP)  |
|  collection)  |      +--------+---------+
+---------------+               |
        |                       v
        |              +--------+---------+
        |              | PPO / SAC algo   |
        |              | .train() loop    |
        |              +------------------+
        |
        v
+------------------+
| SurgicalEnv      |
| (gymnasium.Env)  |
| registered via   |
| tune.register_env|
+------------------+
        |
        v
+------------------+
| MuJoCo / PyBullet|
| Simulator        |
+------------------+
```

### Recommended Project Structure

```
src/surg_rl/rl/
├── environment.py           # Existing SurgicalEnv + SurgicalEnvConfig
├── training.py              # Existing TrainingManager (SB3 path)
├── callbacks.py             # Existing SB3 callbacks
├── rllib/
│   ├── __init__.py          # exports train_rllib, RllibConfig
│   ├── config.py            # RllibConfig dataclass (maps TrainingConfig -> RLlib)
│   ├── env_wrapper.py       # env_creator factory + register_env("surg-rl", ...)
│   ├── train.py             # train_rllib(config) entrypoint
│   ├── checkpoint_utils.py  # inspect_rllib_checkpoint, compare_with_sb3
│   └── tune_integration.py  # build_tune_search_space, run_tune_experiment
```

### Pattern 1: Registering `SurgicalEnv` with RLlib
**What:** `SurgicalEnv` currently accepts `SurgicalEnvConfig` in its constructor. RLlib requires a `config` dict (which may be `None`). We wrap construction in an `env_creator` function and register it with `ray.tune.registry.register_env`.

**When to use:** Required for DIST-01. Always use Tune registration (not gymnasium registry) because Ray's distributed actors cannot access the local gymnasium registry.

**Example:**
```python
# Source: https://docs.ray.io/en/latest/rllib/rllib-env.html
from ray.tune.registry import register_env
from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

def env_creator(env_config: dict | None):
    env_config = env_config or {}
    # Convert dict -> SurgicalEnvConfig dataclass
    cfg = SurgicalEnvConfig(**env_config)
    return SurgicalEnv(cfg)

register_env("surg-rl", env_creator)
```

### Pattern 2: Single-Node Multi-GPU Configuration
**What:** On the new API stack, GPU allocation is done via `config.learners(num_learners=N, num_gpus_per_learner=1)`. `ray.init()` auto-detects local GPUs; no manual cluster setup is needed.

**When to use:** Required for DIST-03. Use `num_learners = num_gpus` on a single node. If only 1 GPU is present, use `num_learners=0, num_gpus_per_learner=1` (local learner on the main process) for better throughput.

**Example:**
```python
# Source: https://docs.ray.io/en/latest/rllib/scaling-guide.html
from ray.rllib.algorithms.ppo import PPOConfig
import ray

ray.init()

config = (
    PPOConfig()
    .environment("surg-rl")
    .framework("torch")
    .env_runners(num_env_runners=4)
    .learners(num_learners=2, num_gpus_per_learner=1)  # 2 GPUs
    .training(
        lr=3e-4,
        gamma=0.99,
        lambda_=0.95,
        clip_param=0.2,
        train_batch_size_per_learner=4000,
        num_epochs=10,
    )
)

algo = config.build_algo()
```

### Pattern 3: Ray Tune Search Space over Scene Definitions & Reward Weights
**What:** `tune.Tuner` accepts an RLlib `AlgorithmConfig` as its `param_space`. Any field inside `.training(...)` or `.environment(...)` can be a `tune` distribution object. For scene definitions, pass a `tune.choice([scene_path_1, scene_path_2])` into `env_config={"scene_path": tune.choice(...)}`.

**When to use:** Required for DIST-04. Use `tune.choice` for categorical scene files, `tune.uniform` / `tune.loguniform` for reward weights and learning rates.

**Example:**
```python
# Source: https://docs.ray.io/en/latest/tune/examples/pbt_ppo_example.html
from ray import tune
from ray.rllib.algorithms.ppo import PPOConfig

config = (
    PPOConfig()
    .environment(
        "surg-rl",
        env_config={
            "scene_path": tune.choice([
                "scenes/simple_suturing.json",
                "scenes/complex_suturing.json",
                "scenes/needle_passing.json",
            ]),
            "reward_config": {
                "distance_weight": tune.loguniform(1e-2, 1.0),
                "success_bonus": tune.uniform(10.0, 100.0),
            },
        },
    )
    .training(
        lr=tune.loguniform(1e-5, 1e-3),
        clip_param=tune.uniform(0.05, 0.3),
    )
)

tuner = tune.Tuner(
    config.algo_class,
    param_space=config,
    tune_config=tune.TuneConfig(
        metric="env_runners/episode_return_mean",
        mode="max",
        num_samples=3,
    ),
    run_config=tune.RunConfig(stop={"training_iteration": 10}),
)
results = tuner.fit()
```

### Pattern 4: Checkpoint Save / Restore & Inspection
**What:** RLlib uses `Checkpointable.save_to_path()` and `Algorithm.from_checkpoint()`. The checkpoint is a directory, not a file. SB3 uses `model.save("path.zip")` (a zip with PyTorch state_dict + metadata).

**When to use:** Required for DIST-05. Provide a utility that:
1. Loads an RLlib checkpoint via `Algorithm.from_checkpoint(dir)`.
2. Extracts the `RLModule` state dict (`rl_module.get_state()`).
3. Compares layer shapes with an SB3 model loaded via `PPO.load("path.zip")`.
4. Documents that a full weight transfer is possible only by manual layer-name mapping (not automated), because SB3 and RLlib use different internal network architectures (SB3 `MlpExtractor` vs RLlib `RLModule`).

**Example:**
```python
# Source: https://docs.ray.io/en/latest/rllib/checkpoints.html
from ray.rllib.algorithms.algorithm import Algorithm
from ray.rllib.core.rl_module.rl_module import RLModule
from pathlib import Path

# Save
algo.save_to_path("/tmp/rllib_ckpt")

# Restore full algorithm
new_algo = Algorithm.from_checkpoint("/tmp/rllib_ckpt")

# Extract bare RLModule for inference / shape inspection
rl_module = RLModule.from_checkpoint(
    Path("/tmp/rllib_ckpt") / "learner_group" / "learner" / "rl_module" / "default_policy"
)
state_dict = rl_module.get_state()
for k, v in state_dict.items():
    print(k, v.shape)
```

### Anti-Patterns to Avoid
- **Using `gymnasium.register` instead of `tune.register_env`:** Ray's distributed actors cannot see the local gymnasium registry. Always use `ray.tune.registry.register_env`. [CITED: docs.ray.io/rllib-env]
- **Mutating `self` in a Pydantic `model_validator(mode="after")`:** The project's `AGENTS.md` already warns about this. If any RLlib integration touches Pydantic models (e.g., for config validation), always use `self.model_copy(update={...})`. [CITED: AGENTS.md]
- **Setting `num_gpus` on the old API stack:** The new API stack deprecates `config.resources(num_gpus=...)` in favor of `config.learners(num_gpus_per_learner=...)`. Using the old setting may trigger deprecation warnings or unexpected behavior on Ray >=2.40. [CITED: docs.ray.io/new-api-stack-migration-guide]
- **Running `ray.init()` inside the env constructor:** This can deadlock or create nested clusters. Initialize Ray once in the `train_rllib()` entrypoint before building the algorithm. [ASSUMED]
- **Serializing `SceneDefinition` Pydantic objects directly into `env_config`:** `env_config` is passed to Ray actors and must be JSON-serializable (dicts, lists, primitives). Convert `SceneDefinition` to `model_dump()` dicts or pass file paths only. [CITED: docs.ray.io/ray-core/handling-dependencies]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Distributed vectorized env sampling | Custom multiprocessing pool | `config.env_runners(num_env_runners=N)` + `config.env_runners(num_envs_per_env_runner=M)` | RLlib handles actor placement, fault tolerance, and batching automatically |
| Multi-GPU data-parallel training | Manual `torch.nn.parallel.DistributedDataParallel` | `config.learners(num_learners=N, num_gpus_per_learner=1)` | RLlib manages gradient aggregation, checkpointing, and learner fault tolerance |
| Hyperparameter search orchestration | Grid-search loops in Python | `ray.tune.Tuner` with `ASHAScheduler` or `PopulationBasedTraining` | Tune handles trial scheduling, early stopping, and result aggregation at scale |
| Checkpoint versioning & compatibility | Custom pickle schema | `Checkpointable.save_to_path()` / `from_checkpoint()` | RLlib guarantees backward compatibility for checkpoints created since Ray 2.40 |
| Environment-to-model observation preprocessing | Custom flatten/unflatten logic inside `SurgicalEnv` | `ConnectorV2` pipelines (env_to_module, module_to_env) | RLlib's new stack encourages connectors for normalization, frame-stacking, etc. |

**Key insight:** RLlib's value is not the algorithm implementations (which are well-known), but the distributed systems plumbing (env sampling, learner DDP, fault tolerance, checkpointing, hyperparameter search). Hand-rolling any of these is a months-long effort with high bug density.

## Runtime State Inventory

> Phase 8 is a greenfield addition (new module `surg_rl.rl.rllib`) with no rename/refactor/migration of existing runtime state. Omitting Runtime State Inventory per instructions.

## Common Pitfalls

### Pitfall 1: Gymnasium Version Mismatch
**What goes wrong:** `ray[rllib]` currently resolves `gymnasium==1.2.2`, while the project already has `gymnasium==1.2.3`. In some edge cases, pip may downgrade or fail with a conflict.
**Why it happens:** RLlib pins a slightly older gymnasium in its dependency tree.
**How to avoid:** Test `pip install "ray[rllib]>=2.10"` in a fresh venv. If a conflict arises, relax the project's gymnasium pin to `>=0.29.0,<2.0.0` (already the case). The dry-run on 2026-05-02 showed no conflict.
**Warning signs:** `pip` outputs `ERROR: Cannot install gymnasium==1.2.3 and ray[rllib]==2.55.1 because these package versions have conflicting dependencies`.

### Pitfall 2: `SurgicalEnv` Constructor Signature Incompatibility
**What goes wrong:** RLlib expects `MyEnv(config)` where `config` is a single dict (or None). `SurgicalEnv` currently takes `config: SurgicalEnvConfig | None` and `render_mode: str | None` as separate positional/keyword args. Passing the RLlib `env_config` dict directly to `SurgicalEnv(**env_config)` will fail because `SurgicalEnv` expects a `SurgicalEnvConfig` dataclass, not a raw dict.
**Why it happens:** RLlib calls `env_creator(env_config)` and then `MyEnv(config)` or `gym.make(id, **env_config)`. Our `env_creator` must perform the dict-to-dataclass conversion.
**How to avoid:** Always provide an `env_creator` wrapper that unpacks the dict into `SurgicalEnvConfig(**env_config)` and then calls `SurgicalEnv(cfg)`. Do NOT pass the raw dict straight into `SurgicalEnv`.
**Warning signs:** `TypeError: SurgicalEnv.__init__() got an unexpected keyword argument 'scene_path'` during RLlib worker initialization.

### Pitfall 3: Ray Not Initialized Before Building Algorithm
**What goes wrong:** Calling `config.build_algo()` without `ray.init()` raises `RayNotInitialized` or hangs indefinitely.
**Why it happens:** RLlib requires a Ray runtime even for single-process local mode.
**How to avoid:** Ensure `train_rllib()` calls `ray.init()` (or `ray.init("auto")`) at the top. For unit tests, use `ray.init(local_mode=True)` or `ray.init(num_cpus=2, num_gpus=0)` and call `ray.shutdown()` in a teardown fixture.
**Warning signs:** `RuntimeError: Maybe you called ray.init twice by accident?` or indefinite hang on `build_algo()`.

### Pitfall 4: Multi-GPU Hang on macOS / Single-GPU Machines
**What goes wrong:** Setting `num_learners=2, num_gpus_per_learner=1` on a machine with 0 or 1 GPU causes the experiment to stall because Ray cannot fulfill the resource request.
**Why it happens:** Ray's scheduler waits for resources that do not exist (unless autoscaling is enabled).
**How to avoid:** Detect GPU count with `torch.cuda.device_count()` (or the project's existing `detect_backends()`) before configuring learners. If `num_gpus < 2`, fall back to `num_learners=0, num_gpus_per_learner=1` (local learner) or `num_learners=1, num_gpus_per_learner=0` (CPU).
**Warning signs:** `WARNING: The number of GPUs per learner is set to 1, but only 0 GPUs are available.` or experiment hangs with no training iterations.

### Pitfall 5: PyBullet GUI / MuJoCo RenderThread Crashes in Ray Workers
**What goes wrong:** Phase 7 added `RenderThread` and eager viewer start for `render_mode="human"`. When RLlib spawns `EnvRunner` actors (subprocesses), GUI windows or Metal/OpenGL contexts may crash or deadlock.
**Why it happens:** Display/GPU contexts are often not available in Ray worker processes, especially on headless nodes or macOS.
**How to avoid:** Force `render_mode=None` inside the `env_creator` used for RLlib training. Keep rendering only for evaluation or local SB3 training. The `env_creator` should strip `render_mode` from the config before constructing `SurgicalEnv`.
**Warning signs:** `RuntimeError: Human render unavailable` repeated in worker logs, or segfaults inside `start_viewer()`.

### Pitfall 6: `tune-sklearn` Redundancy
**What goes wrong:** DIST-06 explicitly lists `tune-sklearn` as a dependency. If we only use raw `ray.tune` (which is already included in `ray[rllib]`), adding `tune-sklearn` may pull in extra packages (e.g., `scikit-learn` is already present, but `ray[tune]` is also pulled) with no functional benefit.
**Why it happens:** `tune-sklearn` is a thin wrapper around `ray.tune` for sklearn-style APIs. Our integration uses RLlib's native Tune API.
**How to avoid:** Include `tune-sklearn` in `[distributed]` extras as required by DIST-06, but document that it is optional and primarily for future sklearn-based hyperparameter search. Do not build core logic around it.
**Warning signs:** Unnecessary dependency bloat, but no runtime errors.

## Code Examples

### Verified patterns from official sources

#### Custom env creator with dict-to-dataclass conversion
```python
# Source: https://docs.ray.io/en/latest/rllib/rllib-env.html
from ray.tune.registry import register_env
from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

def make_surgical_env(env_config: dict | None = None):
    env_config = env_config or {}
    # RLlib passes a dict; convert to dataclass
    cfg = SurgicalEnvConfig(**env_config)
    # Force headless in distributed workers
    cfg.render_mode = None
    return SurgicalEnv(cfg)

register_env("surg-rl", make_surgical_env)
```

#### Minimal PPO training loop (new API stack)
```python
# Source: https://docs.ray.io/en/latest/rllib/getting-started.html
import ray
from ray.rllib.algorithms.ppo import PPOConfig

ray.init()

config = (
    PPOConfig()
    .environment("surg-rl")
    .framework("torch")
    .env_runners(num_env_runners=2)
    .learners(num_gpus_per_learner=0)  # CPU-only for smoke test
    .training(
        lr=3e-4,
        gamma=0.99,
        train_batch_size_per_learner=4000,
        num_epochs=10,
    )
)

algo = config.build_algo()
for i in range(10):
    result = algo.train()
    print(f"Iter {i}: reward={result['env_runners']['episode_return_mean']:.2f}")

checkpoint_dir = algo.save_to_path("/tmp/rllib_ckpt")
ray.shutdown()
```

#### Ray Tune + RLlib with scene search space
```python
# Source: https://docs.ray.io/en/latest/tune/examples/pbt_ppo_example.html
from ray import tune
from ray.rllib.algorithms.ppo import PPOConfig

config = (
    PPOConfig()
    .environment(
        "surg-rl",
        env_config={
            "scene_path": tune.choice([
                "scenes/simple_suturing.json",
                "scenes/needle_passing.json",
            ]),
            "simulator_type": tune.choice(["mujoco", "pybullet"]),
        },
    )
    .training(
        lr=tune.loguniform(1e-5, 1e-3),
        clip_param=tune.uniform(0.05, 0.3),
    )
)

tuner = tune.Tuner(
    config.algo_class,
    param_space=config,
    tune_config=tune.TuneConfig(
        metric="env_runners/episode_return_mean",
        mode="max",
        num_samples=3,
    ),
    run_config=tune.RunConfig(stop={"training_iteration": 10}),
)
results = tuner.fit()
```

#### Checkpoint shape inspection (RLModule)
```python
# Source: https://docs.ray.io/en/latest/rllib/checkpoints.html
from pathlib import Path
from ray.rllib.core.rl_module.rl_module import RLModule
import torch

rl_module = RLModule.from_checkpoint(
    Path(checkpoint_dir) / "learner_group" / "learner" / "rl_module" / "default_policy"
)
state = rl_module.get_state()
for name, param in state.items():
    if isinstance(param, torch.Tensor):
        print(name, param.shape)
```

## Compatibility Notes

### SB3 vs RLlib Checkpoint Formats
- **SB3:** `PPO.save("model.zip")` → zip containing `policy.pth` (PyTorch state_dict), `hyperparameters.pkl`, `observation_space.pkl`, `action_space.pkl`.
- **RLlib:** `algo.save_to_path("dir/")` → directory tree with `metadata.json`, `class_and_ctor_args.pkl`, `state.pkl` (or `state.msgpack`), plus subdirectories for `learner_group/`, `env_runner/`.
- **Interop:** There is no built-in converter. The shapes of the policy network can be inspected and compared, but weight transfer requires manual mapping of layer names (SB3 `MlpExtractor` vs RLlib default `RLModule`). For DIST-05, implement a utility that loads both checkpoints, prints layer shapes, and documents the manual mapping steps rather than promising automatic conversion.

### Gymnasium API Compliance
- RLlib officially supports **gymnasium >= 1.0.0** on the new API stack.
- `SurgicalEnv` already follows the `reset(seed, options) -> (obs, info)` and `step(action) -> (obs, reward, terminated, truncated, info)` signatures.
- No migration needed for the environment itself, only for the constructor wrapper.

### Python Version
- Ray 2.55.1 supports Python 3.9–3.12. The project's `pyproject.toml` specifies `requires-python = ">=3.10"`.
- **Risk:** If the target runtime is Python 3.13 (current active interpreter is 3.13.3), Ray 2.55.1 may not have official wheels. The dry-run succeeded, but installation from source may be required on 3.13.
- **Mitigation:** Pin the `[distributed]` extra to `ray[rllib]>=2.10` and test on the CI Python version. If 3.13 wheels are missing, document that Python 3.10–3.12 are recommended for distributed training.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Old API stack (`Policy`, `ModelV2`, `RolloutWorker`) | New API stack (`RLModule`, `Learner`, `EnvRunner`, `ConnectorV2`) | Ray 2.10+ (default since ~2.40) | Simpler classes, PyTorch-only, cleaner multi-GPU |
| `config.resources(num_gpus=...)` | `config.learners(num_gpus_per_learner=...)` | Ray 2.40+ | Finer-grained resource control, DDP across learners |
| `train_batch_size` global | `train_batch_size_per_learner` per learner | Ray 2.40+ | Scales without changing batch size when adding GPUs |
| gymnasium 0.29 | gymnasium 1.2.x | 2024 | API is stable; mostly internal refactoring |

**Deprecated/outdated:**
- `AlgorithmConfig.framework("tf2")`: TensorFlow support is rudimentary on the new stack; use `"torch"`. [CITED: docs.ray.io/new-api-stack-migration-guide]
- `config.resources(num_gpus=...)`: Deprecated in favor of `config.learners(num_gpus_per_learner=...)`. [CITED: docs.ray.io/new-api-stack-migration-guide]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ray[rllib]>=2.10` installs cleanly alongside the project's existing dependencies (gymnasium 1.2.3, stable-baselines3 2.x, numpy 1.24+, pydantic 2.x) | Standard Stack | Installation fails on CI or user machines, blocking Phase 8. Verified by dry-run on 2026-05-02, but dry-run does not guarantee real install on all platforms. |
| A2 | Python 3.13 is supported by Ray 2.55.1 wheels | Standard Stack | If no wheels exist, users must build Ray from source (slow, requires Bazel). Dry-run on Python 3.13.3 succeeded, but actual compilation may differ. |
| A3 | `SurgicalEnv` spaces (observation_space, action_space) are picklable and therefore safe to serialize across Ray actors | Architecture Patterns | If spaces contain non-picklable objects (e.g., lambdas), RLlib worker startup will fail. `gymnasium.spaces` are generally picklable; surgical env's custom spaces should be verified. |
| A4 | MuJoCo/PyBullet simulators are safe to instantiate inside Ray worker processes (no global state / display conflicts) | Architecture Patterns | If simulators register global OpenGL contexts or static state, multiple workers on the same node may crash. Phase 7's `RenderThread` and GUI mode must be disabled in RLlib envs. |
| A5 | A documented checkpoint migration path (layer shape inspection + manual mapping) satisfies DIST-05; full automated conversion is not required | Compatibility Notes | If the requirement is interpreted as "fully automatic conversion", the current plan is insufficient. The wording "or documented migration path exists" supports the assumption. |

## Open Questions

1. **Does the target CI/user environment run Python 3.13?**
   - What we know: The active interpreter in this session is Python 3.13.3. Ray 2.55.1 dry-run succeeded.
   - What's unclear: Whether official `cp313` wheels exist on PyPI for all platforms (macOS arm64, Linux x86_64).
   - Recommendation: Test `pip install "ray[rllib]>=2.10"` on the CI image before committing the dependency. If wheels are missing, bump `[distributed]` docs to recommend Python 3.10–3.12.

2. **Should `tune-sklearn` be a hard dependency or optional within `[distributed]`?**
   - What we know: DIST-06 explicitly requires `tune-sklearn` in the `[distributed]` extra.
   - What's unclear: Whether `tune-sklearn` pulls any heavy or conflicting dependencies.
   - Recommendation: Include it as specified. It is lightweight (wraps `ray.tune` + `scikit-learn`).

3. **How should `SurgicalEnvConfig` be serialized into `env_config` for RLlib?**
   - What we know: `SurgicalEnvConfig` is a dataclass with nested Pydantic objects (`RewardConfig`, `ObservationConfig`, `ActionConfig`).
   - What's unclear: Whether `dataclasses.asdict()` or `pydantic.BaseModel.model_dump()` produces JSON-safe dicts for all nested fields.
   - Recommendation: Write a converter `surgical_env_config_to_dict(config: SurgicalEnvConfig) -> dict` that explicitly converts enums to strings and drops `None` fields. Test round-trip serialization in a unit test.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core | ✓ | 3.13.3 | Use 3.10–3.12 if Ray wheels missing |
| `ray[rllib]` | DIST-01..06 | ✗ (not installed) | 2.55.1 (latest) | Install via `[distributed]` extra |
| `torch` | RLlib backend | ✓ (vision extra) | 2.x | Required anyway for RLlib new stack |
| `gymnasium` | Both SB3 & RLlib | ✓ | 1.2.3 | RLlib resolves 1.2.2; no conflict expected |
| `stable-baselines3` | Existing training | ✓ | >=2.0.0 | Must remain untouched |
| CUDA / GPUs | DIST-03 | ? | — | Fall back to CPU-only (`num_gpus_per_learner=0`) |
| `tune-sklearn` | DIST-06 | ✗ (not installed) | latest | Install via `[distributed]` extra |

**Missing dependencies with no fallback:**
- `ray[rllib]` and `tune-sklearn` are missing but have a clear install path via `pip install "surg-rl[distributed]"`.

**Missing dependencies with fallback:**
- GPUs: If no CUDA GPUs are present, RLlib falls back to CPU training automatically when `num_gpus_per_learner=0`.

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json`. This section is included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `PYTHONPATH=src pytest tests/test_rllib_smoke.py -x -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | `SurgicalEnv` registered with RLlib, env_config accepted | unit | `pytest tests/test_rllib_env_registration.py -x` | ❌ Wave 0 |
| DIST-02 | `train_rllib()` runs PPO for 10 iterations without crash | smoke/integration | `pytest tests/test_rllib_train.py -x` | ❌ Wave 0 |
| DIST-03 | Multi-GPU config builds without resource errors | unit | `pytest tests/test_rllib_gpu_config.py -x` | ❌ Wave 0 |
| DIST-04 | Tune search space produces 3+ trial variants | smoke | `pytest tests/test_rllib_tune.py -x` | ❌ Wave 0 |
| DIST-05 | Checkpoint inspection utility prints shapes | unit | `pytest tests/test_rllib_checkpoint.py -x` | ❌ Wave 0 |
| DIST-06 | `pip install "surg-rl[distributed]"` resolves | integration | Manual / CI install step | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src pytest tests/test_rllib_smoke.py -x`
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_rllib_env_registration.py` — covers DIST-01
- [ ] `tests/test_rllib_train.py` — covers DIST-02
- [ ] `tests/test_rllib_gpu_config.py` — covers DIST-03 (GPU-mock via `ray.init(num_gpus=2)`)
- [ ] `tests/test_rllib_tune.py` — covers DIST-04
- [ ] `tests/test_rllib_checkpoint.py` — covers DIST-05
- [ ] `tests/conftest.py` — add `ray_init_shutdown` fixture
- [ ] Install `ray[rllib]` in CI or local dev environment before running tests

## Security Domain

> `security_enforcement` is not explicitly set to `false` in `.planning/config.json`, so this section is included. However, Phase 8 is primarily a training infrastructure layer with minimal external attack surface.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Validate `env_config` dict before passing to `SurgicalEnvConfig` to prevent unexpected constructor args |
| V6 Cryptography | no | — |

### Known Threat Patterns for Ray/RLlib Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arbitrary code execution via `env_config` | Execution | Validate all keys against `SurgicalEnvConfig` fields; reject unknown keys |
| Resource exhaustion via high `num_env_runners` | Denial of Service | Cap `num_env_runners` and `num_learners` in `RllibConfig` validation |
| Checkpoint path traversal | Tampering | Use `pathlib.Path.resolve()` and validate that checkpoint paths are within expected directories |

## Sources

### Primary (HIGH confidence)
- Context7 `/ray-project/ray` — topics: "register custom gymnasium environment env_config RLlib", "RLlib PPO multi GPU single node num_gpus_per_worker", "Ray Tune search space hyperparameter RLlib", "RLlib checkpoint save restore algorithm", "RLlib gymnasium compatibility gym version", "PPOConfig environment env_config API", "RLlib AlgorithmConfig resources num_gpus num_cpus", "PPOConfig env_config env_runners num_gpus API reference"
- Official docs: https://docs.ray.io/en/latest/rllib/rllib-env.html — environment registration rules
- Official docs: https://docs.ray.io/en/latest/rllib/scaling-guide.html — multi-GPU configuration
- Official docs: https://docs.ray.io/en/latest/rllib/checkpoints.html — checkpoint structure and API
- Official docs: https://docs.ray.io/en/latest/rllib/new-api-stack-migration-guide.html — deprecation of old API stack settings
- Official docs: https://docs.ray.io/en/latest/rllib/getting-started.html — end-to-end Python API
- Official docs: https://docs.ray.io/en/latest/tune/examples/pbt_ppo_example.html — Tune + RLlib integration

### Secondary (MEDIUM confidence)
- `pip install --dry-run` output on 2026-05-02 verifying dependency resolution for `ray[rllib]>=2.10` against gymnasium 1.2.3
- PyPI version list for `ray` (2.55.1 latest) via `pip index versions ray`

### Tertiary (LOW confidence)
- Python 3.13 wheel availability for Ray 2.55.1 — dry-run succeeded but no explicit verification of `cp313-manylinux` / `cp313-macosx` wheel filenames on PyPI
- Whether `tune-sklearn` introduces any version conflicts — not deeply investigated beyond dry-run

## Metadata

**Confidence breakdown:**
- Standard stack: **MEDIUM** — Ray versions are verified, but gymnasium 1.2.2 vs 1.2.3 alignment and Python 3.13 wheel availability are assumptions.
- Architecture: **HIGH** — Official RLlib docs provide clear patterns for env registration, multi-GPU, and Tune integration.
- Pitfalls: **HIGH** — Each pitfall is drawn from documented RLlib behavior and project-specific constraints (Phase 7 rendering, Pydantic quirks from AGENTS.md).

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (Ray releases monthly; recheck if Ray 2.60+ changes API)
