#!/usr/bin/env python3
"""RL training example for Surg-RL.

Demonstrates how to use the Python API to train an RL agent
programmatically (without the CLI).

Usage:
    python examples/rl_training.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from surg_rl.rl import (
    SurgicalEnv,
    SurgicalEnvConfig,
    TrainingManager,
    TrainingConfig,
    AlgorithmConfig,
)


def main():
    """Train an RL agent using the Python API."""
    print("=" * 50)
    print("  Surg-RL Training Example")
    print("=" * 50)

    # --- Configuration ---
    scene_path = "scenes/simple_suturing.json"

    # Option 1: Create environment directly
    print("\n[1] Creating environment...")
    env_config = SurgicalEnvConfig(
        scene_path=scene_path,
        max_episode_steps=500,
    )
    env = SurgicalEnv(env_config)
    print(f"  Observation space: {env.observation_space}")
    print(f"  Action space:      {env.action_space}")

    # Test environment
    print("\n[2] Testing environment step...")
    obs, info = env.reset(seed=42)
    print(f"  Initial observation keys: {list(obs.keys()) if isinstance(obs, dict) else 'flat array'}")

    # Take a few random steps
    for i in range(5):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        print(f"  Step {i+1}: reward={reward:.4f}, done={terminated or truncated}")

    env.close()
    print("  Environment test complete.")

    # --- Training ---
    print("\n[3] Setting up training...")
    try:
        import stable_baselines3
    except ImportError:
        print("  stable-baselines3 not installed. Skipping training.")
        print("  Install with: pip install stable-baselines3")
        print("\n  To train with the CLI instead:")
        print("    surg-rl train --scene scenes/simple_suturing.json --algorithm PPO --timesteps 10000")
        return

    # Configure algorithm
    algo_config = AlgorithmConfig(
        name="PPO",
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
    )

    # Configure training
    train_config = TrainingConfig(
        scene_path=scene_path,
        algorithm=algo_config,
        total_timesteps=10000,
        n_envs=1,
        seed=42,
        log_dir="logs/training_example",
        save_freq=5000,
        eval_freq=5000,
        max_episode_steps=500,
        verbose=1,
    )

    # Train
    print(f"  Algorithm: {algo_config.name}")
    print(f"  Timesteps: {train_config.total_timesteps:,}")
    print("  Starting training...")

    manager = TrainingManager(train_config)
    model = manager.train()

    print("\n  Training complete!")

    # Quick evaluation
    print("\n[4] Evaluating trained model...")
    results = manager.evaluate(n_episodes=3)
    print(f"  Mean reward:    {results['mean_reward']:.2f}")
    print(f"  Std reward:     {results['std_reward']:.2f}")
    print(f"  Success rate:   {results['success_rate']:.1%}")

    # Save model
    model_path = manager.save_model("logs/training_example/example_model")
    print(f"\n  Model saved to: {model_path}")

    print("\n" + "=" * 50)
    print("  Example complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
