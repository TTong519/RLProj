#!/usr/bin/env python3
"""Suppress OpenMP duplicate-library crashes on macOS / mjpython.

``mjpython`` (the MuJoCo-supplied macOS Cocoa-GUI trampoline) runs the
Python interpreter on a non-main Cocoa thread so the main thread is free
for GUI calls. On Apple Silicon, PyTorch's bundled ``libomp.dylib`` then
hits a known pthread initialization bug:

    OMP: Error #179: Function pthread_mutex_init failed:
    OMP: System error #22: Invalid argument
    zsh: segmentation fault  mjpython demos/demo.py --render

This happens regardless of the SB3 device (cpu / cuda / mps); it is
triggered by the combination of mjpython's off-main-thread init and
PyTorch's libomp. The documented workarounds are:

1. Set ``KMP_DUPLICATE_LIB_OK=TRUE`` so two copies of libomp can coexist
   (this addresses the related OMP Error #15 — libomp already
   initialized — but does NOT fix Error #179 by itself).
2. Force libomp to use a single thread with ``OMP_NUM_THREADS=1`` so
   pthread_mutex_init is never called from the problematic code path.
3. Likewise pin MKL and OpenBLAS to 1 thread to prevent the same family
   of issues from those runtimes.

This module sets all four env vars via ``os.environ.setdefault`` so
externally-provided values (e.g. ``OMP_NUM_THREADS=4`` set by a CI
runner) still take precedence. Imported first in every demo.

Usage::

    import demos._omp_compat  # noqa: F401  -- first import, sets env vars
    # ... rest of the demo ...
"""

import os

# Must be set BEFORE mujoco/torch/numpy are imported. Idempotent and
# silent if already set; safe to call multiple times.

# (1) Allow multiple copies of libomp to coexist (addresses OMP #15).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# (2) Force libomp / MKL / OpenBLAS to a single thread. On mjpython +
# Apple Silicon, this avoids the pthread_mutex_init path that segfaults
# (OMP #179). Single-threaded is fine for our demos: the training loop
# is GIL-bound, SB3 does its parallel work in subprocesses when needed,
# and the env stepping is dominated by MuJoCo's inner loop, not BLAS.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
