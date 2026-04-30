"""Simulator module - Physics simulation backends for surgical robotics.

This module provides unified interfaces for MuJoCo and PyBullet simulators,
with automatic primitive fallbacks for missing asset files.
"""

from .base_simulator import (
    BaseSimulator,
    Observation,
    SimulationStatus,
    State,
    StepResult,
)
from .mujoco_simulator import MuJoCoSimulator
from .pybullet_simulator import PyBulletSimulator
from .scene_builder import AssetMissingError, SceneBuilder

__all__ = [
    # Base classes
    "BaseSimulator",
    "Observation",
    "State",
    "StepResult",
    "SimulationStatus",
    # Implementations
    "MuJoCoSimulator",
    "PyBulletSimulator",
    # Scene building
    "SceneBuilder",
    "AssetMissingError",
]
