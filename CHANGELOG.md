# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release preparation
- Comprehensive documentation suite
- GitHub community files (LICENSE, CODE_OF_CONDUCT, CONTRIBUTING)

## [0.1.0] - 2024-04-06

### Added

#### Core Infrastructure
- Initial project structure and setup
- Python package configuration with `pyproject.toml`
- Development environment setup with virtual environment support
- Core dependencies specification (NumPy, SciPy, MuJoCo, PyBullet, etc.)

#### Scene Definition Module
- Pydantic schema for scene definitions (`SceneDefinition`, `SceneObject`, etc.)
- Scene loader supporting both YAML and JSON formats
- Scene validation against schema
- Support for complex scene hierarchies and references

#### Scene Generation System
- Text-based scene generation using LLM integration
- Vision-based scene generation from surgical images
- Template system for common surgical procedures
- Scene composer orchestrator
- Support for OpenAI and Anthropic LLM providers

#### Simulation Backends
- Abstract base simulator interface for unified API
- MuJoCo simulator implementation with:
  - Soft body dynamics support
  - Tendon and muscle mechanics
  - High-fidelity contact modeling
  - Custom rendering options
- PyBullet simulator implementation with:
  - Fast prototyping capabilities
  - URDF model support
  - Debug visualization tools
- Scene builder utilities for converting definitions to simulator formats

#### Reinforcement Learning Framework
- Gymnasium-compatible environment wrapper
- Integration with Stable-Baselines3
- Support for multiple RL algorithms:
  - PPO (Proximal Policy Optimization)
  - SAC (Soft Actor-Critic)
  - TD3 (Twin Delayed DDPG)
  - DDPG (Deep Deterministic Policy Gradient)
  - A2C (Advantage Actor-Critic)
- Policy wrapper for inference and deployment
- Multi-environment training support

#### CLI Interface
- Command-line interface for scene generation
- Training orchestration commands
- Scene validation commands
- Policy evaluation commands

#### Utilities
- Configuration management system
- YAML-based configuration with environment variable support
- Logging utilities with file and console handlers
- Helper functions for common operations

#### Testing Infrastructure
- Unit tests for core modules
- Integration tests for simulators
- Test fixtures and utilities
- pytest configuration

#### Examples
- Basic usage examples
- Scene generation examples
- Training examples

#### Documentation
- README with project overview and quick start
- Getting Started guide
- Architecture overview
- Scene format specification
- Development guide
- API reference
- Configuration guide
- Contributing guidelines
- Code of conduct

### Example Scenes
- Minimal scene example for testing
- Simple suturing scene
- Laparoscopic dissection scene

### Configuration
- Default configuration file
- Environment variable support
- Scene generation templates
- Logging configuration

## [0.0.1] - 2024-03-01

### Added
- Initial project skeleton
- Basic directory structure
- Git repository initialization

---

## Version History

- **0.1.0**: Initial alpha release with core functionality
- **0.0.1**: Project initialization

---

## Upgrade Guide

### From 0.0.1 to 0.1.0

This is the first usable release. To upgrade:

1. Pull the latest changes
2. Install dependencies: `pip install -r requirements.txt`
3. Install the package in development mode: `pip install -e .`
4. Configure your LLM API keys (see `docs/CONFIGURATION.md`)
5. Run tests to verify installation: `pytest`

---

## Roadmap

### Upcoming in 0.2.0
- [ ] Advanced soft body dynamics for tissue simulation
- [ ] Multi-agent surgical scenarios
- [ ] Integration with surgical robotics hardware
- [ ] Real-time visualization improvements
- [ ] Performance optimizations for high-fidelity simulations
- [ ] Extended template library for surgical procedures

### Planned for 0.3.0
- [ ] Domain randomization for robust policy learning
- [ ] Curriculum learning support
- [ ] Distributed training across multiple machines
- [ ] Integration with surgical video datasets
- [ ] Augmented reality visualization overlay
- [ ] Haptic feedback simulation

### Future Releases
- [ ] Support for additional physics engines
- [ ] Integration with ROS (Robot Operating System)
- [ ] Web-based scene editor
- [ ] Pre-trained policy zoo
- [ ] Docker containers for easy deployment
- [ ] Cloud training integration

---

## Deprecation Policy

We follow semantic versioning:
- **Major version (X.0.0)**: Breaking changes, deprecations become removals
- **Minor version (0.X.0)**: New features, deprecations introduced
- **Patch version (0.0.X)**: Bug fixes, no deprecations

Deprecated features will:
1. Be announced in CHANGELOG.md
2. Show runtime warnings
3. Be removed in the next major version

---

## Security

### Reporting Vulnerabilities

If you discover a security vulnerability, please:
1. Do NOT open a public issue
2. Email the maintainers directly
3. Include detailed steps to reproduce
4. Wait for response before public disclosure

See [SECURITY.md](SECURITY.md) for full security policy (if available).

---

## Acknowledgments

We thank the following projects for inspiration and components:
- [OpenAI Gym](https://gym.openai.com/) / [Gymnasium](https://gymnasium.farama.org/)
- [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3)
- [MuJoCo](https://mujoco.org/)
- [PyBullet](https://pybullet.org/)

---

For a detailed view of changes in each release, see the [GitHub Releases](https://github.com/yourusername/surg-rl/releases) page.
