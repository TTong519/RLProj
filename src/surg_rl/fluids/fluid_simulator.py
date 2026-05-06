"""FluidSimulator wrapping PhiFlow for 2D grid-based Eulerian fluid simulation.

Operates on a 2D vertical slice (xz-plane) suitable for surgical bleeding/irrigation.
Provides two-way coupling forces on obstacles via pressure gradient integration.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from surg_rl.scene_definition.schema import FluidConfig
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


class FluidSimulator:
    """Wraps PhiFlow StaggeredGrid with advection, pressure projection, obstacles."""

    def __init__(self, config: FluidConfig):
        from phi.flow import Box, StaggeredGrid, extrapolation

        if not config.enabled:
            raise ValueError("FluidConfig.enabled must be True")

        self.config = config
        dims = config.bounds.get_dimensions()
        domain = Box(x=float(dims[0]), y=float(dims[2]))

        self._velocity = StaggeredGrid(
            0.0,
            extrapolation.ZERO,
            domain,
            x=config.resolution[0],
            y=config.resolution[1],
        )

        self._pressure: Any | None = None
        self._obstacles: list[Any] = []
        self._obstacle_names: list[str] = []
        self._sim_time = 0.0

    @property
    def velocity(self) -> Any:
        return self._velocity

    @property
    def pressure(self) -> Any | None:
        return self._pressure

    def add_obstacle(self, geometry: Any, name: str) -> None:
        from phi.flow import Obstacle
        self._obstacles.append(Obstacle(geometry))
        self._obstacle_names.append(name)

    def clear_obstacles(self) -> None:
        self._obstacles.clear()
        self._obstacle_names.clear()

    def step(self, dt: float | None = None) -> dict[str, np.ndarray]:
        from phi.flow import Obstacle, Solve, advect, fluid, union

        if dt is None:
            dt = self.config.substep_dt

        self._velocity = advect.mac_cormack(self._velocity, self._velocity, dt)

        obstacles_arg: list[Any] = []
        if self._obstacles:
            geoms = [o.geometry for o in self._obstacles]
            merged = union(*geoms)
            obstacles_arg = [Obstacle(merged)]

        try:
            self._velocity, self._pressure = fluid.make_incompressible(
                self._velocity,
                obstacles_arg,
                solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500),
            )
        except Exception as exc:
            logger.warning("Pressure solve failed: %s", exc)
            self._pressure = None

        forces: dict[str, np.ndarray] = {}
        if self._pressure is not None and self._obstacles:
            from surg_rl.fluids.force_computation import compute_obstacle_forces
            forces = compute_obstacle_forces(
                self._velocity,
                self._pressure,
                self._obstacle_names,
                self.config,
            )

        self._sim_time += dt
        return forces
