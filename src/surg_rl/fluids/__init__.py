"""Grid-based Eulerian fluid simulation with two-way solid coupling."""

from surg_rl.fluids.fluid_simulator import FluidSimulator
from surg_rl.fluids.force_computation import compute_obstacle_forces
from surg_rl.fluids.visualizer import render_fluid_2d

__all__ = [
    "FluidSimulator",
    "compute_obstacle_forces",
    "render_fluid_2d",
]
