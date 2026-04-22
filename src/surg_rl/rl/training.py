"""RL training pipeline with Stable-Baselines3 integration.

This module provides the training infrastructure for RL agents,
including training loop management, hyperparameter configuration,
checkpoint management, and evaluation utilities.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import numpy as np

import gymnasium as gym

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
    policy_kwargs: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
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
    tensorboard_log: Optional[str] = None
    save_freq: int = 50_000
    eval_freq: int = 10_000
    n_eval_episodes: int = 10
    verbose: int = 1
    max_episode_steps: int = 1000
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    enable_tensorboard: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for k, v in self.__dict__.items():
            if k == "algorithm":
                result[k] = v.to_dict()
            elif v is not None:
                result[k] = v
        return result

    def save(self, path: Union[str, Path]) -> None:
        """Save configuration to JSON file.

        Args:
            path: Path to save the configuration.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "TrainingConfig":
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

    def __init__(self, config: Optional[TrainingConfig] = None):
        """Initialize the training manager.

        Args:
            config: Training configuration. Uses defaults if None.
        """
        self.config = config or TrainingConfig()
        self._model = None
        self._env = None
        self._eval_env = None
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
            import stable_baselines3
        except ImportError:
            raise ImportError(
                "stable-baselines3 is required for training. "
                "Install it with: pip install stable-baselines3"
            )

        algo_name = self.config.algorithm.name.upper()
        if algo_name == "PPO":
            from stable_baselines3 import PPO
            return PPO
        elif algo_name == "SAC":
            from stable_baselines3 import SAC
            return SAC
        elif algo_name == "TD3":
            from stable_baselines3 import TD3
            return TD3
        elif algo_name == "DDPG":
            from stable_baselines3 import DDPG
            return DDPG
        elif algo_name == "A2C":
            from stable_baselines3 import A2C
            return A2C
        else:
            raise ValueError(
                f"Unknown algorithm: {algo_name}. "
                f"Supported: {list(self.ALGORITHM_MAP.keys())}"
            )

    def _create_environment(self):
        """Create the training environment.

        Returns:
            Gymnasium environment.
        """
        from .environment import SurgicalEnv, SurgicalEnvConfig
        from .observation import ObservationConfig, ObservationType
        from .action import ActionConfig, ActionType

        config = SurgicalEnvConfig(
            scene_path=self.config.scene_path,
            max_episode_steps=self.config.max_episode_steps,
            seed=self.config.seed,
            use_curriculum=self.config.use_curriculum,
            use_adaptive_difficulty=self.config.use_adaptive_difficulty,
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
        if hasattr(env, "observation_space") and isinstance(
            env.observation_space, gym.spaces.Dict
        ):
            policy_type = "MultiInputPolicy"

        # Create model with common parameters
        common_kwargs = {
            "policy": policy_type,
            "env": env,
            "learning_rate": algo_config.learning_rate,
            "gamma": algo_config.gamma,
            "verbose": self.config.verbose,
            "seed": self.config.seed,
            "device": self.config.device,
            "policy_kwargs": policy_kwargs,
        }

        if self.config.enable_tensorboard:
            common_kwargs["tensorboard_log"] = (
                self.config.tensorboard_log or self.config.log_dir
            )

        # Algorithm-specific parameters
        if algo_config.name.upper() in ("PPO", "A2C"):
            common_kwargs.update({
                "n_steps": algo_config.n_steps,
                "batch_size": algo_config.batch_size,
                "n_epochs": algo_config.n_epochs,
                "gae_lambda": algo_config.gae_lambda,
                "clip_range": algo_config.clip_range,
                "ent_coef": algo_config.ent_coef,
                "vf_coef": algo_config.vf_coef,
                "max_grad_norm": algo_config.max_grad_norm,
            })
        elif algo_config.name in ("SAC", "TD3", "DDPG"):
            common_kwargs.update({
                "buffer_size": algo_config.buffer_size,
                "learning_starts": algo_config.learning_starts,
                "batch_size": algo_config.batch_size,
                "tau": algo_config.tau,
                "train_freq": algo_config.train_freq,
                "gradient_steps": algo_config.gradient_steps,
            })

        model = algo_class(**common_kwargs)
        return model

    def train(
        self,
        callback: Optional[Any] = None,
        log_dir: Optional[str] = None,
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
        tb_log = self.config.tensorboard_log or log_dir

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

    def evaluate(
        self,
        model_path: Optional[str] = None,
        n_episodes: int = 10,
        render: bool = False,
    ) -> Dict[str, Any]:
        """Evaluate a trained model.

        Args:
            model_path: Path to saved model. Uses current model if None.
            n_episodes: Number of evaluation episodes.
            render: Whether to render during evaluation.

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

        # Create eval environment
        eval_env = self._create_environment()

        # Run evaluation
        episode_rewards = []
        episode_lengths = []
        episode_successes = []

        for episode in range(n_episodes):
            obs, info = eval_env.reset()
            total_reward = 0.0
            steps = 0
            done = False

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = eval_env.step(action)
                total_reward += reward
                steps += 1
                done = terminated or truncated

                if render:
                    eval_env.render()

            episode_rewards.append(total_reward)
            episode_lengths.append(steps)
            episode_successes.append(info.get("task_success", False))

        eval_env.close()

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

    def save_model(self, path: Optional[str] = None) -> str:
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
