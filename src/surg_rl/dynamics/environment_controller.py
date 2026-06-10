"""Main environment controller that integrates all dynamic control.

This module provides the EnvironmentController class that combines
parameter randomization, curriculum learning, and adaptive difficulty
into a unified interface.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

logger = logging.getLogger(__name__)

from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    SceneDefinition,
)

from .adaptive_difficulty import (
    AdaptiveDifficultyController,
    DifficultyConfig,
)
from .base_controller import (
    ControllerConfig,
    ParameterSnapshot,
)
from .curriculum import (
    CurriculumConfig,
    CurriculumScheduler,
    CurriculumStage,
)
from .parameter_randomizer import ParameterRandomizer


@dataclass
class EnvironmentControllerConfig:
    """Configuration for the environment controller.

    Attributes:
        enabled: Whether the controller is enabled.
        use_randomization: Whether to use parameter randomization.
        use_curriculum: Whether to use curriculum learning.
        use_adaptive_difficulty: Whether to use adaptive difficulty.
        seed: Random seed for reproducibility.
        randomization_config: Domain randomization configuration.
        curriculum_config: Curriculum learning configuration.
        difficulty_config: Adaptive difficulty configuration.
    """

    enabled: bool = True
    use_randomization: bool = True
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    seed: int | None = None
    randomization_config: DomainRandomizationConfig | None = None
    curriculum_config: CurriculumConfig | None = None
    difficulty_config: DifficultyConfig | None = None


class EnvironmentController:
    """Main controller integrating all dynamic environment modifications.

    This class combines:
    - ParameterRandomizer for domain randomization
    - CurriculumScheduler for curriculum learning
    - AdaptiveDifficultyController for adaptive difficulty

    It provides a unified interface for modifying environment parameters
    during RL training.

    Example:
        >>> from surg_rl.scene_definition import SceneLoader
        >>> scene = SceneLoader.load("scenes/suturing.json")
        >>> controller = EnvironmentController.from_scene(scene)
        >>> controller.start()
        >>> params = controller.reset(seed=42)
        >>> # Apply params to simulator...
        >>> # Run episode...
        >>> info = controller.episode_end(
        ...     {"reward": 100, "success": True},
        ...     simulator,
        ... )
    """

    def __init__(
        self,
        config: EnvironmentControllerConfig | None = None,
        randomizer: ParameterRandomizer | None = None,
        curriculum: CurriculumScheduler | None = None,
        adaptive: AdaptiveDifficultyController | None = None,
    ):
        """Initialize the environment controller.

        Args:
            config: Controller configuration.
            randomizer: Parameter randomizer instance.
            curriculum: Curriculum scheduler instance.
            adaptive: Adaptive difficulty controller instance.
        """
        self.config = config or EnvironmentControllerConfig()

        # Initialize sub-controllers
        self._randomizer = randomizer
        self._curriculum = curriculum
        self._adaptive = adaptive

        # Create sub-controllers if not provided
        if self.config.use_randomization and self._randomizer is None:
            base_config = ControllerConfig(
                enabled=self.config.enabled,
                seed=self.config.seed,
            )
            self._randomizer = ParameterRandomizer(
                config=base_config,
                domain_config=self.config.randomization_config,
            )

        if self.config.use_curriculum and self._curriculum is None:
            base_config = ControllerConfig(
                enabled=self.config.enabled,
                seed=self.config.seed,
            )
            self._curriculum = CurriculumScheduler(
                config=base_config,
                curriculum_config=self.config.curriculum_config,
            )

        if self.config.use_adaptive_difficulty and self._adaptive is None:
            base_config = ControllerConfig(
                enabled=self.config.enabled,
                seed=self.config.seed,
            )
            self._adaptive = AdaptiveDifficultyController(
                config=base_config,
                difficulty_config=self.config.difficulty_config,
            )

        # Current parameters
        self._current_params = ParameterSnapshot()

        # ROS2 real-robot mode (D-10, D-11, D-12)
        self._mode: Literal["sim", "real_robot"] = "sim"
        self._external_action_queue: queue.Queue = queue.Queue(maxsize=1)
        self._last_action: np.ndarray | None = None

        self._step = 0
        self._episode = 0

    @classmethod
    def from_scene(
        cls,
        scene: SceneDefinition,
        use_curriculum: bool = False,
        use_adaptive: bool = False,
        seed: int | None = None,
    ) -> EnvironmentController:
        """Create an environment controller from a scene definition.

        Args:
            scene: Scene definition.
            use_curriculum: Whether to use curriculum learning.
            use_adaptive: Whether to use adaptive difficulty.
            seed: Random seed.

        Returns:
            Configured EnvironmentController instance.
        """
        config = EnvironmentControllerConfig(
            enabled=True,
            use_randomization=scene.domain_randomization.physics.enabled
            or scene.domain_randomization.visual.enabled
            or scene.domain_randomization.dynamics.enabled,
            use_curriculum=use_curriculum,
            use_adaptive_difficulty=use_adaptive,
            seed=seed if seed is not None else scene.domain_randomization.seed,
            randomization_config=scene.domain_randomization,
        )

        return cls(config=config)

    # === Real-Robot Mode (ROS2 Bridge) ===

    @property
    def mode(self) -> str:
        """Current mode: 'sim' (RL policy) or 'real_robot' (external commands)."""
        return self._mode

    def set_real_robot_mode(self, enabled: bool) -> None:
        """Switch between simulation and real-robot mode.

        Per D-12: sets _mode to 'sim' or 'real_robot'.
        Logs the mode transition at INFO level.

        Args:
            enabled: True to switch to real_robot mode, False for sim mode.
        """
        self._mode = "real_robot" if enabled else "sim"
        logger.info("Mode switched to %s", self._mode)

    def inject_external_action(self, action: np.ndarray) -> None:
        """Inject an external action into the command queue.

        Per D-02 (keep-latest): uses queue.Queue(maxsize=1). If the queue
        is full, discards the old command and stores the new one.

        Args:
            action: Action array from external source (e.g., ROS2 command).
        """
        if self._external_action_queue.full():
            try:
                self._external_action_queue.get_nowait()
            except queue.Empty:
                pass
        self._external_action_queue.put_nowait(action.copy())

    def get_action(self, policy_action: np.ndarray) -> np.ndarray:
        """Get the action to apply to the simulator.

        Per D-11: routing depending on current mode:
        - sim mode: returns the policy action unchanged.
        - real_robot mode: returns external action from queue if available,
          or hold-last action if queue is empty.

        Per D-25: validates that the selected action has no NaN/Inf values.

        Args:
            policy_action: Action proposed by the RL policy.

        Returns:
            Action to apply to the simulator (either policy or external).

        Raises:
            ValueError: If selected action contains NaN or Inf values.
        """
        if self._mode == "sim":
            return policy_action

        # real_robot mode: try external queue, fallback to hold-last
        try:
            external = self._external_action_queue.get_nowait()
            self._last_action = external
        except queue.Empty:
            if self._last_action is None:
                # No external command received yet — use policy action
                return policy_action
            logger.debug("No external command, holding last action")
            external = self._last_action

        # Validate no NaN/Inf (D-25, T-09-06 mitigation)
        if not np.all(np.isfinite(external)):
            raise ValueError(
                f"External action contains NaN or Inf values: "
                f"min={np.min(external)}, max={np.max(external)}"
            )
        return external

    # === Properties ===

    @property
    def randomizer(self) -> ParameterRandomizer | None:
        """Get the parameter randomizer."""
        return self._randomizer

    @property
    def curriculum(self) -> CurriculumScheduler | None:
        """Get the curriculum scheduler."""
        return self._curriculum

    @property
    def adaptive(self) -> AdaptiveDifficultyController | None:
        """Get the adaptive difficulty controller."""
        return self._adaptive

    @property
    def current_params(self) -> ParameterSnapshot:
        """Get current parameters."""
        return self._current_params

    @property
    def step(self) -> int:
        """Get current step count."""
        return self._step

    @property
    def episode(self) -> int:
        """Get current episode count."""
        return self._episode

    # === Lifecycle Methods ===

    def start(self) -> None:
        """Start all controllers."""
        if self._randomizer:
            self._randomizer.start()
        if self._curriculum:
            self._curriculum.start()
        if self._adaptive:
            self._adaptive.start()

    def stop(self) -> None:
        """Stop all controllers."""
        if self._randomizer:
            self._randomizer.stop()
        if self._curriculum:
            self._curriculum.stop()
        if self._adaptive:
            self._adaptive.stop()

    def reset(self, seed: int | None = None) -> ParameterSnapshot:
        """Reset for a new episode.

        Args:
            seed: Optional random seed.

        Returns:
            Combined parameter snapshot.
        """
        self._step = 0
        self._episode += 1

        # Collect parameters from all controllers
        physics_params = {}
        visual_params = {}
        dynamics_params = {}

        if self._randomizer:
            rand_params = self._randomizer.reset(seed)
            physics_params.update(rand_params.physics)
            visual_params.update(rand_params.visual)
            dynamics_params.update(rand_params.dynamics)

        if self._curriculum:
            curr_params = self._curriculum.reset(seed + 1 if seed is not None else None)
            physics_params.update(curr_params.physics)
            visual_params.update(curr_params.visual)
            dynamics_params.update(curr_params.dynamics)

        if self._adaptive:
            adapt_params = self._adaptive.reset(seed + 2 if seed is not None else None)
            physics_params.update(adapt_params.physics)
            visual_params.update(adapt_params.visual)
            dynamics_params.update(adapt_params.dynamics)

        self._current_params = ParameterSnapshot(
            physics=physics_params,
            visual=visual_params,
            dynamics=dynamics_params,
            episode=self._episode,
            step=self._step,
        )

        return self._current_params

    def step_update(self, simulator: Any) -> ParameterSnapshot:
        """Update after a simulation step.

        Args:
            simulator: Simulator instance.

        Returns:
            Current parameter snapshot.
        """
        self._step += 1

        # Update all controllers and re-merge their snapshots
        physics_params = dict(self._current_params.physics)
        visual_params = dict(self._current_params.visual)
        dynamics_params = dict(self._current_params.dynamics)

        if self._randomizer:
            rand_params = self._randomizer.step_update(simulator)
            physics_params.update(rand_params.physics)
            visual_params.update(rand_params.visual)
            dynamics_params.update(rand_params.dynamics)
        if self._curriculum:
            curr_params = self._curriculum.step_update(simulator)
            physics_params.update(curr_params.physics)
            visual_params.update(curr_params.visual)
            dynamics_params.update(curr_params.dynamics)
        if self._adaptive:
            adapt_params = self._adaptive.step_update(simulator)
            physics_params.update(adapt_params.physics)
            visual_params.update(adapt_params.visual)
            dynamics_params.update(adapt_params.dynamics)

        self._current_params = ParameterSnapshot(
            physics=physics_params,
            visual=visual_params,
            dynamics=dynamics_params,
            episode=self._episode,
            step=self._step,
        )

        return self._current_params

    def episode_end(
        self,
        metrics: dict[str, float],
        simulator: Any,
    ) -> dict[str, Any]:
        """Handle episode end.

        Args:
            metrics: Episode metrics.
            simulator: Simulator instance.

        Returns:
            Combined info from all controllers.
        """
        info = {
            "episode": self._episode,
            "params": self._current_params,
        }

        if self._randomizer:
            info["randomization"] = self._randomizer.episode_end(metrics, simulator)

        if self._curriculum:
            info["curriculum"] = self._curriculum.episode_end(metrics, simulator)

        if self._adaptive:
            info["adaptive_difficulty"] = self._adaptive.episode_end(metrics, simulator)

        return info

    # === Utility Methods ===

    def apply_parameters(
        self,
        snapshot: ParameterSnapshot,
        simulator: Any,
    ) -> None:
        """Apply parameter snapshot to a simulator.

        Delegates to all sub-controllers so curriculum and adaptive
        overrides are also applied.

        Args:
            snapshot: Parameter snapshot to apply.
            simulator: Simulator instance.
        """
        if self._randomizer is not None:
            self._randomizer.apply_parameters(snapshot, simulator)
        if self._curriculum is not None:
            self._curriculum.apply_parameters(snapshot, simulator)
        if self._adaptive is not None:
            self._adaptive.apply_parameters(snapshot, simulator)

    def get_randomized_action(
        self,
        action: np.ndarray,
        noise_scale: float | None = None,
    ) -> np.ndarray:
        """Apply action noise if randomization is enabled.

        Applies randomizer noise first, then adaptive difficulty noise.

        Args:
            action: Original action.
            noise_scale: Optional noise scale override.

        Returns:
            Noisy action.
        """
        result = action
        if self._randomizer:
            result = self._randomizer.get_randomized_action(result, noise_scale)
        if self._adaptive:
            result = self._adaptive.get_randomized_action(result, noise_scale)
        return result

    def get_randomized_observation(
        self,
        observation: np.ndarray,
        noise_scale: float | None = None,
    ) -> np.ndarray:
        """Apply observation noise if randomization is enabled.

        Applies randomizer noise first, then adaptive difficulty noise.

        Args:
            observation: Original observation.
            noise_scale: Optional noise scale override.

        Returns:
            Noisy observation.
        """
        result = observation
        if self._randomizer:
            result = self._randomizer.get_randomized_observation(result, noise_scale)
        if self._adaptive:
            result = self._adaptive.get_randomized_observation(result, noise_scale)
        return result

    def get_curriculum_stage(self) -> CurriculumStage | None:
        """Get current curriculum stage if curriculum is enabled.

        Returns:
            Current stage or None.
        """
        if self._curriculum:
            return self._curriculum.current_stage
        return None

    def get_difficulty(self) -> float | None:
        """Get current difficulty if adaptive difficulty is enabled.

        Returns:
            Current difficulty or None.
        """
        if self._adaptive:
            return self._adaptive.difficulty
        return None

    def set_difficulty(self, difficulty: float) -> None:
        """Manually set difficulty level.

        Args:
            difficulty: Difficulty level (0.0 to 1.0).
        """
        if self._adaptive:
            self._adaptive.set_difficulty(difficulty)

    def set_curriculum_stage(self, stage: CurriculumStage) -> None:
        """Manually set curriculum stage.

        Args:
            stage: Stage to set.
        """
        if self._curriculum:
            self._curriculum.set_stage(stage)

    def get_status(self) -> dict[str, Any]:
        """Get overall status of the controller.

        Returns:
            Dictionary with status information.
        """
        status = {
            "enabled": self.config.enabled,
            "mode": self._mode,
            "episode": self._episode,
            "step": self._step,
        }

        if self._randomizer:
            status["randomization"] = {
                "enabled": self._randomizer.config.enabled,
                "domain_config": str(self._randomizer.domain_config),
            }

        if self._curriculum:
            progress = self._curriculum.get_progress()
            status["curriculum"] = progress

        if self._adaptive:
            status["adaptive_difficulty"] = {
                "difficulty": self._adaptive.difficulty,
                "adaptation_count": self._adaptive._adaptation_count,
            }

        return status

    def __repr__(self) -> str:
        """String representation."""
        parts = [f"EnvironmentController(episode={self._episode}"]
        if self._randomizer:
            parts.append("randomizer=True")
        if self._curriculum:
            parts.append(f"curriculum={self._curriculum.current_stage.value}")
        if self._adaptive:
            parts.append(f"difficulty={self._adaptive.difficulty:.2f}")
        return ", ".join(parts) + ")"
