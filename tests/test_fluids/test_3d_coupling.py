"""SC#2 — 3D ONE_WAY coupling stability + TWO_WAY opt-in gate (FLUID-02, D-21).

This additive regression test exercises the 3D ``FluidSimulator`` obstacle path
delivered by Plan 02 (``add_instrument`` cylinder-shaft + box-tip SDF via
``union``, 3D ``make_incompressible`` solve, 3D
``_compute_obstacle_forces_3d`` per-axis-clamp force helper). It closes SC#2:

  * **ONE_WAY** (default): run N=100 steps with a thin instrument added via
    ``add_instrument`` and assert velocity + pressure are finite EVERY step
    (per-step ``np.isfinite`` is the Nyquist minimum for per-step divergence,
    VALIDATION D1). ONE_WAY is structurally stable on thin instruments
    because obstacles are static SDFs with no solid→fluid velocity feedback
    (D-10); substepping (``coupling_substeps=4``) + the per-axis independent
    force clamp (D-17) are defense-in-depth.
  * **TWO_WAY** (opt-in): assert the config is accepted (opt-in works) and run
    N=100 steps. TWO_WAY feeds obstacle velocity back into the fluid solve
    (added-mass term) and is DOCUMENTED UNSTABLE on thin instruments (D-10,
    RESEARCH Pitfall 8). The test is marked ``xfail`` so it documents the
    instability rather than asserting stability: if the run diverges (NaN /
    blow-up / exception) that is the expected instability; if it happens to
    complete finitely, that is an xpass (not a guarantee).

This is an ADDITIVE test file — it does NOT edit any existing test.
"""

import numpy as np
import pytest

from surg_rl.scene_definition.schema import (
    BoundingBox,
    FluidConfig,
    FluidCouplingMode,
    Position,
    Pose,
)


@pytest.fixture
def basic_config_3d_one_way() -> FluidConfig:
    """3D FluidConfig with ONE_WAY coupling (default stable path, D-10/D-11)."""
    return FluidConfig(
        enabled=True,
        dim_3d=True,
        grid_size=(16, 16, 16),
        bounds=BoundingBox(
            min_corner=Position(x=0.0, y=0.0, z=0.0),
            max_corner=Position(x=0.3, y=0.3, z=0.3),
        ),
        coupling_mode=FluidCouplingMode.ONE_WAY,
        coupling_substeps=4,
    )


def _thin_instrument_pose() -> Pose:
    """Thin-instrument pose centered in the 3D domain (D-14/D-15)."""
    return Pose(position=Position(x=0.15, y=0.15, z=0.10))


# Thin-instrument dims: (shaft_radius=0.01, shaft_length=0.1, tip_half=0.01).
# Small radius = thin shaft (the geometry TWO_WAY is documented unstable on).
_THIN_DIMS = (0.01, 0.1, 0.01)


def _assert_velocity_pressure_finite(fs, step_idx: int) -> None:
    """Assert 3D velocity (all 3 staggered faces) + pressure are finite.

    Per-step ``np.isfinite`` is the Nyquist minimum for per-step divergence
    (VALIDATION D1 / RESEARCH Sampling Rate). Velocity is a StaggeredGrid with
    non-uniform face tensors (x-face, y-face, z-face have distinct shapes);
    each face is extracted via the explicit-dim-order ``.numpy('x,y,z')`` call
    (Pitfall 1: no-order ``.numpy()`` raises on >1-dim tensors in phi 3.4.0).
    """
    p = fs.pressure
    assert p is not None, f"pressure None at step {step_idx}"
    p_np = p.values.numpy("x,y,z")
    assert np.all(np.isfinite(p_np)), f"NaN/Inf in 3D pressure at step {step_idx}"

    v_values = fs.velocity.values
    vx = v_values["x"].numpy("x,y,z")
    vy = v_values["y"].numpy("x,y,z")
    vz = v_values["z"].numpy("x,y,z")
    assert np.all(np.isfinite(vx)), f"NaN/Inf in 3D vx at step {step_idx}"
    assert np.all(np.isfinite(vy)), f"NaN/Inf in 3D vy at step {step_idx}"
    assert np.all(np.isfinite(vz)), f"NaN/Inf in 3D vz at step {step_idx}"


class Test3DCouplingOneWay:
    """SC#2 ONE_WAY: N=100 steps with a thin instrument, per-step finite."""

    def test_one_way_stable_n100(self, basic_config_3d_one_way):
        """ONE_WAY N=100 steps via add_instrument on a thin instrument must stay
        finite every step (no NaN / blow-up). ONE_WAY is structurally stable on
        thin instruments: obstacles are static SDFs with no velocity feedback
        (D-10), so there is no added-mass instability. Substepping
        (coupling_substeps=4) + the per-axis independent force clamp (D-17) are
        defense-in-depth, not the primary stability mechanism.
        """
        from surg_rl.fluids import FluidSimulator

        fs = FluidSimulator(basic_config_3d_one_way)
        fs.add_instrument(_thin_instrument_pose(), _THIN_DIMS, "instrument")
        assert len(fs._obstacles) == 1
        assert fs._obstacle_names == ["instrument"]

        for i in range(100):
            fs.step()
            _assert_velocity_pressure_finite(fs, i)


class Test3DCouplingTwoWayOptIn:
    """SC#2 TWO_WAY: opt-in accepted + documented unstable (RESEARCH Pitfall 8)."""

    def test_two_way_opt_in_accepted(self):
        """TWO_WAY is opt-in via FluidCouplingMode.TWO_WAY — the config
        constructs without error (opt-in gate works, D-09/D-10)."""
        cfg = FluidConfig(
            enabled=True,
            dim_3d=True,
            grid_size=(16, 16, 16),
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.3, z=0.3),
            ),
            coupling_mode=FluidCouplingMode.TWO_WAY,
            coupling_substeps=4,
        )
        assert cfg.coupling_mode == FluidCouplingMode.TWO_WAY

    @pytest.mark.xfail(
        reason=(
            "TWO_WAY is opt-in and documented unstable on thin instruments "
            "(D-10, RESEARCH Pitfall 8: added-mass instability). The per-axis "
            "clamp is a best-effort brake, not a stability guarantee. This "
            "test documents the instability (xfail on divergence) rather "
            "than asserting stability."
        ),
        strict=False,
    )
    def test_two_way_opt_in_documented_unstable(self):
        """TWO_WAY N=100 steps with a thin instrument. If the run diverges
        (NaN / blow-up / exception) that is the documented instability (xfail);
        if it happens to complete finitely, that is an xpass (not a guarantee).

        The test asserts the SAME per-step finiteness contract as the ONE_WAY
        test so that the xfail genuinely documents "finiteness is not
        guaranteed" rather than skipping the check. RESEARCH Pitfall 8
        explicitly warns: NaN in the TWO_WAY variant is expected.
        """
        from surg_rl.fluids import FluidSimulator

        cfg = FluidConfig(
            enabled=True,
            dim_3d=True,
            grid_size=(16, 16, 16),
            bounds=BoundingBox(
                min_corner=Position(x=0.0, y=0.0, z=0.0),
                max_corner=Position(x=0.3, y=0.3, z=0.3),
            ),
            coupling_mode=FluidCouplingMode.TWO_WAY,
            coupling_substeps=4,
        )
        fs = FluidSimulator(cfg)
        fs.add_instrument(_thin_instrument_pose(), _THIN_DIMS, "instrument")

        for i in range(100):
            fs.step()
            _assert_velocity_pressure_finite(fs, i)