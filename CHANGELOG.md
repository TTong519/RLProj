# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release preparation
- Comprehensive documentation suite
- GitHub community files (LICENSE, CODE_OF_CONDUCT, CONTRIBUTING)

## [0.1.0] - 2026-04-07

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
- Support for OpenAI, Anthropic, and Ollama LLM providers

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
- Primitive shape fallbacks for missing mesh assets

#### Dynamic Environment Controller
- BaseController abstract class defining controller interface
- ParameterRandomizer for physics/visual/dynamics randomization
- CurriculumScheduler for progressive learning stages (Easy → Medium → Hard → Expert)
- AdaptiveDifficultyController for performance-based difficulty adjustment
- EnvironmentController integrating all components
- Full test coverage (37 tests)

#### Reinforcement Learning Framework
- **Observation module**: ObservationType enum, ObservationSpec, ObservationConfig, ObservationBuilder with Gymnasium space generation, normalization, and noise support
- **Action module**: ActionType enum, ActionSpec, ActionConfig, ActionBuilder with joint/EoF/gripper actions, scaling, and relative action support
- **Reward module**: BaseRewardFunction ABC, DistanceReward (linear/exponential/Gaussian), OrientationReward, ActionPenalty, TimePenalty, SuccessReward, CollisionPenalty, CompositeReward, and `create_default_reward()` factory
- **Environment module**: SurgicalEnv (gym.Env), SurgicalEnvConfig, make_env(), make_vec_env() — full Gymnasium integration with simulator, controller, reward, observation/action builders
- **Training module**: AlgorithmConfig, TrainingConfig, TrainingManager — SB3 integration for PPO/SAC/TD3/DDPG/A2C with checkpointing and evaluation
- **Callbacks module**: TrainingProgressCallback, CheckpointCallback, CurriculumCallback, EvaluationCallback
- 54 tests covering observation spaces, action spaces, rewards, training config, and callbacks

#### CLI Interface
- `surg-rl version` - Show version
- `surg-rl config` - Display configuration
- `surg-rl generate` - Generate scenes from templates/text/images
- `surg-rl setup` - Create directories
- `surg-rl train` - Train RL agents (PPO, SAC, TD3, DDPG, A2C)
- `surg-rl evaluate` - Evaluate trained agents

#### Demo Scripts
- `demos/demo.py` - Scene visualization with MuJoCo/PyBullet
- `demos/train_demo.py` - Interactive RL training demo
- `demos/eval_demo.py` - Evaluation visualization demo
- `demos/benchmark.py` - Performance benchmark script

#### Examples
- `examples/basic_usage.py` - Basic setup example
- `examples/visualize_scene.py` - Scene visualization example
- `examples/rl_training.py` - RL training example
- `examples/rl_evaluation.py` - RL evaluation example

#### Testing Infrastructure
- All core tests passing with comprehensive coverage
- Unit tests for all modules
- Integration tests for simulators
- Test fixtures and utilities
- pytest configuration

#### Documentation
- README with project overview and quick start
- Getting Started guide
- Architecture overview
- Scene format specification
- Development guide
- API reference
- Configuration guide
- DYNAMICS_API.md for dynamic environment control
- STATUS.md for project status tracking
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

### Completed in 0.1.0 ✅
- [x] Project structure and dependencies
- [x] Scene schema and file format
- [x] Scene generation module
- [x] Scene loader and parser
- [x] Simulator abstraction layer (MuJoCo/PyBullet)
- [x] Dynamic environment controller
- [x] RL training pipeline
- [x] CLI interface and demos

### Upcoming in 0.2.0
- [ ] Advanced soft body dynamics for tissue simulation
- [ ] Multi-agent surgical scenarios
- [ ] Integration with surgical robotics hardware
- [ ] Real-time visualization improvements
- [ ] Performance optimizations for high-fidelity simulations
- [ ] Extended template library for surgical procedures

### Planned for 0.3.0
- [ ] Vectorized environments for parallel training
- [ ] TensorBoard integration for monitoring
- [ ] Pre-trained model zoo
- [ ] Distributed training across multiple machines
- [ ] Integration with surgical video datasets
- [ ] Haptic feedback simulation

### Future Releases
- [ ] Support for additional physics engines
- [ ] Integration with ROS (Robot Operating System)
- [ ] Web-based scene editor
- [ ] Cloud training integration
- [ ] Docker containers for easy deployment

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
