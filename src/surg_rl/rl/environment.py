"""Gymnasium environment wrapper for surgical robotics RL training.

This module provides the SurgicalEnv class, a Gymnasium-compatible
environment that wraps the simulator and dynamic environment controller
into a standard interface for RL training with Stable-Baselines3.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import gymnasium as gym
import numpy as np

from surg_rl.scene_definition.schema import SceneDefinition
from surg_rl.scene_definition.loader import SceneLoader
from surg_rl.simulators.base_simulator import BaseSimulator, Observation, StepResult
from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
from surg_rl.simulators.pybullet_simulator import PyBulletSimulator
from surg_rl.dynamics.environment_controller import EnvironmentController, EnvironmentControllerConfig
from surg_rl.utils.logging import get_logger

from .observation import (
    ObservationBuilder,
    ObservationConfig,
    ObservationType,
    ObservationSpec,
)
from .action import (
    ActionScaling,
    ActionBuilder,
    ActionConfig,
    ActionType,
)
from .rewards import (
    BaseRewardFunction,
    CompositeReward,
    RewardConfig,
    RewardResult,
    create_default_reward,
)

logger = get_logger(__name__)


@dataclass
class SurgicalEnvConfig:
    """Configuration for the SurgicalEnv environment.

    Attributes:
        scene_path: Path to the scene definition file.
        scene: Scene definition object (alternative to scene_path).
        simulator_type: Simulator backend to use ('mujoco' or 'pybullet').
        timestep: Simulation timestep in seconds.
        frame_skip: Number of simulation steps per environment step.
        max_episode_steps: Maximum steps per episode before truncation.
        render_mode: Rendering mode ('human', 'rgb_array', None).
        reward_config: Reward function configuration.
        observation_config: Observation space configuration.
        action_config: Action space configuration.
        use_curriculum: Whether to use curriculum learning.
        use_adaptive_difficulty: Whether to use adaptive difficulty.
        controller_config: Environment controller configuration.
        seed: Random seed for reproducibility.
    """

    scene_path: Optional[str] = None
    scene: Optional[SceneDefinition] = None
    simulator_type: str = "mujoco"
    timestep: float = 0.002
    frame_skip: int = 1
    max_episode_steps: int = 1000
    render_mode: Optional[str] = None
    reward_config: Optional[RewardConfig] = None
    observation_config: Optional[ObservationConfig] = None
    action_config: Optional[ActionConfig] = None
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    controller_config: Optional[EnvironmentControllerConfig] = None
    seed: Optional[int] = None


class SurgicalEnv(gym.Env):
    """Gymnasium environment for surgical robotics RL training.

    This environment wraps the simulator and dynamic environment controller
    into a standard Gymnasium interface compatible with Stable-Baselines3.

    The environment supports:
    - Multiple simulator backends (MuJoCo, PyBullet)
    - Configurable observation and action spaces
    - Custom reward functions
    - Domain randomization
    - Curriculum learning
    - Adaptive difficulty

    Example:
        >>> from surg_rl.rl import SurgicalEnv, SurgicalEnvConfig
        >>> config = SurgicalEnvConfig(scene_path="scenes/suturing.json")
        >>> env = SurgicalEnv(config)
        >>> obs, info = env.reset()
        >>> for _ in range(100):
        ...     action = env.action_space.sample()
        ...     obs, reward, terminated, truncated, info = env.step(action)
        ...     if terminated or truncated:
        ...         obs, info = env.reset()
        >>> env.close()
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(
        self,
        config: Optional[SurgicalEnvConfig] = None,
        render_mode: Optional[str] = None,
    ):
        """Initialize the surgical environment.

        Args:
            config: Environment configuration. Uses defaults if None.
            render_mode: Rendering mode override.
        """
        super().__init__()

        self.config = config or SurgicalEnvConfig()
        self.render_mode = render_mode or self.config.render_mode

        # Load scene
        self._scene = self._load_scene()

        # Initialize simulator
        self._simulator = self._create_simulator()
        self._simulator.load_scene(self._scene)

        # Initialize observation and action builders
        self._obs_builder = ObservationBuilder(
            config=self.config.observation_config
            or self._default_observation_config()
        )
        self._action_builder = ActionBuilder(
            config=self.config.action_config
            or self._default_action_config()
        )

        # Define spaces
        self.observation_space = self._obs_builder.get_observation_space()
        self.action_space = self._action_builder.get_action_space()

        # Initialize reward function
        task_name = None
        if self._scene.task is not None:
            task_name = self._scene.task.name
        self._reward_fn = create_default_reward(self.config.reward_config, task_name=task_name)

        # Initialize environment controller
        self._controller: Optional[EnvironmentController] = None
        self._setup_controller()

        # Episode state
        self._step_count = 0
        self._episode_count = 0
        self._last_observation: Optional[Dict[str, np.ndarray]] = None
        self._target_pos: Optional[np.ndarray] = None
        self._target_quat: Optional[np.ndarray] = None

    def _load_scene(self) -> SceneDefinition:
        """Load the scene definition.

        Returns:
            SceneDefinition object.
        """
        if self.config.scene is not None:
            return self.config.scene

        if self.config.scene_path is not None:
            return SceneLoader().load(self.config.scene_path)

        # Create a minimal default scene
        logger.warning("No scene specified, using default minimal scene")
        return SceneDefinition()

    def _create_simulator(self) -> BaseSimulator:
        """Create the simulator backend.

        Returns:
            Simulator instance.
        """
        if self.config.simulator_type == "mujoco":
            return MuJoCoSimulator(
                timestep=self.config.timestep,
                frame_skip=self.config.frame_skip,
            )
        elif self.config.simulator_type == "pybullet":
            return PyBulletSimulator(
                timestep=self.config.timestep,
                frame_skip=self.config.frame_skip,
            )
        else:
            raise ValueError(
                f"Unknown simulator type: {self.config.simulator_type}. "
                f"Use 'mujoco' or 'pybullet'."
            )

    def _default_observation_config(self) -> ObservationConfig:
        """Create default observation config based on scene.

        Returns:
            ObservationConfig object.
        """
        return ObservationConfig(
            observation_types=[
                ObservationType.JOINT_POSITIONS,
                ObservationType.JOINT_VELOCITIES,
                ObservationType.ENDEFFECTOR_POS,
                ObservationType.TARGET_POS,
                ObservationType.DISTANCE_TO_TARGET,
            ],
            include_force=False,
            include_tissue=False,
            normalize=True,
            flatten=True,
        )

    def _default_action_config(self) -> ActionConfig:
        """Create default action config based on scene.

        Returns:
            ActionConfig object.
        """
        num_joints = 7  # Default 7-DOF
        if self._scene and self._scene.robots:
            # Use the first robot's joint count
            first_robot = self._scene.robots[0]
            if hasattr(first_robot, "joints") and first_robot.joints:
                num_joints = len(first_robot.joints)

        return ActionConfig(
            action_type=ActionType.JOINT_POSITIONS,
            num_joints=num_joints,
            include_gripper=True,
            scaling=ActionScaling.NORMALIZE,
        )

    def _setup_controller(self) -> None:
        """Set up the dynamic environment controller."""
        if self.config.controller_config is not None:
            self._controller = EnvironmentController(
                config=self.config.controller_config,
            )
        elif self.config.use_curriculum or self.config.use_adaptive_difficulty:
            self._controller = EnvironmentController.from_scene(
                self._scene,
                use_curriculum=self.config.use_curriculum,
                use_adaptive=self.config.use_adaptive_difficulty,
                seed=self.config.seed,
            )

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Reset the environment to initial state.

        Args:
            seed: Random seed for reproducibility.
            options: Additional reset options.

        Returns:
            Tuple of (observation, info).
        """
        super().reset(seed=seed)

        if seed is not None:
            np.random.seed(seed)

        # Reset episode state
        self._step_count = 0
        self._episode_count += 1

        # Reset reward function
        self._reward_fn.reset()

        # Reset action builder
        self._action_builder.reset()

        # Reset environment controller
        if self._controller is not None:
            params = self._controller.reset(seed=seed)
            # Apply randomized parameters to simulator
            self._controller.apply_parameters(params, self._simulator)

        # Reset simulator
        try:
            sim_obs = self._simulator.reset(seed=seed)
        except Exception as e:
            logger.warning(f"Simulator reset failed, using zero observation: {e}")
            sim_obs = Observation()

        # Set random target position for task
        self._target_pos = np.array([0.3, 0.0, 0.5]) + np.random.uniform(
            -0.1, 0.1, size=3
        )
        self._target_quat = np.array([1.0, 0.0, 0.0, 0.0])

        # Extract observation
        obs_dict = self._obs_builder.extract_observation(
            sim_obs,
            target_pos=self._target_pos,
            target_quat=self._target_quat,
        )
        self._last_observation = obs_dict

        # Build info dict
        info = self._build_info(sim_obs)

        return obs_dict, info

    def step(
        self, action: np.ndarray
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """Execute one environment step.

        Args:
            action: Action from the agent.

        Returns:
            Tuple of (observation, reward, terminated, truncated, info).
        """
        # Process action through action builder
        processed_action = self._action_builder.process_action(action)

        # Apply domain randomization noise
        if self._controller is not None:
            processed_action = self._controller.get_randomized_action(
                processed_action
            )

        # Step simulator
        try:
            step_result = self._simulator.step(processed_action)
            sim_obs = step_result.observation
            reward = step_result.reward
            terminated = step_result.terminated
            truncated = step_result.truncated
            sim_info = step_result.info
        except Exception as e:
            logger.warning(f"Simulator step failed: {e}")
            # Return terminal state
            sim_obs = Observation()
            reward = 0.0
            terminated = True
            truncated = False
            sim_info = {"error": str(e)}

        # Update step counter
        self._step_count += 1

        # Check truncation (time limit)
        if self._step_count >= self.config.max_episode_steps:
            truncated = True

        # Apply domain randomization to observation
        obs_dict = self._obs_builder.extract_observation(
            sim_obs,
            target_pos=self._target_pos,
            target_quat=self._target_quat,
        )

        # Apply observation noise
        if self._controller is not None and self.config.observation_config is not None:
            flat_obs = self._obs_builder.flatten_observation(obs_dict)
            noisy_flat = self._controller.get_randomized_observation(flat_obs)
            # Rebuild dict observation from noisy flat array
            obs_dict = self._obs_builder.unflatten_observation(noisy_flat, obs_dict)

        # Compute reward using reward function
        reward_result = self._reward_fn.compute(
            observation=obs_dict,
            action=action,
            info={
                **sim_info,
                "terminated": terminated,
                "truncated": truncated,
                "step": self._step_count,
            },
        )
        reward = reward_result.total

        # Build info dict
        info = self._build_info(sim_obs, reward_result, sim_info)
        info["terminated"] = terminated
        info["truncated"] = truncated
        info["reward_components"] = reward_result.components

        self._last_observation = obs_dict

        # Update environment controller
        if self._controller is not None:
            self._controller.step_update(self._simulator)

        return obs_dict, reward, terminated, truncated, info

    def render(self) -> Optional[np.ndarray]:
        """Render the environment.

        Returns:
            RGB image array if render_mode is 'rgb_array', None otherwise.
        """
        if self.render_mode == "rgb_array":
            return self._simulator.render(mode="rgb_array")
        elif self.render_mode == "human":
            self._simulator.render(mode="human")
            return None
        return None

    def close(self) -> None:
        """Clean up environment resources."""
        if self._simulator is not None:
            self._simulator.close()
        if self._controller is not None:
            self._controller.stop()

    def _build_info(
        self,
        sim_obs: Observation,
        reward_result: Optional[RewardResult] = None,
        sim_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the info dictionary.

        Args:
            sim_obs: Simulator observation.
            reward_result: Reward computation result.
            sim_info: Simulator info dict.

        Returns:
            Info dictionary.
        """
        info: Dict[str, Any] = {
            "step": self._step_count,
            "episode": self._episode_count,
        }

        # Add simulator info
        if sim_info:
            info.update(sim_info)

        # Add reward info
        if reward_result:
            info["reward_components"] = reward_result.components
            info["reward_info"] = reward_result.info

        # Add controller info
        if self._controller is not None:
            info["controller"] = self._controller.get_status()

        # Add target info
        if self._target_pos is not None:
            info["target_pos"] = self._target_pos

        # Add distance info
        if sim_obs.end_effector_pos is not None and self._target_pos is not None:
            info["distance_to_target"] = float(
                np.linalg.norm(sim_obs.end_effector_pos - self._target_pos)
            )

        return info

    @property
    def simulator(self) -> BaseSimulator:
        """Get the underlying simulator instance."""
        return self._simulator

    @property
    def controller(self) -> Optional[EnvironmentController]:
        """Get the environment controller instance."""
        return self._controller

    @property
    def reward_function(self) -> BaseRewardFunction:
        """Get the reward function."""
        return self._reward_fn

    @reward_function.setter
    def reward_function(self, reward_fn: BaseRewardFunction) -> None:
        """Set a custom reward function.

        Args:
            reward_fn: Custom reward function to use.
        """
        self._reward_fn = reward_fn

    def set_target(self, position: np.ndarray, orientation: Optional[np.ndarray] = None) -> None:
        """Set the target position and orientation for the task.

        Args:
            position: Target position (x, y, z).
            orientation: Target orientation as quaternion (w, x, y, z).
        """
        self._target_pos = np.array(position)
        if orientation is not None:
            self._target_quat = np.array(orientation)

    def get_state(self) -> Dict[str, Any]:
        """Get the full environment state for saving/restoring.

        Returns:
            Dictionary containing the full environment state.
        """
        state = {
            "step_count": self._step_count,
            "episode_count": self._episode_count,
            "target_pos": self._target_pos,
            "target_quat": self._target_quat,
        }

        # Save simulator state
        if self._simulator is not None:
            sim_state = self._simulator.get_state()
            state["sim_time"] = sim_state.time
            state["qpos"] = sim_state.qpos
            state["qvel"] = sim_state.qvel

        # Save controller state
        if self._controller is not None:
            state["controller"] = self._controller.get_status()

        return state

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore the environment state.

        Args:
            state: State dictionary from get_state().
        """
        self._step_count = state.get("step_count", 0)
        self._episode_count = state.get("episode_count", 0)
        self._target_pos = state.get("target_pos")
        self._target_quat = state.get("target_quat")

        # Restore simulator state
        if self._simulator is not None and "qpos" in state:
            from surg_rl.simulators.base_simulator import State

            sim_state = State(
                time=state.get("sim_time", 0.0),
                qpos=state.get("qpos"),
                qvel=state.get("qvel"),
            )
            self._simulator.set_state(sim_state)


# ============================================================================
# Environment Factory
# ============================================================================

def make_env(
    scene_path: str,
    simulator_type: str = "mujoco",
    render_mode: Optional[str] = None,
    max_episode_steps: int = 1000,
    seed: Optional[int] = None,
    use_curriculum: bool = False,
    use_adaptive_difficulty: bool = False,
    reward_config: Optional[RewardConfig] = None,
    observation_config: Optional[ObservationConfig] = None,
    action_config: Optional[ActionConfig] = None,
) -> SurgicalEnv:
    """Factory function to create a SurgicalEnv.

    Args:
        scene_path: Path to the scene definition file.
        simulator_type: Simulator backend ('mujoco' or 'pybullet').
        render_mode: Rendering mode.
        max_episode_steps: Maximum steps per episode.
        seed: Random seed.
        use_curriculum: Whether to use curriculum learning.
        use_adaptive_difficulty: Whether to use adaptive difficulty.
        reward_config: Reward configuration.
        observation_config: Observation configuration.
        action_config: Action configuration.

    Returns:
        Configured SurgicalEnv instance.
    """
    config = SurgicalEnvConfig(
        scene_path=scene_path,
        simulator_type=simulator_type,
        render_mode=render_mode,
        max_episode_steps=max_episode_steps,
        seed=seed,
        use_curriculum=use_curriculum,
        use_adaptive_difficulty=use_adaptive_difficulty,
        reward_config=reward_config,
        observation_config=observation_config,
        action_config=action_config,
    )
    return SurgicalEnv(config)


def make_vec_env(
    scene_path: str,
    n_envs: int = 1,
    simulator_type: str = "mujoco",
    seed: Optional[int] = None,
    **kwargs,
) -> gym.vector.VectorEnv:
    """Create a vectorized environment for parallel training.

    Args:
        scene_path: Path to the scene definition file.
        n_envs: Number of parallel environments.
        simulator_type: Simulator backend.
        seed: Base random seed.
        **kwargs: Additional arguments passed to SurgicalEnvConfig.

    Returns:
        Vectorized Gymnasium environment.
    """
    def env_factory(rank: int):
        def _init():
            env_seed = seed + rank if seed is not None else None
            config = SurgicalEnvConfig(
                scene_path=scene_path,
                simulator_type=simulator_type,
                seed=env_seed,
                **kwargs,
            )
            return SurgicalEnv(config)
        return _init

    return gym.vector.SyncVectorEnv(
        [env_factory(i) for i in range(n_envs)],
    )
