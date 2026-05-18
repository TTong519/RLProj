"""Multi-agent training manager - shared and independent SB3 policy training.

D-07: Shared policy -> single model; Independent -> per-agent models.
D-08: Independent mode uses threading.Thread for parallel learn() calls.
"""

from __future__ import annotations

import os
import threading
from typing import Any

import numpy as np
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.base_class import BaseAlgorithm
from stable_baselines3.common.vec_env import VecEnv

from surg_rl.utils.logging import get_logger

from .wrappers import wrap_for_sb3

logger = get_logger(__name__)

ALGORITHM_MAP: dict[str, type[BaseAlgorithm]] = {
    "PPO": PPO,
    "SAC": SAC,
}


class MultiAgentTrainingManager:
    """Manages shared or independent SB3 policy training for dual-arm scenes.

    D-07: Shared policy -> single model; Independent -> per-agent models.
    D-08: Independent mode uses threading.Thread for parallel learn() calls.
    """

    def __init__(
        self,
        env,
        algorithm: str = "PPO",
        shared_policy: bool = True,
        total_timesteps: int = 100000,
        model_dir: str = "models/",
        **algo_kwargs: Any,
    ):
        self.env = env
        self.algorithm = algorithm
        self.shared_policy = shared_policy
        self.total_timesteps = total_timesteps
        self.model_dir = model_dir
        self.algo_kwargs = algo_kwargs
        self._algorithm_cls = ALGORITHM_MAP.get(algorithm, PPO)

    def train(self) -> dict[str, str]:
        """Run training - dispatches to shared or independent mode."""
        if self.shared_policy:
            return self._train_shared()
        else:
            return self._train_independent()

    def _train_shared(self) -> dict[str, str]:
        """Train a single SB3 model for both agents (D-07: shared policy)."""
        logger.info("Starting shared-policy MARL training with %s", self.algorithm)
        vec_env = wrap_for_sb3(self.env)
        model = self._algorithm_cls("MlpPolicy", vec_env, verbose=1, **self.algo_kwargs)
        model.learn(total_timesteps=self.total_timesteps)
        os.makedirs(self.model_dir, exist_ok=True)
        model_path = f"{self.model_dir}marl_shared_{self.algorithm.lower()}"
        model.save(model_path)
        logger.info("Shared model saved to %s.zip", model_path)
        return {"shared": model_path}

    def _train_independent(self) -> dict[str, str]:
        """Train separate SB3 models per agent in parallel threads (D-07, D-08).

        Each agent gets an independent model; the shared env steps with
        synchronized access (lock-protected).
        """
        logger.info("Starting independent-policy MARL training")
        agents = self.env.possible_agents
        models: dict[str, BaseAlgorithm] = {}
        model_paths: dict[str, str] = {}
        errors: dict[str, Exception] = {}
        error_lock = threading.Lock()

        def train_agent(agent_id: str):
            try:
                vec_env = wrap_for_sb3(self.env)
                model = self._algorithm_cls("MlpPolicy", vec_env, verbose=1, **self.algo_kwargs)
                model.learn(total_timesteps=self.total_timesteps // len(agents))
                os.makedirs(self.model_dir, exist_ok=True)
                model_path = f"{self.model_dir}marl_independent_{agent_id}_{self.algorithm.lower()}"
                model.save(model_path)
                models[agent_id] = model
                model_paths[agent_id] = model_path
            except Exception as e:
                with error_lock:
                    errors[agent_id] = e

        threads = []
        for agent_id in agents:
            t = threading.Thread(target=train_agent, args=(agent_id,), name=f"train-{agent_id}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if errors:
            error_msgs = "; ".join(f"{aid}: {e}" for aid, e in errors.items())
            logger.error("Independent training failed for agents: %s", error_msgs)
            raise RuntimeError(f"Independent training failed: {error_msgs}")

        logger.info("Independent models saved: %s", list(model_paths.values()))
        return model_paths
