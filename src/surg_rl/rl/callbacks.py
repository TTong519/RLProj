"""Custom callbacks for Stable-Baselines3 training.

This module provides custom callbacks for monitoring, logging, and
controlling the RL training process.
"""

import time
from pathlib import Path
from typing import Any

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


class TrainingProgressCallback(BaseCallback):
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
        super().__init__(verbose)
        self.log_interval = log_interval
        self.reward_window = reward_window
        self._step = 0
        self._episode_rewards: list[float] = []
        self._episode_lengths: list[int] = []
        self._start_time = time.time()

    def _on_step(self) -> bool:
        """Called by SB3 during each training step."""
        locals_dict = self.locals

        # Track steps
        self._step += 1

        # Check for episode end
        infos = locals_dict.get("infos", [])
        for info in infos:
            ep = info.get("episode")
            if isinstance(ep, dict):
                reward = ep.get("r", 0.0)
                length = ep.get("l", 0)
                self._episode_rewards.append(reward)
                self._episode_lengths.append(length)

        # Periodic logging
        if self._step % self.log_interval == 0 and self.verbose >= 1:
            self._log_progress()

        return True

    def _log_progress(self) -> None:
        """Log training progress."""
        if not self._episode_rewards:
            return

        recent_rewards = self._episode_rewards[-self.reward_window :]
        recent_lengths = self._episode_lengths[-self.reward_window :]

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

    def get_stats(self) -> dict[str, Any]:
        """Get current training statistics.

        Returns:
            Dictionary with training statistics.
        """
        if not self._episode_rewards:
            return {"step": self._step, "episodes": 0}

        recent_rewards = self._episode_rewards[-self.reward_window :]
        recent_lengths = self._episode_lengths[-self.reward_window :]

        return {
            "step": self._step,
            "episodes": len(self._episode_rewards),
            "mean_reward": float(np.mean(recent_rewards)),
            "std_reward": float(np.std(recent_rewards)),
            "max_reward": float(np.max(recent_rewards)),
            "min_reward": float(np.min(recent_rewards)),
            "mean_length": float(np.mean(recent_lengths)),
            "fps": self._step / (time.time() - self._start_time) if self._start_time else 0,
        }


class CheckpointCallback(BaseCallback):
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
        super().__init__(verbose)
        self.save_freq = save_freq
        self.save_path = Path(save_path)
        self.name_prefix = name_prefix
        self._last_save_step = 0

    def _on_step(self) -> bool:
        """Called by SB3 during each training step."""
        locals_dict = self.locals
        model = locals_dict.get("self")
        step = self.num_timesteps

        if model is None:
            return True

        # Check if we should save
        if step - self._last_save_step >= self.save_freq:
            self._save_checkpoint(model, step)
            self._last_save_step = step

        return True

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


class CurriculumCallback(BaseCallback):
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
        super().__init__(verbose)
        self.controller = controller
        self._episode_count = 0

    def _on_step(self) -> bool:
        """Called by SB3 during each training step."""
        if self.controller is None:
            return True

        locals_dict = self.locals
        infos = locals_dict.get("infos", [])
        for info in infos:
            ep = info.get("episode")
            if isinstance(ep, dict):
                self._episode_count += 1

                # Report episode metrics to controller
                metrics = {
                    "reward": ep.get("r", 0.0),
                    "success": info.get("success", False),
                }

                self.controller.episode_end(metrics, None)

                # Log curriculum progress
                if self.verbose >= 1 and self._episode_count % 50 == 0:
                    stage = self.controller.get_curriculum_stage()
                    difficulty = self.controller.get_difficulty()
                    logger.info(
                        f"Curriculum: episode={self._episode_count}, "
                        f"stage={stage.value if stage else 'N/A'}, "
                        f"difficulty={difficulty:.2f if difficulty else 'N/A'}"
                    )

        return True


class EvaluationCallback(BaseCallback):
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
        super().__init__(verbose)
        self.eval_env = eval_env
        self.eval_freq = eval_freq
        self.n_eval_episodes = n_eval_episodes
        self.deterministic = deterministic
        self._last_eval_step = 0
        self._eval_results: list[dict[str, Any]] = []

    def _on_step(self) -> bool:
        """Called by SB3 during each training step."""
        locals_dict = self.locals
        model = locals_dict.get("self")
        step = self.num_timesteps

        if model is None or self.eval_env is None:
            return True

        # Check if we should evaluate
        if step - self._last_eval_step >= self.eval_freq:
            self._evaluate(model, step)
            self._last_eval_step = step

        return True

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

    def get_results(self) -> list[dict[str, Any]]:
        """Get all evaluation results.

        Returns:
            List of evaluation result dictionaries.
        """
        return self._eval_results.copy()


