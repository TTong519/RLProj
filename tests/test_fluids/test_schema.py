"""Tests for FluidConfig Pydantic schema (FLUD-03)."""

import pytest
from pydantic import ValidationError

from surg_rl.scene_definition.schema import (
    BoundingBox,
    FluidConfig,
    Position,
)


class TestFluidConfig:
    def test_defaults(self):
        fc = FluidConfig(
            enabled=True,
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.0, z=0.3),
            ),
        )
        assert fc.resolution == (32, 32)
        assert fc.density == 1000.0
        assert fc.viscosity == 0.004
        assert fc.enabled is True

    def test_explicit_resolution(self):
        fc = FluidConfig(
            enabled=True,
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.0, z=0.3),
            ),
            resolution=(64, 48),
        )
        assert fc.resolution == (64, 48)

    def test_missing_enabled_defaults_false(self):
        """When enabled is not passed, it defaults to False."""
        fc = FluidConfig(
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.0, z=0.3),
            ),
        )
        assert fc.enabled is False

    def test_rejects_too_small_resolution(self):
        with pytest.raises(ValueError):
            FluidConfig(
                enabled=True,
                bounds=BoundingBox(
                    min_corner=Position(x=0.0, y=0.0, z=0.0),
                    max_corner=Position(x=0.3, y=0.0, z=0.3),
                ),
                resolution=(2, 2),
            )

    def test_rejects_too_large_resolution(self):
        with pytest.raises(ValueError):
            FluidConfig(
                enabled=True,
                bounds=BoundingBox(
                    min_corner=Position(x=0.0, y=0.0, z=0.0),
                    max_corner=Position(x=0.3, y=0.0, z=0.3),
                ),
                resolution=(256, 256),
            )

    def test_rejects_wrong_dim_resolution(self):
        with pytest.raises(ValueError):
            FluidConfig(
                enabled=True,
                bounds=BoundingBox(
                    min_corner=Position(x=0.0, y=0.0, z=0.0),
                    max_corner=Position(x=0.3, y=0.0, z=0.3),
                ),
                resolution=(32,),
            )

    def test_serialization(self):
        import json

        fc = FluidConfig(
            enabled=True,
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.0, z=0.3),
            ),
            resolution=(32, 32),
        )
        data = fc.model_dump()
        assert data["enabled"] is True
        assert data["resolution"] == (32, 32)
        json_str = json.dumps(data, indent=2)
        assert "32" in json_str


# ============================================================================
# Phase 38 (FLUID-01/FLUID-03): 3D FluidConfig additive schema tests.
# These tests cover the additive dim_3d / grid_size / coupling_mode /
# coupling_substeps surface. The 2D FluidConfig surface above MUST stay
# byte-identical — these tests are ADDITIVE only.
# ============================================================================


def _make_2d_bounds() -> BoundingBox:
    """2D domain (zero y extent) — used to verify defaults stay 2D-oriented."""
    return BoundingBox(
        min_corner=Position(x=0.0, y=0.0, z=0.0),
        max_corner=Position(x=0.3, y=0.0, z=0.3),
    )


def _make_3d_bounds() -> BoundingBox:
    """3D domain (non-zero y extent) — used for dim_3d=True cases."""
    return BoundingBox(
        min_corner=Position(x=0.0, y=0.0, z=0.0),
        max_corner=Position(x=0.3, y=0.3, z=0.3),
    )


