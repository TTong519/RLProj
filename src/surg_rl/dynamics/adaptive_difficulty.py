"""Adaptive difficulty controller for RL training.

This module provides adaptive difficulty adjustment based on agent
performance, allowing dynamic difficulty scaling during training.
"""

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from .base_controller import (
    BaseController,
    ControllerConfig,
    ParameterSnapshot,
)


class AdaptationStrategy(Enum):
    """Strategy for difficulty adaptation."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    PROPORTIONAL = "proportional"
    THRESHOLD = "threshold"


class AdaptationDirection(Enum):
    """Direction of difficulty adaptation."""
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"


@dataclass
class DifficultyConfig:
    """Configuration for adaptive difficulty.
    
    Attributes:
        enabled: Whether adaptive difficulty is enabled.
        initial_difficulty: Starting difficulty (0.0 to 1.0).
        min_difficulty: Minimum difficulty level.
        max_difficulty: Maximum difficulty level.
        adaptation_rate: Rate of difficulty change.
        adaptation_strategy: Strategy for adaptation.
        performance_window: Number of episodes to consider.
        success_threshold_high: High success threshold (increase difficulty).
        success_threshold_low: Low success threshold (decrease difficulty).
        reward_threshold_high: High reward threshold.
        reward_threshold_low: Low reward threshold.
    """
    enabled: bool = True
    initial_difficulty: float = 0.3
    min_difficulty: float = 0.1
    max_difficulty: float = 1.0
    adaptation_rate: float = 0.05
    adaptation_strategy: AdaptationStrategy = AdaptationStrategy.PROPORTIONAL
    performance_window: int = 20
    success_threshold_high: float = 0.8
    success_threshold_low: float = 0.3
    reward_threshold_high: float = 0.0
    reward_threshold_low: float = -100.0


@dataclass
class DifficultyState:
    """Current state of difficulty adaptation.
    
    Attributes:
        difficulty: Current difficulty level.
        direction: Last adaptation direction.
        performance_history: Recent performance metrics.
        adaptation_count: Number of adaptations.
    """
    difficulty: float
    direction: AdaptationDirection = AdaptationDirection.MAINTAIN
    performance_history: List[Dict[str, float]] = field(default_factory=list)
    adaptation_count: int = 0


class AdaptiveDifficultyController(BaseController):
    """Adaptive difficulty controller for dynamic difficulty scaling.
    
    This controller adjusts task difficulty based on agent performance,
    increasing difficulty when the agent performs well and decreasing
    when the agent struggles.
    
    Example:
        >>> config = DifficultyConfig(
        ...     initial_difficulty=0.3,
        ...     adaptation_rate=0.05,
        ... )
        >>> controller = AdaptiveDifficultyController(config)
        >>> controller.start()
        >>> params = controller.reset(seed=42)
        >>> # Run episode...
        >>> info = controller.episode_end(
        ...     {"reward": 50, "success": True},
        ...     simulator,
        ... )
    """

    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        difficulty_config: Optional[DifficultyConfig] = None,
    ):
        """Initialize the adaptive difficulty controller.
        
        Args:
            config: Base controller configuration.
            difficulty_config: Difficulty adaptation configuration.
        """
        super().__init__(config)
        self.difficulty_config = difficulty_config or DifficultyConfig()
        
        # Initialize difficulty state
        self._difficulty = self.difficulty_config.initial_difficulty
        self._direction = AdaptationDirection.MAINTAIN
        self._performance_history: List[Dict[str, float]] = []
        self._adaptation_count = 0
        
        # Track per-difficulty performance for analysis
        self._difficulty_history: List[float] = []

    @property
    def difficulty(self) -> float:
        """Current difficulty level."""
        return self._difficulty

    @property
    def direction(self) -> AdaptationDirection:
        """Last adaptation direction."""
        return self._direction

    def sample_parameters(self) -> ParameterSnapshot:
        """Sample parameters based on current difficulty.
        
        Returns:
            Parameter snapshot scaled by difficulty.
        """
        # Base parameters at difficulty 1.0
        base_params = self._get_base_parameters()
        
        # Scale parameters by difficulty
        scaled_params = self._scale_by_difficulty(base_params, self._difficulty)
        
        return ParameterSnapshot(
            physics=scaled_params.get("physics", {}),
            visual=scaled_params.get("visual", {}),
            dynamics=scaled_params.get("dynamics", {}),
            episode=self._episode,
            step=self._step,
        )

    def _get_base_parameters(self) -> Dict[str, Dict[str, float]]:
        """Get base parameters at maximum difficulty.
        
        Returns:
            Dictionary of parameter categories and values.
        """
        return {
            "physics": {
                "mass_ratio_range": 0.2,  # +/- 20% variation at max difficulty
                "friction_range": 0.3,   # Friction variation
                "gravity_variation": 1.0,  # Gravity variation
            },
            "dynamics": {
                "action_noise": 0.1,      # Max action noise
                "observation_noise": 0.05,  # Max observation noise
            },
            "visual": {
                "texture_variation": 0.2,  # Texture randomness
            },
        }

    def _scale_by_difficulty(
        self,
        base_params: Dict[str, Dict[str, float]],
        difficulty: float,
    ) -> Dict[str, Dict[str, float]]:
        """Scale base parameters by difficulty level.
        
        Args:
            base_params: Base parameter values.
            difficulty: Difficulty level (0.0 to 1.0).
            
        Returns:
            Scaled parameters.
        """
        scaled = {}
        
        # Scale factor: difficulty affects how much randomization
        # Lower difficulty = less randomization
        # Higher difficulty = more randomization
        scale = difficulty
        
        for category, params in base_params.items():
            scaled[category] = {}
            for param_name, base_value in params.items():
                # Scale parameter value by difficulty
                scaled[category][param_name] = base_value * scale
        
        return scaled

    def apply_parameters(
        self,
        snapshot: ParameterSnapshot,
        simulator: Any,
    ) -> bool:
        """Apply difficulty-scaled parameters to simulator.
        
        Args:
            snapshot: Parameters to apply.
            simulator: Simulator instance.
            
        Returns:
            True if successful, False otherwise.
        """
        # Parameter application is typically done by ParameterRandomizer
        return True

    def update_curriculum(
        self,
        episode: int,
        metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """Update difficulty based on episode results.
        
        Args:
            episode: Episode number.
            metrics: Episode metrics.
            
        Returns:
            Dictionary with adaptation information.
        """
        # Store performance
        self._performance_history.append(metrics)
        self._difficulty_history.append(self._difficulty)
        
        # Trim history
        if len(self._performance_history) > self.difficulty_config.performance_window:
            self._performance_history = self._performance_history[
                -self.difficulty_config.performance_window:
            ]
        
        # Determine adaptation
        direction, delta = self._compute_adaptation()
        
        # Apply adaptation
        old_difficulty = self._difficulty
        
        if direction == AdaptationDirection.INCREASE:
            self._difficulty = min(
                self.difficulty_config.max_difficulty,
                self._difficulty + delta
            )
        elif direction == AdaptationDirection.DECREASE:
            self._difficulty = max(
                self.difficulty_config.min_difficulty,
                self._difficulty - delta
            )
        
        # Track adaptation
        if self._difficulty != old_difficulty:
            self._adaptation_count += 1
            self._direction = direction
        
        return {
            "episode": episode,
            "old_difficulty": old_difficulty,
            "new_difficulty": self._difficulty,
            "direction": direction.value,
            "delta": delta,
            "adaptation_count": self._adaptation_count,
        }

    def _compute_adaptation(self) -> Tuple[AdaptationDirection, float]:
        """Compute adaptation direction and magnitude.
        
        Returns:
            Tuple of (direction, delta).
        """
        if not self._performance_history:
            return AdaptationDirection.MAINTAIN, 0.0
        
        # Calculate performance metrics
        recent = self._performance_history[-self.difficulty_config.performance_window:]
        
        success_rate = sum(m.get("success", 0) for m in recent) / len(recent)
        avg_reward = sum(m.get("reward", 0) for m in recent) / len(recent)
        
        # Determine direction
        if success_rate >= self.difficulty_config.success_threshold_high:
            direction = AdaptationDirection.INCREASE
        elif success_rate <= self.difficulty_config.success_threshold_low:
            direction = AdaptationDirection.DECREASE
        elif avg_reward >= self.difficulty_config.reward_threshold_high:
            direction = AdaptationDirection.INCREASE
        elif avg_reward <= self.difficulty_config.reward_threshold_low:
            direction = AdaptationDirection.DECREASE
        else:
            direction = AdaptationDirection.MAINTAIN
        
        # Compute delta based on strategy
        rate = self.difficulty_config.adaptation_rate
        
        if self.difficulty_config.adaptation_strategy == AdaptationStrategy.LINEAR:
            delta = rate
        elif self.difficulty_config.adaptation_strategy == AdaptationStrategy.EXPONENTIAL:
            # Exponential scaling based on performance
            performance_ratio = (success_rate - 0.5) * 2  # -1 to 1
            delta = rate * (1 + abs(performance_ratio))
        elif self.difficulty_config.adaptation_strategy == AdaptationStrategy.PROPORTIONAL:
            # Proportional to performance difference from threshold
            if direction == AdaptationDirection.INCREASE:
                delta = max(0.0, rate * (success_rate - self.difficulty_config.success_threshold_high))
            else:
                delta = max(0.0, rate * (self.difficulty_config.success_threshold_low - success_rate))
        else:  # THRESHOLD
            # Fixed step if threshold crossed
            delta = rate
        
        return direction, delta

    def set_difficulty(self, difficulty: float) -> None:
        """Manually set the difficulty level.
        
        Args:
            difficulty: Difficulty level (0.0 to 1.0).
        """
        self._difficulty = max(
            self.difficulty_config.min_difficulty,
            min(self.difficulty_config.max_difficulty, difficulty)
        )

    def get_difficulty_state(self) -> DifficultyState:
        """Get current difficulty state.
        
        Returns:
            Current difficulty state.
        """
        return DifficultyState(
            difficulty=self._difficulty,
            direction=self._direction,
            performance_history=copy.deepcopy(self._performance_history),
            adaptation_count=self._adaptation_count,
        )

    def get_difficulty_for_parameter(
        self,
        param_name: str,
        min_value: float,
        max_value: float,
    ) -> float:
        """Get difficulty-scaled parameter value.
        
        Args:
            param_name: Parameter name.
            min_value: Minimum value (at difficulty 0).
            max_value: Maximum value (at difficulty 1).
            
        Returns:
            Difficulty-scaled parameter value.
        """
        return min_value + (max_value - min_value) * self._difficulty

    def reset_difficulty(self) -> None:
        """Reset difficulty to initial level."""
        self._difficulty = self.difficulty_config.initial_difficulty
        self._direction = AdaptationDirection.MAINTAIN
        self._performance_history.clear()
        self._adaptation_count = 0
