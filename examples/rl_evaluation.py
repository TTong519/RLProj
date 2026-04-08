#!/usr/bin/env python3
"""RL evaluation example for Surg-RL.

Demonstrates how to evaluate a trained agent and analyze
performance metrics using the Python API.

Usage:
    python examples/rl_evaluation.py --model logs/training/final_model
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from surg_rl.rl import (
    SurgicalEnv,
    SurgicalEnvConfig,
    TrainingManager,
    TrainingConfig,
)


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trained RL agent")
    parser.add_argument(
        "--model", "-m", type=str,
        default="logs/training/final_model",
        help="Path to trained model",
    )
    parser.add_argument(
        "--scene", "-s", type=str,
        default="scenes/simple_suturing.json",
        help="Path to scene file",
    )
    parser.add_argument(
        "--episodes", "-e", type=int, default=10,
        help="Number of evaluation episodes",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  Surg-RL Evaluation Example")
    print("=" * 50)
    print(f"  Model:    {args.model}")
    print(f"  Scene:     {args.scene}")
    print(f"  Episodes:  {args.episodes}")

    # Check SB3 availability
    try:
        import stable_baselines3
    except ImportError:
        print("\n  stable-baselines3 not installed!")
        print("  Install with: pip install stable-baselines3")
        sys.exit(1)

    # Create evaluation config
    config = TrainingConfig(
        scene_path=args.scene,
        seed=args.seed,
        verbose=1,
    )

    # Evaluate
    print("\n  Running evaluation...")
    manager = TrainingManager(config)
    results = manager.evaluate(
        model_path=args.model,
        n_episodes=args.episodes,
    )

    # Display results
    print("\n  Results:")
    print(f"    Episodes:       {results['n_episodes']}")
    print(f"    Mean reward:    {results['mean_reward']:.2f}")
    print(f"    Std reward:     {results['std_reward']:.2f}")
    print(f"    Max reward:      {results['max_reward']:.2f}")
    print(f"    Min reward:      {results['min_reward']:.2f}")
    print(f"    Mean ep length: {results['mean_episode_length']:.1f}")
    print(f"    Success rate:   {results['success_rate']:.1%}")

    # Per-episode breakdown
    print("\n  Per-episode details:")
    for i, (reward, length) in enumerate(
        zip(results["episode_rewards"], results["episode_lengths"])
    ):
        best = " *" if reward == max(results["episode_rewards"]) else ""
        print(f"    Episode {i+1:3d}: reward={reward:8.2f}  steps={length:5d}{best}")

    # Optionally save
    save_path = "logs/eval_results.json"
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
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {save_path}")

    print("\n" + "=" * 50)
    print("  Evaluation complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
