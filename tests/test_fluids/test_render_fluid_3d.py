"""Tests for render_fluid_3d z-layer slice renderer (D-18) + 2D refactor guard.

Phase 38 Plan 03. render_fluid_3d is a slice-of-3D fallback: it extracts a 2D
z-layer slice from a 3D pressure field and delegates to the shared private
``_render_np_2d`` helper extracted from ``render_fluid_2d``. The 2D
image-array-equality test (SC#1) pins the 2D output so the ``_render_np_2d``
extraction is byte-identical.
"""

from __future__ import annotations

import numpy as np

from surg_rl.fluids.visualizer import render_fluid_2d, render_fluid_3d


def _make_2d_pressure_fixture() -> object:
    """Build a small 2D pressure-like object for the byte-identical guard.

    The values tensor carries a known 4x4 array; render_fluid_2d's extraction
    path (``.numpy()``) returns it unchanged. The pinned expected output
    below was computed once from the CURRENT render_fluid_2d so the upcoming
    ``_render_np_2d`` extraction MUST reproduce it byte-for-byte.
    """

    class _Values:
        def numpy(self, *args, **kwargs):
            return np.array(
                [
                    [0.0, 1.0, 2.0, 3.0],
                    [4.0, 5.0, 6.0, 7.0],
                    [8.0, 9.0, 10.0, 11.0],
                    [12.0, 13.0, 14.0, 15.0],
                ],
                dtype=np.float64,
            )

    class _Pressure:
        def __init__(self):
            self.values = _Values()

    return _Pressure()


# Pinned 2D output (width=8, height=6) computed from the PRE-refactor
# render_fluid_2d. The _render_np_2d extraction MUST reproduce this exactly.
_EXPECTED_2D_IMG = np.array(
    [
        [
            [15, 3, 15],
            [15, 3, 15],
            [24, 4, 24],
            [32, 6, 32],
            [41, 8, 41],
            [49, 9, 49],
            [58, 11, 58],
            [58, 11, 58],
        ],
        [
            [38, 7, 38],
            [38, 7, 38],
            [46, 9, 46],
            [55, 11, 55],
            [63, 12, 63],
            [72, 14, 72],
            [80, 16, 80],
            [80, 16, 80],
        ],
        [
            [83, 16, 83],
            [83, 16, 83],
            [92, 18, 92],
            [100, 20, 100],
            [109, 21, 109],
            [117, 23, 117],
            [126, 25, 126],
            [126, 25, 126],
        ],
        [
            [128, 25, 128],
            [128, 25, 128],
            [137, 27, 137],
            [145, 29, 145],
            [154, 30, 154],
            [162, 32, 162],
            [171, 34, 171],
            [171, 34, 171],
        ],
        [
            [174, 34, 174],
            [174, 34, 174],
            [182, 36, 182],
            [191, 38, 191],
            [199, 39, 199],
            [208, 41, 208],
            [216, 43, 216],
            [216, 43, 216],
        ],
        [
            [196, 39, 196],
            [196, 39, 196],
            [205, 41, 205],
            [213, 42, 213],
            [222, 44, 222],
            [230, 46, 230],
            [239, 47, 239],
            [239, 47, 239],
        ],
    ],
    dtype=np.uint8,
)


def _make_3d_pressure_fixture():
    """Build a 3D pressure field directly via PhiFlow (independent of plan 02).

    Mirrors the Wake_Flow 3D pattern: Box(x,y,z) + StaggeredGrid(x,y,z) +
    make_incompressible -> 3D pressure.
    """
    from phi.flow import Box, Solve, StaggeredGrid, extrapolation, fluid

    domain = Box(x=0.3, y=0.3, z=0.3)
    velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain, x=16, y=16, z=16)
    _, pressure = fluid.make_incompressible(
        velocity, solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500)
    )
    return pressure


class TestRenderFluid3D:
    """render_fluid_3d z-layer slice renderer (D-18)."""

    def test_render_3d_returns_image(self):
        pressure = _make_3d_pressure_fixture()
        img = render_fluid_3d(pressure, None, z_layer=8, width=100, height=80)
        assert img is not None
        assert img.shape == (80, 100, 3)
        assert img.dtype == np.uint8

    def test_render_3d_default_layer(self):
        pressure = _make_3d_pressure_fixture()
        img = render_fluid_3d(pressure, None)  # z_layer=None -> nz//2
        assert img is not None
        assert img.shape[0] > 0 and img.shape[1] > 0
        assert img.dtype == np.uint8

    def test_render_3d_null_pressure_returns_none(self):
        assert render_fluid_3d(None, None) is None

    def test_render_3d_layer_clamp(self):
        """z_layer out of range is clamped to [0, nz-1] (T-38-07)."""
        pressure = _make_3d_pressure_fixture()
        # Very large layer index should not raise; clamped to last layer.
        img_high = render_fluid_3d(pressure, None, z_layer=999, width=10, height=10)
        assert img_high is not None
        img_low = render_fluid_3d(pressure, None, z_layer=-5, width=10, height=10)
        assert img_low is not None


class TestRenderFluid2DByteIdentical:
    """SC#1: render_fluid_2d 2D output stays byte-identical after the
    _render_np_2d extraction (refactor guard)."""

    def test_render_2d_image_byte_identical_after_refactor(self):
        pressure = _make_2d_pressure_fixture()
        img = render_fluid_2d(pressure, None, width=8, height=6)
        assert img is not None
        assert img.shape == (6, 8, 3)
        assert img.dtype == np.uint8
        # Pin the 2D output against the pre-refactor expected array.
        assert np.array_equal(img, _EXPECTED_2D_IMG), (
            "render_fluid_2d output changed after _render_np_2d extraction; "
            "the 2D path must stay byte-identical (SC#1)."
        )
