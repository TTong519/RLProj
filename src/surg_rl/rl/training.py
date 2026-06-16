"""RL training pipeline with Stable-Baselines3 integration.

This module provides the training infrastructure for RL agents,
including training loop management, hyperparameter configuration,
checkpoint management, and evaluation utilities.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np

from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.utils.gpu import get_torch_device
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Training Configuration
# ============================================================================


@dataclass
class AlgorithmConfig:
    """Configuration for an RL algorithm.

    Attributes:
        name: Algorithm name ('PPO', 'SAC', 'TD3', 'DDPG', 'A2C').
        learning_rate: Learning rate.
        n_steps: Number of steps per rollout (PPO/A2C).
        batch_size: Mini-batch size.
        n_epochs: Number of epochs per update (PPO).
        gamma: Discount factor.
        gae_lambda: GAE lambda (PPO/A2C).
        clip_range: PPO clipping range.
        ent_coef: Entropy coefficient.
        vf_coef: Value function coefficient.
        max_grad_norm: Maximum gradient norm.
        buffer_size: Replay buffer size (SAC/TD3/DDPG).
        learning_starts: Steps before learning starts (SAC/TD3/DDPG).
        tau: Target network update rate (SAC/TD3/DDPG).
        train_freq: Update frequency (SAC/TD3/DDPG).
        gradient_steps: Number of gradient steps per update.
        policy_kwargs: Additional policy network arguments.
    """

    name: str = "PPO"
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    buffer_size: int = 1_000_000
    learning_starts: int = 100
    tau: float = 0.005
    train_freq: int = 1
    gradient_steps: int = 1
    policy_kwargs: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                result[k] = v
        return result


@dataclass
class TrainingConfig:
    """Configuration for the training run.

    Attributes:
        scene_path: Path to scene definition file.
        algorithm: Algorithm configuration.
        total_timesteps: Total training timesteps.
        n_envs: Number of parallel environments.
        seed: Random seed.
        device: Device for training ('auto', 'cpu', 'cuda', 'mps').
        log_dir: Directory for logs and checkpoints.
        tensorboard_log: TensorBoard log directory.
        save_freq: Checkpoint save frequency (in steps).
        eval_freq: Evaluation frequency (in steps).
        n_eval_episodes: Number of evaluation episodes.
        verbose: Verbosity level (0=silent, 1=info, 2=debug).
        max_episode_steps: Maximum steps per episode.
        use_curriculum: Whether to use curriculum learning.
        use_adaptive_difficulty: Whether to use adaptive difficulty.
        enable_tensorboard: Whether to enable TensorBoard logging.
    """

    scene_path: str = "scenes/simple_suturing.json"
    algorithm: AlgorithmConfig = field(default_factory=AlgorithmConfig)
    total_timesteps: int = 1_000_000
    n_envs: int = 1
    seed: int = 42
    device: str = "auto"
    log_dir: str = "logs/training"
    tensorboard_log: str | None = None
    save_freq: int = 50_000
    eval_freq: int = 10_000
    n_eval_episodes: int = 10
    verbose: int = 1
    max_episode_steps: int = 1000
    simulator: str = "mujoco"
    render_mode: str | None = None
    render_fps: float = 30.0
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    enable_tensorboard: bool = False
    use_wandb: bool = False
    use_mlflow: bool = False
    experiment_name: str | None = None
    wandb_project: str | None = None
    backend: HardwareBackend = HardwareBackend.auto

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for k, v in self.__dict__.items():
            if k == "algorithm":
                result[k] = v.to_dict()
            elif k == "backend":
                result[k] = v.value
            elif v is not None:
                result[k] = v
        return result

    def save(self, path: str | Path) -> None:
        """Save configuration to JSON file.

        Args:
            path: Path to save the configuration.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> "TrainingConfig":
        """Load configuration from JSON file.

        Args:
            path: Path to the configuration file.

        Returns:
            TrainingConfig instance.
        """
        with open(path) as f:
            data = json.load(f)

        algo_data = data.pop("algorithm", {})
        algorithm = AlgorithmConfig(**algo_data)
        return cls(algorithm=algorithm, **data)


# ============================================================================
# Training Manager
# ============================================================================


