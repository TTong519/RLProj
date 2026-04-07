# Architecture Overview

This document describes the architecture of Surg-RL.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                        │
│                     (CLI + Python API)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴───────────────────────────────────┐
│                    Scene Generation Layer                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐       │
│  │ Text Parser │  │ Vision Parser│  │ Scene Composer      │       │
│  │             │  │              │  │                     │       │
│  │ LLM-based   │  │ VLM-based    │  │ Physics + Geometry  │       │
│  │ extraction  │  │ analysis     │  │ + Constraints       │       │
│  └─────────────┘  └──────────────┘  └─────────────────────┘       │
│         │                              │                           │
│    OpenAI/Anthropic               Image Input                      │
│    or Ollama (local)                                                │
└───────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴───────────────────────────────────┐
│                    Scene Definition Layer                          │
│  - JSON/YAML scene files                                          │
│  - Pydantic models (schema.py)                                    │
│  - Scene loader with validation                                   │
│  - Domain randomization configuration                             │
└───────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴───────────────────────────────────┐
│                    Simulator Abstraction Layer                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              BaseSimulator Interface                      │   │
│  │  - load_scene() - reset() - step() - render()             │   │
│  │  - get_state() - set_state() - apply_action()             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                              │                           │
│    ┌────┴────┐                    ┌────┴────┐                      │
│    │ MuJoCo │                    │ PyBullet│                      │
│    │ Backend│                    │ Backend │                      │
│    └────────┘                    └────────┘                        │
└───────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴───────────────────────────────────┐
│              Dynamic Environment Controller (NEW)                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              EnvironmentController                            │   │
│  │  - ParameterRandomizer (physics, visual, dynamics)            │   │
│  │  - CurriculumScheduler (Easy → Medium → Hard → Expert)       │   │
│  │  - AdaptiveDifficultyController (performance-based)            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  Features:                                                         │
│  - Domain randomization (physics, visual, dynamics)               │
│  - Curriculum learning with auto-advancement                       │
│  - Adaptive difficulty based on performance                         │
│  - Reproducible parameter sampling                                  │
│  - Callback system for episode events                              │
└───────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴───────────────────────────────────┐
│              RL Training Pipeline (PLANNED)                         │
│  - Stable-Baselines3 / RLlib integration                           │
│  - Custom reward functions for surgical tasks                      │
│  - Observation and action space definitions                        │
│  - Training monitoring and logging                                 │
└───────────────────────────────────────────────────────────────────────┘
```

## Component Overview

### 1. Scene Generation Layer

**Purpose:** Convert natural language or images into structured scene definitions.

**Components:**
- `TextParser`: Uses LLMs (OpenAI, Anthropic, Ollama) to parse text descriptions
- `VisionParser`: Uses VLMs to analyze images and generate scenes
- `SceneComposer`: Combines multiple inputs into complete scenes
- `templates.py`: Pre-defined scene templates for common tasks

**Key Features:**
- Multi-provider support (OpenAI, Anthropic, Ollama)
- Async and sync APIs
- Context-aware scene modification
- JSON extraction from LLM responses

### 2. Scene Definition Layer

**Purpose:** Define and validate surgical robotics scenes.

**Components:**
- `schema.py`: Comprehensive Pydantic models for all scene elements
- `loader.py`: File loading with caching and validation

**Key Features:**
- Strong typing with Pydantic v2
- JSON and YAML support
- Comprehensive validation
- Automatic primitive fallbacks

### 3. Simulator Abstraction Layer

**Purpose:** Provide unified interface for physics simulation.

**Components:**
- `BaseSimulator`: Abstract base class defining the interface
- `MuJoCoSimulator`: MuJoCo backend implementation
- `PyBulletSimulator`: PyBullet backend implementation
- `SceneBuilder`: Scene-to-simulator format conversion

**Key Features:**
- Unified API for both simulators
- State save/restore
- Rendering support
- Primitive fallbacks for missing assets

### 4. Dynamic Environment Controller (NEW)

**Purpose:** Provide dynamic environment modification for RL training.

**Components:**
- `BaseController`: Abstract base class with lifecycle management
- `ParameterRandomizer`: Domain randomization for physics/visual/dynamics
- `CurriculumScheduler`: Progressive learning stages (Easy → Medium → Hard → Expert)
- `AdaptiveDifficultyController`: Performance-based difficulty adjustment
- `EnvironmentController`: Main controller integrating all components

**Key Features:**
- Domain randomization configurable via scene definitions
- 4-stage curriculum with automatic advancement
- Multiple difficulty adaptation strategies (proportional, linear, exponential)
- Reproducible parameter sampling with seeds
- Callback system for episode events
- Integration with scene definitions via `from_scene()` factory method

**Usage Example:**
```python
from surg_rl.dynamics import EnvironmentController
from surg_rl.scene_definition import SceneLoader

