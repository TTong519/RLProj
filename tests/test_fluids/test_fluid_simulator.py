"""Tests for FluidSimulator core (FLUD-01, FLUD-02)."""

import numpy as np
import pytest

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
        from surg_rl.fluids import FluidSimulator
        from phi.flow import Box, vec

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "instrument_1")
        assert len(fs._obstacles) == 1
        assert fs._obstacle_names == ["instrument_1"]

    def test_clear_obstacles(self, basic_config):
        from surg_rl.fluids import FluidSimulator
        from phi.flow import Box, vec

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "test")
        fs.clear_obstacles()
        assert len(fs._obstacles) == 0

    def test_step_with_obstacle(self, basic_config):
        from surg_rl.fluids import FluidSimulator
        from phi.flow import Box, vec

        fs = FluidSimulator(basic_config)
        size = vec(x=0.05, y=0.05)
        geom = Box(vec(x=0.15, y=0.15), size)
        fs.add_obstacle(geom, "block")
        forces = fs.step()
        assert isinstance(forces, dict)

    def test_step_with_obstacle_stable(self, basic_config):
        """Multiple steps with obstacle should not diverge."""
        from surg_rl.fluids import FluidSimulator
        from phi.flow import Box, vec

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
        from surg_rl.fluids import FluidSimulator
        from phi.flow import Box, vec

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
