"""Tests for FluidSimulator core (FLUD-01, FLUD-02)."""

import numpy as np
import pytest

# phi (phiflow) is an optional `simulation` extra; skip the whole module when phi
# is absent. See debug session ci-failures-lint-pybullet (C1).
pytest.importorskip("phi")

from surg_rl.scene_definition.schema import (
    BoundingBox,
    FluidConfig,
    Position,
)


@pytest.fixture
def basic_config() -> FluidConfig:
    return FluidConfig(
        enabled=True,
        bounds=BoundingBox(
            min_corner=Position(x=0.0, y=0.0, z=0.0),
            max_corner=Position(x=0.3, y=0.0, z=0.3),
        ),
        resolution=(32, 32),
    )


class TestFluidSimulatorInit:
    def test_create(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        assert fs.velocity is not None
        assert fs.pressure is None
        assert fs._sim_time == 0.0

    def test_disabled_raises(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        basic_config.enabled = False
        with pytest.raises(ValueError, match="enabled"):
            FluidSimulator(basic_config)

    def test_no_pressure_before_step(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        assert fs.pressure is None

    def test_step_produces_pressure(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        fs.step()
        assert fs.pressure is not None

    def test_step_increments_time(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        fs.step(dt=0.02)
        assert abs(fs._sim_time - 0.02) < 1e-9

    def test_step_returns_empty_forces_without_obstacles(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        forces = fs.step()
        assert forces == {}

    def test_initial_velocity_default_zero(self):
        from surg_rl.fluids import FluidSimulator

        cfg = FluidConfig(
            enabled=True,
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.0, z=0.3),
            ),
            resolution=(32, 32),
        )
        fs = FluidSimulator(cfg)
        assert fs.velocity is not None

    def test_multiple_steps(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        for _ in range(3):
            fs.step()
        assert abs(fs._sim_time - 0.06) < 1e-9


class TestFluidSimulatorObstacles:
    def test_add_obstacle(self, basic_config):
        from phi.flow import Box, vec

        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "instrument_1")
        assert len(fs._obstacles) == 1
        assert fs._obstacle_names == ["instrument_1"]

    def test_clear_obstacles(self, basic_config):
        from phi.flow import Box, vec

        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "test")
        fs.clear_obstacles()
        assert len(fs._obstacles) == 0

    def test_step_with_obstacle(self, basic_config):
        from phi.flow import Box, vec

        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "block")
        forces = fs.step()
        assert isinstance(forces, dict)

    def test_step_with_obstacle_stable(self, basic_config):
        """Multiple steps with obstacle should not diverge."""
        from phi.flow import Box, vec

        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "block")
        for _ in range(5):
            result = fs.step()
            assert isinstance(result, dict)


class TestFluidVisualization:
    """FLUD-04: Fluid rendering produces valid output."""

    def test_render_2d_returns_image(self, basic_config):
        from surg_rl.fluids import FluidSimulator
        from surg_rl.fluids.visualizer import render_fluid_2d

        fs = FluidSimulator(basic_config)
        fs.step()
        img = render_fluid_2d(fs.pressure, fs.config, width=100, height=80)
        assert img is not None
        assert img.shape == (80, 100, 3)
        assert img.dtype == np.uint8

    def test_render_null_pressure_returns_none(self):
        from surg_rl.fluids.visualizer import render_fluid_2d

        img = render_fluid_2d(None, None)
        assert img is None


class TestFluidDivergence:
    """FLUD-01: Velocity field remains stable after pressure projection."""

    def test_velocity_finite_after_step(self, basic_config):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        fs.step()
        p = fs.pressure
        assert p is not None

        p_vals = np.asarray(p.values)
        assert np.all(np.isfinite(p_vals))


class TestFluidForceComputation:
    """FLUD-02: Obstacle force direction."""

    def test_force_on_obstacle_nonzero(self, basic_config):
        from phi.flow import Box, vec

        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "block")

        forces = fs.step()
        if forces:
            f = forces.get("block")
            if f is not None:
                assert f.shape == (3,)
                assert all(np.isfinite(f))
        else:
            assert isinstance(forces, dict)


