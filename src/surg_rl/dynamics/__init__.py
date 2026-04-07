"""Dynamic environment control - Domain randomization and curriculum.

This module provides controllers for dynamic environment modification during
RL training, including:
- Domain randomization for physics, visual, and dynamics parameters
- Curriculum learning with progressive difficulty stages
- Adaptive difficulty adjustment based on agent performance

Main Classes:
    EnvironmentController: Main controller integrating all dynamic control
    ParameterRandomizer: Domain randomization controller
    CurriculumScheduler: Curriculum learning scheduler
    AdaptiveDifficultyController: Adaptive difficulty controller

Example:
    >>> from surg_rl.dynamics import EnvironmentController
    >>> from surg_rl.scene_definition import SceneLoader
    >>> 
    >>> # Create from scene
    >>> scene = SceneLoader.load("scenes/suturing.json")
    >>> controller = EnvironmentController.from_scene(scene)
    >>> 
    >>> # Start training
    >>> controller.start()
    >>> params = controller.reset(seed=42)
    >>> # Apply params to simulator...
    >>> # Run episode...
    >>> info = controller.episode_end(
    ...     {"reward": 100, "success": True},
    ...     simulator,
    ... )
"""

from .base_controller import (
    BaseController,
    ControllerConfig,
    ControllerState,
    ParameterBounds,
    ParameterSnapshot,
)

from .parameter_randomizer import (
    ParameterRandomizer,
    PhysicsParameterBounds,
    VisualParameterBounds,
    DynamicsParameterBounds,
)

from .curriculum import (
    CurriculumScheduler,
    CurriculumConfig,
    CurriculumStage,
    CurriculumStageConfig,
)

from .adaptive_difficulty import (
    AdaptiveDifficultyController,
    DifficultyConfig,
    DifficultyState,
    AdaptationStrategy,
    AdaptationDirection,
)

from .environment_controller import (
    EnvironmentController,
    EnvironmentControllerConfig,
)

__all__ = [
    # Base controller
    "BaseController",
    "ControllerConfig",
    "ControllerState",
    "ParameterBounds",
    "ParameterSnapshot",
    
    # Parameter randomizer
    "ParameterRandomizer",
    "PhysicsParameterBounds",
    "VisualParameterBounds",
    "DynamicsParameterBounds",
    
    # Curriculum
    "CurriculumScheduler",
    "CurriculumConfig",
    "CurriculumStage",
    "CurriculumStageConfig",
    
    # Adaptive difficulty
    "AdaptiveDifficultyController",
    "DifficultyConfig",
    "DifficultyState",
    "AdaptationStrategy",
    "AdaptationDirection",
    
    # Main controller
    "EnvironmentController",
    "EnvironmentControllerConfig",
]
