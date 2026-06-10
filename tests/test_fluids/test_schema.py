"""Tests for FluidConfig Pydantic schema (FLUD-03)."""

import pytest

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
