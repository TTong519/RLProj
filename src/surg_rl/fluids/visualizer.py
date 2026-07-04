"""Fluid visualization: 2D colormesh rendering and data export."""

from __future__ import annotations

from typing import Any

import numpy as np


def _render_np_2d(
    arr: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray | None:
    """Render a 2D numpy array as an RGB image (private shared helper).

    Shared by ``render_fluid_2d`` (2D path) and ``render_fluid_3d`` (z-layer
    slice of a 3D field). Normalizes the array, resizes it to
    ``(height, width)``, and maps it to a blue-dominant colormap.

    Returns:
        (height, width, 3) uint8 array or None if rendering fails.
    """
    try:
        from skimage.transform import resize

        p_norm = arr - arr.min()
        p_max = p_norm.max()
        p_norm = p_norm / p_max if p_max > 1e-12 else np.zeros_like(p_norm)

        img = np.zeros((height, width, 3), dtype=np.uint8)

        resized = resize(p_norm, (height, width), anti_aliasing=False)

        blue = np.clip(resized * 255, 0, 255).astype(np.uint8)

        img[:, :, 2] = blue
        img[:, :, 0] = blue
        img[:, :, 1] = (blue * 0.2).astype(np.uint8)

        return img
    except Exception:
        return None


def render_fluid_2d(
    pressure: Any | None,
    config: Any,
    width: int = 400,
    height: int = 400,
) -> np.ndarray | None:
    """Render pressure field as RGB image array.

    Returns:
        (height, width, 3) uint8 array or None if unavailable.
    """
    if pressure is None:
        return None

    try:
        p_vals: np.ndarray = pressure.values.numpy()
    except Exception:
        try:
            p_vals = np.asarray(pressure.values, dtype=np.float64)
        except Exception:
            return None

    return _render_np_2d(p_vals, width, height)


def render_fluid_3d(
    pressure: Any | None,
    config: Any,
    z_layer: int | None = None,
    width: int = 400,
    height: int = 400,
) -> np.ndarray | None:
    """Render a 2D z-layer slice of a 3D pressure field via the 2D renderer.

    Slice-of-3D fallback (D-18): extracts the ``z_layer`` xy-plane from the 3D
    pressure field and delegates to ``_render_np_2d``. This is NOT a true
    volume / iso-surface renderer (deferred per CONTEXT.md).

    Args:
        pressure: 3D PhiFlow pressure field (or None).
        config: Fluid config (unused by the slice renderer but kept for API
            symmetry with ``render_fluid_2d``).
        z_layer: z-layer index to slice; ``None`` uses the middle layer
            (``nz // 2``). Clamped to ``[0, nz-1]`` (T-38-07).
        width: Output image width.
        height: Output image height.

    Returns:
        (height, width, 3) uint8 array or None if unavailable / extraction
        fails.
    """
    if pressure is None:
        return None

    try:
        p_np: np.ndarray = pressure.values.numpy("x,y,z")
    except Exception:
        return None

    nz = p_np.shape[2]
    layer = z_layer if z_layer is not None else nz // 2
    # Clamp to valid range (T-38-07: tampering/DoS on z_layer arg).
    layer = max(0, min(layer, nz - 1))
    slice_2d = p_np[:, :, layer]
    return _render_np_2d(slice_2d, width, height)
