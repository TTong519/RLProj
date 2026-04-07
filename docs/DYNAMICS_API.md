# Dynamics Module API Reference

The `surg_rl.dynamics` module provides dynamic environment control for reinforcement learning training, including domain randomization, curriculum learning, and adaptive difficulty adjustment.

## Quick Start

```python
from surg_rl.dynamics import EnvironmentController
from surg_rl.scene_definition import SceneLoader

# Create from scene
scene = SceneLoader().load("scenes/suturing.json")
controller = EnvironmentController.from_scene(scene)

# Training loop
controller.start()
for episode in range(1000):
    params = controller.reset(seed=episode)
    
    # Get randomized parameters
    physics = params.physics      # e.g., {"mass_ratio": 1.05, "friction": 0.5}
    visual = params.visual        # e.g., {"color_r_offset": 0.02}
    dynamics = params.dynamics    # e.g., {"action_noise": 0.03}
    
    # Run episode...
    info = controller.episode_end(
        {"reward": reward, "success": success},
        simulator
    )
```

## Classes

### EnvironmentController

Main controller integrating all dynamic environment modifications.

```python
class EnvironmentController:
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
            scene: Scene definition with domain randomization config.
            use_curriculum: Enable curriculum learning.
            use_adaptive: Enable adaptive difficulty.
            seed: Random seed.
            
        Returns:
            Configured EnvironmentController instance.
        """
    
    def start(self) -> None:
        """Start all controllers."""
    
    def stop(self) -> None:
        """Stop all controllers."""
    
    def reset(self, seed: Optional[int] = None) -> ParameterSnapshot:
        """Reset for a new episode.
        
        Args:
            seed: Optional random seed.
            
        Returns:
            Parameter snapshot for the episode.
        """
    
    def step_update(self, simulator: Any) -> ParameterSnapshot:
        """Update after a simulation step.
        
        Args:
            simulator: Simulator instance.
            
        Returns:
            Current parameter snapshot.
        """
    
    def episode_end(
        self,
        metrics: Dict[str, float],
        simulator: Any,
    ) -> Dict[str, Any]:
        """Handle episode end.
        
        Args:
            metrics: Episode metrics (reward, success, etc.).
            simulator: Simulator instance.
            
        Returns:
            Info dictionary from all controllers.
        """
    
    def get_randomized_action(
        self,
        action: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply action noise if randomization is enabled."""
    
    def get_randomized_observation(
        self,
        observation: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply observation noise if randomization is enabled."""
    
    def get_curriculum_stage(self) -> Optional[CurriculumStage]:
        """Get current curriculum stage if enabled."""
    
    def get_difficulty(self) -> Optional[float]:
        """Get current difficulty if adaptive difficulty is enabled."""
    
    def set_difficulty(self, difficulty: float) -> None:
        """Manually set difficulty level (0.0 to 1.0)."""
    
    def set_curriculum_stage(self, stage: CurriculumStage) -> None:
        """Manually set curriculum stage."""
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall status of the controller."""
```

### ParameterRandomizer

Domain randomization for physics, visual, and dynamics parameters.

```python
class ParameterRandomizer(BaseController):
    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        domain_config: Optional[DomainRandomizationConfig] = None,
        physics_bounds: Optional[PhysicsParameterBounds] = None,
        visual_bounds: Optional[VisualParameterBounds] = None,
        dynamics_bounds: Optional[DynamicsParameterBounds] = None,
    ):
        """Initialize the parameter randomizer.
        
        Args:
            config: Controller configuration.
            domain_config: Domain randomization config from scene.
            physics_bounds: Bounds for physics parameters.
            visual_bounds: Bounds for visual parameters.
            dynamics_bounds: Bounds for dynamics parameters.
        """
    
    def sample_parameters(self) -> ParameterSnapshot:
        """Sample randomized parameters."""
    
    def apply_parameters(
        self,
        snapshot: ParameterSnapshot,
        simulator: Any,
    ) -> bool:
        """Apply randomized parameters to the simulator."""
    
    def get_randomized_action(
        self,
        action: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply noise to action."""
    
    def get_randomized_observation(
        self,
        observation: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply noise to observation."""
```

