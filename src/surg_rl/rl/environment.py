"""Gymnasium environment wrapper for surgical robotics RL training.

This module provides the SurgicalEnv class, a Gymnasium-compatible
environment that wraps the simulator and dynamic environment controller
into a standard interface for RL training with Stable-Baselines3.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import platform  # noqa: F401 — imported at module level for test patching
import queue
from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np

from surg_rl.dynamics.environment_controller import (
    EnvironmentController,
    EnvironmentControllerConfig,
)
from surg_rl.rl.difficulty import DifficultyLevel
from surg_rl.ros2 import HAS_ROS2  # noqa: F401 — used by bridge lifecycle
from surg_rl.ros2.config import Ros2BridgeConfig
from surg_rl.scene_definition.schema import SceneDefinition
from surg_rl.simulators.base_simulator import BaseSimulator, Observation
from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
from surg_rl.simulators.pybullet_simulator import PyBulletSimulator
from surg_rl.utils.logging import get_logger

from .action import (
    ActionBuilder,
    ActionConfig,
    ActionScaling,
    ActionType,
)
from .observation import (
    ObservationBuilder,
    ObservationConfig,
    ObservationType,
)
from .rewards import (
    BaseRewardFunction,
    CompositeReward,
    RewardConfig,
    RewardResult,
    create_default_reward,
)
from .task_reward_router import TaskRewardRouter
from .task_termination import check_task_success

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
        difficulty: Config-level difficulty scalar fallback (default 0.5).
    """

    scene_path: str | None = None
    scene: SceneDefinition | None = None
    simulator_type: str = "mujoco"
    timestep: float = 0.002
    frame_skip: int = 1
    max_episode_steps: int = 1000
    render_mode: str | None = None
    render_fps: float = 30.0
    reward_config: RewardConfig | None = None
    observation_config: ObservationConfig | None = None
    action_config: ActionConfig | None = None
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    controller_config: EnvironmentControllerConfig | None = None
    seed: int | None = None
    ros2_bridge_config: Ros2BridgeConfig | None = None
    use_ros2_control: bool = False
    controller_yaml: str | None = None
    # Config-level difficulty scalar fallback (Q2 — makes the config.difficulty
    # precedence level real and truth-table-testable). Default 0.5 preserves
    # v0.5.0 behavior.
    difficulty: float = 0.5


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
        config: SurgicalEnvConfig | None = None,
        render_mode: str | None = None,
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

        # Propagate action mode to simulator if needed
        action_cfg = self.config.action_config or self._default_action_config()
        if action_cfg.action_type == ActionType.JOINT_TORQUES:
            try:
                self._simulator.set_action_mode("torque")
            except (NotImplementedError, AttributeError):
                logger.debug("Backend does not support torque mode switching")
        elif action_cfg.action_type == ActionType.ENDEFFECTOR_POSE:
            try:
                self._simulator.set_action_mode("endeffector_pose")
            except (NotImplementedError, AttributeError):
                logger.debug("Backend does not support endeffector_pose mode switching")
        elif action_cfg.action_type == ActionType.ENDEFFECTOR_DELTA:
            try:
                self._simulator.set_action_mode("endeffector_delta")
            except (NotImplementedError, AttributeError):
                logger.debug("Backend does not support endeffector_delta mode switching")

        # Initialize observation and action builders
        self._obs_builder = ObservationBuilder(
            config=self.config.observation_config or self._default_observation_config()
        )
        self._action_builder = ActionBuilder(config=action_cfg)

        # Validate action type is supported at load time (ACT-05)
        # All ActionType enum values are now implemented; this guard catches
        # any future or edge-case types.
        unsupported_types = ()
        if self._action_builder.config.action_type in unsupported_types:
            raise NotImplementedError(
                f"Action type {self._action_builder.config.action_type.value!r} is not yet supported. "
                "Supported types: JOINT_POSITIONS, JOINT_VELOCITIES, JOINT_TORQUES, "
                "ENDEFFECTOR_POSE, ENDEFFECTOR_DELTA, GRIPPER, DISCRETE."
            )

        # Define spaces
        if self.config.observation_config and self.config.observation_config.flatten:
            self.observation_space = self._obs_builder.get_flat_observation_space()
        else:
            self.observation_space = self._obs_builder.get_observation_space()
        self.action_space = self._action_builder.get_action_space()

        # Initialize environment controller before reward setup so curriculum
        # difficulty is available at reward construction time.
        self._controller: EnvironmentController | None = None
        self._setup_controller()

        # ROS2 Bridge (D-01: spawn as separate multiprocessing Process)
        self._bridge: Ros2Bridge | None = None
        self._setup_bridge()

        # ros2_control ControllerBridge
        self._controller_bridge: ControllerBridge | None = None
        self._setup_controller_bridge()

        # Initialize reward function and difficulty (single normalization point).
        self._reward_fn: BaseRewardFunction | CompositeReward | None = None
        self._task_difficulty: float = 0.5
        self._setup_rewards()

        # Episode state
        self._step_count = 0
        self._episode_count = 0
        self._last_observation: dict[str, np.ndarray] | None = None
        self._target_pos: np.ndarray | None = None
        self._target_quat: np.ndarray | None = None
        self._last_cut_step: int = -1000  # cooldown tracking
        self._cut_cooldown_steps: int = 25  # ~500ms at 50Hz

        self._fluid_simulator: object | None = None
        self._init_fluid()

        # Eager viewer start (D-01)
        if self.render_mode == "human":
            try:
                viewer_started = self._simulator.start_viewer(
                    target_fps=getattr(self.config, "render_fps", 30.0)
                )
            except RuntimeError as exc:
                # macOS without mjpython – treat as headless fallback
                logger.warning(
                    "Human render unavailable: %s. " "Training will continue without viewer.",
                    exc,
                )
                self._switch_to_headless()
            else:
                if not viewer_started:
                    logger.warning(
                        "Human render requested but display unavailable. "
                        "Training will continue without viewer."
                    )
                    self._switch_to_headless()  # headless fallback per D-03

        # Signal handlers (D-05)
        self._setup_signal_handlers()

    def _switch_to_headless(self) -> None:
        """Drop the simulator back to headless mode after a failed viewer start.

        Without this, the simulator was constructed with
        ``render_mode="human"`` and may keep a half-initialized
        ``_viewer`` reference even after ``start_viewer()`` failed.
        Under mjpython + Apple Silicon + SB3 this can segfault during
        teardown. Forcing the simulator's ``render_mode`` to ``None``
        here keeps its state consistent with the env's.
        """
        self.render_mode = None
        if self._simulator is not None and hasattr(self._simulator, "render_mode"):
            with contextlib.suppress(AttributeError, TypeError):
                self._simulator.render_mode = None

    def _load_scene(self) -> SceneDefinition:
        """Load the scene definition.

        Returns:
            SceneDefinition object.
        """
        if self.config.scene is not None:
            return self.config.scene

        if self.config.scene_path is not None:
            # Lazy import to break the import cycle:
            # environment.py -> loader.py -> schema.py -> rl.__init__
            # The SceneLoader is only needed at runtime (not at module load).
            from surg_rl.scene_definition.loader import SceneLoader

            return SceneLoader().load(self.config.scene_path)

        # Create a minimal default scene
        logger.warning("No scene specified, using default minimal scene")
        return SceneDefinition()

    def _create_simulator(self) -> BaseSimulator:
        """Create the simulator backend.

        Returns:
            Simulator instance.
        """
        sim_render_mode = self.render_mode or "rgb_array"
        if self.config.simulator_type == "mujoco":
            return MuJoCoSimulator(
                timestep=self.config.timestep,
                frame_skip=self.config.frame_skip,
                render_mode=sim_render_mode,
            )
        elif self.config.simulator_type == "pybullet":
            # PyBullet must know at construction whether to use GUI
            pb_mode = "GUI" if self.render_mode == "human" else "DIRECT"
            return PyBulletSimulator(
                timestep=self.config.timestep,
                frame_skip=self.config.frame_skip,
                render_mode=pb_mode,
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
        """Create default action config based on scene and simulator.

        Detects gripper availability from simulator control map or scene
        definition and adjusts ``num_joints`` / ``include_gripper`` accordingly.

        Returns:
            ActionConfig object.
        """
        # Default fallback values
        num_joints = 7  # Default 7-DOF
        include_gripper = False

        # 1. Introspect loaded simulator control map (most accurate)
        if (
            self._simulator is not None
            and hasattr(self._simulator, "_control_map")
            and isinstance(self._simulator._control_map, list)
        ):
            control_map = self._simulator._control_map
            if control_map:
                gripper_count = sum(1 for m in control_map if m.get("is_gripper"))
                total = len(control_map)
                include_gripper = gripper_count > 0
                num_joints = total - gripper_count
                return ActionConfig(
                    action_type=ActionType.JOINT_POSITIONS,
                    num_joints=num_joints,
                    include_gripper=include_gripper,
                    scaling=ActionScaling.NORMALIZE,
                )

        # 2. Fallback to scene definition
        if self._scene and self._scene.robots:
            first_robot = self._scene.robots[0]
            # Detect gripper from end_effectors
            if hasattr(first_robot, "end_effectors") and first_robot.end_effectors:
                include_gripper = True
            if hasattr(first_robot, "joints") and first_robot.joints:
                num_joints = len(first_robot.joints)
            elif include_gripper:
                # Primitive scene with no explicit joints: assume 1 DOF arm + gripper
                num_joints = 1

        return ActionConfig(
            action_type=ActionType.JOINT_POSITIONS,
            num_joints=num_joints,
            include_gripper=include_gripper,
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

    def _setup_bridge(self) -> None:
        """Set up the ROS2 bridge Process (D-01).

        Spawns a separate multiprocessing.Process running Ros2BridgeNode
        when ros2_bridge_config is provided and ROS2 is available.

        Per D-13: on macOS, logs warning and disables bridge.
        Per D-01: bridge spawns at __init__ time, terminates at close().
        Per K8S-03: skips in-process spawn when SURGRL_BRIDGE_SIDECAR=true
        (bridge runs as K8s sidecar container).
        """
        if os.environ.get("SURGRL_BRIDGE_SIDECAR") == "true":
            logger.info(
                "SURGRL_BRIDGE_SIDECAR=true — bridge runs as K8s sidecar, "
                "skipping in-process spawn"
            )
            return

        if self.config.ros2_bridge_config is None:
            return

        # Platform check (D-13)
        system = platform.system()
        if system == "Darwin":
            logger.warning(
                "ROS2 bridge not supported on macOS. "
                "Use Docker Linux container: docker run -v $(pwd):/workspace ros:humble."
            )
            return

        if not HAS_ROS2:
            logger.warning(
                "rclpy not installed — bridge disabled. " "Install via apt: ros-humble-rclpy"
            )
            return

        bridge_cfg = self.config.ros2_bridge_config

        # Get joint names from simulator
        joint_states = self._simulator.get_joint_states()
        joint_names = list(joint_states.keys()) if joint_states else ["joint_0"]

        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        # Create multiprocessing.Queue for cross-process command IPC (CR-01 fix)
        cmd_queue = multiprocessing.Queue(maxsize=1)

        node = Ros2BridgeNode(
            joint_names=joint_names,
            publisher_topic=bridge_cfg.state_topic,
            command_topic=bridge_cfg.command_topic,
            command_queue=cmd_queue,
            frame_id=bridge_cfg.frame_id,
            qos_profile=bridge_cfg.qos_profile,
            on_nan_inf=bridge_cfg.on_nan_inf,
            on_dimension_mismatch=bridge_cfg.on_dimension_mismatch,
        )
        self._bridge = Ros2Bridge(node=node, config=bridge_cfg, command_queue=cmd_queue)
        self._bridge.start()
        logger.info(
            "ROS2 bridge started: pub=%s, sub=%s",
            bridge_cfg.state_topic,
            bridge_cfg.command_topic,
        )

    def _setup_controller_bridge(self) -> None:
        """Set up ros2_control ControllerBridge.

        Launches the controller_manager lifecycle via ControllerBridge
        when use_ros2_control is enabled and ROS2 is available.
        """
        if not self.config.use_ros2_control:
            return
        if not HAS_ROS2:
            logger.warning(
                "ros2_control requested but ROS2 not available — " "hardware control disabled"
            )
            return
        from surg_rl.ros2.hardware_bridge import ControllerBridge

        joint_states = self._simulator.get_joint_states()
        joint_names = list(joint_states.keys()) if joint_states else ["joint_0"]

        self._controller_bridge = ControllerBridge(
            controller_yaml=self.config.controller_yaml,
            joint_names=joint_names,
        )
        self._controller_bridge.start()

    def _setup_rewards(self) -> None:
        """Build the reward function and resolve the difficulty scalar.

        This is the single env-construction place where reward difficulty is
        resolved and normalized to a float before it reaches the reward builder.
        """
        task_name = None
        task_type = None
        if self._scene.task is not None:
            task_name = self._scene.task.name
            task_type = getattr(self._scene.task, "task_type", None)

        # Resolve difficulty scalar from task -> config -> curriculum -> default.
        difficulty: float | DifficultyLevel
        if self._scene.task is not None and self._scene.task.difficulty_level is not None:
            difficulty = self._scene.task.difficulty_level
        else:
            # SurgicalEnvConfig may or may not have a difficulty field; getattr is safe
            difficulty = getattr(self.config, "difficulty", 0.5)

        # If curriculum drives difficulty, normalize the scheduler's current value.
        if (
            self.config.use_curriculum
            and self._controller is not None
            and self._controller._curriculum is not None
        ):
            difficulty = self._controller._curriculum.current_difficulty

        # Phase 29: coerce enum or float to a scalar float for all reward builders.
        difficulty_float = float(difficulty.value) if isinstance(difficulty, DifficultyLevel) else float(difficulty)
        self._task_difficulty = difficulty_float

        # P37 (TASK-08): scene-level difficulty_blocks override branch (additive
        # early-return BEFORE the existing router branch). Applies ONLY when the
        # resolved difficulty is a DifficultyLevel enum (Q4 guard) AND the task
        # carries difficulty_blocks for that level. Under use_curriculum=True
        # with a continuous scalar, the isinstance guard fails -> blocks are
        # INERT and the existing router branch below runs (continuous path
        # byte-identical, TASK-09). compose_difficulty_overrides is lazy-local
        # imported here (Pitfall 4 — NOT module-level), mirroring the SceneLoader
        # lazy import idiom at _load_scene.
        blocks = (
            getattr(self._scene.task, "difficulty_blocks", None)
            if self._scene.task is not None
            else None
        )
        if (
            blocks is not None
            and isinstance(difficulty, DifficultyLevel)
            and self._scene.task is not None
            and task_type is not None
            and difficulty in blocks
        ):
            from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides
            from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY

            reward_cls = TASK_REWARD_REGISTRY.get(task_type)
            if reward_cls is not None:
                params = compose_difficulty_overrides(
                    task_type,
                    difficulty,
                    blocks[difficulty],
                    reward_cls,
                )
                router = TaskRewardRouter(difficulty=difficulty_float)
                reward_list = router.build(task_type)
                # apply_params overrides the interpolated values set by
                # router.build()'s apply_difficulty call with the composed
                # dict (D-06 additive). Q1 MINIMAL: only the single mapped
                # PARAM_BOUNDS key per reward is affected (Pitfall 2 inert).
                if hasattr(reward_list[0], "apply_params"):
                    reward_list[0].apply_params(params)
                self._reward_fn = CompositeReward([(r, 1.0) for r in reward_list])
                return

        if task_type is not None:
            router = TaskRewardRouter(difficulty=difficulty_float)
            reward_list = router.build(task_type)
            self._reward_fn = CompositeReward([(r, 1.0) for r in reward_list])
        else:
            self._reward_fn = create_default_reward(self.config.reward_config, task_name=task_name)

    def _teardown_controller_bridge(self) -> None:
        """Stop and clean up the ros2_control ControllerBridge."""
        if self._controller_bridge is not None:
            self._controller_bridge.stop()
            self._controller_bridge = None

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset the environment to initial state.

        Args:
            seed: Random seed for reproducibility.
            options: Additional reset options.

        Returns:
            Tuple of (observation, info).
        """
        super().reset(seed=seed)

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

        # Phase 21: Update task difficulty from curriculum
        if self._controller is not None:
            try:
                self._task_difficulty = self._controller.get_difficulty() or 0.5
            except (AttributeError, Exception):
                pass

        # Reset simulator
        try:
            sim_obs = self._simulator.reset(seed=seed)
        except Exception as e:
            logger.warning(f"Simulator reset failed, using zero observation: {e}")
            sim_obs = Observation()

        # Set random target position for task
        self._target_pos = np.array([0.3, 0.0, 0.5]) + self.np_random.uniform(-0.1, 0.1, size=3)
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
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Execute one environment step.

        Args:
            action: Action from the agent.

        Returns:
            Tuple of (observation, reward, terminated, truncated, info).
        """
        # Process action through action builder
        processed_action = self._action_builder.process_action(action)

        # Forward pending ROS2 commands from bridge queue to controller (G-1 fix)
        if self._bridge is not None and self._controller is not None:
            self._bridge.forward_commands(self._controller)

        # Route through controller mode switch (D-11):
        # sim mode → passthrough, real_robot → external action from queue
        if self._controller is not None:
            processed_action = self._controller.get_action(processed_action)

        # Apply domain randomization noise
        if self._controller is not None:
            processed_action = self._controller.get_randomized_action(processed_action)

        return self._step_simulator_and_build_outputs(processed_action, source_action=action)

    def passthrough_step(self) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Step the environment when per-arm actions were applied via simulator.apply_action(arm_id=...) directly.

        MultiAgentSurgicalEnv routes per-arm actions to the simulator BEFORE
        calling this method, so the surgical env's action builder is bypassed
        entirely. The simulator is stepped with a no-op action of the correct
        shape; the per-arm joint targets already set via apply_action() drive
        the actual motion.

        Returns:
            Tuple of (observation, reward, terminated, truncated, info).
        """
        if self._simulator is None:
            raise RuntimeError(
                "SurgicalEnv.passthrough_step() called before simulator loaded"
            )
        num_controls = self._simulator.get_num_controls()
        no_op = np.zeros(num_controls, dtype=np.float32)
        return self._step_simulator_and_build_outputs(no_op, source_action=None)

    def _step_simulator_and_build_outputs(
        self, processed_action: np.ndarray, source_action: np.ndarray | None
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Build (obs, reward, terminated, truncated, info) given an already-processed action.

        Shared body used by both step() and passthrough_step(). The caller
        has already routed the action through the action builder and
        controller; this method steps the simulator and produces the env
        outputs. ``source_action`` is the pre-builder action used for
        reward shaping (None for passthrough callers).

        Returns:
            Tuple of (observation, reward, terminated, truncated, info).
        """
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
            action=source_action if source_action is not None else processed_action,
            info={
                **sim_info,
                "terminated": terminated,
                "truncated": truncated,
                "step": self._step_count,
            },
        )
        reward = reward_result.total

        # Backend-agnostic task success check
        task_success, success_details = check_task_success(
            self._scene, sim_obs, self._target_pos, self._target_quat, sim_info
        )
        if task_success:
            terminated = True
            sim_info["success"] = True

        # Build info dict
        info = self._build_info(sim_obs, reward_result, sim_info)
        info["terminated"] = terminated
        info["truncated"] = truncated
        info["reward_components"] = reward_result.components

        self._last_observation = obs_dict

        # Step fluid simulation (subsampled at fluid.substep_dt rhythm)
        if self._fluid_simulator is not None and self._simulator is not None:
            fluid_interval = max(
                1,
                int(
                    self._fluid_simulator.config.substep_dt
                    / (
                        self._scene.physics.timestep
                        if self._scene and self._scene.physics
                        else 0.002
                    )
                ),
            )
            if self._step_count % fluid_interval == 0:
                self._fluid_simulator.step()

        # Invoke per-simulator fluid hook (DEBT-03 — currently no-op for MuJoCo/PyBullet)
        # Subclasses with native fluid support override fluid_step() in their backend.
        if self._simulator is not None:
            self._simulator.fluid_step(
                self._scene.physics.timestep if self._scene and self._scene.physics else 0.002
            )

        # Publish joint state via ROS2 bridge (D-19: every step)
        if self._bridge is not None:
            sim_state = self._simulator.get_state()
            self._bridge.publish_joint_state(sim_state.qpos, sim_state.qvel)

        # Update environment controller
        if self._controller is not None:
            self._controller.step_update(self._simulator)

        return obs_dict, reward, terminated, truncated, info

    def trigger_cut(
        self, tissue_name: str, surface_point: Position, direction: Position, depth: float = 0.01
    ) -> bool:
        """Trigger a volumetric cut on a soft body tissue.

        Enforces a cooldown (~500ms at 50Hz) to prevent spam cutting.

        Args:
            tissue_name: Name of the tissue to cut.
            surface_point: Entry point on tissue surface (world coords).
            direction: Cut direction vector.
            depth: Cut depth in meters (default 0.01).

        Returns:
            True if the cut was applied, False if on cooldown or invalid.
        """
        from surg_rl.scene_definition.schema import CutAction
        from surg_rl.scene_definition.schema import Position as SchemaPosition

        if self._step_count - self._last_cut_step < self._cut_cooldown_steps:
            return False

        sp = (
            surface_point
            if isinstance(surface_point, SchemaPosition)
            else SchemaPosition(x=surface_point.x, y=surface_point.y, z=surface_point.z)
        )
        di = (
            direction
            if isinstance(direction, SchemaPosition)
            else SchemaPosition(x=direction.x, y=direction.y, z=direction.z)
        )

        cut_action = CutAction(
            tissue_name=tissue_name,
            surface_point=sp,
            direction=di,
            depth=depth,
        )

        if hasattr(self._simulator, "_apply_cut"):
            self._simulator._apply_cut(cut_action)
            self._last_cut_step = self._step_count
            return True
        return False

    def _init_fluid(self) -> None:
        """Instantiate FluidSimulator if FluidConfig is present and enabled."""
        fluid_cfg = getattr(self._scene, "fluid", None)
        if fluid_cfg is None or not fluid_cfg.enabled:
            return
        try:
            from surg_rl.fluids import FluidSimulator

            self._fluid_simulator = FluidSimulator(fluid_cfg)
            logger.info("Fluid simulator initialized: %s", fluid_cfg.resolution)
        except Exception as exc:
            logger.warning("Fluid simulator init failed: %s", exc)
            self._fluid_simulator = None

    def render(self) -> np.ndarray | None:
        """Render the environment.

        Returns:
            RGB image array if render_mode is 'rgb_array', None otherwise.
        """
        if self.render_mode == "rgb_array":
            return self._simulator.render(mode="rgb_array")
        # human mode: rendering handled asynchronously by RenderThread in simulator
        return None

    def close(self) -> None:
        """Clean up environment resources.

        Order matters — bridge terminates first (before simulator cleanup)
        per D-01 to avoid dangling shared-state references.
        """
        self._teardown_controller_bridge()

        if self._bridge is not None:
            self._bridge.terminate()
            logger.info("ROS2 bridge terminated")

        if self._simulator is not None:
            if hasattr(self._simulator, "stop_viewer"):
                self._simulator.stop_viewer()
            self._simulator.close()
        if self._controller is not None:
            self._controller.stop()

    def _setup_signal_handlers(self) -> None:
        """Register SIGINT and atexit so the viewer cleans up on Ctrl+C."""
        import atexit
        import signal

        if getattr(self, "_handlers_registered", False):
            return

        def _handle_sigint(signum, frame) -> None:
            self.close()
            raise KeyboardInterrupt

        try:
            signal.signal(signal.SIGINT, _handle_sigint)
        except ValueError:
            pass  # Not on main thread (e.g., SubprocVecEnv)

        atexit.register(self.close)
        self._handlers_registered = True

    def _build_info(
        self,
        sim_obs: Observation,
        reward_result: RewardResult | None = None,
        sim_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the info dictionary.

        Args:
            sim_obs: Simulator observation.
            reward_result: Reward computation result.
            sim_info: Simulator info dict.

        Returns:
            Info dictionary.
        """
        info: dict[str, Any] = {
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
    def controller(self) -> EnvironmentController | None:
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

    def set_target(self, position: np.ndarray, orientation: np.ndarray | None = None) -> None:
        """Set the target position and orientation for the task.

        Args:
            position: Target position (x, y, z).
            orientation: Target orientation as quaternion (w, x, y, z).
        """
        self._target_pos = np.array(position)
        if orientation is not None:
            self._target_quat = np.array(orientation)

    def get_state(self) -> dict[str, Any]:
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

    def set_state(self, state: dict[str, Any]) -> None:
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
    render_mode: str | None = None,
    max_episode_steps: int = 1000,
    seed: int | None = None,
    use_curriculum: bool = False,
    use_adaptive_difficulty: bool = False,
    reward_config: RewardConfig | None = None,
    observation_config: ObservationConfig | None = None,
    action_config: ActionConfig | None = None,
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
    n_envs: int = 4,
    vec_env_cls: Any | None = None,
    **kwargs,
) -> gym.Env:
    """Create a vectorized environment for parallel training.

    Uses Stable-Baselines3's DummyVecEnv (single process) or SubprocVecEnv
    (multiprocess) depending on ``n_envs`` and ``vec_env_cls``.

    Args:
        scene_path: Path to the scene definition file.
        n_envs: Number of parallel environments.
        vec_env_cls: VecEnv class to use (``DummyVecEnv`` or ``SubprocVecEnv``).
            Defaults to ``DummyVecEnv`` when ``n_envs == 1`` and
            ``SubprocVecEnv`` otherwise.
        **kwargs: Additional arguments passed to ``SurgicalEnvConfig``.

    Returns:
        Vectorized SB3 environment.
    """
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    def env_factory(rank: int):
        def _init():
            env_seed = kwargs.get("seed")
            if env_seed is not None:
                env_seed = env_seed + rank
            config = SurgicalEnvConfig(
                scene_path=scene_path,
                seed=env_seed,
                **{k: v for k, v in kwargs.items() if k != "seed"},
            )
            return SurgicalEnv(config)

        return _init

    if vec_env_cls is None:
        vec_env_cls = DummyVecEnv if n_envs == 1 else SubprocVecEnv

    return vec_env_cls([env_factory(i) for i in range(n_envs)])


# ============================================================================
# ROS2 Bridge Process Wrapper
# ============================================================================


class Ros2Bridge:
    """Manages Ros2BridgeNode lifecycle as a separate multiprocessing Process.

    Per D-01: the bridge runs in a separate Process so rclpy.spin() doesn't
    block the training loop. The main thread calls ``publish_joint_state()``
    directly on the node object (rclpy Node is thread-safe for publish).

    Lifecycle:
        1. ``Ros2Bridge(node, config)`` — create wrapper.
        2. ``start()`` — spawn child Process running rclpy.spin().
        3. ``publish_joint_state(qpos, qvel)`` — called from main at every step().
        4. ``terminate()`` — graceful shutdown: terminate → join(5s) → kill → join(2s).
    """

    def __init__(self, node, config: Ros2BridgeConfig, command_queue=None):
        self._node = node
        self._config = config
        self._command_queue = command_queue
        self._process: multiprocessing.Process | None = None
        self._running = False

    def start(self) -> None:
        """Spawn bridge process with topic liveness check."""
        # Topic liveness check per D-24 / WR-05
        if HAS_ROS2:
            try:
                import rclpy

                if rclpy.ok():
                    existing = [n for n, _ in rclpy.get_topic_names_and_types()]
                    missing = []
                    if self._config.state_topic not in existing:
                        missing.append(self._config.state_topic)
                    if self._config.command_topic not in existing:
                        missing.append(self._config.command_topic)
                    if missing:
                        msg = f"ROS2 topics not found: {missing}"
                        if self._config.on_missing_topic == "error":
                            raise RuntimeError(msg)
                        elif self._config.on_missing_topic == "warn":
                            logger.warning(msg)
            except RuntimeError:
                raise
            except Exception:
                pass  # rclpy may not be initialized yet

        self._process = multiprocessing.Process(
            target=_run_bridge,
            args=(self._node, self._command_queue),
            daemon=True,  # dies with parent
            name="ros2-bridge",
        )
        self._process.start()
        self._running = True

    def terminate(self) -> None:
        """Terminate bridge process and join.

        Per T-09-07: escalation chain ensures cleanup even if process is
        unresponsive: terminate → join(5s) → kill → join(2s).
        """
        if self._process is not None and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5.0)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=2.0)
            self._running = False

    def forward_commands(self, controller) -> None:
        """Forward pending ROS2 commands from shared queue to controller.

        Polls the shared multiprocessing.Queue (child process writes,
        parent reads) and injects each pending command via
        ``controller.inject_external_action()`` for keep-latest semantics.

        Called at every ``SurgicalEnv.step()`` before ``get_action()``.
        """
        if self._command_queue is None or controller is None:
            return
        drained = False
        try:
            while True:
                cmd = self._command_queue.get_nowait()
                controller.inject_external_action(cmd)
                drained = True
        except queue.Empty:
            if not drained:
                logger.debug(
                    "forward_commands: command queue empty (no external command this step)"
                )

    def publish_joint_state(self, qpos: np.ndarray, qvel: np.ndarray) -> None:
        """Publish joint state from main process — delegates to node.

        Called at every ``SurgicalEnv.step()`` call when bridge is active.
        The node's ``publish_state()`` method is thread-safe.

        Args:
            qpos: Joint positions array.
            qvel: Joint velocities array.
        """
        if self._running:
            self._node.publish_state(qpos, qvel)


def _run_bridge(node, command_queue=None) -> None:
    """Bridge process main function.

    Initializes rclpy, adds the node to a MultiThreadedExecutor,
    and spins until terminated. Handles keyboard interrupt and cleanup.
    The command_queue is injected from the parent process for cross-process IPC.
    """
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    # Set the injected multiprocessing.Queue on the node if provided
    if command_queue is not None and hasattr(node, "_command_queue"):
        node._command_queue = command_queue

    rclpy.init()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
