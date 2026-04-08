# Surg-RL Demos

This directory contains demonstration scripts for the Surg-RL project.

## Demo Scripts

### demo.py - Scene Visualization

Interactive visualization of surgical scenes using MuJoCo or PyBullet.

**Usage:**

```bash
# View with MuJoCo (opens window)
python demos/demo.py --scene scenes/simple_suturing.json

# View with PyBullet (opens window)
python demos/demo.py --scene scenes/simple_suturing.json --backend pybullet

# Headless mode (no window, for testing/CI)
python demos/demo.py --scene scenes/minimal_scene.json --headless --steps 100
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--scene, -s` | Path to scene file | `scenes/simple_suturing.json` |
| `--backend, -b` | Simulator backend (`mujoco` or `pybullet`) | `mujoco` |
| `--headless` | Run without GUI window | `false` |
| `--steps` | Number of simulation steps | `1000` |

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
| `--render, -r` | Render during evaluation | `false` |
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
| `simple_suturing.json` | Basic suturing scene with robot, tissue, needle |
| `laparoscopic_dissection.yaml` | Dual-arm laparoscopic scene |
| `minimal_scene.json` | Minimal scene for testing |

## Troubleshooting

### "Cannot start viewer: no display available"

Run in a terminal with a display, or use `--headless` / `--simulator-only` mode.

### "stable-baselines3 not installed"

Install with: `pip install stable-baselines3`

### Training fails with simulator errors

This can happen if MuJoCo/PyBullet assets are not available. Run `surg-rl setup` to create necessary directories. The simulator uses primitive shapes as fallbacks when mesh files are not present.
