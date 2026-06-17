# Surg-RL Demos

This directory contains demonstration scripts for the Surg-RL project.

## Demo Scripts

### demo.py - Scene Visualization

Interactive RL training + evaluation of surgical scenes. Trains a PPO agent on
the configured scene and runs evaluation episodes.

**Usage:**

```bash
# Quick training run (headless)
python demos/demo.py --headless --steps 10000

# Full PPO training
python demos/demo.py --scene scenes/suturing_demo.json --algo PPO --steps 100000

# Training with curriculum learning
python demos/demo.py --steps 50000 --use-curriculum

# Evaluate only (requires a trained model)
python demos/demo.py --steps 0 --eval-episodes 20

# Open a MuJoCo viewer window during training (requires a display)
python demos/demo.py --render --steps 1000
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--scene, -s` | Path to scene file | `scenes/suturing_demo.json` |
| `--algo, -a` | RL algorithm (`PPO`, `SAC`, `A2C`) | `PPO` |
| `--steps` | Total training timesteps (0 to skip training) | `50000` |
| `--eval-episodes` | Number of evaluation episodes | `5` |
| `--headless` | Run without GUI window | `false` (default headless when no display) |
| `--render` | Open a MuJoCo viewer window during training and the interactive demo | `false` |
| `--max-episode-steps` | Max steps per episode | `2000` |
| `--seed` | Random seed | `42` |
| `--device` | Training device (`auto`, `cpu`, `cuda`, `mps`) | `auto` |
| `--n-envs` | Number of parallel environments | `1` |
| `--use-curriculum` | Enable curriculum learning | `false` |
| `--use-adaptive` | Enable adaptive difficulty | `false` |
| `--log-dir` | Directory for logs and checkpoints | `logs/suturing_demo` |

### train_demo.py - RL Training

Interactive training of RL agents on surgical scenes. Supports PPO, SAC, TD3, DDPG, and A2C algorithms.

**Usage:**

```bash
# Quick training demo (PPO, 10k steps)
python demos/train_demo.py

# Train with SAC for longer
python demos/train_demo.py --algorithm SAC --timesteps 50000

# Train with curriculum learning
python demos/train_demo.py --curriculum

# Train with adaptive difficulty
python demos/train_demo.py --adaptive

# Train on specific scene
python demos/train_demo.py --scene scenes/simple_suturing.json --algorithm PPO --timesteps 100000

# Open a MuJoCo viewer window during training (requires a display)
python demos/train_demo.py --render --timesteps 5000
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--scene, -s` | Path to scene file | `scenes/simple_suturing.json` |
| `--algorithm, -a` | RL algorithm (PPO, SAC, TD3, DDPG, A2C) | `PPO` |
| `--timesteps, -t` | Total training timesteps | `10000` |
| `--lr` | Learning rate | `3e-4` |
| `--batch-size` | Batch size | `64` |
| `--n-envs, -n` | Number of parallel environments | `1` |
| `--seed` | Random seed | `42` |
| `--device` | Training device (auto, cpu, cuda, mps) | `auto` |
| `--log-dir` | Log directory | `logs/training_demo` |
| `--curriculum` | Enable curriculum learning | `false` |
| `--adaptive` | Enable adaptive difficulty | `false` |
| `--max-steps` | Max steps per episode | `500` |
| `--save-freq` | Checkpoint save frequency | `5000` |
| `--render` | Open a MuJoCo viewer window during training | `false` |

### eval_demo.py - Evaluation

Evaluate a trained RL agent and display performance metrics.

**Usage:**

```bash
# Evaluate a trained model
python demos/eval_demo.py --model logs/training/final_model

# Evaluate with rendering
python demos/eval_demo.py --model logs/training/final_model --render

# Evaluate for more episodes
python demos/eval_demo.py --model logs/training/final_model --episodes 50

# Save results to JSON
python demos/eval_demo.py --model logs/training/final_model --save-results results.json
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--model, -m` | Path to trained model (required) | — |
| `--scene, -s` | Path to scene file | `scenes/simple_suturing.json` |
| `--episodes, -e` | Number of evaluation episodes | `10` |
| `--render, -r` | Open a MuJoCo viewer window during evaluation | `false` |
| `--seed` | Random seed | `42` |
| `--save-results` | Save results to JSON file | — |
| `--verbose, -v` | Verbosity level (0, 1, 2) | `1` |

### benchmark.py - Performance Benchmark

Measure environment and simulator throughput, observation/action space sizes, and reset time.

**Usage:**

```bash
# Quick benchmark (default settings)
python demos/benchmark.py

# Benchmark with more episodes/steps
python demos/benchmark.py --episodes 20 --steps-per-episode 500

# Save results to JSON
python demos/benchmark.py --save benchmark_results.json

# Benchmark simulator only
python demos/benchmark.py --simulator-only
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--scene, -s` | Path to scene file | `scenes/simple_suturing.json` |
| `--episodes, -e` | Number of benchmark episodes | `10` |
| `--steps-per-episode` | Max steps per episode | `100` |
| `--seed` | Random seed | `42` |
| `--simulator-only` | Only benchmark simulator (no RL env) | `false` |
| `--backend` | Simulator backend (`mujoco` or `pybullet`) | `mujoco` |
| `--save` | Save results to JSON file | — |

## CLI Commands

The `surg-rl` CLI also provides training and evaluation commands:

