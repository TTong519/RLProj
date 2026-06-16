#!/usr/bin/env python3
"""Suppress OpenMP duplicate-library crashes on macOS / mjpython.

``mjpython`` (the MuJoCo-supplied macOS Cocoa-GUI trampoline) and plain
Python builds on Apple Silicon can both end up linking two copies of
``libomp.dylib`` — one from MuJoCo's bundled framework, one from
``torch``/``numpy``/system OpenMP. Loading both produces:

    OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib
    already initialized.
    zsh: abort      mjpython demos/demo.py --render

The documented (unsafe, unsupported) workaround is to set
``KMP_DUPLICATE_LIB_OK=TRUE`` *before* either library is loaded. The
env var must be set in ``os.environ`` before the first ``import
mujoco`` / ``import torch``, which is why this module is imported
first in every demo that might need it.

Usage::

    import demos._omp_compat  # noqa: F401  -- first import, sets env var
    # ... rest of the demo ...
"""

import os

# Must be set BEFORE mujoco/torch/numpy are imported. Idempotent and
# silent if already set; safe to call multiple times.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