### CurriculumScheduler

Progressive difficulty curriculum with automatic advancement.

```python
class CurriculumScheduler(BaseController):
    # Default stages: EASY (0.25) → MEDIUM (0.5) → HARD (0.75) → EXPERT (1.0)
    
    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        curriculum_config: Optional[CurriculumConfig] = None,
    ):
        """Initialize the curriculum scheduler."""
    
    @property
    def current_stage(self) -> CurriculumStage:
        """Current curriculum stage."""
    
    @property
    def current_difficulty(self) -> float:
        """Current difficulty level (0.0 to 1.0)."""
    
    def set_stage(self, stage: CurriculumStage) -> None:
        """Manually set the curriculum stage."""
    
    def advance_stage(self) -> bool:
        """Advance to next stage. Returns True if advanced."""
    
    def regress_stage(self) -> bool:
        """Regress to previous stage. Returns True if regressed."""
    
    def get_progress(self) -> Dict[str, Any]:
        """Get curriculum progress information."""
    
    def get_performance_summary(self) -> Dict[str, float]:
        """Get performance summary over recent episodes."""
    
    def reset_curriculum(self) -> None:
        """Reset curriculum to initial stage."""
```

### AdaptiveDifficultyController

Performance-based adaptive difficulty adjustment.

```python
class AdaptiveDifficultyController(BaseController):
    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        difficulty_config: Optional[DifficultyConfig] = None,
    ):
        """Initialize the adaptive difficulty controller."""
    
    @property
    def difficulty(self) -> float:
        """Current difficulty level (0.0 to 1.0)."""
    
    def set_difficulty(self, difficulty: float) -> None:
        """Manually set difficulty level."""
    
    def get_difficulty_state(self) -> DifficultyState:
        """Get current difficulty state."""
    
    def get_difficulty_for_parameter(
        self,
        param_name: str,
        min_value: float,
        max_value: float,
    ) -> float:
        """Get difficulty-scaled parameter value."""
    
    def reset_difficulty(self) -> None:
        """Reset difficulty to initial level."""
```

### BaseController

Abstract base class for all controllers.

```python
class BaseController(ABC):
    @property
    def state(self) -> ControllerState:
        """Current controller state (idle, active, paused, error)."""
    
    @property
    def step(self) -> int:
        """Current step count."""
    
    @property
    def episode(self) -> int:
        """Current episode count."""
    
    @property
    def current_params(self) -> ParameterSnapshot:
        """Current parameter values."""
    
    def start(self) -> None:
        """Start the controller."""
    
    def stop(self) -> None:
        """Stop the controller."""
    
    def pause(self) -> None:
        """Pause the controller."""
    
    def resume(self) -> None:
        """Resume from paused state."""
    
    def reset(self, seed: Optional[int] = None) -> ParameterSnapshot:
        """Reset for a new episode."""
    
    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for events:
        - 'on_episode_start'
        - 'on_episode_end'
        - 'on_step'
        - 'on_reset'
        """
    
    def off(self, event: str, callback: Callable) -> None:
        """Remove a callback."""
    
    def get_history(self, last_n: int = 10) -> List[ParameterSnapshot]:
        """Get recent parameter history."""
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
```

## Data Classes

### EnvironmentControllerConfig

```python
@dataclass
class EnvironmentControllerConfig:
    enabled: bool = True
    use_randomization: bool = True
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    seed: Optional[int] = None
    randomization_config: Optional[DomainRandomizationConfig] = None
    curriculum_config: Optional[CurriculumConfig] = None
    difficulty_config: Optional[DifficultyConfig] = None
```

### CurriculumConfig

```python
@dataclass
class CurriculumConfig:
    enabled: bool = True
    initial_stage: CurriculumStage = CurriculumStage.EASY
    auto_advance: bool = True
    advancement_window: int = 50  # Episodes to consider
    min_success_rate: float = 0.7
    stage_configs: Dict[CurriculumStage, CurriculumStageConfig] = {}
```

### DifficultyConfig

