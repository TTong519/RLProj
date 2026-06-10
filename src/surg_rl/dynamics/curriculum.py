"""Curriculum learning scheduler for progressive task difficulty.

This module provides curriculum learning support for surgical robotics
training, allowing tasks to start easy and progressively increase in
difficulty as the agent improves.
"""

import contextlib
import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from surg_rl.utils.logging import get_logger

from .base_controller import (
    BaseController,
    ControllerConfig,
    ParameterSnapshot,
)

logger = get_logger(__name__)


class CurriculumStage(Enum):
    """Stages of curriculum learning."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"
    CUSTOM = "custom"


@dataclass
class CurriculumStageConfig:
    """Configuration for a single curriculum stage.

    Attributes:
        name: Stage name.
        stage: Stage enum value.
        difficulty: Difficulty level (0.0 to 1.0).
        parameter_overrides: Parameter overrides for this stage.
        success_threshold: Success rate threshold to advance.
        episode_threshold: Minimum episodes before advancement.
        reward_threshold: Reward threshold to advance.
        task_param_bounds: Optional per-task parameter bounds for difficulty
            interpolation (Phase 21 — task curriculum). When set, this dict
            is merged into parameter_overrides during sample_parameters().
            Each key maps to a [min, max] pair or a fixed value.
    """

    name: str
    stage: CurriculumStage
    difficulty: float = 0.5
    parameter_overrides: dict[str, Any] = field(default_factory=dict)
    success_threshold: float = 0.8
    episode_threshold: int = 100
    reward_threshold: float = 0.0
    task_param_bounds: dict[str, Any] = field(default_factory=dict)


@dataclass
class CurriculumConfig:
    """Configuration for curriculum learning.

    Attributes:
        enabled: Whether curriculum learning is enabled.
        initial_stage: Starting stage.
        auto_advance: Whether to automatically advance stages.
        advancement_window: Number of episodes to consider for advancement.
        min_success_rate: Minimum success rate to advance.
        difficulty_hysteresis: Prevents difficulty oscillation when success rate
            hovers near threshold. Stage must succeed at current difficulty for
            hysteresis*100% extra episodes before advancing. (Phase 21)
        stage_configs: Per-stage configurations.
    """

    enabled: bool = True
    initial_stage: CurriculumStage = CurriculumStage.EASY
    auto_advance: bool = True
    advancement_window: int = 50
    min_success_rate: float = 0.7
    difficulty_hysteresis: float = 0.05
    stage_configs: dict[CurriculumStage, CurriculumStageConfig] = field(default_factory=dict)


class CurriculumScheduler(BaseController):
    """Curriculum learning scheduler for progressive difficulty.

    This controller manages curriculum learning by tracking episode results
    and automatically advancing through difficulty stages based on agent
    performance.

    Example:
        >>> config = CurriculumConfig(
        ...     initial_stage=CurriculumStage.EASY,
        ...     auto_advance=True,
        ... )
        >>> scheduler = CurriculumScheduler(config)
        >>> scheduler.start()
        >>> params = scheduler.reset(seed=42)
        >>> # Run episode...
        >>> curriculum_info = scheduler.episode_end(
        ...     {"reward": 100, "success": True},
        ...     simulator,
        ... )
    """

    # Default stage configurations
    DEFAULT_STAGES: dict[CurriculumStage, CurriculumStageConfig] = {
        CurriculumStage.EASY: CurriculumStageConfig(
            name="Easy",
            stage=CurriculumStage.EASY,
            difficulty=0.25,
            parameter_overrides={
                "mass_ratio": (0.95, 1.05),
                "friction": (0.45, 0.55),
                "action_noise": 0.01,
            },
            success_threshold=0.7,
            episode_threshold=50,
        ),
        CurriculumStage.MEDIUM: CurriculumStageConfig(
            name="Medium",
            stage=CurriculumStage.MEDIUM,
            difficulty=0.5,
            parameter_overrides={
                "mass_ratio": (0.9, 1.1),
                "friction": (0.4, 0.6),
                "action_noise": 0.03,
            },
            success_threshold=0.75,
            episode_threshold=100,
        ),
        CurriculumStage.HARD: CurriculumStageConfig(
            name="Hard",
            stage=CurriculumStage.HARD,
            difficulty=0.75,
            parameter_overrides={
                "mass_ratio": (0.85, 1.15),
                "friction": (0.35, 0.65),
                "action_noise": 0.05,
            },
            success_threshold=0.8,
            episode_threshold=150,
        ),
        CurriculumStage.EXPERT: CurriculumStageConfig(
            name="Expert",
            stage=CurriculumStage.EXPERT,
            difficulty=1.0,
            parameter_overrides={
                "mass_ratio": (0.8, 1.2),
                "friction": (0.3, 0.7),
                "action_noise": 0.08,
            },
            success_threshold=1.0,
            episode_threshold=200,
        ),
    }

    def __init__(
        self,
        config: ControllerConfig | None = None,
        curriculum_config: CurriculumConfig | None = None,
    ):
        """Initialize the curriculum scheduler.

        Args:
            config: Base controller configuration.
            curriculum_config: Curriculum learning configuration.
        """
        super().__init__(config)
        self.curriculum_config = curriculum_config or CurriculumConfig()

        # Initialize stages
        self._stages = copy.deepcopy(self.DEFAULT_STAGES)
        if self.curriculum_config.stage_configs:
            self._stages.update(self.curriculum_config.stage_configs)

        # Current state
        self._current_stage = self.curriculum_config.initial_stage
        self._stage_history: list[CurriculumStage] = []
        self._performance_history: list[dict[str, float]] = []
        self._stage_entry_episode: int = 0

        # Active dynamics parameters (stored for downstream consumption)
        self._active_action_noise: float | None = None
        self._active_joint_noise: float | None = None
        self._active_delay: float | None = None

        # Stage order
        self._stage_order = [
            CurriculumStage.EASY,
            CurriculumStage.MEDIUM,
            CurriculumStage.HARD,
            CurriculumStage.EXPERT,
        ]

    @property
    def current_stage(self) -> CurriculumStage:
        """Current curriculum stage."""
        return self._current_stage

    @property
    def current_difficulty(self) -> float:
        """Current difficulty level (0.0 to 1.0)."""
        return self._stages[self._current_stage].difficulty

    @property
    def stage_config(self) -> CurriculumStageConfig:
        """Current stage configuration."""
        return self._stages[self._current_stage]

    def set_stage(self, stage: CurriculumStage) -> None:
        """Manually set the curriculum stage.

        Args:
            stage: Stage to set.
        """
        if stage != self._current_stage:
            self._stage_entry_episode = self._episode
        self._current_stage = stage
        self._stage_history.append(stage)

    def advance_stage(self) -> bool:
        """Advance to the next curriculum stage.

        Returns:
            True if advanced, False if already at max stage.
        """
        if self._current_stage not in self._stage_order:
            return False
        current_idx = self._stage_order.index(self._current_stage)
        if current_idx < len(self._stage_order) - 1:
            self._stage_entry_episode = self._episode
            self._current_stage = self._stage_order[current_idx + 1]
            self._stage_history.append(self._current_stage)
            return True
        return False

    def regress_stage(self) -> bool:
        """Regress to the previous curriculum stage.

        Returns:
            True if regressed, False if already at min stage.
        """
        if self._current_stage not in self._stage_order:
            return False
        current_idx = self._stage_order.index(self._current_stage)
        if current_idx > 0:
            self._stage_entry_episode = self._episode
            self._current_stage = self._stage_order[current_idx - 1]
            self._stage_history.append(self._current_stage)
            return True
        return False

    def sample_parameters(self) -> ParameterSnapshot:
        """Sample parameters for current curriculum stage.

        Returns:
            Parameter snapshot with stage-specific parameters.
        """
        stage_cfg = self._stages[self._current_stage]

        # D-08: Merge task_param_bounds into parameter_overrides for interpolation
        # difficulty is the single source of truth — no separate task_difficulty field
        task_bounds = getattr(stage_cfg, "task_param_bounds", None) or {}
        if task_bounds:
            merged_overrides = dict(stage_cfg.parameter_overrides)
            merged_overrides.update(task_bounds)
        else:
            merged_overrides = stage_cfg.parameter_overrides

        physics_params = {}
        visual_params = {}
        dynamics_params = {}

        # Sample from stage parameter overrides (with task_param_bounds merged in)
        for param_name, param_value in merged_overrides.items():
            if isinstance(param_value, tuple) and len(param_value) == 2:
                # Sample uniformly from range
                value = self._rng.uniform(param_value[0], param_value[1])
            else:
                # Use fixed value
                value = param_value

            # Categorize parameter
            if param_name in [
                "mass_ratio",
                "friction",
                "damping",
                "stiffness",
                "gravity_x",
                "gravity_y",
                "gravity_z",
            ]:
                physics_params[param_name] = value
            elif param_name in ["action_noise", "joint_noise", "delay"]:
                dynamics_params[param_name] = value
            else:
                visual_params[param_name] = value

        return ParameterSnapshot(
            physics=physics_params,
            visual=visual_params,
            dynamics=dynamics_params,
            episode=self._episode,
            step=self._step,
        )

    def apply_parameters(
        self,
        snapshot,
        simulator,
    ) -> bool:
        """Apply curriculum parameters to simulator.

        Expands beyond gravity to include mass, friction, damping, and stiffness
        when the simulator exposes the appropriate APIs.

        Args:
            snapshot: Parameters to apply.
            simulator: Simulator instance.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # --- Physics ---
            # Gravity
            if "gravity_x" in snapshot.physics:
                gx = snapshot.physics.get("gravity_x", 0.0)
                gy = snapshot.physics.get("gravity_y", 0.0)
                gz = snapshot.physics.get("gravity_z", -9.81)
                if hasattr(simulator, "setGravity"):
                    simulator.setGravity(gx, gy, gz)
                elif hasattr(simulator, "_physics_client"):
                    import pybullet as p

                    p.setGravity(
                        gx,
                        gy,
                        gz,
                        physicsClientId=simulator._physics_client,
                    )

            # Mass ratio applied via simulator.set_body_property when available
            if "mass_ratio" in snapshot.physics and hasattr(simulator, "set_body_property"):
                ratio = snapshot.physics["mass_ratio"]
                # Discover body names from simulator internals
                body_names = []
                if hasattr(simulator, "_body_ids"):
                    body_names.extend(simulator._body_ids.keys())
                elif hasattr(simulator, "_scene") and simulator._scene is not None:
                    scene = simulator._scene
                    body_names.extend(r.name for r in getattr(scene, "robots", []))
                    body_names.extend(t.name for t in getattr(scene, "tissues", []))
                    body_names.extend(i.name for i in getattr(scene, "instruments", []))
                for name in body_names:
                    with contextlib.suppress(Exception):
                        simulator.set_body_property(name, "mass", ratio)

            # Friction coefficient applied via set_body_property
            if "friction" in snapshot.physics and hasattr(simulator, "set_body_property"):
                friction = snapshot.physics["friction"]
                body_names = []
                if hasattr(simulator, "_body_ids"):
                    body_names.extend(simulator._body_ids.keys())
                elif hasattr(simulator, "_scene") and simulator._scene is not None:
                    scene = simulator._scene
                    body_names.extend(r.name for r in getattr(scene, "robots", []))
                    body_names.extend(t.name for t in getattr(scene, "tissues", []))
                for name in body_names:
                    with contextlib.suppress(Exception):
                        simulator.set_body_property(name, "friction", friction)

            # Damping coefficient (MuJoCo direct / PyBullet fallback)
            if "damping" in snapshot.physics:
                damping = snapshot.physics["damping"]
                if hasattr(simulator, "_model") and hasattr(simulator._model, "dof_damping"):
                    simulator._model.dof_damping[:] = damping
                elif hasattr(simulator, "_physics_client") and hasattr(simulator, "_body_ids"):
                    import pybullet as p

                    for body_id in simulator._body_ids.values():
                        p.changeDynamics(
                            body_id,
                            -1,
                            linearDamping=damping,
                            angularDamping=damping,
                            physicsClientId=simulator._physics_client,
                        )

            # Stiffness (soft-body) — only MuJoCo flex has this natively
            if "stiffness" in snapshot.physics:
                stiffness = snapshot.physics["stiffness"]
                if hasattr(simulator, "_model") and hasattr(simulator._model, "flex_stiffness"):
                    with contextlib.suppress(Exception):
                        simulator._model.flex_stiffness[:] = stiffness

            # --- Visual ---
            if snapshot.visual and hasattr(simulator, "set_body_property"):
                intensity = snapshot.visual.get("lighting_intensity")
                if intensity is not None:
                    # No universal lighting setter; log for now
                    logger.debug(
                        f"Visual parameter lighting_intensity={intensity} not applied (no simulator API)"
                    )

            # --- Dynamics ---
            for key in ("action_noise", "joint_noise", "delay"):
                value = snapshot.dynamics.get(key)
                if value is not None:
                    setter_name = f"set_{key}"
                    if hasattr(simulator, setter_name):
                        getattr(simulator, setter_name)(value)
                    else:
                        logger.debug(
                            f"Dynamics parameter {key}={value} received but cannot be applied directly (no simulator.{setter_name})"
                        )
                        setattr(self, f"_active_{key}", value)

            return True
        except Exception:
            return False

    def update_curriculum(
        self,
        episode: int,
        metrics: dict[str, float],
    ) -> dict[str, Any]:
        """Update curriculum based on episode results.

        Args:
            episode: Episode number.
            metrics: Episode metrics (reward, success, etc.).

        Returns:
            Curriculum update information.
        """
        # Store performance
        self._performance_history.append(metrics)

        # Keep only recent history
        if len(self._performance_history) > self.curriculum_config.advancement_window:
            self._performance_history = self._performance_history[
                -self.curriculum_config.advancement_window :
            ]

        curriculum_info = {
            "episode": episode,
            "stage": self._current_stage.value,
            "difficulty": self.current_difficulty,
            "advanced": False,
        }

        # Check if we should advance
        if self.curriculum_config.auto_advance and self._should_advance():
            advanced = self.advance_stage()
            curriculum_info["advanced"] = advanced
            if advanced:
                curriculum_info["new_stage"] = self._current_stage.value
                curriculum_info["new_difficulty"] = self.current_difficulty

        return curriculum_info

    def _should_advance(self) -> bool:
        """Check if conditions are met to advance curriculum stage.

        Returns:
            True if should advance, False otherwise.
        """
        stage_cfg = self._stages[self._current_stage]

        # Check episode threshold (per-stage count)
        episodes_at_stage = self._episode - self._stage_entry_episode
        if episodes_at_stage < stage_cfg.episode_threshold:
            return False

        # Check if already at max stage
        if self._current_stage not in self._stage_order:
            return False
        current_idx = self._stage_order.index(self._current_stage)
        if current_idx >= len(self._stage_order) - 1:
            return False

        # Calculate performance metrics
        recent_metrics = self._performance_history[-self.curriculum_config.advancement_window :]

        if not recent_metrics:
            return False

        # Check success rate
        success_rate = sum(m.get("success", 0) for m in recent_metrics) / len(recent_metrics)

        if success_rate >= stage_cfg.success_threshold:
            return True

        # Check reward threshold if set
        if stage_cfg.reward_threshold > 0:
            avg_reward = sum(m.get("reward", 0) for m in recent_metrics) / len(recent_metrics)
            if avg_reward >= stage_cfg.reward_threshold:
                return True

        return False

    def episode_end_with_task_result(
        self,
        task_result,  # TaskResult from per-task reward check_success
        simulator: Any,
    ) -> dict[str, Any]:
        """D-09: Handle episode end with structured TaskResult.

        Auto-reads TaskResult from the environment, updates difficulty
        progression internally, and triggers parameter recalculation.

        Args:
            task_result: TaskResult from reward.check_success()/check_failure().
            simulator: Simulator instance.

        Returns:
            Curriculum update information.
        """
        # Extract standard metrics from TaskResult for existing update_curriculum path
        metrics = {
            "success": task_result.success,
            "reward": 0.0,  # filled by upstream
        }
        # Merge task-specific metrics into performance history
        if task_result.metrics:
            metrics.update(task_result.metrics)

        # Delegate to standard episode_end pipeline
        return self.episode_end(metrics, simulator)

    def _should_regress(self) -> bool:
        """Check if conditions are met to regress curriculum stage.

        D-09: Regression occurs when success rate drops significantly below
        threshold, with hysteresis to prevent oscillation.

        Returns:
            True if should regress, False otherwise.
        """
        stage_cfg = self._stages[self._current_stage]

        episodes_at_stage = self._episode - self._stage_entry_episode
        if episodes_at_stage < stage_cfg.episode_threshold:
            return False

        if self._current_stage not in self._stage_order:
            return False
        current_idx = self._stage_order.index(self._current_stage)
        if current_idx <= 0:
            return False

        recent_metrics = self._performance_history[-self.curriculum_config.advancement_window :]
        if not recent_metrics:
            return False

        success_rate = sum(m.get("success", 0) for m in recent_metrics) / len(recent_metrics)
        hysteresis = self.curriculum_config.difficulty_hysteresis
        regression_threshold = stage_cfg.success_threshold - 0.2 - hysteresis

        return success_rate < regression_threshold

    def get_progress(self) -> dict[str, Any]:
        """Get curriculum progress information.

        Returns:
            Dictionary with progress details.
        """
        if self._current_stage not in self._stage_order:
            return {"current_stage": self._current_stage.value, "stage_index": -1, "progress": 0.0}
        stage_idx = self._stage_order.index(self._current_stage)
        progress = stage_idx / (len(self._stage_order) - 1) if len(self._stage_order) > 1 else 1.0

        return {
            "current_stage": self._current_stage.value,
            "stage_index": stage_idx,
            "total_stages": len(self._stage_order),
            "progress": progress,
            "difficulty": self.current_difficulty,
            "episodes_at_stage": self._episode - self._stage_entry_episode,
        }

    def get_performance_summary(self) -> dict[str, float]:
        """Get performance summary over recent episodes.

        Returns:
            Dictionary with performance metrics.
        """
        if not self._performance_history:
            return {"success_rate": 0.0, "avg_reward": 0.0}

        recent = self._performance_history[-self.curriculum_config.advancement_window :]

        return {
            "success_rate": sum(m.get("success", 0) for m in recent) / len(recent),
            "avg_reward": sum(m.get("reward", 0) for m in recent) / len(recent),
            "total_episodes": len(self._performance_history),
        }

    def reset_curriculum(self) -> None:
        """Reset curriculum to initial stage."""
        self._current_stage = self.curriculum_config.initial_stage
        self._stage_history.clear()
        self._performance_history.clear()
        self._episode = 0
        self._stage_entry_episode = 0
        self._stages = copy.deepcopy(self.DEFAULT_STAGES)
        if self.curriculum_config.stage_configs:
            self._stages.update(self.curriculum_config.stage_configs)
