"""SC#1 — 2D byte-identical baseline regression gate (FLUID-01, D-19).

This additive regression test pins the 2D ``FluidSimulator`` velocity+pressure
output for ``dim_3d=False`` against a v0.5.0 baseline captured from the CURRENT
2D path (Plan 02 preserved the 2D path byte-identical behind a top-of-method
``if config.dim_3d:`` branch). Any change to the 2D path that perturbs the
velocity or pressure output will change the SHA256 hash and fail this test.

The test runs N=10 deterministic steps (default ``substep_dt=0.02``, no
obstacles, zero initial velocity) on the same 2D ``FluidConfig`` fixture used by
the existing 2D suite, then asserts:
  1. Finiteness of velocity + pressure (per-step Nyquist minimum, VALIDATION D1).
  2. SHA256 hash of the pressure array equals the pinned v0.5.0 baseline hash.
  3. SHA256 hash of the velocity x-face and y-face arrays equal the pinned
     v0.5.0 baseline hashes.

Velocity is a ``StaggeredGrid`` whose ``.values`` tensor is non-uniform (x-faces
and y-faces have different shapes: ``(31,32)`` vs ``(32,31)``). The plan's
suggested ``np.asarray(fs.velocity.values)`` raises on this non-uniform tensor
in phi 3.4.0 (``AssertionError: Getting native of non-uniform tensors ...``), so
the test extracts the x-face and y-face components via the explicit-dim-order
``.numpy('x,y')`` call (Pitfall 1 discipline). This is a Rule 3 blocking-fix
deviation from the plan's literal ``np.asarray`` form; the semantic intent (pin
the 2D velocity+pressure byte-identical output) is preserved.

This is an ADDITIVE test file — it does NOT edit the existing ``basic_config``
fixture or any existing 2D test in ``test_fluid_simulator.py`` (SC#1
byte-identical gate).
"""

import hashlib

import numpy as np
import pytest

# phi (phiflow) is an optional `simulation` extra; FluidSimulator methods import
# it lazily. Skip the whole module when phi is absent so CI installs without the
# simulation extra stay green. See debug session ci-failures-lint-pybullet (C1).
pytest.importorskip("phi")

from surg_rl.scene_definition.schema import (
    BoundingBox,
    FluidConfig,
    Position,
)


@pytest.fixture
def basic_config_2d() -> FluidConfig:
    """2D FluidConfig fixture mirroring the existing basic_config (do NOT edit
    the existing fixture). dim_3d is left at its default False."""
    return FluidConfig(
        enabled=True,
        bounds=BoundingBox(
            min_corner=Position(x=0.0, y=0.0, z=0.0),
            max_corner=Position(x=0.3, y=0.0, z=0.3),
        ),
        resolution=(32, 32),
    )


# Pinned v0.5.0 2D baseline hashes — captured from the CURRENT 2D path
# (Plan 02 preserved it byte-identical). N=10 steps, no obstacles, zero initial
# velocity, default substep_dt=0.02. Any perturbation of the 2D path that
# changes velocity/pressure output will fail these hashes (SC#1).
_EXPECTED_PRESSURE_HASH = "9ae73c40d4b155b85a27613cb5fd1a046c35d7e5ff999e24d1afcd8299da048b"
# Velocity is zero (fluid at rest, no forcing) — pinning the zero array still
# guards the byte-identical 2D StaggeredGrid construction + advection + solve.
_EXPECTED_VX_HASH = "12525d303b667ee3d0917d8257a21fa0ae80a706be72d4fe8fa4b06739bdbe38"
_EXPECTED_VY_HASH = "12525d303b667ee3d0917d8257a21fa0ae80a706be72d4fe8fa4b06739bdbe38"

# Expected array shapes (StaggeredGrid faces: x-face is (nx-1, ny), y-face is
# (nx, ny-1) for resolution=(32,32); pressure is (nx, ny) CenteredGrid).
_EXPECTED_PRESSURE_SHAPE = (32, 32)
_EXPECTED_VX_SHAPE = (31, 32)
_EXPECTED_VY_SHAPE = (32, 31)


def _sha256(arr: np.ndarray) -> str:
    """Deterministic SHA256 of a numpy array's raw bytes."""
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


class Test2DBaselineByteIdentical:
    """SC#1: 2D velocity+pressure output pinned against the v0.5.0 baseline."""

    def test_2d_velocity_pressure_pinned_to_baseline(self, basic_config_2d):
        """N=10 2D steps produce byte-identical velocity+pressure output.

        Asserts finiteness (Nyquist minimum) AND SHA256 hash equality against
        the pinned v0.5.0 baseline. Any change to the 2D path
        (``FluidSimulator.__init__`` 2D branch, 2D ``step`` body,
        ``compute_obstacle_forces`` 2D body, or the ``Solve`` settings) that
        perturbs the output will change the hash and fail this test.
        """
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_2d)
        for _ in range(10):
            fs.step()

        # Pressure — uniform CenteredGrid, np.asarray works (existing pattern).
        p = fs.pressure
        assert p is not None, "pressure must be produced after a step"
        p_np = np.asarray(p.values)
        assert p_np.shape == _EXPECTED_PRESSURE_SHAPE
        assert np.all(np.isfinite(p_np)), "2D pressure must be finite (SC#1)"
        assert _sha256(p_np) == _EXPECTED_PRESSURE_HASH, (
            "2D pressure hash drifted from the v0.5.0 baseline — the 2D path "
            "is no longer byte-identical (SC#1 regression)"
        )

        # Velocity — StaggeredGrid non-uniform tensor; extract x-face and
        # y-face via explicit dim order (Pitfall 1). np.asarray on the whole
        # StaggeredGrid .values raises in phi 3.4.0 (non-uniform tensor).
        v = fs.velocity
        assert v is not None
        v_values = v.values
        vx = v_values["x"].numpy("x,y")
        vy = v_values["y"].numpy("x,y")
        assert vx.shape == _EXPECTED_VX_SHAPE
        assert vy.shape == _EXPECTED_VY_SHAPE
        assert np.all(np.isfinite(vx)), "2D velocity x-face must be finite"
        assert np.all(np.isfinite(vy)), "2D velocity y-face must be finite"
        assert _sha256(vx) == _EXPECTED_VX_HASH, (
            "2D velocity x-face hash drifted from the v0.5.0 baseline " "(SC#1 regression)"
        )
        assert _sha256(vy) == _EXPECTED_VY_HASH, (
            "2D velocity y-face hash drifted from the v0.5.0 baseline " "(SC#1 regression)"
        )

    def test_2d_per_step_finite_n10(self, basic_config_2d):
        """Per-step finiteness is the Nyquist minimum for per-step divergence
        (VALIDATION D1). Asserts velocity+pressure are finite EVERY step for
        N=10 steps, not just the final state."""
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_2d)
        for i in range(10):
            fs.step()
            p = fs.pressure
            assert p is not None, f"pressure None at step {i}"
            p_np = np.asarray(p.values)
            assert np.all(np.isfinite(p_np)), f"NaN/Inf in pressure at step {i}"
            v_values = fs.velocity.values
            vx = v_values["x"].numpy("x,y")
            vy = v_values["y"].numpy("x,y")
            assert np.all(np.isfinite(vx)), f"NaN/Inf in vx at step {i}"
            assert np.all(np.isfinite(vy)), f"NaN/Inf in vy at step {i}"
