#!/usr/bin/env python3
"""Suturing RL training demo for Surg-RL.

Trains a PPO agent to perform a multi-stage suturing task:
  1. Approach and pick up a surgical needle
  2. Transport the needle to the tissue
  3. Drive the needle through both skin patches
  4. Complete the suture connecting both patches

Usage:
  python demos/demo.py --headless --steps 10000
  python demos/demo.py --scene scenes/suturing_demo.json --algo PPO
"""

# IMPORTANT: import _omp_compat FIRST, before any library that may link
# to OpenMP (mujoco, torch, numpy with MKL, etc.). This suppresses the
# "OMP: Error #15: libomp.dylib already initialized" crash that hits
# mjpython on macOS when two OpenMP runtimes are linked into the process.
# The shim lives in this demos/ directory; insert it onto sys.path so
# the import resolves regardless of where the user invokes from.
# fmt: off
import sys as _omp_sys
from pathlib import Path as _omp_Path
_omp_sys.path.insert(0, str(_omp_Path(__file__).resolve().parent))
import _omp_compat  # noqa: F401, E402
import _platform_guard  # noqa: F401, E402 — used to detect risky mjpython combos
# fmt: on

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np

from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig, make_env
from surg_rl.rl.training import TrainingManager, TrainingConfig, AlgorithmConfig
from surg_rl.rl.observation import ObservationConfig, ObservationType
from surg_rl.rl.action import ActionConfig, ActionType
from surg_rl.rl.rewards import (
    CompositeReward,
    DistanceReward,
    OrientationReward,
    ActionPenalty,
    TimePenalty,
    SuccessReward,
    CollisionPenalty,
)
from surg_rl.scene_definition import load_scene


def build_suturing_reward() -> CompositeReward:
    """Build a composite reward function for the multi-stage suturing task.

    Components:
    - DistanceReward: Dense shaping for needle approach and transport
    - OrientationReward: Alignment of end effector with needle/tissue
    - ActionPenalty: Smooth, energy-efficient motions
    - TimePenalty: Efficiency pressure
    - SuccessReward: Sparse bonus on task completion
    - CollisionPenalty: Avoid unintended tissue damage

    Returns:
        CompositeReward configured for suturing.
    """
    reward = CompositeReward()
    reward.add(DistanceReward(weight=1.0, shape="exponential", scale=10.0), 1.0)
    reward.add(OrientationReward(weight=0.5, scale=5.0), 1.0)
    reward.add(ActionPenalty(weight=0.01, penalty_type="l2"), 1.0)
    reward.add(TimePenalty(weight=0.001), 1.0)
    reward.add(SuccessReward(), 1.0)
    reward.add(CollisionPenalty(weight=0.5), 1.0)
    return reward


def build_observation_config() -> ObservationConfig:
    """Build observation configuration for suturing.

    Includes joint state, end effector pose, target info, and distance/angle
    metrics needed for the multi-stage task.

    Returns:
        ObservationConfig for the suturing environment.
    """
    return ObservationConfig(
        observation_types=[
            ObservationType.JOINT_POSITIONS,
            ObservationType.JOINT_VELOCITIES,
            ObservationType.ENDEFFECTOR_POS,
            ObservationType.ENDEFFECTOR_QUAT,
            ObservationType.TARGET_POS,
            ObservationType.DISTANCE_TO_TARGET,
            ObservationType.ANGLE_TO_TARGET,
        ],
        include_force=False,
        include_tissue=False,
        normalize=True,
        flatten=True,
    )