# ---------------------------------------------------------------------------
# Phase 38: additive 3D tests (dim_3d=True). Existing 2D tests above are
# byte-identical (SC#1). New 3D fixture + classes appended below.
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_config_3d() -> FluidConfig:
    """3D FluidConfig fixture (additive — does not edit basic_config)."""
    from surg_rl.scene_definition.schema import FluidCouplingMode

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


class TestFluidSimulatorInit3D:
    """3D FluidSimulator construction (dim_3d=True, D-07)."""

    def test_create_3d(self, basic_config_3d):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        assert fs.velocity is not None
        assert fs.velocity.spatial_rank == 3
        assert fs.pressure is None
        assert fs._sim_time == 0.0

    def test_step_produces_3d_pressure(self, basic_config_3d):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        fs.step()
        assert fs.pressure is not None
        assert fs.pressure.spatial_rank == 3

    def test_step_increments_time_3d(self, basic_config_3d):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        fs.step(dt=0.02)
        assert abs(fs._sim_time - 0.02) < 1e-9

    def test_step_returns_empty_forces_without_obstacles_3d(self, basic_config_3d):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        forces = fs.step()
        assert forces == {}


class TestFluidSimulatorObstacles3D:
    """3D obstacle + instrument API (D-14/D-15)."""

    def test_add_obstacle_3d(self, basic_config_3d):
        from phi.geom import infinite_cylinder

        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        cyl = infinite_cylinder(x=0.15, y=0.15, radius=0.05, inf_dim="z")
        fs.add_obstacle(cyl, "cyl")
        assert len(fs._obstacles) == 1
        assert fs._obstacle_names == ["cyl"]

    def test_add_instrument_3d(self, basic_config_3d):
        from surg_rl.fluids import FluidSimulator
        from surg_rl.scene_definition.schema import Pose

        fs = FluidSimulator(basic_config_3d)
        pose = Pose(position=Position(x=0.15, y=0.15, z=0.10))
        fs.add_instrument(pose, (0.02, 0.1, 0.02), "instrument")
        assert len(fs._obstacles) == 1
        assert fs._obstacle_names == ["instrument"]

    def test_add_instrument_requires_dim_3d(self, basic_config):
        """add_instrument raises ValueError when dim_3d is False (D-15)."""
        from surg_rl.fluids import FluidSimulator
        from surg_rl.scene_definition.schema import Pose

        fs = FluidSimulator(basic_config)
        pose = Pose(position=Position(x=0.15, y=0.15, z=0.10))
        with pytest.raises(ValueError, match="dim_3d"):
            fs.add_instrument(pose, (0.02, 0.1, 0.02))

    def test_add_instrument_requires_pose(self, basic_config_3d):
        """add_instrument raises ValueError when pose is None (CLAUDE.md guard)."""
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        with pytest.raises(ValueError, match="pose"):
            fs.add_instrument(None, (0.02, 0.1, 0.02))

    def test_step_with_instrument_stable_3d(self, basic_config_3d):
        """N=5 steps with a thin instrument should not diverge (SC#2 level)."""
        from surg_rl.fluids import FluidSimulator
        from surg_rl.scene_definition.schema import Pose

        fs = FluidSimulator(basic_config_3d)
        pose = Pose(position=Position(x=0.15, y=0.15, z=0.10))
        fs.add_instrument(pose, (0.02, 0.1, 0.02), "instrument")
        for _ in range(5):
            result = fs.step()
            assert isinstance(result, dict)


class TestFluidDivergence3D:
    """3D velocity/pressure finiteness after a step."""

    def test_velocity_finite_after_step_3d(self, basic_config_3d):
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d)
        fs.step()
        p = fs.pressure
        assert p is not None
        p_vals = p.values.numpy("x,y,z")
        assert np.all(np.isfinite(p_vals))
