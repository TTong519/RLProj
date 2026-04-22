"""Base class for dynamic environment controllers.

This module defines the abstract interface for controllers that modify
environment parameters during training, supporting domain randomization,
curriculum learning, and adaptive difficulty.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np


class ControllerState(Enum):
    """State of the environment controller."""
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class ControllerConfig:
    """Configuration for the environment controller.

    Attributes:
        enabled: Whether the controller is active.
        seed: Random seed for reproducibility.
        update_frequency: How often to update parameters (in steps).
        warmup_episodes: Number of episodes before starting modifications.
    """
    enabled: bool = True
    seed: Optional[int] = None
    update_frequency: int = 1
    warmup_episodes: int = 0


@dataclass
class ParameterBounds:
    """Bounds for a parameter that can be randomized.
    
    Attributes:
        name: Parameter name.
        min_value: Minimum allowed value.
        max_value: Maximum allowed value.
        default: Default value.
        distribution: Distribution type ('uniform', 'normal', 'log_uniform').
        distribution_params: Additional distribution parameters.
    """
    name: str
    min_value: float
    max_value: float
    default: float
    distribution: str = "uniform"
    distribution_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterSnapshot:
    """Snapshot of current parameter values.
    
    Attributes:
        physics: Current physics parameters.
        visual: Current visual parameters.
        dynamics: Current dynamics parameters.
        step: Current step number.
        episode: Current episode number.
    """
    physics: Dict[str, float] = field(default_factory=dict)
    visual: Dict[str, float] = field(default_factory=dict)
    dynamics: Dict[str, float] = field(default_factory=dict)
    step: int = 0
    episode: int = 0


class BaseController(ABC):
    """Abstract base class for dynamic environment controllers.
    
    This class defines the interface for controllers that modify
    environment parameters during training. Implementations can
    provide domain randomization, curriculum learning, or adaptive
    difficulty adjustment.
    
    The controller integrates with the simulator to:
    - Randomize physics parameters (mass, friction, damping)
    - Randomize visual parameters (colors, textures, lighting)
    - Randomize dynamics parameters (noise, delays)
    - Apply curriculum learning schedules
    - Adapt difficulty based on agent performance
    """

    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        parameter_bounds: Optional[Dict[str, ParameterBounds]] = None,
    ):
        """Initialize the controller.
        
        Args:
            config: Controller configuration.
            parameter_bounds: Bounds for controllable parameters.
        """
        self.config = config or ControllerConfig()
        self.parameter_bounds = parameter_bounds or {}
        self._state = ControllerState.IDLE
        self._step = 0
        self._episode = 0
        self._rng = np.random.default_rng(self.config.seed)
        self._current_params = ParameterSnapshot()
        self._param_history: List[ParameterSnapshot] = []
        self._callbacks: Dict[str, List[Callable]] = {
            "on_episode_start": [],
            "on_episode_end": [],
            "on_step": [],
            "on_reset": [],
        }

    @property
    def state(self) -> ControllerState:
        """Current controller state."""
        return self._state

    @property
    def step(self) -> int:
        """Current step count."""
        return self._step

    @property
    def episode(self) -> int:
        """Current episode count."""
        return self._episode

    @property
    def current_params(self) -> ParameterSnapshot:
        """Current parameter values."""
        return self._current_params

    @abstractmethod
    def sample_parameters(self) -> ParameterSnapshot:
        """Sample new parameter values based on current state.
        
        Returns:
            Snapshot of sampled parameters.
        """
        pass

    @abstractmethod
    def apply_parameters(
        self,
        snapshot: ParameterSnapshot,
        simulator: Any,
    ) -> bool:
        """Apply parameter snapshot to the simulator.
        
        Args:
            snapshot: Parameters to apply.
            simulator: Simulator instance to modify.
            
        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def update_curriculum(
        self,
        episode: int,
        metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """Update curriculum state based on episode results.
        
        Args:
            episode: Episode number.
            metrics: Episode metrics (reward, success, etc.).
            
        Returns:
            Updated curriculum parameters.
        """
        pass

    def start(self) -> None:
        """Start the controller."""
        self._state = ControllerState.ACTIVE
        self._emit("on_reset")

    def stop(self) -> None:
        """Stop the controller."""
        self._state = ControllerState.IDLE

    def pause(self) -> None:
        """Pause the controller."""
        self._state = ControllerState.PAUSED

    def resume(self) -> None:
        """Resume the controller from paused state."""
        self._state = ControllerState.ACTIVE

    def reset(self, seed: Optional[int] = None) -> ParameterSnapshot:
        """Reset controller state for a new episode.
        
        Args:
            seed: Optional new random seed.
            
        Returns:
            New parameter snapshot for the episode.
        """
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        
        self._step = 0
        self._episode += 1
        
        if self.config.enabled and self._episode > self.config.warmup_episodes:
            self._current_params = self.sample_parameters()
        else:
            self._current_params = ParameterSnapshot(episode=self._episode)
        
        self._emit("on_reset")
        self._emit("on_episode_start")
        
        return self._current_params

    def step_update(self, simulator: Any) -> ParameterSnapshot:
        """Update parameters after a simulation step.
        
        Args:
            simulator: Simulator instance.
            
        Returns:
            Current parameter snapshot.
        """
        self._step += 1
        
        if self._state != ControllerState.ACTIVE:
            return self._current_params
        
        if not self.config.enabled:
            return self._current_params
        
        if self._episode <= self.config.warmup_episodes:
            return self._current_params
        
        if self._step % self.config.update_frequency == 0:
            self._current_params = self.sample_parameters()
            self.apply_parameters(self._current_params, simulator)
        
        self._emit("on_step")
        return self._current_params

    def episode_end(
        self,
        metrics: Dict[str, float],
        simulator: Any,
    ) -> Dict[str, Any]:
        """Handle episode end and update curriculum.
        
        Args:
            metrics: Episode metrics (reward, success, steps, etc.).
            simulator: Simulator instance.
            
        Returns:
            Curriculum update information.
        """
        self._emit("on_episode_end")
        
        self._param_history.append(self._current_params)
        
        curriculum_info = {}
        if self.config.enabled:
            curriculum_info = self.update_curriculum(self._episode, metrics)
        
        return curriculum_info

    def _sample_value(self, bounds: ParameterBounds) -> float:
        """Sample a value from parameter bounds.
        
        Args:
            bounds: Parameter bounds.
            
        Returns:
            Sampled value.
        """
        if bounds.distribution == "uniform":
            return self._rng.uniform(bounds.min_value, bounds.max_value)
        elif bounds.distribution == "normal":
            mean = bounds.distribution_params.get("mean", bounds.default)
            std = bounds.distribution_params.get("std", 
                (bounds.max_value - bounds.min_value) / 4)
            value = self._rng.normal(mean, std)
            return np.clip(value, bounds.min_value, bounds.max_value)
        elif bounds.distribution == "log_uniform":
            if bounds.min_value <= 0:
                raise ValueError(
                    f"log_uniform requires positive min_value, got {bounds.min_value}"
                )
            log_min = np.log(bounds.min_value)
            log_max = np.log(bounds.max_value)
            return np.exp(self._rng.uniform(log_min, log_max))
        else:
            return self._rng.uniform(bounds.min_value, bounds.max_value)

    def _sample_dict(
        self,
        param_dict: Dict[str, ParameterBounds],
    ) -> Dict[str, float]:
        """Sample multiple parameters from a dictionary.
        
        Args:
            param_dict: Dictionary of parameter bounds.
            
        Returns:
            Dictionary of sampled values.
        """
        return {
            name: self._sample_value(bounds)
            for name, bounds in param_dict.items()
        }

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for an event.
        
        Args:
            event: Event name ('on_episode_start', 'on_episode_end', 'on_step', 'on_reset').
            callback: Callback function.
        """
        if event not in self._callbacks:
            raise ValueError(f"Unknown event: {event}")
        self._callbacks[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """Remove a callback for an event.
        
        Args:
            event: Event name.
            callback: Callback function to remove.
        """
        if event in self._callbacks:
            try:
                self._callbacks[event].remove(callback)
            except ValueError:
                pass

    def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event to all registered callbacks.
        
        Args:
            event: Event name.
            *args: Positional arguments for callbacks.
            **kwargs: Keyword arguments for callbacks.
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                import warnings
                warnings.warn(f"Callback error in {event}: {e}")

    def get_history(self, last_n: int = 10) -> List[ParameterSnapshot]:
        """Get recent parameter history.
        
        Args:
            last_n: Number of recent snapshots to return.
            
        Returns:
            List of parameter snapshots.
        """
        return self._param_history[-last_n:]

    def clear_history(self) -> None:
        """Clear parameter history."""
        self._param_history.clear()

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility.
        
        Args:
            seed: Random seed.
        """
        self._rng = np.random.default_rng(seed)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"{self.__class__.__name__}("
            f"state={self._state.value}, "
            f"step={self._step}, "
            f"episode={self._episode})"
        )
