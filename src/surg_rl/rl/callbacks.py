"""Custom callbacks for Stable-Baselines3 training.

This module provides custom callbacks for monitoring, logging, and
controlling the RL training process.
"""

import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


class TrainingProgressCallback:
    """Callback for tracking and reporting training progress.

    Logs training metrics including episode rewards, lengths,
    and training speed.

    Example:
        >>> callback = TrainingProgressCallback(verbose=1)
        >>> # Use with TrainingManager or SB3 model
    """

    def __init__(
        self,
        verbose: int = 1,
        log_interval: int = 100,
        reward_window: int = 100,
    ):
        """Initialize the progress callback.

        Args:
            verbose: Verbosity level (0=silent, 1=info, 2=detailed).
            log_interval: Logging interval in timesteps.
            reward_window: Window for computing running statistics.
        """
        self.verbose = verbose
        self.log_interval = log_interval
        self.reward_window = reward_window
        self._step = 0
        self._episode_rewards: List[float] = []
        self._episode_lengths: List[int] = []
        self._start_time = time.time()

    def __call__(self, **kwargs) -> None:
        """Called by SB3 during training.

        Args:
            **kwargs: Callback arguments from SB3.
        """
        locals_dict = kwargs.get("locals", {})

        # Track steps
        self._step += 1

        # Check for episode end
        done = locals_dict.get("done", False)
        if done:
            info = locals_dict.get("info", {})
            if isinstance(info, dict):
                reward = info.get("episode", {}).get("r", 0.0)
                length = info.get("episode", {}).get("l", 0)
            else:
                # SB3 VecEnv format
                reward = 0.0
                length = 0
            self._episode_rewards.append(reward)
            self._episode_lengths.append(length)

        # Periodic logging
        if self._step % self.log_interval == 0 and self.verbose >= 1:
            self._log_progress()

    def _log_progress(self) -> None:
        """Log training progress."""
        if not self._episode_rewards:
            return

        recent_rewards = self._episode_rewards[-self.reward_window:]
        recent_lengths = self._episode_lengths[-self.reward_window:]

        elapsed = time.time() - self._start_time
        fps = self._step / elapsed if elapsed > 0 else 0

        mean_reward = np.mean(recent_rewards) if recent_rewards else 0.0
        mean_length = np.mean(recent_lengths) if recent_lengths else 0.0

        logger.info(
            f"Step {self._step:,} | "
            f"Episodes: {len(self._episode_rewards)} | "
            f"Mean reward: {mean_reward:.2f} | "
            f"Mean length: {mean_length:.0f} | "
            f"FPS: {fps:.0f}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get current training statistics.

        Returns:
            Dictionary with training statistics.
        """
        if not self._episode_rewards:
            return {"step": self._step, "episodes": 0}

        recent_rewards = self._episode_rewards[-self.reward_window:]
        recent_lengths = self._episode_lengths[-self.reward_window:]

        return {
            "step": self._step,
            "episodes": len(self._episode_rewards),
            "mean_reward": float(np.mean(recent_rewards)),
            "std_reward": float(np.std(recent_rewards)),
            "max_reward": float(np.max(recent_rewards)),
            "min_reward": float(np.min(recent_rewards)),
            "mean_length": float(np.mean(recent_lengths)),
            "fps": self._step / (time.time() - self._start_time)
            if self._start_time
            else 0,
        }


class CheckpointCallback:
    """Callback for saving model checkpoints during training.

    Saves the model at regular intervals during training.

    Example:
        >>> callback = CheckpointCallback(
        ...     save_freq=10000,
        ...     save_path="checkpoints/",
        ...     name_prefix="surg_rl_ppo",
        ... )
    """

    def __init__(
        self,
        save_freq: int = 50_000,
        save_path: str = "checkpoints/",
        name_prefix: str = "surg_rl",
        verbose: int = 0,
    ):
        """Initialize the checkpoint callback.

        Args:
            save_freq: Save frequency in timesteps.
            save_path: Directory to save checkpoints.
            name_prefix: Prefix for checkpoint filenames.
            verbose: Verbosity level.
        """
        self.save_freq = save_freq
        self.save_path = Path(save_path)
        self.name_prefix = name_prefix
        self.verbose = verbose
        self._last_save_step = 0

    def __call__(self, **kwargs) -> None:
        """Called by SB3 during training.

        Args:
            **kwargs: Callback arguments from SB3.
        """
        locals_dict = kwargs.get("locals", {})
        model = locals_dict.get("self")
        step = locals_dict.get("num_collected_steps", 0)

        if model is None:
            return

        # Check if we should save
        if step - self._last_save_step >= self.save_freq:
            self._save_checkpoint(model, step)
            self._last_save_step = step

    def _save_checkpoint(self, model, step: int) -> None:
        """Save a model checkpoint.

        Args:
            model: SB3 model to save.
            step: Current training step.
        """
        self.save_path.mkdir(parents=True, exist_ok=True)
        filename = f"{self.name_prefix}_{step}_steps"
        filepath = self.save_path / filename

        try:
            model.save(str(filepath))
            if self.verbose >= 1:
                logger.info(f"Checkpoint saved: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")


class CurriculumCallback:
    """Callback for curriculum learning integration.

    Updates the curriculum scheduler based on training progress,
    automatically advancing through difficulty stages.

    Example:
        >>> callback = CurriculumCallback(controller=env.controller)
    """

    def __init__(
        self,
        controller=None,
        verbose: int = 1,
    ):
        """Initialize the curriculum callback.

        Args:
            controller: EnvironmentController instance.
            verbose: Verbosity level.
        """
        self.controller = controller
        self.verbose = verbose
        self._episode_count = 0

    def __call__(self, **kwargs) -> None:
        """Called by SB3 during training.

        Args:
            **kwargs: Callback arguments from SB3.
        """
        if self.controller is None:
            return

        locals_dict = kwargs.get("locals", {})
        done = locals_dict.get("done", False)

        if done:
            self._episode_count += 1
            info = locals_dict.get("info", {})

            # Report episode metrics to controller
            metrics = {
                "reward": info.get("episode", {}).get("r", 0.0),
                "success": info.get("success", False),
            }

            controller_info = self.controller.episode_end(metrics, None)

            # Log curriculum progress
            if self.verbose >= 1 and self._episode_count % 50 == 0:
                stage = self.controller.get_curriculum_stage()
                difficulty = self.controller.get_difficulty()
                logger.info(
                    f"Curriculum: episode={self._episode_count}, "
                    f"stage={stage.value if stage else 'N/A'}, "
                    f"difficulty={difficulty:.2f if difficulty else 'N/A'}"
                )


class EvaluationCallback:
    """Callback for periodic evaluation during training.

    Runs evaluation episodes at regular intervals and logs results.

    Example:
        >>> callback = EvaluationCallback(
        ...     eval_env=env,
        ...     eval_freq=10000,
        ...     n_eval_episodes=5,
        ... )
    """

    def __init__(
        self,
        eval_env=None,
        eval_freq: int = 10_000,
        n_eval_episodes: int = 5,
        deterministic: bool = True,
        verbose: int = 1,
    ):
        """Initialize the evaluation callback.

        Args:
            eval_env: Environment for evaluation.
            eval_freq: Evaluation frequency in timesteps.
            n_eval_episodes: Number of evaluation episodes.
            deterministic: Whether to use deterministic actions.
            verbose: Verbosity level.
        """
        self.eval_env = eval_env
        self.eval_freq = eval_freq
        self.n_eval_episodes = n_eval_episodes
        self.deterministic = deterministic
        self.verbose = verbose
        self._last_eval_step = 0
        self._eval_results: List[Dict[str, Any]] = []

    def __call__(self, **kwargs) -> None:
        """Called by SB3 during training.

        Args:
            **kwargs: Callback arguments from SB3.
        """
        locals_dict = kwargs.get("locals", {})
        model = locals_dict.get("self")
        step = locals_dict.get("num_collected_steps", 0)

        if model is None or self.eval_env is None:
            return

        # Check if we should evaluate
        if step - self._last_eval_step >= self.eval_freq:
            self._evaluate(model, step)
            self._last_eval_step = step

    def _evaluate(self, model, step: int) -> None:
        """Run evaluation episodes.

        Args:
            model: SB3 model to evaluate.
            step: Current training step.
        """
        episode_rewards = []
        episode_lengths = []

        for _ in range(self.n_eval_episodes):
            obs, info = self.eval_env.reset()
            total_reward = 0.0
            steps = 0
            done = False

            while not done:
                action, _ = model.predict(obs, deterministic=self.deterministic)
                obs, reward, terminated, truncated, info = self.eval_env.step(action)
                total_reward += reward
                steps += 1
                done = terminated or truncated

            episode_rewards.append(total_reward)
            episode_lengths.append(steps)

        results = {
            "step": step,
            "mean_reward": float(np.mean(episode_rewards)),
            "std_reward": float(np.std(episode_rewards)),
            "mean_length": float(np.mean(episode_lengths)),
        }
        self._eval_results.append(results)

        if self.verbose >= 1:
            logger.info(
                f"Eval at step {step:,}: "
                f"mean_reward={results['mean_reward']:.2f} "
                f"+/- {results['std_reward']:.2f}, "
                f"mean_length={results['mean_length']:.0f}"
            )

    def get_results(self) -> List[Dict[str, Any]]:
        """Get all evaluation results.

        Returns:
            List of evaluation result dictionaries.
        """
        return self._eval_results.copy()
