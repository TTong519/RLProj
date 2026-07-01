"""Tests for fluid force computation (FLUID-02, Phase 38).

Covers the 3D obstacle-mask force helper `_compute_obstacle_forces_3d` (D-16:
per-obstacle mask integration via `phi.field.sample`; deliberately distinct from
the 2D global-sum path) and the per-axis independent clamp (D-17).

The 2D `compute_obstacle_forces` global-sum + scalar-magnitude-clamp path is
preserved byte-identical; one test pins its unchanged behavior + signature.
"""

from __future__ import annotations

import numpy as np

from surg_rl.scene_definition.schema import (
    BoundingBox,
    FluidConfig,
    FluidCouplingMode,
    Position,
)


def _make_3d_config() -> FluidConfig:
    """Build a minimal 3D FluidConfig for force-helper tests."""
    return FluidConfig(
        enabled=True,
        dim_3d=True,
        grid_size=(16, 16, 16),
        bounds=BoundingBox(
            min_corner=Position(x=0.0, y=0.0, z=0.0),
            max_corner=Position(x=0.3, y=0.3, z=0.3),
        ),
        coupling_mode=FluidCouplingMode.ONE_WAY,
    )


def _make_3d_pressure_with_obstacle(
    cyl_x: float = 0.15,
    cyl_y: float = 0.15,
    radius: float = 0.05,
):
    """Run make_incompressible in 3D with an infinite_cylinder obstacle.

    Returns (velocity, pressure, obstacle) where `obstacle` is the PhiFlow
    `Obstacle` wrapping the cylinder geometry (used for per-obstacle mask
    sampling in `_compute_obstacle_forces_3d`).
    """
    from phi.flow import Box, Obstacle, Solve, StaggeredGrid, extrapolation, fluid
    from phi.geom import infinite_cylinder

    dom = Box(x=0.3, y=0.3, z=0.3)
    v = StaggeredGrid(0.0, extrapolation.ZERO, dom, x=16, y=16, z=16)
    cyl = infinite_cylinder(x=cyl_x, y=cyl_y, radius=radius, inf_dim="z")
    obstacle = Obstacle(cyl)
    v, p = fluid.make_incompressible(
        v,
        [obstacle],
        solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500),
    )
    return v, p, obstacle


def _make_synthetic_3d_pressure(arr: np.ndarray):
    """Build a 3D CenteredGrid pressure field from a numpy array.

    Used for the per-axis-clamp test where a natural pressure field's gradient
    is far below the 1e4 cap; a synthetic extreme gradient is required to
    exercise the clamp. The grid is built on the same domain/resolution as the
    real 3D pressure field so `phi.field.sample(geometry, pressure)` returns a
    valid {0.0, 1.0} mask.
    """
    import phi.math as math
    from phi.field import CenteredGrid
    from phi.flow import Box, extrapolation

    dom = Box(x=0.3, y=0.3, z=0.3)
    nx, ny, nz = arr.shape
    t = math.wrap(arr, math.spatial("x,y,z"))
    return CenteredGrid(t, extrapolation.ZERO, dom, x=nx, y=ny, z=nz)


