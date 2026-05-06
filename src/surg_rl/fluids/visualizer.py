"""Fluid visualization: 2D colormesh rendering and data export."""

from __future__ import annotations

from typing import Any

import numpy as np


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

    try:
        from skimage.transform import resize

        p_norm = p_vals - p_vals.min()
        p_max = p_norm.max()
        if p_max > 1e-12:
            p_norm = p_norm / p_max
        else:
            p_norm = np.zeros_like(p_norm)

        img = np.zeros((height, width, 3), dtype=np.uint8)

        resized = resize(p_norm, (height, width), anti_aliasing=False)

        blue = np.clip(resized * 255, 0, 255).astype(np.uint8)

        img[:, :, 2] = blue
        img[:, :, 0] = blue
        img[:, :, 1] = (blue * 0.2).astype(np.uint8)

        return img
    except Exception:
        return None