def run_training(args: argparse.Namespace) -> Tuple[TrainingManager, object]:
    """Run the RL training loop.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Tuple of (TrainingManager, trained model).
    """
    algo_config = AlgorithmConfig(
        name=args.algo,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
    )

    training_config = TrainingConfig(
        scene_path=args.scene,
        algorithm=algo_config,
        total_timesteps=args.steps,
        n_envs=args.n_envs,
        seed=args.seed,
        device=args.device,
        log_dir=args.log_dir,
        save_freq=max(args.steps // 10, 1000),
        eval_freq=max(args.steps // 20, 500),
        n_eval_episodes=args.eval_episodes,
        verbose=1,
        max_episode_steps=args.max_episode_steps,
        use_curriculum=args.use_curriculum,
        use_adaptive_difficulty=args.use_adaptive,
        render_mode="human" if args.render else None,
    )

    print(f"\n{'='*60}")
    print("  Phase 1: Training")
    print(f"{'='*60}")
    print(f"  Algorithm:     {args.algo}")
    print(f"  Timesteps:     {args.steps:,}")
    print(f"  Scene:         {args.scene}")
    print(f"  Max ep steps:  {args.max_episode_steps}")
    print(f"  Seed:          {args.seed}")
    print(f"  Curriculum:    {args.use_curriculum}")
    print(f"  Adaptive:      {args.use_adaptive}")
    print(f"  Log dir:       {args.log_dir}")
    print(f"  Render:        {'human (viewer window)' if args.render else 'headless'}")
    print()

    manager = TrainingManager(training_config)
    start = time.time()
    model = manager.train()
    elapsed = time.time() - start

    print(f"\n  Training completed in {elapsed:.1f}s")
    print(f"  Model saved to: {args.log_dir}/final_model")

    return manager, model


def run_evaluation(
    manager: TrainingManager,
    n_episodes: int,
    headless: bool = True,
) -> dict:
    """Evaluate the trained model.

    Args:
        manager: TrainingManager with a trained model.
        n_episodes: Number of evaluation episodes.
        headless: Whether to suppress rendering.

    Returns:
        Evaluation results dictionary.
    """
    print(f"\n{'='*60}")
    print("  Phase 2: Evaluation")
    print(f"{'='*60}")
    print(f"  Episodes: {n_episodes}")
    print()

    results = manager.evaluate(
        n_episodes=n_episodes,
        render=not headless,
    )

    print(f"\n  {'Metric':<25} {'Value':>12}")
    print(f"  {'-'*25} {'-'*12}")
    print(f"  {'Mean reward':<25} {results['mean_reward']:>12.2f}")
    print(f"  {'Std reward':<25} {results['std_reward']:>12.2f}")
    print(f"  {'Max reward':<25} {results['max_reward']:>12.2f}")
    print(f"  {'Min reward':<25} {results['min_reward']:>12.2f}")
    print(f"  {'Mean episode length':<25} {results['mean_episode_length']:>12.1f}")
    print(f"  {'Success rate':<25} {results['success_rate']:>11.1%}")

    return results


def run_interactive(
    env: SurgicalEnv,
    model: Optional[object] = None,
    steps: int = 1000,
) -> None:
    """Run an interactive episode with the trained model or random actions.

    Args:
        env: SurgicalEnv instance.
        model: Trained SB3 model (None for random actions).
        steps: Maximum number of steps.
    """
    print(f"\n{'='*60}")
    print("  Phase 3: Interactive Demo")
    print(f"{'='*60}")

    obs, info = env.reset()
    total_reward = 0.0
    mode = "model" if model is not None else "random"
    print(f"  Action mode: {mode}")
    print(f"  Max steps:   {steps}")
    print()

    for step in range(steps):
        if model is not None:
            action, _ = model.predict(obs, deterministic=True)
        else:
            action = env.action_space.sample()

        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        dist = info.get("distance_to_target", float("nan"))

        if step % 100 == 0 or terminated or truncated:
            print(
                f"  Step {step:>5} | "
                f"reward: {reward:+.4f} | "
                f"total: {total_reward:+.2f} | "
                f"dist: {dist:.4f} | "
                f"{'DONE' if terminated or truncated else ''}"
            )

        if terminated or truncated:
            success = info.get("task_success", False)
            print(f"\n  Episode ended at step {step}")
            print(f"  Total reward: {total_reward:.2f}")
            print(f"  Success: {success}")
            break

    env.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Suturing RL training demo - train an agent to pick up a "
        "needle and suture two skin patches together",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick training run (headless)
  python demos/demo.py --headless --steps 10000

  # Full PPO training
  python demos/demo.py --scene scenes/suturing_demo.json --algo PPO --steps 100000

  # Training with curriculum learning
  python demos/demo.py --steps 50000 --use-curriculum

  # Evaluate only (requires a trained model)
  python demos/demo.py --steps 0 --eval-episodes 20
        """,
    )

    parser.add_argument(
        "--scene", "-s",
        type=str,
        default="scenes/suturing_demo.json",
        help="Path to scene file (default: scenes/suturing_demo.json)",
    )
    parser.add_argument(
        "--algo", "-a",
        type=str,
        choices=["PPO", "SAC", "A2C"],
        default="PPO",
        help="RL algorithm (default: PPO)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=50000,
        help="Total training timesteps (default: 50000)",
    )
    parser.add_argument(
        "--eval-episodes",
        type=int,
        default=5,
        help="Number of evaluation episodes (default: 5)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI rendering (default: headless)",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Open a MuJoCo viewer window during training and the interactive "
        "demo (requires a display; on macOS run with mjpython)",
    )
    parser.add_argument(
        "--max-episode-steps",
        type=int,
        default=2000,
        help="Max steps per episode (default: 2000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Training device: auto, cpu, cuda, mps (default: auto)",
    )
    parser.add_argument(
        "--n-envs",
        type=int,
        default=1,
        help="Number of parallel environments (default: 1)",
    )
    parser.add_argument(
        "--use-curriculum",
        action="store_true",
        help="Enable curriculum learning",
    )
    parser.add_argument(
        "--use-adaptive",
        action="store_true",
        help="Enable adaptive difficulty",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs/suturing_demo",
        help="Directory for logs and checkpoints (default: logs/suturing_demo)",
    )

    args = parser.parse_args()

    # Refuse the known-unstable mjpython+AppleSilicon+--render combination
    # before we try to construct the env. The segfault happens during SB3
    # training startup (after Monitor/DummyVecEnv wrapping) and is not
    # recoverable from inside Python — exiting early with a clear message
    # is the only way to give the user an actionable error.
    if args.render and _platform_guard.is_risky_render_combination(device=args.device):
        print(_platform_guard.format_risky_render_message(), file=sys.stderr)
        sys.exit(2)

    # Resolve scene path
    scene_path = Path(args.scene)
    if not scene_path.exists():
        project_root = Path(__file__).parent.parent
        scene_path = project_root / args.scene
        if not scene_path.exists():
            print(f"Error: Scene file not found: {args.scene}")
            sys.exit(1)
    args.scene = str(scene_path)

    # Print banner
    print(f"\n{'='*60}")
    print("  Suturing RL Training Demo")
    print(f"{'='*60}")
    print()
    print("  Task stages:")
    print("    1. Approach the surgical needle")
    print("    2. Grasp and pick up the needle")
    print("    3. Drive the needle through both skin patches")
    print("    4. Complete the suture connecting both patches")
    print()

    # Load and display scene info
    try:
        scene = load_scene(args.scene)
        print(f"  Scene:  {scene.metadata.name}")
        print(f"  Robots: {len(scene.robots)}")
        print(f"  Tissues: {len(scene.tissues)}")
        print(f"  Instruments: {len(scene.instruments)}")
        if scene.task:
            print(f"  Task: {scene.task.name}")
            for obj in scene.task.objectives:
                print(f"    - {obj.name} (weight={obj.weight})")
    except Exception as e:
        print(f"  Warning: Could not load scene for info display: {e}")

    # Training phase
    if args.steps > 0:
        manager, model = run_training(args)

        # Evaluation phase
        eval_results = run_evaluation(
            manager,
            n_episodes=args.eval_episodes,
            headless=not args.render,
        )

        # Interactive demo
        if not args.headless:
            print()
            try:
                response = input("  Run interactive demo? [y/N]: ").strip().lower()
            except EOFError:
                response = "n"
            if response == "y":
                from surg_rl.rl.environment import make_env as _make_env

                env = _make_env(
                    scene_path=args.scene,
                    max_episode_steps=args.max_episode_steps,
                    seed=args.seed + 100,
                    render_mode="human" if args.render else None,
                )
                run_interactive(env, model=model, steps=args.max_episode_steps)
    else:
        print("\n  Skipping training (--steps 0)")

    print(f"\n{'='*60}")
    print("  Demo complete")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()