class TensorBoardCallback(BaseCallback):
    """Callback for logging training metrics to TensorBoard.

    Logs episode reward and length, training FPS, curriculum stage,
    adaptive difficulty, and domain randomization parameters using
    Stable-Baselines3's built-in logger.

    Example:
        >>> callback = TensorBoardCallback(
        ...     controller=env.controller,
        ...     log_interval=100,
        ... )
    """

    def __init__(
        self,
        controller=None,
        log_interval: int = 100,
        verbose: int = 0,
    ):
        """Initialize the TensorBoard callback.

        Args:
            controller: EnvironmentController instance for accessing
                curriculum and randomization state.
            log_interval: Number of timesteps between logger dumps.
            verbose: Verbosity level.
        """
        super().__init__(verbose)
        self.controller = controller
        self.log_interval = log_interval
        self._episode_rewards: list[float] = []
        self._episode_lengths: list[int] = []
        self._start_time: float | None = None
        self._last_log_step = 0

    def _on_training_start(self) -> None:
        """Record training start time."""
        self._start_time = time.time()

    def _on_step(self) -> bool:
        """Log metrics at each training step."""
        infos = self.locals.get("infos", [])
        for info in infos:
            ep = info.get("episode")
            if isinstance(ep, dict):
                reward = ep.get("r", 0.0)
                length = ep.get("l", 0)
                self._episode_rewards.append(reward)
                self._episode_lengths.append(length)

                if self.logger is not None:
                    self.logger.record("rollout/episode_reward", reward)
                    self.logger.record("rollout/episode_length", length)

        # Log controller state
        if self.controller is not None and self.logger is not None:
            stage = self.controller.get_curriculum_stage()
            if stage is not None:
                self.logger.record("curriculum/stage", stage.value)

            difficulty = self.controller.get_difficulty()
            if difficulty is not None:
                self.logger.record("curriculum/difficulty", difficulty)

            params = self.controller.current_params
            for key, value in params.physics.items():
                if isinstance(value, (int, float)):
                    self.logger.record(f"randomization/physics/{key}", value)
            for key, value in params.visual.items():
                if isinstance(value, (int, float)):
                    self.logger.record(f"randomization/visual/{key}", value)
            for key, value in params.dynamics.items():
                if isinstance(value, (int, float)):
                    self.logger.record(f"randomization/dynamics/{key}", value)

        # Log FPS
        if self._start_time is not None and self.logger is not None:
            elapsed = time.time() - self._start_time
            fps = self.num_timesteps / elapsed if elapsed > 0 else 0
            self.logger.record("time/fps", fps)

        # Dump logger at intervals
        if self.num_timesteps - self._last_log_step >= self.log_interval:
            if self.logger is not None:
                self.logger.dump(self.num_timesteps)
            self._last_log_step = self.num_timesteps

        return True


class WandbCallback(BaseCallback):
    """Callback for logging training metrics to Weights & Biases.

    Logs episode reward and length, training FPS, curriculum stage,
    adaptive difficulty, and domain randomization parameters.

    Opt-in: requires `pip install -e ".[tracking]"`.

    Example:
        >>> callback = WandbCallback(
        ...     project_name="surg-rl",
        ...     experiment_name="ppo-suturing",
        ...     controller=env.controller,
        ... )
    """

    def __init__(
        self,
        project_name: str | None = None,
        experiment_name: str | None = None,
        wandb_api_key: str | None = None,
        controller=None,
        verbose: int = 0,
    ):
        """Initialize the W&B callback.

        Args:
            project_name: W&B project name (default: surg-rl).
            experiment_name: Run name displayed in W&B dashboard.
            wandb_api_key: Optional API key override.
            controller: EnvironmentController for curriculum/randomization state.
            verbose: Verbosity level.
        """
        super().__init__(verbose)
        self.project_name = project_name or "surg-rl"
        self.experiment_name = experiment_name
        self.wandb_api_key = wandb_api_key
        self.controller = controller
        self._step = 0
        self._episode_rewards: list[float] = []
        self._episode_lengths: list[int] = []
        self._start_time: float | None = None

    def _on_training_start(self) -> None:
        """Initialize W&B run."""
        try:
            import wandb
        except ImportError:
            logger.warning("wandb not installed. Install with: pip install -e '.[tracking]'")
            return
        if self.wandb_api_key:
            wandb.login(key=self.wandb_api_key)
        wandb.init(project=self.project_name, name=self.experiment_name, reinit=True)
        self._start_time = time.time()

    def _on_step(self) -> bool:
        """Log episode data and periodic metrics."""
        self._step += 1
        infos = self.locals.get("infos", [])
        for info in infos:
            ep = info.get("episode")
            if isinstance(ep, dict):
                self._episode_rewards.append(ep.get("r", 0.0))
                self._episode_lengths.append(ep.get("l", 0))

        if self._step % 100 == 0:
            self._log_metrics()
        return True

    def _log_metrics(self) -> None:
        """Write aggregated metrics to W&B."""
        try:
            import wandb
        except ImportError:
            return
        if not self._episode_rewards:
            return
        recent_rewards = self._episode_rewards[-100:]
        recent_lengths = self._episode_lengths[-100:]
        elapsed = time.time() - self._start_time if self._start_time else 0
        fps = self._step / elapsed if elapsed > 0 else 0
        metrics: dict[str, Any] = {
            "rollout/mean_reward": float(np.mean(recent_rewards)),
            "rollout/mean_length": float(np.mean(recent_lengths)),
            "time/fps": fps,
            "time/elapsed": elapsed,
        }
        if self.controller is not None:
            stage = self.controller.get_curriculum_stage()
            if stage is not None:
                metrics["curriculum/stage"] = stage.value
            difficulty = self.controller.get_difficulty()
            if difficulty is not None:
                metrics["curriculum/difficulty"] = difficulty
            params = self.controller.current_params
            for key, value in params.physics.items():
                if isinstance(value, (int, float)):
                    metrics[f"randomization/physics/{key}"] = value
            for key, value in params.visual.items():
                if isinstance(value, (int, float)):
                    metrics[f"randomization/visual/{key}"] = value
            for key, value in params.dynamics.items():
                if isinstance(value, (int, float)):
                    metrics[f"randomization/dynamics/{key}"] = value
        wandb.log(metrics, step=self._step)

    def _on_training_end(self) -> None:
        """Finish W&B run."""
        try:
            import wandb
        except ImportError:
            return
        wandb.finish()


