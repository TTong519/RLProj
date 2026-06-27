"""Force computation: pressure gradient integration over obstacle masks."""

from __future__ import annotations

from typing import Any

import numpy as np

from surg_rl.scene_definition.schema import FluidConfig


def _compute_obstacle_forces_3d(
    velocity: Any,
    pressure: Any,
    obstacles: list[Any],
    obstacle_names: list[str],
    config: FluidConfig,
) -> dict[str, np.ndarray]:
    """3D obstacle-mask force integration -> per-obstacle (fx, fy, fz).

    Deliberately distinct from the 2D global-sum path (D-16): the 3D path
    integrates the pressure gradient over each obstacle's mask cells via
    ``phi.field.sample`` per obstacle, rather than summing the global pressure
    gradient. Do NOT unify the two paths.

    Per-axis INDEPENDENT clamp (D-17): each of fx, fy, fz is clamped to
    ``[-1e4, 1e4]`` independently; a spike on one axis does not shrink the
    others (unlike the 2D scalar-magnitude clamp).

    Args:
        velocity: 3D StaggeredGrid velocity (unused for the force computation;
            accepted for symmetry with the 2D helper).
        pressure: 3D pressure Field (CenteredGrid) from ``make_incompressible``.
        obstacles: list of PhiFlow ``Obstacle`` objects (their ``.geometry`` is
            sampled onto the pressure grid to obtain the per-obstacle mask).
        obstacle_names: parallel list of obstacle name strings.
        config: FluidConfig with ``dim_3d=True``, ``grid_size`` set, and
            ``bounds`` defining the 3D domain.

    Returns:
        dict mapping obstacle name -> ``np.array([fx, fy, fz], dtype=float64)``.
    """
    if pressure is None or not obstacle_names:
        return {}

    import phi.field as field

    try:
        p_np = pressure.values.numpy("x,y,z")
    except Exception as exc:  # pragma: no cover - defensive guard
        return {name: np.zeros(3) for name in obstacle_names}

    dims = config.bounds.get_dimensions()
    nx, ny, nz = config.grid_size
    dx = dims[0] / nx
    dy = dims[1] / ny
    dz = dims[2] / nz
    cell_vol = dx * dy * dz

    # Physical pressure gradient (per meter), NOT per cell-index. Passing the
    # cell spacing to np.gradient is what makes the units Pa/m rather than
    # Pa/cell; the 2D `compute_obstacle_forces` already divides by `dx`/`dz`
    # explicitly. Without this the per-axis forces are off by `dx`, `dy`, `dz`
    # respectively (3D-only regression — CR-01).
    if dx == 0.0 or dy == 0.0 or dz == 0.0:
        return {name: np.zeros(3) for name in obstacle_names}
    grad_x = np.gradient(p_np, dx, axis=0)
    grad_y = np.gradient(p_np, dy, axis=1)
    grad_z = np.gradient(p_np, dz, axis=2)

    cap = 1e4
    forces: dict[str, np.ndarray] = {}
    for obs, name in zip(obstacles, obstacle_names):
        mask = field.sample(obs.geometry, pressure)
        mask_np = mask.numpy("x,y,z")
        fx = -float(np.sum(grad_x * mask_np)) * cell_vol
        fy = -float(np.sum(grad_y * mask_np)) * cell_vol
        fz = -float(np.sum(grad_z * mask_np)) * cell_vol
        # Per-axis INDEPENDENT clamp (D-17).
        fx = max(-cap, min(cap, fx))
        fy = max(-cap, min(cap, fy))
        fz = max(-cap, min(cap, fz))
        forces[name] = np.array([fx, fy, fz], dtype=np.float64)
    return forces


def compute_obstacle_forces(
    velocity: Any,
    pressure: Any,
    obstacle_names: list[str],
    config: FluidConfig,
) -> dict[str, np.ndarray]:
    """Compute net fluid force on each obstacle via pressure gradient integration.

    F = -∫_Ω ∇p dV ≈ -∑(central difference of p over mask cells) × ΔV

    Returns a dict mapping obstacle name → force vector (fx, fy, fz) in world frame.
    For the 2D xz-plane, forces are (fx, 0, fz).
    """
    if pressure is None or not obstacle_names:
        return {}

    try:
        p_vals: np.ndarray = pressure.values.numpy()
    except Exception:
        try:
            p_vals = np.asarray(pressure.values, dtype=np.float64)
        except Exception:
            return {name: np.zeros(3) for name in obstacle_names}

    dims = config.bounds.get_dimensions()
    nx, nz = config.resolution
    dx = dims[0] / nx
    dz = dims[2] / nz
    cell_vol = dx * dz

    grad_x = np.zeros_like(p_vals)
    grad_z = np.zeros_like(p_vals)

    grad_x[1:-1, :] = (p_vals[2:, :] - p_vals[:-2, :]) / (2.0 * dx)
    grad_x[0, :] = (p_vals[1, :] - p_vals[0, :]) / dx
    grad_x[-1, :] = (p_vals[-1, :] - p_vals[-2, :]) / dx

    grad_z[:, 1:-1] = (p_vals[:, 2:] - p_vals[:, :-2]) / (2.0 * dz)
    grad_z[:, 0] = (p_vals[:, 1] - p_vals[:, 0]) / dz
    grad_z[:, -1] = (p_vals[:, -1] - p_vals[:, -2]) / dz

    fx_total = -float(np.sum(grad_x)) * cell_vol
    fz_total = -float(np.sum(grad_z)) * cell_vol

    magnitude = float(np.sqrt(fx_total * fx_total + fz_total * fz_total))
    if magnitude > 1e4:
        scale = 1e4 / magnitude
        fx_total *= scale
        fz_total *= scale

    force = np.array([fx_total, 0.0, fz_total], dtype=np.float64)
    return dict.fromkeys(obstacle_names, force)
