#!/usr/bin/env python3
"""Performance benchmark for Surg-RL environments.

Measures environment throughput (steps/second), observation space size,
action space size, and reset time across different configurations.

Usage:
    # Quick benchmark (default settings)
    python demos/benchmark.py

    # Benchmark with more episodes/steps
    python demos/benchmark.py --episodes 20 --steps-per-episode 500

    # Benchmark specific scene
    python demos/benchmark.py --scene scenes/simple_suturing.json

    # Save results to JSON
    python demos/benchmark.py --save benchmark_results.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def benchmark_environment(scene_path, max_steps, episodes, seed=42):
    """Benchmark a SurgicalEnv environment.

    Args:
        scene_path: Path to scene definition file.
        max_steps: Maximum steps per episode.
        episodes: Number of episodes to run.
        seed: Random seed for reproducibility.

    Returns:
        Dictionary with benchmark results.
    """
    from surg_rl.rl import SurgicalEnv, SurgicalEnvConfig

    # Create environment
    config = SurgicalEnvConfig(
        scene_path=scene_path,
        max_episode_steps=max_steps,
    )
    env = SurgicalEnv(config)

    # Collect benchmark data
    results = {
        "scene": scene_path,
        "max_steps": max_steps,
        "episodes": episodes,
        "observation_space": str(env.observation_space),
        "action_space": str(env.action_space),
        "obs_space_size": _count_obs_size(env.observation_space),
        "action_space_size": _count_action_size(env.action_space),
    }

    # Benchmark reset
    reset_times = []
    step_times = []
    episode_rewards = []
    episode_lengths = []

    print("  Running benchmark...")
    for ep in range(episodes):
        # Reset
        t0 = time.perf_counter()
        obs, info = env.reset(seed=seed + ep)
        reset_times.append(time.perf_counter() - t0)

        total_reward = 0.0
        steps = 0

        for step in range(max_steps):
            # Random action
            action = env.action_space.sample()

            # Step
            t0 = time.perf_counter()
            obs, reward, terminated, truncated, info = env.step(action)
            step_times.append(time.perf_counter() - t0)

            total_reward += reward
            steps += 1

            if terminated or truncated:
                break

        episode_rewards.append(total_reward)
        episode_lengths.append(steps)

        if (ep + 1) % max(1, episodes // 5) == 0:
            print(f"    Episode {ep+1}/{episodes}: "
                  f"reward={total_reward:.2f}, steps={steps}")

    env.close()

    # Compute statistics
    results["reset_time_mean"] = float(np.mean(reset_times))
    results["reset_time_std"] = float(np.std(reset_times))
    results["step_time_mean"] = float(np.mean(step_times))
    results["step_time_std"] = float(np.std(step_times))
    results["steps_per_second"] = float(1.0 / np.mean(step_times)) if np.mean(step_times) > 0 else 0.0
    results["resets_per_second"] = float(1.0 / np.mean(reset_times)) if np.mean(reset_times) > 0 else 0.0
    results["episode_reward_mean"] = float(np.mean(episode_rewards))
    results["episode_reward_std"] = float(np.std(episode_rewards))
    results["episode_length_mean"] = float(np.mean(episode_lengths))
    results["episode_length_std"] = float(np.std(episode_lengths))

    return results


def _count_obs_size(space):
    """Count total elements in observation space."""
    total = 0
    if hasattr(space, "shape"):
        total += int(np.prod(space.shape))
    elif hasattr(space, "spaces"):
        for v in space.spaces.values():
            total += _count_obs_size(v)
    return total


def _count_action_size(space):
    """Count total elements in action space."""
    if hasattr(space, "shape"):
        return int(np.prod(space.shape))
    elif hasattr(space, "n"):
        return space.n
    elif hasattr(space, "spaces"):
        total = 0
        for v in space.spaces.values():
            total += _count_action_size(v)
        return total
    return 0


def benchmark_simulator(scene_path, backend, steps=1000):
    """Benchmark a simulator backend directly.

    Args:
        scene_path: Path to scene definition file.
        backend: Simulator backend ('mujoco' or 'pybullet').
        steps: Number of steps to benchmark.

    Returns:
        Dictionary with benchmark results.
    """
    from surg_rl.scene_definition import load_scene
    from surg_rl.simulators import MuJoCoSimulator, PyBulletSimulator

    scene = load_scene(scene_path)

    if backend == "mujoco":
        sim = MuJoCoSimulator(assets_dir=Path(__file__).parent.parent / "assets")
    else:
        sim = PyBulletSimulator(assets_dir=Path(__file__).parent.parent / "assets", render_mode="DIRECT")

    # Load and reset
    sim.load_scene(scene)

    t0 = time.perf_counter()
    obs = sim.reset()
    reset_time = time.perf_counter() - t0

    # Step benchmark
    step_times = []
    for i in range(steps):
        action = np.zeros(7)  # Zero action
        t0 = time.perf_counter()
        result = sim.step(action)
        step_times.append(time.perf_counter() - t0)

    sim.close()

    return {
        "backend": backend,
        "steps": steps,
        "reset_time": reset_time,
        "step_time_mean": float(np.mean(step_times)),
        "step_time_std": float(np.std(step_times)),
        "steps_per_second": float(1.0 / np.mean(step_times)) if np.mean(step_times) > 0 else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Performance benchmark for Surg-RL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scene", "-s", type=str,
        default="scenes/simple_suturing.json",
        help="Path to scene file",
    )
    parser.add_argument(
        "--episodes", "-e", type=int, default=10,
        help="Number of benchmark episodes (default: 10)",
    )
    parser.add_argument(
        "--steps-per-episode", type=int, default=100,
        help="Max steps per episode (default: 100)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--simulator-only", action="store_true",
        help="Only benchmark simulator (no RL env)",
    )
    parser.add_argument(
        "--backend", type=str, default="mujoco",
        choices=["mujoco", "pybullet"],
        help="Simulator backend for direct benchmark (default: mujoco)",
    )
    parser.add_argument(
        "--save", type=str, default=None,
        help="Save results to JSON file",
    )
    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("  Surg-RL Performance Benchmark")
    print("=" * 60)
    print(f"  Scene: {args.scene}")
    print(f"  Episodes: {args.episodes}")
    print(f"  Steps/episode: {args.steps_per_episode}")
    print("=" * 60)

    all_results = {}

    # Simulator benchmark
    print("\n[1/2] Benchmarking simulator backend...")
    try:
        sim_results = benchmark_simulator(
            args.scene, args.backend, steps=1000
        )
        all_results["simulator"] = sim_results

        print(f"\n  Simulator Results ({sim_results['backend']}):")
        print(f"    Steps:              {sim_results['steps']}")
        print(f"    Reset time:         {sim_results['reset_time']*1000:.2f} ms")
        print(f"    Step time (mean):   {sim_results['step_time_mean']*1000:.3f} ms")
        print(f"    Step time (std):    {sim_results['step_time_std']*1000:.3f} ms")
        print(f"    Steps/second:       {sim_results['steps_per_second']:.0f}")
    except Exception as e:
        print(f"  Simulator benchmark failed: {e}")
        print("  (This is expected if MuJoCo/PyBullet is not available)")

    # Environment benchmark
    if not args.simulator_only:
        print("\n[2/2] Benchmarking RL environment...")
        try:
            env_results = benchmark_environment(
                args.scene, args.steps_per_episode, args.episodes, args.seed
            )
            all_results["environment"] = env_results

            print(f"\n  Environment Results:")
            print(f"    Observation space size: {env_results['obs_space_size']}")
            print(f"    Action space size:       {env_results['action_space_size']}")
            print(f"    Reset time (mean):       {env_results['reset_time_mean']*1000:.2f} ms")
            print(f"    Reset time (std):        {env_results['reset_time_std']*1000:.2f} ms")
            print(f"    Step time (mean):        {env_results['step_time_mean']*1000:.3f} ms")
            print(f"    Step time (std):         {env_results['step_time_std']*1000:.3f} ms")
            print(f"    Steps/second:            {env_results['steps_per_second']:.0f}")
            print(f"    Resets/second:           {env_results['resets_per_second']:.0f}")
            print(f"    Episode reward (mean):   {env_results['episode_reward_mean']:.2f}")
            print(f"    Episode length (mean):   {env_results['episode_length_mean']:.1f}")
        except Exception as e:
            print(f"  Environment benchmark failed: {e}")
            print("  (This is expected if MuJoCo/PyBullet is not available)")

    # Save results
    if args.save:
        with open(args.save, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n  Results saved to: {args.save}")

    print("\n" + "=" * 60)
    print("  Benchmark Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
