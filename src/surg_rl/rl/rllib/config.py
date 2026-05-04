"""RLlib configuration dataclass.

Maps :class:`~surg_rl.rl.training.TrainingConfig` / :class:`~surg_rl.rl.training.AlgorithmConfig`
to Ray RLlib ``AlgorithmConfig`` objects.  The dataclass itself is importable without
Ray installed — only :meth:`build_rllib_config` triggers the import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


def _mps_available() -> bool:
    """Check if Apple Metal MPS is available."""
    try:
        import torch

        return bool(torch.backends.mps.is_available())
    except Exception:
        return False


@dataclass
class RllibConfig:
    """Configuration that bridges ``TrainingConfig`` → RLlib ``AlgorithmConfig``.

    Defaults are chosen for quick surgical-RL experiments.  Callers should
    override ``env_config`` with scene-specific values.

    Attributes:
        env_name: Name passed to ``register_env`` (default ``"surg-rl"``).
        env_config: Dict forwarded to :func:`.env_wrapper.make_surgical_env`.
        algorithm: ``"PPO"`` or ``"SAC"``.
        framework: Always ``"torch"``.
        num_env_runners: Number of RLlib env runner processes.
        num_learners: Number of remote GPU learners (``0`` = local learner).
        num_gpus_per_learner: GPUs per learner (``0`` = CPU).
        train_batch_size_per_learner: Batch size sampled per learner.
        lr: Learning rate.
        gamma: Discount factor.
        lambda_: GAE lambda (PPO only).
        clip_param: PPO clipping range.
        num_epochs: PPO epochs per update.
        entropy_coeff: Entropy regularisation coefficient.
        vf_loss_coeff: Value-loss coefficient.
        total_timesteps: Total env steps budget (not passed to RLlib directly; used
            for a stop criterion).
        seed: Random seed.
        save_dir: Directory for checkpoints / logs.
        checkpoint_freq: Save checkpoint every *N* timesteps.
    """

    env_name: str = "surg-rl"
    env_config: dict[str, Any] = field(default_factory=dict)
    algorithm: str = "PPO"  # noqa: S105
    framework: str = "torch"
    num_env_runners: int = 0
    num_learners: int = 0
    num_gpus_per_learner: float = 0.0
    train_batch_size_per_learner: int = 4000
    lr: float = 3e-4
    gamma: float = 0.99
    lambda_: float = 0.95
    clip_param: float = 0.2
    num_epochs: int = 10
    entropy_coeff: float = 0.01
    vf_loss_coeff: float = 0.5
    total_timesteps: int = 1_000_000
    seed: int | None = None
    save_dir: str | None = None
    checkpoint_freq: int = 50_000

    # ------------------------------------------------------------------ #
    # Factory methods
    # ------------------------------------------------------------------ #

    @classmethod
    def from_training_config(
        cls,
        training_config: "surg_rl.rl.training.TrainingConfig",
        env_config: dict[str, Any] | None = None,
    ) -> "RllibConfig":
        """Build from an existing :class:`TrainingConfig`.

        GPU distribution is auto-detected via ``torch.cuda.device_count()``.
        """
        import torch

        gpu_count = torch.cuda.device_count()
        if gpu_count >= 2:
            num_learners = gpu_count
            num_gpus_per_learner = 1.0
        elif gpu_count == 1:
            num_learners = 0
            num_gpus_per_learner = 1.0
        elif _mps_available():
            logger.info(
                "Metal MPS detected — using local learner "
                "(distributed MPS not yet supported by Ray)"
            )
            num_learners = 0
            num_gpus_per_learner = 0.0
        else:
            num_learners = 0
            num_gpus_per_learner = 0.0

        algo = training_config.algorithm
        rllib_env_cfg = env_config or {}
        if training_config.scene_path:
            rllib_env_cfg.setdefault("scene_path", training_config.scene_path)
        if training_config.simulator:
            rllib_env_cfg.setdefault("simulator_type", training_config.simulator)
        if training_config.seed is not None:
            rllib_env_cfg.setdefault("seed", training_config.seed)

        return cls(
            env_name="surg-rl",
            env_config=rllib_env_cfg,
            algorithm=algo.name,
            num_env_runners=max(0, training_config.n_envs - 1),
            num_learners=num_learners,
            num_gpus_per_learner=num_gpus_per_learner,
            train_batch_size_per_learner=max(
                1, algo.n_steps * training_config.n_envs
            ),
            lr=algo.learning_rate,
            gamma=algo.gamma,
            lambda_=algo.gae_lambda,
            clip_param=algo.clip_range,
            num_epochs=algo.n_epochs,
            entropy_coeff=algo.ent_coef,
            vf_loss_coeff=algo.vf_coef,
            total_timesteps=training_config.total_timesteps,
            seed=training_config.seed,
            save_dir=training_config.log_dir,
            checkpoint_freq=training_config.save_freq,
        )

    # ------------------------------------------------------------------ #
    # Build RLlib AlgorithmConfig
    # ------------------------------------------------------------------ #

    def build_rllib_config(self) -> Any:
        """Return an RLlib ``AlgorithmConfig`` configured for this run.

        Lazy-imports Ray so that importing :mod:`surg_rl.rl.rllib` does
        **not** require Ray to be installed.
        """
        from ray.rllib.algorithms.ppo import PPOConfig
        from ray.rllib.algorithms.sac import SACConfig

        algo_cls = PPOConfig if self.algorithm.upper() == "PPO" else SACConfig

        config = (
            algo_cls()
            .environment(self.env_name, env_config=self.env_config)
            .framework(self.framework)
            .env_runners(num_env_runners=max(0, self.num_env_runners))
            .learners(
                num_learners=self.num_learners,
                num_gpus_per_learner=self.num_gpus_per_learner,
            )
        )

        training_kwargs: dict[str, Any] = {
            "lr": self.lr,
            "gamma": self.gamma,
            "train_batch_size_per_learner": self.train_batch_size_per_learner,
        }

        if self.algorithm.upper() == "PPO":
            training_kwargs.update(
                {
                    "lambda_": self.lambda_,
                    "clip_param": self.clip_param,
                    "num_epochs": self.num_epochs,
                    "entropy_coeff": self.entropy_coeff,
                    "vf_loss_coeff": self.vf_loss_coeff,
                }
            )

        return config.training(**training_kwargs)

    def build_stop_criteria(self) -> dict[str, Any]:
        """Return a ``tune.run`` stop dict derived from ``total_timesteps``.

        RLlib 2.55+ tracks lifetime steps via
        ``num_env_steps_sampled_lifetime``.
        """
        return {
            "num_env_steps_sampled_lifetime": self.total_timesteps,
        }
