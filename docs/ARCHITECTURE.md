# Architecture Overview

This document describes the architecture of Surg-RL.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                       │
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
│              Scene Builder (Asset Management)                      │
│  - Convert scenes to simulator formats (MJCF/URDF)               │
│  - Automatic primitive fallbacks for missing assets               │
│  - Mesh caching and optimization                                  │
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

### 4. CLI Layer

**Purpose:** Command-line interface for common tasks.

**Commands:**
- `surg-rl version`: Show version
- `surg-rl config`: Display configuration
- `surg-rl setup`: Create directories
- `surg-rl generate`: Generate scenes from text/image/template
- `surg-rl train`: Train RL agents (placeholder)
- `surg-rl evaluate`: Evaluate trained agents (placeholder)

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