```python
@dataclass
class DifficultyConfig:
    enabled: bool = True
    initial_difficulty: float = 0.3
    min_difficulty: float = 0.1
    max_difficulty: float = 1.0
    adaptation_rate: float = 0.05
    adaptation_strategy: AdaptationStrategy = AdaptationStrategy.PROPORTIONAL
    performance_window: int = 20
    success_threshold_high: float = 0.8
    success_threshold_low: float = 0.3
```

### ParameterSnapshot

```python
@dataclass
class ParameterSnapshot:
    physics: Dict[str, float] = field(default_factory=dict)
    visual: Dict[str, float] = field(default_factory=dict)
    dynamics: Dict[str, float] = field(default_factory=dict)
    step: int = 0
    episode: int = 0
```

## Enums

### CurriculumStage

```python
class CurriculumStage(Enum):
    EASY = "easy"      # Difficulty: 0.25
    MEDIUM = "medium"  # Difficulty: 0.5
    HARD = "hard"      # Difficulty: 0.75
    EXPERT = "expert"  # Difficulty: 1.0
```

### AdaptationStrategy

```python
class AdaptationStrategy(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    PROPORTIONAL = "proportional"
    THRESHOLD = "threshold"
```

### ControllerState

```python
class ControllerState(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
```

## Examples

### Basic Usage

```python
from surg_rl.dynamics import EnvironmentController, EnvironmentControllerConfig
from surg_rl.scene_definition.schema import DomainRandomizationConfig

# Create with domain randomization
domain_config = DomainRandomizationConfig(
    physics=PhysicsRandomization(
        enabled=True,
        mass_range=(0.9, 1.1),
        friction_range=(0.4, 0.6),
    ),
    seed=42,
)

controller = EnvironmentController(
    config=EnvironmentControllerConfig(
        use_randomization=True,
        randomization_config=domain_config,
    )
)

controller.start()
params = controller.reset(seed=42)
print(f"Physics: {params.physics}")
```

### With Curriculum Learning

```python
from surg_rl.dynamics import (
    EnvironmentController,
    CurriculumConfig,
    CurriculumStage,
)

controller = EnvironmentController(
    config=EnvironmentControllerConfig(
        use_curriculum=True,
        curriculum_config=CurriculumConfig(
            initial_stage=CurriculumStage.EASY,
            auto_advance=True,
        ),
    )
)

controller.start()
for episode in range(100):
    params = controller.reset()
    # Run episode...
    info = controller.episode_end({"reward": reward, "success": success}, None)
    
    if info["curriculum"]["advanced"]:
        print(f"Advanced to {info['curriculum']['new_stage']}")
```

### With Adaptive Difficulty

```python
from surg_rl.dynamics import (
    EnvironmentController,
    DifficultyConfig,
    AdaptationStrategy,
)

controller = EnvironmentController(
    config=EnvironmentControllerConfig(
        use_adaptive_difficulty=True,
        difficulty_config=DifficultyConfig(
            initial_difficulty=0.3,
            adaptation_rate=0.05,
            adaptation_strategy=AdaptationStrategy.PROPORTIONAL,
        ),
    )
)

controller.start()
for episode in range(100):
    params = controller.reset()
    # Run episode...
    info = controller.episode_end({"reward": reward, "success": success}, None)
    
    print(f"Difficulty: {info['adaptive_difficulty']['new_difficulty']}")
```

### Using Callbacks

```python
controller = EnvironmentController(...)

def on_episode_start():
    print("Episode starting!")

def on_episode_end():
    print("Episode ended!")

controller._randomizer.on("on_episode_start", on_episode_start)
controller._randomizer.on("on_episode_end", on_episode_end)

controller.start()
```

### Reproducible Training

```python
# Same seed produces same parameters
controller1 = EnvironmentController(
    config=EnvironmentControllerConfig(seed=42, use_randomization=True)
)
controller2 = EnvironmentController(
    config=EnvironmentControllerConfig(seed=42, use_randomization=True)
)

controller1.start()
controller2.start()

params1 = controller1.reset()
params2 = controller2.reset()

assert params1.physics == params2.physics  # True
```