class MLflowCallback(BaseCallback):
    """Callback for logging training metrics to MLflow.

    Logs episode reward and length, training FPS, curriculum stage,
    adaptive difficulty, and domain randomization parameters.

    Opt-in: requires `pip install -e ".[tracking]"`.

    Example:
        >>> callback = MLflowCallback(
        ...     experiment_name="surg-rl",
        ...     tracking_uri="http://localhost:5000",
        ...     controller=env.controller,
        ... )
    """

    def __init__(
        self,
        experiment_name: str | None = None,
        tracking_uri: str | None = None,
        controller=None,
        verbose: int = 0,
    ):
        """Initialize the MLflow callback.

        Args:
            experiment_name: MLflow experiment name (default: surg-rl).
            tracking_uri: MLflow tracking server URI.
            controller: EnvironmentController for curriculum/randomization state.
            verbose: Verbosity level.
        """
        super().__init__(verbose)
        self.experiment_name = experiment_name or "surg-rl"
        self.tracking_uri = tracking_uri
        self.controller = controller
        self._step = 0
        self._episode_rewards: list[float] = []
        self._episode_lengths: list[int] = []
        self._start_time: float | None = None
        self._run_id: str | None = None

    def _on_training_start(self) -> None:
        """Initialize MLflow run."""
        try:
            import mlflow
        except ImportError:
            logger.warning("mlflow not installed. Install with: pip install -e '.[tracking]'")
            return
        if self.tracking_uri:
            mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment_name)
        run = mlflow.start_run()
        self._run_id = run.info.run_id
        self._start_time = time.time()

    def _on_step(self) -> bool:
        """Log episode data and periodic metrics."""
        self._step += 1
        infos = self.locals.get("infos", [])
        for info in infos:
            ep = info.get("episode")
            if isinstance(ep, dict):
                self._episode_rewards.append(ep.get("r", 0.0))
                self._episode_lengths.append(ep.get("l", 0))

        if self._step % 100 == 0:
            self._log_metrics()
        return True

    def _log_metrics(self) -> None:
        """Write aggregated metrics to MLflow."""
        try:
            import mlflow
        except ImportError:
            return
        if not self._episode_rewards:
            return
        recent_rewards = self._episode_rewards[-100:]
        recent_lengths = self._episode_lengths[-100:]
        elapsed = time.time() - self._start_time if self._start_time else 0
        fps = self._step / elapsed if elapsed > 0 else 0
        mlflow.log_metric("rollout_mean_reward", float(np.mean(recent_rewards)), step=self._step)
        mlflow.log_metric("rollout_mean_length", float(np.mean(recent_lengths)), step=self._step)
        mlflow.log_metric("time_fps", fps, step=self._step)
        if self.controller is not None:
            stage = self.controller.get_curriculum_stage()
            if stage is not None:
                mlflow.log_metric("curriculum_stage", stage.value, step=self._step)
            difficulty = self.controller.get_difficulty()
            if difficulty is not None:
                mlflow.log_metric("curriculum_difficulty", difficulty, step=self._step)
            params = self.controller.current_params
            for key, value in params.physics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"randomization_physics_{key}", value, step=self._step)
            for key, value in params.visual.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"randomization_visual_{key}", value, step=self._step)
            for key, value in params.dynamics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"randomization_dynamics_{key}", value, step=self._step)

    def _on_training_end(self) -> None:
        """End MLflow run."""
        try:
            import mlflow
        except ImportError:
            return
        mlflow.end_run()