```bash
# Train with CLI
surg-rl train --scene scenes/suturing.json --algorithm PPO --timesteps 100000

# Train with curriculum learning
surg-rl train --scene scenes/suturing.json --algorithm SAC --curriculum

# Evaluate trained agent
surg-rl evaluate --scene scenes/suturing.json --model logs/training/final_model
```

## Scene Files

Available scenes in `scenes/`:

| Scene | Description |
|-------|-------------|
| `cutting.json` | Cutting task scene |
| `dissection.json` | Dissection task scene |
| `grasping.json` | Grasping task scene |
| `knot_tying.json` | Knot-tying task scene |
| `laparoscopic_dissection.yaml` | Dual-arm laparoscopic scene |
| `minimal_scene.json` | Minimal scene for testing |
| `needle_insertion.json` | Needle insertion task scene |
| `simple_suturing.json` | Basic suturing scene with robot, tissue, needle |
| `suturing_demo.json` | Multi-stage suturing demo (default for demo.py) |

## Troubleshooting

### "Cannot start viewer: no display available"

Run in a terminal with a display, or omit the `--render` flag (the demos
default to headless). On macOS, the MuJoCo passive viewer requires
`mjpython` instead of plain `python`:

```bash
# On macOS, to open a viewer window
mjpython demos/demo.py --render --steps 1000
mjpython demos/train_demo.py --render --timesteps 5000
mjpython demos/eval_demo.py --model logs/training_demo/final_model --render --episodes 5
```

On Linux/Windows, plain `python` works:

```bash
python demos/demo.py --render --steps 1000
```

**macOS + Apple Silicon + mjpython — known segfault risk.**
If you see `zsh: segmentation fault mjpython demos/demo.py --render`
during training startup, the combination of mjpython's Cocoa-GL
trampoline (which runs the Python interpreter on a non-main Cocoa
thread) + PyTorch's bundled `libomp.dylib` is unstable on Apple
Silicon. The crash signature is:

```
OMP: Error #179: Function pthread_mutex_init failed:
OMP: System error #22: Invalid argument
zsh: segmentation fault
```

The OMP shim (`demos/_omp_compat.py`, imported first by every demo)
works around this by setting `OMP_NUM_THREADS=1`,
`MKL_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1` before any
libomp-linked library is loaded. With the shim in effect, libomp
never enters the problematic pthread_mutex_init path and
`mjpython ... --render` runs to completion regardless of the SB3
device (cpu/cuda/mps/auto). The shim is imported first in every
demo, so the workaround is automatic.

The platform guard (`demos/_platform_guard.py`) detects the
**remaining** case where the shim is somehow not in effect (e.g.
the user wrote a script that imports `mujoco`/`torch` before
importing the shim) and **refuses to launch** with a clear error
message (exit code 2) before constructing the env, so you get an
actionable error instead of a cryptic segfault.

If you somehow still hit the segfault (the shim was bypassed or
its env vars were unset), the workarounds are:

1. **Make sure the shim is in effect.** The demos import
   `demos._omp_compat` first; if you wrote your own script, do the
   same:
   ```python
   import demos._omp_compat  # noqa: F401
   ```
2. **Or set the env vars manually** in your shell:
   ```bash
   export OMP_NUM_THREADS=1
   export MKL_NUM_THREADS=1
   export OPENBLAS_NUM_THREADS=1
   export KMP_DUPLICATE_LIB_OK=TRUE
   mjpython demos/demo.py --render --steps 1000
   ```
3. **Drop `--render` and use plain `python`** — plain Python on
   Apple Silicon does not hit this issue (it doesn't use the
   mjpython trampoline), and the OMP shim's other env var
   (`KMP_DUPLICATE_LIB_OK`) keeps libomp happy:
   ```bash
   python demos/demo.py --headless --steps 1000
   ```
4. **Open the viewer post-training**, not during. Train headless
   with `python` (option 3), then use `mjpython` only for
   `demos/eval_demo.py --render` to render a saved model.

If you are writing your own script that triggers the segfault
reliably, wrap the `TrainingManager.train()` call in
`try/finally` and call `manager.close()` (which calls
`env.close()` → `simulator.stop_viewer()`) in the `finally`. This
ensures the MuJoCo viewer thread is stopped cleanly on every exit
path, including `KeyboardInterrupt` and `SystemExit`.

### "OMP: Error #15: libomp.dylib already initialized"

On macOS, when two copies of OpenMP (one from MuJoCo's bundled
framework, one from the system or from `torch`/`numpy`/MKL) end up
linked into the process, the program aborts with `zsh: abort`.

The demos handle this automatically: every demo `import`s the
`demos/_omp_compat.py` shim as its very first import, which sets
`KMP_DUPLICATE_LIB_OK=TRUE` in the environment *before* `mujoco` or
`torch` is loaded. This is the documented (unsafe but supported)
workaround for the duplicate-runtime crash.

If you write your own script that imports `surg_rl`, do the same:

```python
# First import — must be before mujoco/torch/numpy
import sys; sys.path.insert(0, "demos")
import _omp_compat  # noqa: F401

# Then the rest
from surg_rl.rl.environment import SurgicalEnv
# ...
```

### "stable-baselines3 not installed"

Install with: `pip install stable-baselines3`

### Training fails with simulator errors

This can happen if MuJoCo/PyBullet assets are not available. Run `surg-rl setup` to create necessary directories. The simulator uses primitive shapes as fallbacks when mesh files are not present.
