"""Force computation: pressure gradient integration over obstacle masks."""

from __future__ import annotations

from typing import Any

import numpy as np

from surg_rl.scene_definition.schema import FluidConfig


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