class TestFluidConfig3D:
    """Additive tests for the 3D FluidConfig surface (Phase 38)."""

    def test_defaults_dim_3d_off(self):
        """2D default config: dim_3d=False, grid_size=None, ONE_WAY, substeps=4."""
        from surg_rl.scene_definition.schema import FluidCouplingMode

        fc = FluidConfig(enabled=True, bounds=_make_2d_bounds())
        assert fc.dim_3d is False
        assert fc.grid_size is None
        assert fc.coupling_mode == FluidCouplingMode.ONE_WAY
        assert fc.coupling_substeps == 4

    def test_grid_size_required_when_dim_3d(self):
        """SC#3 guard: dim_3d=True with grid_size=None MUST hard-error."""
        with pytest.raises(ValidationError):
            FluidConfig(
                enabled=True,
                bounds=_make_3d_bounds(),
                dim_3d=True,
                grid_size=None,
            )

    def test_grid_size_ok_when_dim_3d_true(self):
        """Cubic 24^3 and anisotropic (64,32,64) both validate when dim_3d=True."""
        fc_cubic = FluidConfig(
            enabled=True,
            bounds=_make_3d_bounds(),
            dim_3d=True,
            grid_size=(24, 24, 24),
        )
        assert fc_cubic.grid_size == (24, 24, 24)

        fc_aniso = FluidConfig(
            enabled=True,
            bounds=_make_3d_bounds(),
            dim_3d=True,
            grid_size=(64, 32, 64),
        )
        assert fc_aniso.grid_size == (64, 32, 64)

    def test_cap_grid_size_rejects_too_small(self):
        """Any dim < 4 raises ValidationError."""
        with pytest.raises(ValidationError):
            FluidConfig(
                enabled=True,
                bounds=_make_3d_bounds(),
                dim_3d=True,
                grid_size=(3, 24, 24),
            )

    def test_cap_grid_size_rejects_too_large(self):
        """Any dim > 64 raises ValidationError."""
        with pytest.raises(ValidationError):
            FluidConfig(
                enabled=True,
                bounds=_make_3d_bounds(),
                dim_3d=True,
                grid_size=(65, 24, 24),
            )

    def test_cap_grid_size_rejects_wrong_len(self):
        """grid_size must be a 3-tuple (nx, ny, nz); 2-tuple raises."""
        with pytest.raises(ValidationError):
            FluidConfig(
                enabled=True,
                bounds=_make_3d_bounds(),
                dim_3d=True,
                grid_size=(24, 24),
            )

    def test_coupling_substeps_bounds(self):
        """coupling_substeps is bounded ge=1, le=16; 0 and 17 raise, 1 and 16 ok."""
        with pytest.raises(ValidationError):
            FluidConfig(
                enabled=True,
                bounds=_make_3d_bounds(),
                dim_3d=True,
                grid_size=(24, 24, 24),
                coupling_substeps=0,
            )
        with pytest.raises(ValidationError):
            FluidConfig(
                enabled=True,
                bounds=_make_3d_bounds(),
                dim_3d=True,
                grid_size=(24, 24, 24),
                coupling_substeps=17,
            )
        ok_low = FluidConfig(
            enabled=True,
            bounds=_make_3d_bounds(),
            dim_3d=True,
            grid_size=(24, 24, 24),
            coupling_substeps=1,
        )
        assert ok_low.coupling_substeps == 1
        ok_high = FluidConfig(
            enabled=True,
            bounds=_make_3d_bounds(),
            dim_3d=True,
            grid_size=(24, 24, 24),
            coupling_substeps=16,
        )
        assert ok_high.coupling_substeps == 16

    def test_coupling_mode_enum_values(self):
        """FluidCouplingMode str-Enum mirrors FluidBoundaryType style."""
        from surg_rl.scene_definition.schema import FluidCouplingMode

        assert FluidCouplingMode.ONE_WAY.value == "one_way"
        assert FluidCouplingMode.TWO_WAY.value == "two_way"
        # str-Enum members compare equal to their string values.
        assert FluidCouplingMode.ONE_WAY == "one_way"
        assert FluidCouplingMode.TWO_WAY == "two_way"

    def test_serialization_coupling_mode(self):
        """model_dump() preserves coupling_mode as the Enum object
        (per CLAUDE.md — Enum values stay as Enum in model_dump, convert
        .value before YAML serialization)."""
        from surg_rl.scene_definition.schema import FluidCouplingMode

        fc = FluidConfig(
            enabled=True,
            bounds=_make_3d_bounds(),
            dim_3d=True,
            grid_size=(24, 24, 24),
            coupling_mode=FluidCouplingMode.TWO_WAY,
        )
        data = fc.model_dump()
        assert data["coupling_mode"] == FluidCouplingMode.TWO_WAY
        assert data["coupling_mode"].value == "two_way"