class TrainingManager:
    """Manager for RL training runs.

    Handles environment creation, algorithm selection, training loop,
    checkpoint management, and evaluation.

    Example:
        >>> config = TrainingConfig(
        ...     scene_path="scenes/suturing.json",
        ...     total_timesteps=100000,
        ...     algorithm=AlgorithmConfig(name="PPO"),
        ... )
        >>> manager = TrainingManager(config)
        >>> model = manager.train()
    """

    # Mapping of algorithm names to SB3 classes
    ALGORITHM_MAP = {
        "PPO": "stable_baselines3.PPO",
        "SAC": "stable_baselines3.SAC",
        "TD3": "stable_baselines3.TD3",
        "DDPG": "stable_baselines3.DDPG",
        "A2C": "stable_baselines3.A2C",
    }

    def __init__(self, config: TrainingConfig | None = None):
        """Initialize the training manager.

        Args:
            config: Training configuration. Uses defaults if None.
        """
        self.config = config or TrainingConfig()
        self._model = None
        self._env = None
        self._eval_env = None
        self._eval_env_key = ""
        self._start_time = None
        self._total_steps = 0

    def _get_algorithm_class(self):
        """Get the SB3 algorithm class.

        Returns:
            Algorithm class from stable_baselines3.

        Raises:
            ImportError: If stable_baselines3 is not installed.
            ValueError: If algorithm name is not recognized.
        """
        try:
            import importlib
            import importlib.util

            if importlib.util.find_spec("stable_baselines3") is None:
                raise ImportError(
                    "stable-baselines3 is required for training. "
                    "Install it with: pip install stable-baselines3"
                )
        except ImportError as exc:
            raise ImportError(
                "stable-baselines3 is required for training. "
                "Install it with: pip install stable-baselines3"
            ) from exc

        algo_name = self.config.algorithm.name.upper()
        try:
            module_name, class_name = self.ALGORITHM_MAP[algo_name].rsplit(".", 1)
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except KeyError as exc:
            raise ValueError(
                f"Unknown algorithm: {algo_name}. " f"Supported: {list(self.ALGORITHM_MAP.keys())}"
            ) from exc
        except ImportError as exc:
            raise ImportError(
                f"Algorithm {algo_name} import failed. "
                "Ensure stable-baselines3 is installed: pip install stable-baselines3"
            ) from exc

    def _create_environment(self):
        """Create the training environment.

        Returns:
            Gymnasium environment or SB3 vectorized environment.
        """
        from .environment import make_vec_env

        if self.config.n_envs > 1:
            return make_vec_env(
                scene_path=self.config.scene_path,
                n_envs=self.config.n_envs,
                seed=self.config.seed,
                max_episode_steps=self.config.max_episode_steps,
                simulator_type=self.config.simulator,
                use_curriculum=self.config.use_curriculum,
                use_adaptive_difficulty=self.config.use_adaptive_difficulty,
                render_mode=self.config.render_mode,
                render_fps=self.config.render_fps,
            )

        from .environment import SurgicalEnv, SurgicalEnvConfig

        config = SurgicalEnvConfig(
            scene_path=self.config.scene_path,
            max_episode_steps=self.config.max_episode_steps,
            simulator_type=self.config.simulator,
            seed=self.config.seed,
            use_curriculum=self.config.use_curriculum,
            use_adaptive_difficulty=self.config.use_adaptive_difficulty,
            render_mode=self.config.render_mode,
            render_fps=self.config.render_fps,
        )
        return SurgicalEnv(config)

    def _create_model(self, env):
        """Create the RL model.

        Args:
            env: Training environment.

        Returns:
            SB3 model instance.
        """
        algo_class = self._get_algorithm_class()
        algo_config = self.config.algorithm

        # Build policy kwargs
        policy_kwargs = algo_config.policy_kwargs or {}
        if not policy_kwargs.get("net_arch"):
            policy_kwargs["net_arch"] = [256, 256]

        # Select policy type based on observation space
        policy_type = "MlpPolicy"
        if hasattr(env, "observation_space") and isinstance(env.observation_space, gym.spaces.Dict):
            policy_type = "MultiInputPolicy"

        # Create model with common parameters
        resolved_device = get_torch_device(self.config.device)

        common_kwargs = {
            "policy": policy_type,
            "env": env,
            "learning_rate": algo_config.learning_rate,
            "gamma": algo_config.gamma,
            "verbose": self.config.verbose,
            "seed": self.config.seed,
            "device": resolved_device,
            "policy_kwargs": policy_kwargs,
        }

        if self.config.enable_tensorboard:
            common_kwargs["tensorboard_log"] = self.config.tensorboard_log or self.config.log_dir

        # Algorithm-specific parameters
        if algo_config.name.upper() in ("PPO", "A2C"):
            common_kwargs.update(
                {
                    "n_steps": algo_config.n_steps,
                    "batch_size": algo_config.batch_size,
                    "n_epochs": algo_config.n_epochs,
                    "gae_lambda": algo_config.gae_lambda,
                    "clip_range": algo_config.clip_range,
                    "ent_coef": algo_config.ent_coef,
                    "vf_coef": algo_config.vf_coef,
                    "max_grad_norm": algo_config.max_grad_norm,
                }
            )
        elif algo_config.name.upper() in ("SAC", "TD3", "DDPG"):
            common_kwargs.update(
                {
                    "buffer_size": algo_config.buffer_size,
                    "learning_starts": algo_config.learning_starts,
                    "batch_size": algo_config.batch_size,
                    "tau": algo_config.tau,
                    "train_freq": algo_config.train_freq,
                    "gradient_steps": algo_config.gradient_steps,
                }
            )

        model = algo_class(**common_kwargs)
        return model

    def train(
        self,
        callback: Any | None = None,
        log_dir: str | None = None,
        reset_num_timesteps: bool = True,
    ):
        """Run the training loop.

        Args:
            callback: Callback for training events.
            log_dir: Directory for TensorBoard logs.
            reset_num_timesteps: Whether to reset timestep counter.

        Returns:
            Trained model.
        """
        log_dir = log_dir or self.config.log_dir
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        # Save configuration
        self.config.save(Path(log_dir) / "training_config.json")

        # Create environment
        logger.info(f"Creating environment from scene: {self.config.scene_path}")
        self._env = self._create_environment()

        # Create model
        logger.info(f"Creating {self.config.algorithm.name} model")
        self._model = self._create_model(self._env)

        # Setup TensorBoard logging

        # Import checkpoint callback
        from .callbacks import CheckpointCallback, TrainingProgressCallback

        # Create callbacks
        callbacks = []
        if callback is not None:
            callbacks.append(callback)

        # Checkpoint callback
        checkpoint_callback = CheckpointCallback(
            save_freq=self.config.save_freq,
            save_path=str(Path(log_dir) / "checkpoints"),
            name_prefix=f"surg_rl_{self.config.algorithm.name.lower()}",
        )
        callbacks.append(checkpoint_callback)

        # Progress callback
        progress_callback = TrainingProgressCallback(
            verbose=self.config.verbose,
        )
        callbacks.append(progress_callback)

        # TensorBoard callback
        if self.config.enable_tensorboard:
            from .callbacks import TensorBoardCallback

            tb_callback = TensorBoardCallback(
                controller=getattr(self._env, "controller", None),
                log_interval=100,
                verbose=self.config.verbose,
            )
            callbacks.append(tb_callback)

        # W&B callback
        if self.config.use_wandb:
            from surg_rl.utils.config import get_settings

            from .callbacks import WandbCallback

            wandb_callback = WandbCallback(
                project_name=self.config.wandb_project,
                experiment_name=self.config.experiment_name,
                wandb_api_key=get_settings().wandb_api_key,
                controller=getattr(self._env, "controller", None),
                verbose=self.config.verbose,
            )
            callbacks.append(wandb_callback)

        # MLflow callback
        if self.config.use_mlflow:
            from surg_rl.utils.config import get_settings

            from .callbacks import MLflowCallback

            mlflow_callback = MLflowCallback(
                experiment_name=self.config.experiment_name,
                tracking_uri=get_settings().mlflow_tracking_uri,
                controller=getattr(self._env, "controller", None),
                verbose=self.config.verbose,
            )
            callbacks.append(mlflow_callback)

        # Combine callbacks
        from stable_baselines3.common.callbacks import CallbackList

        callback_list = CallbackList(callbacks)

        # Train
        logger.info(
            f"Starting training: {self.config.total_timesteps:,} steps "
            f"with {self.config.algorithm.name}"
        )
        self._start_time = time.time()

        try:
            self._model.learn(
                total_timesteps=self.config.total_timesteps,
                callback=callback_list,
                log_interval=100,
                tb_log_name=f"surg_rl_{self.config.algorithm.name.lower()}",
                reset_num_timesteps=reset_num_timesteps,
                progress_bar=self.config.verbose >= 2,
            )
        except KeyboardInterrupt:
            logger.info("Training interrupted by user")
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

        # Save final model
        final_path = Path(log_dir) / "final_model"
        self._model.save(str(final_path))
        logger.info(f"Final model saved to: {final_path}")

        # Log training summary
        elapsed = time.time() - self._start_time
        logger.info(
            f"Training completed in {elapsed:.1f}s "
            f"({self.config.total_timesteps / elapsed:.0f} steps/s)"
        )

        return self._model

    def _build_eval_env_key(self) -> str:
        """Build a stable key representing current eval env configuration."""
        algo = self.config.algorithm
        return (
            f"{self.config.scene_path}:"
            f"{self.config.simulator}:"
            f"{algo.name}:"
            f"{algo.learning_rate}:"
            f"{algo.gamma}:"
            f"{self.config.n_envs}:"
            f"{self.config.max_episode_steps}:"
            f"{self.config.seed}:"
            f"{self.config.use_curriculum}:"
            f"{self.config.use_adaptive_difficulty}"
        )

    def evaluate(
        self,
        model_path: str | None = None,
        n_episodes: int = 10,
        render: bool = False,
    ) -> dict[str, Any]:
        """Evaluate a trained model.

        Args:
            model_path: Path to saved model. Uses current model if None.
            n_episodes: Number of evaluation episodes.
            render: If True, the eval environment is created with
                ``render_mode="human"`` (a MuJoCo passive viewer in a
                background thread). If False, the env uses whatever
                ``render_mode`` is set on ``self.config`` (default: headless).

        Returns:
            Dictionary with evaluation results.
        """
        # Load model if path provided
        if model_path is not None:
            algo_class = self._get_algorithm_class()
            model = algo_class.load(model_path)
        elif self._model is not None:
            model = self._model
        else:
            raise ValueError("No model available. Provide model_path or train first.")

        # Honor the `render` flag by temporarily switching the config's
        # render_mode to "human" for the eval env. We save and restore so
        # subsequent train() calls are unaffected.
        original_render_mode = self.config.render_mode
        if render:
            self.config.render_mode = "human"
        try:
            # Determine if we can reuse cached eval env
            current_key = self._build_eval_env_key()
            if self._eval_env is not None and self._eval_env_key == current_key:
                eval_env = self._eval_env
                try:
                    eval_env.reset()
                except Exception:
                    pass
            else:
                # Cache mismatch — dispose old and create new
                if self._eval_env is not None:
                    self._eval_env.close()
                eval_env = self._create_environment()
                self._eval_env = eval_env
                self._eval_env_key = current_key
        finally:
            self.config.render_mode = original_render_mode

        # Run evaluation
        episode_rewards = []
        episode_lengths = []
        episode_successes = []

        is_vec_env = hasattr(eval_env, "num_envs")

        for _episode in range(n_episodes):
            reset_result = eval_env.reset()
            if is_vec_env:
                # VecEnv reset() may return just obs, or (obs, info)
                if isinstance(reset_result, tuple):
                    obs, info = reset_result
                else:
                    obs = reset_result
                    info = {}
            else:
                obs, info = reset_result

            total_reward = 0.0
            steps = 0
            done = False

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                step_result = eval_env.step(action)
                if is_vec_env:
                    # VecEnv step() returns (obs, reward, done, info) where info is list[dict]
                    obs, reward, done_flag, info = step_result
                    terminated = done_flag
                    truncated = False
                    done = bool(done_flag.any()) if hasattr(done_flag, "any") else bool(done_flag)
                    total_reward += float(reward.sum()) if hasattr(reward, "sum") else float(reward)
                else:
                    obs, reward, terminated, truncated, info = step_result
                    done = terminated or truncated
                    total_reward += float(reward)

                steps += 1

                if render:
                    eval_env.render()

            episode_rewards.append(total_reward)
            episode_lengths.append(steps)
            # info may be a list of dicts for VecEnv; extract success from first env or dict
            if isinstance(info, list) and len(info) > 0 and isinstance(info[0], dict):
                episode_successes.append(info[0].get("task_success", False))
            elif isinstance(info, dict):
                episode_successes.append(info.get("task_success", False))
            else:
                episode_successes.append(False)

        # Compute statistics
        results = {
            "n_episodes": n_episodes,
            "mean_reward": float(np.mean(episode_rewards)),
            "std_reward": float(np.std(episode_rewards)),
            "max_reward": float(np.max(episode_rewards)),
            "min_reward": float(np.min(episode_rewards)),
            "mean_episode_length": float(np.mean(episode_lengths)),
            "success_rate": float(np.mean(episode_successes)),
            "episode_rewards": episode_rewards,
            "episode_lengths": episode_lengths,
        }

        logger.info(
            f"Evaluation: mean_reward={results['mean_reward']:.2f} "
            f"+/- {results['std_reward']:.2f}, "
            f"success_rate={results['success_rate']:.2%}"
        )

        return results

    def load_model(self, path: str):
        """Load a trained model.

        Args:
            path: Path to saved model.
        """
        algo_class = self._get_algorithm_class()
        self._model = algo_class.load(path)

    def save_model(self, path: str | None = None) -> str:
        """Save the current model.

        Args:
            path: Save path. Uses log_dir if None.

        Returns:
            Path where model was saved.
        """
        if self._model is None:
            raise ValueError("No model to save. Train or load first.")

        path = path or str(Path(self.config.log_dir) / "model")
        self._model.save(path)
        logger.info(f"Model saved to: {path}")
        return path

    def close(self) -> None:
        """Clean up resources."""
        if self._env is not None:
            self._env.close()
        if self._eval_env is not None:
            self._eval_env.close()
            self._eval_env = None
            self._eval_env_key = ""