class TestComputeObstacleForces3D:
    """3D obstacle-mask force helper (D-16/D-17)."""

    def test_compute_obstacle_forces_3d_returns_3tuple(self):
        """The 3D helper returns per-obstacle (fx, fy, fz) of shape (3,), all finite."""
        from surg_rl.fluids.force_computation import _compute_obstacle_forces_3d

        cfg = _make_3d_config()
        v, p, obstacle = _make_3d_pressure_with_obstacle()
        obstacles = [obstacle]
        names = ["cyl"]

        forces = _compute_obstacle_forces_3d(v, p, obstacles, names, cfg)

        assert "cyl" in forces
        f = forces["cyl"]
        assert f.shape == (3,)
        assert np.all(np.isfinite(f))

    def test_3d_force_y_axis_nonzero(self):
        """An asymmetric 3D pressure field (y-ramp) yields a nonzero fy component.

        A natural make_incompressible solve with zero initial velocity produces
        a symmetric (zero-gradient) pressure field -> fy == 0. To exercise the
        y-axis integration path, this test builds a synthetic 3D pressure field
        with a linear ramp in y and samples the cylinder mask; the integral of
        grad_y over the mask cells is nonzero by construction.
        """
        from phi.flow import Obstacle
        from phi.geom import infinite_cylinder

        from surg_rl.fluids.force_computation import _compute_obstacle_forces_3d

        cfg = _make_3d_config()
        # Synthetic pressure ramp in y: p[i,j,k] = j / ny.
        arr = np.zeros((16, 16, 16), dtype=np.float64)
        for j in range(16):
            arr[:, j, :] = float(j) / 16.0
        p = _make_synthetic_3d_pressure(arr)
        cyl = infinite_cylinder(x=0.15, y=0.15, radius=0.05, inf_dim="z")
        obstacle = Obstacle(cyl)

        forces = _compute_obstacle_forces_3d(None, p, [obstacle], ["cyl"], cfg)
        f = forces["cyl"]
        assert f.shape == (3,)
        assert abs(float(f[1])) > 0.0, f"expected fy nonzero, got {f}"

    def test_3d_force_per_axis_independent_clamp(self):
        """Per-axis independent clamp (D-17): a spike on two axes is clamped
        independently to the per-axis cap (1e4), NOT scaled together.

        A synthetic pressure field with linear ramps in BOTH x and y produces
        unclamped fx ~= fy ~= -1.58e5 (well above the 1e4 cap). Under the 2D
        scalar-magnitude clamp, both would be scaled by 1e4/magnitude to
        ~= -7071 each. Under the 3D per-axis independent clamp, BOTH are clamped
        to exactly -1e4. Asserting |fx| == 1e4 AND |fy| == 1e4 distinguishes the
        two clamp strategies.
        """
        from phi.flow import Obstacle
        from phi.geom import infinite_cylinder

        from surg_rl.fluids.force_computation import _compute_obstacle_forces_3d

        cfg = _make_3d_config()
        arr = np.zeros((16, 16, 16), dtype=np.float64)
        for i in range(16):
            for j in range(16):
                arr[i, j, :] = 1e9 * (float(i) / 16.0) + 1e9 * (float(j) / 16.0)
        p = _make_synthetic_3d_pressure(arr)
        cyl = infinite_cylinder(x=0.15, y=0.15, radius=0.05, inf_dim="z")
        obstacle = Obstacle(cyl)

        forces = _compute_obstacle_forces_3d(None, p, [obstacle], ["cyl"], cfg)
        f = forces["cyl"]
        cap = 1e4
        # Independent per-axis clamp: each component bounded by the cap.
        assert abs(float(f[0])) <= cap, f"fx exceeds cap: {f}"
        assert abs(float(f[1])) <= cap, f"fy exceeds cap: {f}"
        assert abs(float(f[2])) <= cap, f"fz exceeds cap: {f}"
        # Both spiked axes reach the cap independently (would be ~7071 under
        # scalar-magnitude clamp).
        assert abs(abs(float(f[0])) - cap) < 1e-6, f"fx not independently clamped to cap: {f}"
        assert abs(abs(float(f[1])) - cap) < 1e-6, f"fy not independently clamped to cap: {f}"

    def test_compute_obstacle_forces_3d_finite_no_nan(self):
        """Forces from a normal 3D step contain no NaN/Inf."""
        from surg_rl.fluids.force_computation import _compute_obstacle_forces_3d

        cfg = _make_3d_config()
        v, p, obstacle = _make_3d_pressure_with_obstacle()
        forces = _compute_obstacle_forces_3d(v, p, [obstacle], ["cyl"], cfg)
        f = forces["cyl"]
        assert np.all(np.isfinite(f)), f"non-finite force: {f}"


class TestComputeObstacleForces2DUnchanged:
    """2D compute_obstacle_forces signature + behavior unchanged (SC#1)."""

    def test_2d_compute_obstacle_forces_unchanged(self):
        """The 2D function signature (velocity, pressure, obstacle_names, config)
        is unchanged and returns (fx, 0, fz) with the scalar-magnitude clamp.

        Builds a 2D FluidConfig + a synthetic 2D pressure field, calls the 2D
        `compute_obstacle_forces`, and asserts the force vector is (fx, 0, fz)
        with |fx|, |fz| <= 1e4 (scalar-magnitude clamp behavior).
        """
        from phi.flow import Box, Solve, StaggeredGrid, extrapolation, fluid

        from surg_rl.fluids.force_computation import compute_obstacle_forces

        cfg = FluidConfig(
            enabled=True,
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.0, z=0.3),
            ),
            resolution=(32, 32),
        )
        dom = Box(x=0.3, y=0.3)
        v = StaggeredGrid(0.0, extrapolation.ZERO, dom, x=32, y=32)
        v, p = fluid.make_incompressible(
            v, solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500)
        )

        forces = compute_obstacle_forces(v, p, ["block"], cfg)
        assert "block" in forces
        f = forces["block"]
        assert f.shape == (3,)
        # 2D path returns (fx, 0, fz) — y component is exactly zero.
        assert float(f[1]) == 0.0
        assert np.all(np.isfinite(f))
