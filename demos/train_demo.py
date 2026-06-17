#!/usr/bin/env python3
"""Interactive RL training demo for Surg-RL.

This demo shows how to train an RL agent on a surgical scene using
the Surg-RL training pipeline. It supports multiple algorithms,
curriculum learning, and adaptive difficulty.

Usage:
    # Quick training demo (PPO, 10k steps)
    python demos/train_demo.py

    # Train with SAC for longer
    python demos/train_demo.py --algorithm SAC --timesteps 50000

    # Train with curriculum learning
    python demos/train_demo.py --curriculum

    # Train with adaptive difficulty
    python demos/train_demo.py --adaptive
"""

# IMPORTANT: must be the first import — see _omp_compat docstring.
# The shim lives in this demos/ directory; insert it onto sys.path
# so the import resolves regardless of where the user invokes from.
# fmt: off
import sys as _omp_sys
from pathlib import Path as _omp_Path
_omp_sys.path.insert(0, str(_omp_Path(__file__).resolve().parent))
import _omp_compat  # noqa: F401, E402
import _platform_guard  # noqa: F401, E402
# fmt: on

import argparse
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    parser = argparse.ArgumentParser(
        description="Interactive RL training demo for Surg-RL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scene", "-s", type=str,
        default="scenes/simple_suturing.json",
        help="Path to scene file",
    )
    parser.add_argument(
        "--algorithm", "-a", type=str, default="PPO",
        choices=["PPO", "SAC", "TD3", "DDPG", "A2C"],
        help="RL algorithm (default: PPO)",
    )
    parser.add_argument(
        "--timesteps", "-t", type=int, default=10000,
        help="Total training timesteps (default: 10000)",
    )
    parser.add_argument(
        "--lr", type=float, default=3e-4,
        help="Learning rate (default: 3e-4)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=64,
        help="Batch size (default: 64)",
    )
    parser.add_argument(
        "--n-envs", "-n", type=int, default=1,
        help="Number of parallel environments (default: 1)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--device", type=str, default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="Training device (default: auto)",
    )
    parser.add_argument(
        "--log-dir", type=str, default="logs/training_demo",
        help="Log directory (default: logs/training_demo)",
    )
    parser.add_argument(
        "--curriculum", action="store_true",
        help="Enable curriculum learning",
    )
    parser.add_argument(
        "--adaptive", action="store_true",
        help="Enable adaptive difficulty",
    )
    parser.add_argument(
        "--max-steps", type=int, default=500,
        help="Max steps per episode (default: 500)",
    )
    parser.add_argument(
        "--save-freq", type=int, default=5000,
        help="Checkpoint save frequency (default: 5000)",
    )
    parser.add_argument(
        "--render", action="store_true",
        help="Open a MuJoCo viewer window during training (requires a display; "
        "on macOS run with mjpython)",
    )
    args = parser.parse_args()

    # Refuse the known-unstable mjpython+AppleSilicon+--render combination.
    if args.render and _platform_guard.is_risky_render_combination(device=args.device):
        print(_platform_guard.format_risky_render_message(), file=sys.stderr)
        sys.exit(2)

    # Banner
    print("=" * 60)
    print("  Surg-RL Training Demo")
    print("=" * 60)
    print(f"  Scene:      {args.scene}")
    print(f"  Algorithm:  {args.algorithm}")
    print(f"  Timesteps:  {args.timesteps:,}")
    print(f"  Seed:       {args.seed}")
    print(f"  Device:     {args.device}")
    if args.curriculum:
        print("  Curriculum: ON")
    if args.adaptive:
        print("  Adaptive:   ON")
    print(f"  Render:     {'human (viewer window)' if args.render else 'headless'}")
    print("=" * 60)

    # Try importing SB3
    try:
        import stable_baselines3
        print(f"\n  Stable-Baselines3 version: {stable_baselines3.__version__}")
    except ImportError:
        print("\n  [ERROR] stable-baselines3 is not installed!")
        print("  Install with: pip install stable-baselines3")
        sys.exit(1)

    from surg_rl.rl.training import TrainingConfig, AlgorithmConfig, TrainingManager

    # Build config
    algo_config = AlgorithmConfig(
        name=args.algorithm,
        learning_rate=args.lr,
        batch_size=args.batch_size,
    )

    config = TrainingConfig(
        scene_path=args.scene,
        algorithm=algo_config,
        total_timesteps=args.timesteps,
        n_envs=args.n_envs,
        seed=args.seed,
        device=args.device,
        log_dir=args.log_dir,
        save_freq=args.save_freq,
        use_curriculum=args.curriculum,
        use_adaptive_difficulty=args.adaptive,
        max_episode_steps=args.max_steps,
        render_mode="human" if args.render else None,
        verbose=1,
    )

    # Train
    print("\n  Starting training...")
    print("  " + "-" * 56)

    start_time = time.time()
    try:
        manager = TrainingManager(config)
        model = manager.train()
        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print("  Training Complete!")
        print("=" * 60)
        print(f"  Duration:       {elapsed:.1f}s")
        print(f"  Steps/sec:      {args.timesteps / max(elapsed, 0.001):.0f}")
        print(f"  Model saved to: {args.log_dir}/final_model")
        print(f"  Config saved to: {args.log_dir}/training_config.json")
        print()

        # Quick evaluation
        print("  Running quick evaluation (5 episodes)...")
        results = manager.evaluate(n_episodes=5, render=args.render)
        print(f"  Mean reward:    {results['mean_reward']:.2f}")
        print(f"  Std reward:     {results['std_reward']:.2f}")
        print(f"  Success rate:   {results['success_rate']:.1%}")
        print()

    except Exception as e:
        print(f"\n  [ERROR] Training failed: {e}")
        print("  This is expected if MuJoCo/PyBullet assets are not available.")
        print("  Try running: surg-rl setup")
        sys.exit(1)


if __name__ == "__main__":
    main()
