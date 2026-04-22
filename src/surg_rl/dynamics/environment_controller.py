"""Main environment controller that integrates all dynamic control.

This module provides the EnvironmentController class that combines
parameter randomization, curriculum learning, and adaptive difficulty
into a unified interface.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import numpy as np

from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    SceneDefinition,
)

from .base_controller import (
    BaseController,
    ControllerConfig,
    ParameterSnapshot,
)
from .parameter_randomizer import ParameterRandomizer
from .curriculum import (
    CurriculumScheduler,
    CurriculumConfig,
    CurriculumStage,
)
from .adaptive_difficulty import (
    AdaptiveDifficultyController,
    DifficultyConfig,
)


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
    seed: Optional[int] = None
    randomization_config: Optional[DomainRandomizationConfig] = None
    curriculum_config: Optional[CurriculumConfig] = None
    difficulty_config: Optional[DifficultyConfig] = None


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
        config: Optional[EnvironmentControllerConfig] = None,
        randomizer: Optional[ParameterRandomizer] = None,
        curriculum: Optional[CurriculumScheduler] = None,
        adaptive: Optional[AdaptiveDifficultyController] = None,
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
        self._step = 0
        self._episode = 0

    @classmethod
    def from_scene(
        cls,
        scene: SceneDefinition,
        use_curriculum: bool = False,
        use_adaptive: bool = False,
        seed: Optional[int] = None,
    ) -> "EnvironmentController":
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
            seed=seed or scene.domain_randomization.seed,
            randomization_config=scene.domain_randomization,
        )
        
        return cls(config=config)

    # === Properties ===

    @property
    def randomizer(self) -> Optional[ParameterRandomizer]:
        """Get the parameter randomizer."""
        return self._randomizer

    @property
    def curriculum(self) -> Optional[CurriculumScheduler]:
        """Get the curriculum scheduler."""
        return self._curriculum

    @property
    def adaptive(self) -> Optional[AdaptiveDifficultyController]:
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

    def reset(self, seed: Optional[int] = None) -> ParameterSnapshot:
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
        metrics: Dict[str, float],
        simulator: Any,
    ) -> Dict[str, Any]:
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
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply action noise if randomization is enabled.
        
        Args:
            action: Original action.
            noise_scale: Optional noise scale override.
            
        Returns:
            Noisy action.
        """
        if self._randomizer:
            return self._randomizer.get_randomized_action(action, noise_scale)
        return action

    def get_randomized_observation(
        self,
        observation: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply observation noise if randomization is enabled.
        
        Args:
            observation: Original observation.
            noise_scale: Optional noise scale override.
            
        Returns:
            Noisy observation.
        """
        if self._randomizer:
            return self._randomizer.get_randomized_observation(observation, noise_scale)
        return observation

    def get_curriculum_stage(self) -> Optional[CurriculumStage]:
        """Get current curriculum stage if curriculum is enabled.
        
        Returns:
            Current stage or None.
        """
        if self._curriculum:
            return self._curriculum.current_stage
        return None

    def get_difficulty(self) -> Optional[float]:
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

    def get_status(self) -> Dict[str, Any]:
        """Get overall status of the controller.
        
        Returns:
            Dictionary with status information.
        """
        status = {
            "enabled": self.config.enabled,
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