# Create from scene
scene = SceneLoader().load("scenes/suturing.json")
controller = EnvironmentController.from_scene(
    scene,
    use_curriculum=True,
    use_adaptive=True
)

# Training loop
controller.start()
for episode in range(1000):
    params = controller.reset(seed=episode)
    
    # Apply parameters to simulator
    # physics: mass_ratio, friction, gravity
    # visual: color offsets, lighting
    # dynamics: action_noise, observation_noise
    
    # Run episode...
    info = controller.episode_end(
        {"reward": reward, "success": success},
        simulator
    )
```

### 5. CLI Layer

**Purpose:** Command-line interface for common tasks.

**Commands:**
- `surg-rl version`: Show version
- `surg-rl config`: Display configuration
- `surg-rl setup`: Create directories
- `surg-rl generate`: Generate scenes from text/image/template
- `surg-rl train`: Train RL agents (planned)
- `surg-rl evaluate`: Evaluate trained agents (planned)

## Data Flow

```
User Input (Text/Image/Template)
         │
         ▼
┌─────────────────────┐
│   Scene Generation  │
│   (TextParser/      │
│    VisionParser/     │
│    Templates)       │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Scene Definition  │
│  (SceneDefinition   │
│   Pydantic Model)   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Scene Loader      │
│   (Validation &     │
│    Caching)         │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Scene Builder     │
│   (Asset Loading &  │
│    Primitive Gen)   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Simulator         │
│   (MuJoCo/PyBullet) │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Environment       │
│   Controller        │
│   (Randomization/   │
│    Curriculum)      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   RL Training       │
│   (Future: Step 7)  │
└─────────────────────┘
```

## Extension Points

### Adding a New LLM Provider

1. Create a new parser class extending `BaseParser`
2. Implement the `parse()` and `parse_with_context()` methods
3. Add provider-specific configuration to `config.py`

### Adding a New Simulator

1. Create a new class extending `BaseSimulator`
2. Implement all abstract methods
3. Add simulator-specific configuration
4. Register in `__init__.py`

### Adding a New Scene Template

1. Create a function returning a `SceneDefinition`
2. Add to `TEMPLATE_REGISTRY` in `templates.py`

### Adding New Randomization Parameters

1. Add parameter to `PhysicsRandomization`, `VisualRandomization`, or `DynamicsRandomization` in schema.py
2. Update `ParameterRandomizer._build_parameter_bounds()` to handle new parameter
3. Implement application logic in `ParameterRandomizer.apply_parameters()`

## Performance Considerations

### Scene Caching

- Loaded scenes are cached by file path and modification time
- LRU eviction when cache is full
- Thread-safe operations

### Asset Management

- Mesh files are generated once and cached
- Primitive OBJ files are created on-demand
- Automatic cleanup of temporary files

### LLM Integration

- Async API calls for better performance
- Lazy client initialization
- Support for both sync and async usage

### Controller Performance

- Parameter sampling is O(1) for most operations
- History tracking limited by configurable window size
- Callbacks executed synchronously (keep callbacks lightweight)

## Error Handling

### Exception Hierarchy

```
SceneLoaderError (base)
├── SceneFileNotFoundError
├── SceneValidationError
├── SceneParseError
└── AssetLoadError

ParserError (base)
├── ParseTimeoutError
└── ParseValidationError
```

### Error Recovery

- Missing assets automatically fall back to primitives
- Invalid JSON/YAML raises clear error messages
- LLM response parsing handles various formats (plain JSON, markdown code blocks)

## Testing

### Test Organization

```
tests/
├── test_config.py           # Configuration tests
├── test_imports.py          # Import verification
├── test_loader.py           # Scene loader tests
├── test_schema.py           # Schema validation tests
├── test_scene_generation.py # Scene generation tests
├── test_simulators.py       # Simulator tests
└── test_dynamics.py         # Environment controller tests (NEW)
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_dynamics.py -v

# Run with coverage
pytest tests/ --cov=surg_rl
```

### Test Coverage

- Unit tests: All core functionality
- Integration tests: Scene loading, controller integration
- Edge cases: Boundary conditions, error handling
