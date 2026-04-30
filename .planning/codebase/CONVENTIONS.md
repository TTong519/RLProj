---
focus: quality
created: 2026-04-29
---

# Conventions

## Summary
Surg-RL is a Python >=3.10 project using Pydantic v2, Rich logging, and strict typing. Code style is enforced by `black` and `ruff` (line length 100), with `mypy` requiring fully typed definitions. Naming follows PEP 8 with domain-specific conventions for surgical robotics schemas, simulator backends, and RL components.

## Code Style & Formatting
- **Line length:** 100 characters (`tool.black.line-length = 100`, `tool.ruff.line-length = 100`).
- **Formatter:** `black` targets `py310`, `py311`, `py312`.
- **Linter:** `ruff` with `select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]` and `ignore = ["E501"]` (line length handled by black).
- **Type checker:** `mypy` with `disallow_untyped_defs = true`, `warn_return_any = true`, and the `pydantic.mypy` plugin.
- **Lint order:** `ruff check src/ tests/` → `black --check src/ tests/` → `mypy src/surg_rl`.

## Naming Conventions
- **Classes:** `PascalCase` (`SceneDefinition`, `BaseSimulator`, `ActionBuilder`).
- **Functions / methods / variables:** `snake_case` (`load_scene`, `process_action`, `_step_count`).
- **Constants / module-level defaults:** `UPPER_SNAKE_CASE` (`DEFAULT_ACTION_SPECS`, `SUPPORTED_MESH_FORMATS`, `JOINT_POSITIONS_SPEC`).
- **Enums:** `PascalCase` class name with `UPPER_SNAKE_CASE` members (`SimulatorType.MUJOCO`, `ActionType.JOINT_POSITIONS`).
- **Private attributes:** leading underscore (`_scene`, `_loaded`, `_cache`, `_lock`).
- **Abstract base classes:** prefixed with `Base` (`BaseSimulator`, `BaseController`, `BaseRewardFunction`).
- **Exception classes:** suffixed with `Error` and inherit from a domain base (`SceneLoaderError` → `SceneValidationError`).
- **Files:** module names `snake_case.py`; test files `test_*.py`.

## Type Hints
- **Mandatory:** `mypy` enforces `disallow_untyped_defs = true`; every function/method must have typed signatures.
- **Union syntax:** Python 3.10+ pipe unions (`str | None`, `dict[str, np.ndarray] | None`).
- **Return types:** Always declared, including `-> None` for side-effect methods.
- **Numpy arrays:** Typed as `np.ndarray` (not yet migrating to `np.ndarray[Any, np.dtype[np.float64]]`).
- **Pydantic models:** Used as both schema definitions and runtime validated data containers.
- **Generic hints:** `TypeVar` used sparingly (e.g., `T = TypeVar("T", bound=SceneDefinition)` in `loader.py`).

## Docstrings
- **Style:** Google-style docstrings with `Args`, `Returns`, `Raises`, and `Attributes` sections.
- **Module docstrings:** Every file starts with a module-level docstring summarizing purpose.
- **Class docstrings:** Describe responsibilities and list public attributes.
- **Method docstrings:** Describe behavior, parameter semantics, and exceptions raised.
- **Examples:** `SurgicalEnv` in `src/surg_rl/rl/environment.py` includes a `>>>` usage example.

## Import Ordering
- **Order:** stdlib → third-party → local package (`surg_rl.*`).
- **Multi-line imports:** Parenthesized `from module import (` is used; opening parenthesis must be verified before editing.
- **Example pattern:**
  ```python
  from abc import ABC, abstractmethod
  from dataclasses import dataclass, field

  import numpy as np
  import gymnasium as gym

  from surg_rl.scene_definition.schema import SceneDefinition
  from surg_rl.utils.logging import get_logger
  ```

## Error Handling
- **Custom hierarchies:** Each domain defines a base exception (e.g., `SceneLoaderError`) and concrete subclasses (`SceneValidationError`, `SceneParseError`, `AssetLoadError`).
- **Exception fields:** Custom exceptions carry a `details: dict[str, Any]` payload for structured error reporting.
- **Recoverable errors:** Caught and logged with `logger.warning` (e.g., simulator step failure returns a terminal observation rather than crashing).
- **Fatal errors:** Logged with `logger.error` and re-raised with `raise ... from e` to preserve tracebacks.
- **Pydantic validation:** Wrapped into domain exceptions with formatted error locations (`_format_validation_errors`).

## Logging Patterns
- **Logger acquisition:** `logger = get_logger(__name__)` in every module.
- **Rich formatting:** `setup_logging()` configures `RichHandler(console=Console(stderr=True), show_path=True, show_time=True, rich_tracebacks=True)`.
- **File logging:** Optional `FileHandler` appended when `log_file` is configured; parent directories created automatically.
- **Level validation:** `setup_logging()` validates the level string and raises `ValueError` for invalid inputs.
- **Handler hygiene:** Existing handlers are closed and removed before adding new ones to prevent descriptor leaks.

## Pydantic v2 Patterns
- **Validation bypass:** `Model.model_construct(**data)` is the **only** way to skip validation. `Model(**data)` and `Model.model_validate(data)` both validate.
- **`model_validator(mode="after")`:** Must mutate via `self.model_copy(update={...})`; do not mutate `self` in place because Pydantic may discard the mutation.
- **Serialization quirk:** `model_dump()` returns **Enum objects**, not `.value` strings. Convert enums before YAML serialization (see `loader.py` `convert_tuples`).
- **Field definitions:** Heavy use of `Field(default=..., ge=..., le=..., description="...")` for constraints and documentation.
- **Nested defaults:** Default factories used for mutable nested objects (`default_factory=PhysicsConfig`, `default_factory=lambda: [LightConfig(...)]`).

## Structural Patterns
- **ABC + dataclasses:** `BaseSimulator` defines the interface; `Observation` and `State` are `@dataclass` containers.
- **Builder pattern:** `ObservationBuilder`, `ActionBuilder`, `SceneBuilder` construct complex spaces and files from config.
- **Factory functions:** `create_default_reward()`, `make_env()`, `make_vec_env()` wire defaults without exposing all constructors.
- **Context managers:** Simulators implement `__enter__` / `__exit__`; `__del__` guards against finalizer crashes with `contextlib.suppress(Exception)`.
- **Optional field guards:** Always guard before accessing nested attributes on:
  - `InstrumentConfig.pose` (default `None`)
  - `SceneDefinition.task` (default `None`)
  - `TissueConfig.physics.pybullet` override fields (`mass`, `scale`, `sim_mesh_path` default `None`)

## Key Files
- `pyproject.toml` — `tool.black`, `tool.ruff`, `tool.mypy`, `tool.pytest.ini_options` configuration.
- `src/surg_rl/scene_definition/schema.py` — Pydantic v2 models, validators, enum definitions.
- `src/surg_rl/simulators/base_simulator.py` — Abstract base class with Google-style docstrings and typed signatures.
- `src/surg_rl/utils/logging.py` — Rich logger setup, handler hygiene, level validation.
- `src/surg_rl/scene_definition/loader.py` — Custom exception hierarchy, Pydantic validation wrapping, YAML enum conversion.
- `src/surg_rl/cli.py` — Typer CLI with Rich console tables and structured error messages.
- `AGENTS.md` — Project-specific Pydantic v2 quirks and simulator backend conventions.
