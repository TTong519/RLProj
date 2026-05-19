"""Multi-Agent Surgical Environment — PettingZoo ParallelEnv adapter.

Wraps a single SurgicalEnv instance (D-11: passthrough composition), routes
per-agent actions via apply_action(action, arm_id=role), splits observation
and reward per agent, and exposes the PettingZoo ParallelEnv contract for
SB3 training via SuperSuit wrappers.

Contract: MARL-01, MARL-04.
"""

from __future__ import annotations

import importlib
from typing import Any

import gymnasium as gym
import numpy as np

from surg_rl.scene_definition.schema import SceneDefinition
from surg_rl.utils.logging import get_logger

from .observation_filter import ObservationFilter

logger = get_logger(__name__)

_PARALLEL_ENV_BASE: type | None = None


def _get_parallel_env_base() -> type:
    """Lazily resolve the PettingZoo ParallelEnv base class."""
    global _PARALLEL_ENV_BASE
    if _PARALLEL_ENV_BASE is None:
        try:
            from pettingzoo import ParallelEnv
            _PARALLEL_ENV_BASE = ParallelEnv
        except ImportError:
            _PARALLEL_ENV_BASE = object
    return _PARALLEL_ENV_BASE


class MultiAgentSurgicalEnv(_get_parallel_env_base()):
    """Multi-agent surgical RL environment (PettingZoo ParallelEnv adapter).

    This is a PASSTHROUGH adapter (D-11) — it owns exactly ONE SurgicalEnv
    and delegates all simulation logic to it. This env is NOT a subclass of
    SurgicalEnv; isinstance(env, SurgicalEnv) returns False.

    Agents correspond to arm roles defined in SceneDefinition.multi_agent:
    typically "surgeon" and "assistant".

    Usage:
        >>> config = {"scene_path": "dual_arm_scene.json", "simulator_type": "mujoco"}
        >>> env = MultiAgentSurgicalEnv(config)
        >>> obs, info = env.reset()
        >>> obs, rewards, terms, truncs, infos = env.step(
        ...     {"surgeon": action_s, "assistant": action_a}
        ... )
        >>> env.close()
    """

    metadata = {"render_modes": ["human", "rgb_array"], "name": "multi_agent_surgical"}

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the multi-agent surgical environment.

        Args:
            config: Dictionary config forwarded to SurgicalEnvConfig.
                Must contain either 'scene_path' or 'scene'.
                If 'scene' is a SceneDefinition, validates multi_agent.

        Raises:
            ValueError: If scene.multi_agent is None.
        """
        config = dict(config or {})

        # Load/validate scene definition
        scene = config.get("scene")
        if isinstance(scene, SceneDefinition):
            if scene.multi_agent is None:
                raise ValueError(
                    "MultiAgentSurgicalEnv requires SceneDefinition.multi_agent "
                    "to be set. Use a dual-arm scene with MultiAgentConfig."
                )
            self._multi_agent = scene.multi_agent
        elif "scene_path" in config:
            from surg_rl.scene_definition.loader import SceneLoader

            loaded_scene = SceneLoader().load(config["scene_path"])
            if loaded_scene.multi_agent is None:
                raise ValueError(
                    f"Scene at {config['scene_path']} has no multi_agent config. "
                    "MultiAgentSurgicalEnv requires a dual-arm scene."
                )
            self._multi_agent = loaded_scene.multi_agent
            config["scene"] = loaded_scene

        # Agent IDs from arm roles
        self.agents: list[str] = []
        self.possible_agents: list[str] = []

        # Collect agent IDs from arm configs
        for arm in self._multi_agent.arm_configs:
            agent_id = arm.role.value if hasattr(arm.role, "value") else str(arm.role)
            self.possible_agents.append(agent_id)

        # Create the single SurgicalEnv instance (D-11: one env only)
        self._surgical_env = self._create_surgical_env(config)

        # Build observation/action spaces per agent
        self._obs_filter = ObservationFilter(self._multi_agent)
        self._build_spaces()

    @property
    def possible_agents_list(self) -> list[str]:
        """All possible agents (required by PettingZoo)."""
        return self.possible_agents

    def _create_surgical_env(self, config: dict[str, Any]) -> Any:
        """Create the single SurgicalEnv instance.

        Args:
            config: Configuration dict forwarded to SurgicalEnvConfig.

        Returns:
            SurgicalEnv instance.
        """
        from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

        # Strip marl-specific keys before passing to SurgicalEnvConfig
        env_config = SurgicalEnvConfig(
            scene=config.get("scene"),
            scene_path=config.get("scene_path"),
            simulator_type=config.get("simulator_type", "mujoco"),
            timestep=config.get("timestep", 0.002),
            frame_skip=config.get("frame_skip", 1),
            max_episode_steps=config.get("max_episode_steps", 1000),
            render_mode=config.get("render_mode"),
            seed=config.get("seed"),
            observation_config=config.get("observation_config"),
            action_config=config.get("action_config"),
            reward_config=config.get("reward_config"),
            use_curriculum=config.get("use_curriculum", False),
            use_adaptive_difficulty=config.get("use_adaptive_difficulty", False),
        )
        return SurgicalEnv(env_config)

    def _build_spaces(self) -> None:
        """Build per-agent observation and action spaces.

        Observation spaces are filtered per agent via ObservationFilter.
        Action spaces are auto-computed from RobotConfig DOF counts (D-05).
        """
        self.observation_spaces: dict[str, gym.Space] = {}
        self.action_spaces: dict[str, gym.Space] = {}

        for arm in self._multi_agent.arm_configs:
            agent_id = arm.role.value if hasattr(arm.role, "value") else str(arm.role)

            # Find the robot this arm binds to
            scene = self._surgical_env._scene
            robot = None
            for r in scene.robots:
                if r.name == arm.robot_ref:
                    robot = r
                    break

            # Compute observation space for this agent
            obs_space = self._build_agent_observation_space(agent_id)
            self.observation_spaces[agent_id] = obs_space

            # Compute action space for this agent
            act_space = self._build_agent_action_space(robot)
            self.action_spaces[agent_id] = act_space

    def _build_agent_observation_space(self, agent_id: str) -> gym.Space:
        """Build observation space for a single agent."""
        # Use surgical env's observation space as base
        env_obs_space = self._surgical_env.observation_space

        arm = self._multi_agent.get_arm(agent_id)
        if arm is None or arm.observation_keys is None:
            return env_obs_space

        # Filter to only requested keys
        if isinstance(env_obs_space, gym.spaces.Dict):
            filtered_spaces = {}
            for key in arm.observation_keys:
                if key in env_obs_space.spaces:
                    filtered_spaces[key] = env_obs_space.spaces[key]
            if filtered_spaces:
                return gym.spaces.Dict(filtered_spaces)
            # If no keys matched, return full space as fallback
            return env_obs_space

        return env_obs_space

    def _build_agent_action_space(self, robot: Any | None) -> gym.Space:
        """Build action space for a single agent based on robot DOF count (D-05).

        Args:
            robot: RobotConfig for this agent. If None, returns default 1-DOF.

        Returns:
            Gymnasium Box action space.
        """
        if robot is not None and robot.joints:
            num_joints = len(robot.joints)
            return gym.spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(num_joints,),
                dtype=np.float32,
            )

        # Fallback: 1-DOF action
        return gym.spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(1,),
            dtype=np.float32,
        )

    def observation_space(self, agent: str) -> gym.Space:
        """Get observation space for a specific agent.

        Args:
            agent: Agent identifier (e.g., "surgeon").

        Returns:
            Gymnasium Space for this agent's observations.
        """
        return self.observation_spaces.get(agent, gym.spaces.Box(
            low=0, high=1, shape=(1,), dtype=np.float32
        ))

    def action_space(self, agent: str) -> gym.Space:
        """Get action space for a specific agent.

        Args:
            agent: Agent identifier (e.g., "surgeon").

        Returns:
            Gymnasium Space for this agent's actions.
        """
        return self.action_spaces.get(agent, gym.spaces.Box(
            low=-1.0, high=1.0, shape=(1,), dtype=np.float32
        ))

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, dict[str, Any]]]:
        """Reset the environment.

        Resets the underlying SurgicalEnv, then splits the full observation
        per agent via ObservationFilter.

        Args:
            seed: Random seed.
            options: Additional reset options.

        Returns:
            Tuple of (observations_dict, infos_dict) keyed by agent_id.
        """
        # Re-populate agents (Pitfall 1: must be mutable)
        self.agents = list(self.possible_agents)

        # Reset the single SurgicalEnv
        full_obs, full_info = self._surgical_env.reset(seed=seed, options=options)

        # Split observation per agent
        observations: dict[str, dict[str, np.ndarray]] = {}
        infos: dict[str, dict[str, Any]] = {}
        for agent_id in self.agents:
            observations[agent_id] = self._obs_filter.filter(agent_id, full_obs)
            infos[agent_id] = dict(full_info)
            infos[agent_id]["agent_id"] = agent_id

        return observations, infos

    def step(
        self, actions: dict[str, np.ndarray]
    ) -> tuple[
        dict[str, dict[str, np.ndarray]],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        """Execute one multi-agent environment step.

        Applies each agent's action to the corresponding arm via
        apply_action(action, arm_id=role), then steps the underlying
        SurgicalEnv once. Splits observation and reward per agent.

        Args:
            actions: Dictionary mapping agent_id → action array.

        Returns:
            5-tuple of dicts (PettingZoo contract):
                observations: dict[agent_id → obs_dict]
                rewards: dict[agent_id → float]
                terminations: dict[agent_id → bool]
                truncations: dict[agent_id → bool]
                infos: dict[agent_id → info_dict]
        """
        # Process arm_id for the first agent first to set up the scene
        # For the passthrough, we need to apply actions to both arms
        # before calling step()

        scene = self._surgical_env._scene  # type: ignore
        simulator = self._surgical_env.simulator

        # Apply per-arm actions before stepping (D-09)
        for agent_id in self.agents:
            action = actions.get(agent_id)
            if action is not None and len(action) > 0:
                simulator.apply_action(action, arm_id=agent_id)

        # Step the single SurgicalEnv once
        full_obs, full_reward, terminated, truncated, full_info = (
            self._surgical_env.step(np.zeros(0))
        )

        # Split observations, rewards, and infos per agent
        observations: dict[str, dict[str, np.ndarray]] = {}
        rewards: dict[str, float] = {}
        terminations: dict[str, bool] = {}
        truncations: dict[str, bool] = {}
        infos: dict[str, dict[str, Any]] = {}

        for agent_id in self.agents:
            observations[agent_id] = self._obs_filter.filter(agent_id, full_obs)
            terminations[agent_id] = terminated
            truncations[agent_id] = truncated
            infos[agent_id] = dict(full_info)
            infos[agent_id]["agent_id"] = agent_id

            # Per-agent reward routing (D-10):
            #   surgeon → task-specific reward (full_reward)
            #   assistant → positioning reward (computed from observation delta)
            if agent_id == "surgeon":
                rewards[agent_id] = float(full_reward)
            elif agent_id == "assistant":
                # Assistant gets a positioning reward based on arm proximity
                # to a useful observation position
                rewards[agent_id] = self._compute_assistant_reward(full_obs, full_info)
            else:
                rewards[agent_id] = 0.0

        return observations, rewards, terminations, truncations, infos

    def _compute_assistant_reward(
        self,
        full_obs: dict[str, np.ndarray],
        full_info: dict[str, Any],
    ) -> float:
        """Compute a positioning reward for the assistant arm (D-10).

        The assistant's reward reflects how well it's positioned for
        the observation task. Uses end-effector position stability
        and proximity to a useful viewpoint.

        Args:
            full_obs: Full observation dict from SurgicalEnv step.
            full_info: Info dict from SurgicalEnv step.

        Returns:
            Positioning reward (float, typically near 0).
        """
        # Small default reward to keep assistant engaged
        reward = 0.0

        # Check if end-effector position is available
        ee_pos = full_obs.get("endeffector_pos")
        if ee_pos is not None:
            # Penalize extreme positions (keep arm in reasonable workspace)
            pos_norm = float(np.linalg.norm(ee_pos))
            if pos_norm > 1.0:
                reward -= 0.01 * (pos_norm - 1.0)
            else:
                reward += 0.005

        return reward

    def render(self) -> np.ndarray | None:
        """Render the current environment state.

        Returns:
            Rendered image array or None.
        """
        return self._surgical_env.render()

    def close(self) -> None:
        """Clean up environment resources."""
        if hasattr(self, "_surgical_env") and self._surgical_env is not None:
            self._surgical_env.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Context manager exit — cleans up."""
        self.close()
        return False

    def __del__(self):
        """Destructor to ensure cleanup."""
        import contextlib
        import sys

        if sys.is_finalizing():
            return
        with contextlib.suppress(Exception):
            self.close()
