# Surg-RL Documentation

Welcome to the Surg-RL documentation! This comprehensive guide will help you get started and master the Surg-RL framework for surgical robotics reinforcement learning.

## 📚 Documentation Index

### Getting Started

- **[README.md](../README.md)** - Project overview and quick start guide
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Detailed installation and setup instructions
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Common commands and patterns

### Technical Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design decisions
- **[API_REFERENCE.md](API_REFERENCE.md)** - Comprehensive API documentation
- **[DYNAMICS_API.md](DYNAMICS_API.md)** - Dynamic environment control API
- **[SCENE_FORMAT.md](SCENE_FORMAT.md)** - Scene definition format specification
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration options and best practices

### Development

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development workflow and guidelines
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### Project Status

Project status and roadmap live in `.planning/STATE.md` and
`.planning/ROADMAP.md` (current at v0.4.2 shipped; v0.5.0 not yet planned).
Pre-GSD historical snapshots of `STATUS.md` and `IMPLEMENTATION_PLAN.md`
are archived in `.planning/milestones/v0.0.0-*.md`.

## 🚀 Quick Navigation

### For New Users

1. Start with the [README](../README.md) to understand what Surg-RL does
2. Follow the [Getting Started Guide](GETTING_STARTED.md) to install and set up
3. Read the [Scene Format Specification](SCENE_FORMAT.md) to understand scene definitions
4. Explore the [API Reference](API_REFERENCE.md) to learn the API

### For Developers

1. Read the [Architecture Overview](ARCHITECTURE.md) to understand the system design
2. Follow the [Development Guide](DEVELOPMENT.md) for development workflow
3. Review the [Configuration Guide](CONFIGURATION.md) for advanced configuration
4. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues

### For Contributors

1. Read the [Contributing Guidelines](../CONTRIBUTING.md)
2. Follow the [Development Guide](DEVELOPMENT.md)
3. Review the [Code of Conduct](../CODE_OF_CONDUCT.md)
4. Check [`.planning/STATE.md`](../.planning/STATE.md) for current priorities

## 📖 Documentation by Topic

### Scene Generation

- [Scene Format Specification](SCENE_FORMAT.md) - Complete scene format reference
- [API Reference - Scene Generation](API_REFERENCE.md#scene-generation) - Scene generation API
- [Configuration - Scene Generation](CONFIGURATION.md#scene-generation-configuration) - LLM settings

### Simulators

- [Architecture - Simulators](ARCHITECTURE.md#simulators) - Simulator design
- [API Reference - Simulators](API_REFERENCE.md#simulators) - Simulator API
- [Configuration - Simulation](CONFIGURATION.md#simulation-configuration) - Physics settings

### Dynamic Environment Control

- [DYNAMICS_API.md](DYNAMICS_API.md) - Complete dynamics module API
- [Architecture - Dynamics](ARCHITECTURE.md#dynamic-environment-controller) - Controller architecture
- Quick start:
  ```python
  from surg_rl.dynamics import EnvironmentController
  
  controller = EnvironmentController.from_scene(scene)
  controller.start()
  params = controller.reset(seed=42)
  ```

### Reinforcement Learning

- [API Reference - RL](API_REFERENCE.md#reinforcement-learning) - RL training API
- [Configuration - RL Training](CONFIGURATION.md#rl-training-configuration) - Training settings

### CLI Usage

- [API Reference - CLI](API_REFERENCE.md#cli) - CLI commands
- [Quick Reference](QUICK_REFERENCE.md) - Common CLI patterns

## 🔧 Advanced Topics

### Domain Randomization

The dynamics module provides domain randomization for:
- **Physics**: mass, friction, gravity, damping, stiffness
- **Visual**: colors, textures, lighting
- **Dynamics**: action noise, observation noise, delays

```python
from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    PhysicsRandomization,
)

domain_config = DomainRandomizationConfig(
    physics=PhysicsRandomization(
        enabled=True,
        mass_range=(0.9, 1.1),
        friction_range=(0.4, 0.6),
    ),
)
```

### Curriculum Learning

Progressive difficulty with automatic advancement:
- **EASY** (0.25) → **MEDIUM** (0.5) → **HARD** (0.75) → **EXPERT** (1.0)

```python
from surg_rl.dynamics import CurriculumScheduler, CurriculumConfig

scheduler = CurriculumScheduler(
    curriculum_config=CurriculumConfig(auto_advance=True)
)
```

### Adaptive Difficulty

Performance-based difficulty adjustment:
```python
from surg_rl.dynamics import AdaptiveDifficultyController, DifficultyConfig

adaptive = AdaptiveDifficultyController(
    difficulty_config=DifficultyConfig(
        adaptation_rate=0.05,
        success_threshold_high=0.8,
    )
)
```

### Custom Components

- [Configuration - Advanced Topics](CONFIGURATION.md#advanced-topics) - Custom reward functions, policies, etc.
- [Development Guide](DEVELOPMENT.md) - Extending Surg-RL

### Integration

- [Architecture Overview](ARCHITECTURE.md) - Understanding system integration points
- [API Reference](API_REFERENCE.md) - All public APIs

### Performance Optimization

- [Configuration - Best Practices](CONFIGURATION.md#best-practices) - Optimization tips
- [Architecture - Performance](ARCHITECTURE.md) - Performance considerations

## 📝 Contributing to Documentation

We welcome documentation improvements! To contribute:

1. Fork the repository
2. Make your changes in the `docs/` directory
3. Follow the existing documentation style
4. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.

## 🆘 Getting Help

If you can't find what you're looking for:

1. Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Search existing GitHub issues
3. Open a new issue with the "question" label
4. Join our community discussions

## 📄 Document Formats

All documentation is written in Markdown with the following conventions:

- **Bold** for important terms
- `code` for commands, file names, and code snippets
- [Links]() for cross-references
- Code blocks for examples:

```python
# Python examples
from surg_rl import load_scene
```

```bash
# Bash examples
surg-rl generate --help
```

## 🔄 Documentation Updates

Documentation is versioned with the codebase. Each release includes:

- Updated API references
- New feature documentation
- Migration guides if needed
- Changelog updates

Check the [CHANGELOG.md](../CHANGELOG.md) for recent changes.

---

**Happy coding!** 🎉

If you have suggestions for improving the documentation, please open an issue or pull request.
