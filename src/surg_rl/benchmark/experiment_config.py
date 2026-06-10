"""ExperimentConfig Pydantic model for benchmark configuration.

This module defines the ExperimentConfig class which extends BenchmarkConfig
from scene_definition.schema and adds all benchmark-specific fields.

YAML round-trip is deterministic: model_dump(mode='json') -> yaml.dump(sort_keys=True)
produces byte-identical output for the same input.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, field_validator, model_validator

from surg_rl.scene_definition.schema import BenchmarkConfig


class ExperimentConfig(BenchmarkConfig):
    """Complete experiment configuration for benchmark runs.

    Extends BenchmarkConfig with benchmark-specific fields. All fields must
    be present in YAML output (no None elision) for deterministic round-trip.
    """

    # Task specification
    task: str | None = Field(
        default=None,
        description="Surgical task type to benchmark (suturing, knot_tying, needle_insertion, grasping, cutting, dissection)",
    )

    # Training parameters
    timesteps: int = Field(
        default=100_000,
        ge=1000,
        description="Training timesteps per seed run",
    )

    # Simulator backends
    backends: list[Literal["mujoco", "pybullet", "all"]] = Field(
        default=["all"],
        description="Simulator backends to benchmark",
    )

    # Parallelism
    max_parallel: int = Field(
        default_factory=lambda: max(1, os.cpu_count() - 1),
        ge=1,
        description="Max parallel seed processes",
    )

    # Experiment naming
    experiment_name: str = Field(
        default_factory=lambda: f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        description="Experiment name for output directory",
    )

    # Hyperparameters (per-algorithm overrides)
    hyperparameters: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-algorithm hyperparameter overrides",
    )

    # Evaluation
    eval_episodes: int = Field(
        default=10,
        ge=1,
        description="Evaluation episodes per seed after training",
    )
    render_eval: bool = Field(
        default=False,
        description="Render during evaluation episodes",
    )

    # Output options
    save_per_seed_csv: bool = Field(
        default=True,
        description="Save per-seed metrics CSV",
    )
    save_aggregated_json: bool = Field(
        default=True,
        description="Save aggregated metrics.json",
    )

    # DreamerV3 comparison (Phase 24)
    dreamer_comparison: bool = Field(
        default=False,
        description="Include DreamerV3 comparison (auto-discovers checkpoints from models/dreamerv3/)",
    )
    dreamer_obs_types: list[Literal["pixels", "state"]] = Field(
        default_factory=lambda: ["state"], description="Observation types to evaluate for DreamerV3"
    )
    dreamer_eval_episodes: int = Field(
        default=10, ge=1, description="Evaluation episodes for DreamerV3"
    )

    @field_validator("backends", mode="before")
    @classmethod
    def _normalize_backends(cls, v: Any) -> list[str]:
        """Normalize backends input - allow string or list."""
        if isinstance(v, str):
            return [v]
        return v

    @model_validator(mode="after")
    def _validate_backends(self) -> "ExperimentConfig":
        """Validate backend values."""
        valid_backends = {"mujoco", "pybullet", "all"}
        for backend in self.backends:
            if backend not in valid_backends:
                raise ValueError(f"Invalid backend: {backend}. Must be one of {valid_backends}")
        return self

    def to_yaml(self, path: str | Path) -> None:
        """Write deterministic YAML to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use model_dump with mode='json' to get JSON-serializable types
        data = self.model_dump(mode="json")

        # Write with sort_keys=True for deterministic output
        with open(path, "w") as f:
            yaml.dump(data, f, sort_keys=True, default_flow_style=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        """Load ExperimentConfig from YAML file."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    @classmethod
    def merge(cls, base: "ExperimentConfig", overrides: dict) -> "ExperimentConfig":
        """Merge CLI overrides over YAML base config.

        Performs shallow merge for nested dicts (like hyperparameters).
        """
        base_data = base.model_dump(mode="json")

        def deep_merge(base_dict: dict, override_dict: dict) -> dict:
            """Merge two dicts, with overrides taking precedence."""
            result = base_dict.copy()
            for key, value in override_dict.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    # Shallow merge for nested dicts
                    result[key] = {**result[key], **value}
                else:
                    result[key] = value
            return result

        merged_data = deep_merge(base_data, overrides)
        return cls.model_validate(merged_data)

    @property
    def expanded_backends(self) -> list[str]:
        """Get expanded list of backends (replaces 'all' with actual backends)."""
        if "all" in self.backends:
            return ["mujoco", "pybullet"]
        return self.backends

    @property
    def effective_algorithms(self) -> list[str]:
        """Get effective algorithm list (None = all 5 SB3 algorithms)."""
        if self.algorithms is None:
            return ["PPO", "SAC", "TD3", "DDPG", "A2C"]
        return self.algorithms
