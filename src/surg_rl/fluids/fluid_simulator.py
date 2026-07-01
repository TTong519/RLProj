"""FluidSimulator wrapping PhiFlow for 2D grid-based Eulerian fluid simulation.

Operates on a 2D vertical slice (xz-plane) suitable for surgical bleeding/irrigation.
Provides two-way coupling forces on obstacles via pressure gradient integration.

## PhiFlow multi-obstacle workaround (DEBT-05)

PhiFlow's ``fluid.make_incompressible()`` expects a single SDF per call. Passing
multiple ``Obstacle`` instances with separate geometries produces overlapping
zero-velocity regions that crash the linear solver (ill-conditioned pressure
Poisson system; ``Solve`` exceeds ``max_iterations`` with no convergence).

The workaround is to merge all obstacle geometries into ONE SDF via ``union(*geoms)``
before wrapping in a single ``Obstacle`` — see line ~74 in ``step()``. This produces
a single coherent boundary condition that the pressure solver can handle.

Example (the existing implementation in ``step()``):

.. code-block:: python

    obstacles_arg: list[Any] = []
    if self._obstacles:
        geoms = [o.geometry for o in self._obstacles]
        merged = union(*geoms)            # <-- THE WORKAROUND
        obstacles_arg = [Obstacle(merged)]

    self._velocity, self._pressure = fluid.make_incompressible(
        self._velocity, obstacles_arg,
        solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500),
    )

Upstream context: https://github.com/tum-pbs/PhiFlow/issues — search for
"make_incompressible multiple obstacles" or "overlapping SDF pressure solve"
to find related issues. The workaround predates v0.3.2; if PhiFlow ships a
native multi-obstacle API in a future release, this can be revisited.

Rationale for the merged-SDF approach:
1. The pressure solve is a Poisson problem with the obstacle boundary
   imposing zero velocity. Two separate SDFs would require two boundary
   conditions on the same grid, which PhiFlow's solver does not natively support.
2. ``union(*geoms)`` produces a single SDF that is positive outside all
   obstacles and negative inside any — equivalent to a single coherent obstacle
   for the solver's purposes.
3. The merged-SDF approach loses per-obstacle force attribution precision
   (we compute obstacle forces via ``compute_obstacle_forces`` in
   ``force_computation.py``, which uses pressure-gradient integration around
   each original obstacle's bounding box, so per-obstacle forces are still
   recoverable downstream).
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
        if config.dim_3d:
            # 3D branch (NEW, D-06/D-07) — direct (x,y,z)->(x,y,z) mapping.
            domain = Box(x=float(dims[0]), y=float(dims[1]), z=float(dims[2]))
            nx, ny, nz = config.grid_size  # guaranteed non-None by schema (D-03)
            self._velocity = StaggeredGrid(
                0.0,
                extrapolation.ZERO,
                domain,
                x=nx,
                y=ny,
                z=nz,
            )
        else:
            # 2D branch (BYTE-IDENTICAL to v0.5.0)
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

    def add_instrument(
        self,
        pose: Any,
        dims: tuple[float, float, float],
        name: str = "instrument",
    ) -> None:
        """Construct a thin-instrument SDF (cylinder shaft + box tip) and register it.

        3D-only (raises ``ValueError`` when ``config.dim_3d`` is False). The
        shaft is modeled as an ``infinite_cylinder`` aligned along the z-axis
        at the instrument position (mirrors the PhiFlow ``Wake_Flow`` 3D
        pattern, D-14); the tip is a small ``Box`` placed at the shaft end
        (``pose.position.z + shaft_length``). The two geometries are merged
        via ``union(shaft, tip)`` (DEBT-05 workaround) and handed to
        ``add_obstacle`` (the raw 2D API is unchanged, D-15).

        Args:
            pose: ``Pose`` (``InstrumentConfig.pose``, ``Optional[Pose]`` per
                CLAUDE.md — must not be ``None``). Only ``pose.position`` is
                consumed; orientation is ignored (shaft is axis-aligned to z).
            dims: ``(shaft_radius, shaft_length, tip_half_size)``:
                - ``dims[0]``: shaft cylinder radius (m).
                - ``dims[1]``: shaft length along +z used to place the tip (m).
                - ``dims[2]``: half-size of the cubic box tip (m).
            name: obstacle name registered with ``add_obstacle``.

        Raises:
            ValueError: if ``not self.config.dim_3d`` or ``pose is None``.

        Note (WR-03): the shaft is ``infinite_cylinder(..., inf_dim="z")`` (full
        z coverage), so the finite tip ``Box`` only extends the union when
        ``tip_half > shaft_radius`` (a wider flange at one z-slice). For the
        common equal-half case ``tip_half == shaft_radius`` (used by every
        Phase 38 fixture), the tip is geometrically absorbed by the shaft disc
        and ``union(shaft, tip) == shaft``. Callers that need a genuinely
        distinct tip must pass ``tip_half > shaft_radius``; that case has no
        test coverage today.
        """
        from phi.flow import Box, union, vec
        from phi.geom import infinite_cylinder

        if not self.config.dim_3d:
            raise ValueError(
                "add_instrument requires dim_3d=True "
                "(enable FluidConfig.dim_3d to use instrument SDFs)"
            )
        if pose is None:
            raise ValueError("pose required for add_instrument (InstrumentConfig.pose is None)")

        shaft_radius = float(dims[0])
        shaft_length = float(dims[1])
        tip_half = float(dims[2])
        px = float(pose.position.x)
        py = float(pose.position.y)
        pz = float(pose.position.z)

        shaft = infinite_cylinder(x=px, y=py, radius=shaft_radius, inf_dim="z")
        tip = Box(
            vec(x=px, y=py, z=pz + shaft_length),
            vec(x=2.0 * tip_half, y=2.0 * tip_half, z=2.0 * tip_half),
        )
        merged = union(shaft, tip)
        self.add_obstacle(merged, name)

    def step(self, dt: float | None = None) -> dict[str, np.ndarray]:
        """Advance the fluid by ``dt`` and return per-obstacle coupling forces.

        Inert 3D config surface (WR-01/WR-02, documented honestly rather than
        implemented to avoid destabilizing the verified 3D path):

        - ``config.coupling_mode`` (ONE_WAY / TWO_WAY) is **not** branched on here.
          TWO_WAY currently aliases ONE_WAY — the obstacle-velocity feedback
          required for true added-mass two-way coupling (RESEARCH Pitfall 8) is
          deferred. The ``test_two_way_opt_in_documented_unstable`` xfail
          therefore exercises the same stable ONE_WAY code path; an xpass is the
          expected outcome, not a guarantee of TWO_WAY behavior. Do not read
          ``coupling_mode == TWO_WAY`` as enabling real two-way coupling.
        - ``config.coupling_substeps`` is **not** consumed here — ``step`` does a
          single advection + pressure solve + force integration per call. The
          field is reserved for a future substep loop
          (``sub_dt = dt / coupling_substeps``) and is validated/bounded by the
          schema so callers can pin it without effect today.

        Both knobs are intentionally kept inert (vs. removed) so the validated
        3D path is not perturbed by post-hoc new coupling behavior. The 2D
        branch below is byte-identical to v0.5.0 (SC#1) and must not change.
        """
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
            if self.config.dim_3d:
                # 3D branch (NEW, D-08/D-16) — per-obstacle mask path.
                from surg_rl.fluids.force_computation import (
                    _compute_obstacle_forces_3d,
                )

                forces = _compute_obstacle_forces_3d(
                    self._velocity,
                    self._pressure,
                    self._obstacles,
                    self._obstacle_names,
                    self.config,
                )
            else:
                # 2D branch (BYTE-IDENTICAL to v0.5.0)
                from surg_rl.fluids.force_computation import (
                    compute_obstacle_forces,
                )

                forces = compute_obstacle_forces(
                    self._velocity,
                    self._pressure,
                    self._obstacle_names,
                    self.config,
                )

        self._sim_time += dt
        return forces
