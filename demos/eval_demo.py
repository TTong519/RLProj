#!/usr/bin/env python3
"""Evaluation visualization demo for Surg-RL.

This demo evaluates a trained RL agent and displays performance
metrics including reward curves, episode lengths, and success rates.

Usage:
    # Evaluate a trained model
    python demos/eval_demo.py --model logs/training/final_model

    # Evaluate with rendering
    python demos/eval_demo.py --model logs/training/final_model --render

    # Evaluate for more episodes
    python demos/eval_demo.py --model logs/training/final_model --episodes 50
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    parser = argparse.ArgumentParser(
        description="Evaluation visualization demo for Surg-RL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model", "-m", type=str, required=True,
        help="Path to trained model",
    )
    parser.add_argument(
        "--scene", "-s", type=str,
        default="scenes/simple_suturing.json",
        help="Path to scene file",
    )
    parser.add_argument(
        "--episodes", "-e", type=int, default=10,
        help="Number of evaluation episodes (default: 10)",
    )
    parser.add_argument(
        "--render", "-r", action="store_true",
        help="Open a MuJoCo viewer window during evaluation (requires a display; "
        "on macOS run with mjpython)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--save-results", type=str, default=None,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--verbose", "-v", type=int, default=1,
        help="Verbosity level (0, 1, 2)",
    )
    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("  Surg-RL Evaluation Demo")
    print("=" * 60)
    print(f"  Model:    {args.model}")
    print(f"  Scene:     {args.scene}")
    print(f"  Episodes:  {args.episodes}")
    print(f"  Seed:      {args.seed}")
    print(f"  Render:    {'human (viewer window)' if args.render else 'headless'}")
    print("=" * 60)

    # Check model exists
    model_path = Path(args.model)
    if not model_path.exists() and not model_path.with_suffix(".zip").exists():
        print(f"\n  [ERROR] Model not found: {args.model}")
        print("  Train a model first with: python demos/train_demo.py")
        sys.exit(1)

    # Try importing SB3
    try:
        import stable_baselines3
    except ImportError:
        print("\n  [ERROR] stable-baselines3 is not installed!")
        print("  Install with: pip install stable-baselines3")
        sys.exit(1)

    from surg_rl.rl.training import TrainingConfig, TrainingManager

    # Build minimal config for evaluation
    config = TrainingConfig(
        scene_path=args.scene,
        seed=args.seed,
        verbose=args.verbose,
    )

    # Evaluate
    print("\n  Running evaluation...")
    print("  " + "-" * 56)

    try:
        manager = TrainingManager(config)
        results = manager.evaluate(
            model_path=args.model,
            n_episodes=args.episodes,
            render=args.render,
        )

        # Display results
        print("\n" + "=" * 60)
        print("  Evaluation Results")
        print("=" * 60)
        print(f"  Episodes:       {results['n_episodes']}")
        print(f"  Mean reward:    {results['mean_reward']:.2f}")
        print(f"  Std reward:     {results['std_reward']:.2f}")
        print(f"  Max reward:     {results['max_reward']:.2f}")
        print(f"  Min reward:     {results['min_reward']:.2f}")
        print(f"  Mean ep length: {results['mean_episode_length']:.1f}")
        print(f"  Success rate:   {results['success_rate']:.1%}")

        # Per-episode breakdown
        print("\n  Per-episode rewards:")
        for i, (reward, length) in enumerate(
            zip(results["episode_rewards"], results["episode_lengths"])
        ):
            marker = " ***" if i == 0 or reward == max(results["episode_rewards"]) else ""
            print(f"    Episode {i+1:3d}: reward={reward:8.2f}  steps={length:5d}{marker}")

        # Save results if requested
        if args.save_results:
            output = {
                "model_path": args.model,
                "scene_path": args.scene,
                "n_episodes": results["n_episodes"],
                "mean_reward": results["mean_reward"],
                "std_reward": results["std_reward"],
                "max_reward": results["max_reward"],
                "min_reward": results["min_reward"],
                "mean_episode_length": results["mean_episode_length"],
                "success_rate": results["success_rate"],
                "episode_rewards": results["episode_rewards"],
                "episode_lengths": results["episode_lengths"],
            }
            with open(args.save_results, "w") as f:
                json.dump(output, f, indent=2)
            print(f"\n  Results saved to: {args.save_results}")

        print()

    except Exception as e:
        print(f"\n  [ERROR] Evaluation failed: {e}")
        print("  Make sure the model and scene are compatible.")
        sys.exit(1)


if __name__ == "__main__":
    main()
