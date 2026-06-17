#!/usr/bin/env python3
"""Detect known-incompatible mjpython+AppleSilicon combinations that the
OMP shim cannot mitigate.

The combination of mjpython's Cocoa-GL trampoline + PyTorch's bundled
``libomp.dylib`` on Apple Silicon is unstable: mjpython runs the Python
interpreter on a non-main Cocoa thread, and libomp's pthread_mutex_init
segfaults from that thread. The result is:

    OMP: Error #179: Function pthread_mutex_init failed:
    OMP: System error #22: Invalid argument
    zsh: segmentation fault  mjpython demos/demo.py --render

The fix is in :mod:`demos._omp_compat`, which sets
``OMP_NUM_THREADS=1`` (and MKL/OPENBLAS equivalents) so libomp never
enters the problematic pthread_mutex_init path. This module refuses the
``--render`` request only if those env vars are NOT in effect — i.e.
when the demo would actually segfault. If the shim has done its job,
we let the user through with a non-zero exit only when something is
genuinely wrong.

This module exposes a single function, ``is_risky_render_combination``,
that the demos consult before honoring ``--render``. When the
combination is detected, the demo prints a clear error pointing to the
workaround and exits non-zero — better than segfaulting, since the user
can actually see and act on the message.
"""

import os
import platform
import sys


def is_under_mjpython() -> bool:
    """True when running under mjpython's Cocoa-GUI trampoline.

    Detection: ``MJPYTHON_BIN`` env var (set by mjpython) is the
    authoritative signal. Fallbacks cover the rare case where the
    user invokes the mjpython binary directly via its full path.
    """
    return (
        "MJPYTHON_BIN" in os.environ
        or "mjpython" in os.path.basename(sys.executable)
        or "mjpython" in (sys.argv[0] if sys.argv else "")
    )


def is_apple_silicon() -> bool:
    """True on macOS arm64 (M1/M2/M3/M4)."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _omp_thread_singletons_in_effect() -> bool:
    """True iff the OMP shim's thread=1 env vars are in effect.

    These env vars prevent the mjpython+AppleSilicon pthread_mutex_init
    segfault. If they're set (whether by the shim or by the user's
    shell), the demo should run safely under mjpython.
    """
    return (
        os.environ.get("OMP_NUM_THREADS") == "1"
        and os.environ.get("MKL_NUM_THREADS") == "1"
        and os.environ.get("OPENBLAS_NUM_THREADS") == "1"
        and os.environ.get("KMP_DUPLICATE_LIB_OK", "").upper() == "TRUE"
    )


def is_risky_render_combination(device: str | None = None) -> bool:
    """True for the known-unstable combination the shim cannot fix.

    Returns True when ALL of the following are true:

    1. Running under mjpython (the Cocoa-GL trampoline).
    2. macOS Apple Silicon (arm64).
    3. The OMP shim's thread=1 env vars are NOT in effect.

    The ``device`` argument is accepted for backwards compatibility with
    callers that pass ``args.device``, but it is intentionally NOT used
    in the check: the segfault is mjpython+AppleSilicon regardless of
    the SB3 device (cpu/cuda/mps/auto all hit the same pthread path).
    The shim's thread=1 env vars fix the issue for every device value.
    """
    del device  # unused; see docstring
    if not is_under_mjpython():
        return False
    if not is_apple_silicon():
        return False
    if _omp_thread_singletons_in_effect():
        return False
    return True


def format_risky_render_message() -> str:
    """Multi-line error string the demos print when --render is unsafe."""
    sep = "=" * 72  # 72-character separator line
    return (
        "\n"
        + sep + "\n"
        + "  RENDER REQUESTED UNDER A KNOWN-UNSTABLE COMBINATION\n"
        + sep + "\n"
        + "\n"
        + "You ran:  mjpython demos/<demo>.py --render\n"
        + "On:      macOS arm64 with the OMP thread workaround not in effect.\n"
        + "\n"
        + "This combination is known to segfault during SB3 training\n"
        + "startup (after Monitor/DummyVecEnv wrapping) with:\n"
        + "\n"
        + "  OMP: Error #179: Function pthread_mutex_init failed:\n"
        + "  OMP: System error #22: Invalid argument\n"
        + "\n"
        + "The cause is mjpython's Cocoa-GL trampoline running the Python\n"
        + "interpreter on a non-main thread, where PyTorch's bundled\n"
        + "libomp.dylib hits a pthread initialization bug. The segfault\n"
        + "is independent of the SB3 device (cpu/cuda/mps/auto all hit\n"
        + "the same code path).\n"
        + "\n"
        + "Use one of these workarounds instead:\n"
        + "\n"
        + "  1. The demos' OMP shim should have set the thread=1 env\n"
        + "     vars before this point. If you see this message, the\n"
        + "     shim was not imported first; check the demo's import\n"
        + "     order (it must be the first import).\n"
        + "\n"
        + "  2. Set the env vars manually in your shell:\n"
        + "       export OMP_NUM_THREADS=1\n"
        + "       export MKL_NUM_THREADS=1\n"
        + "       export OPENBLAS_NUM_THREADS=1\n"
        + "       export KMP_DUPLICATE_LIB_OK=TRUE\n"
        + "       mjpython demos/demo.py --render --steps 1000\n"
        + "\n"
        + "  3. Drop --render and use plain Python:\n"
        + "       python demos/demo.py --headless --steps 1000\n"
        + "\n"
        + "  4. Train headless, then render a saved model post-training:\n"
        + "       python demos/demo.py --headless --steps 1000\n"
        + "       mjpython demos/eval_demo.py --model \\\n"
        + "           logs/suturing_demo/final_model --render --episodes 5\n"
        + "\n"
        + "See demos/README.md, 'Cannot start viewer: no display available'\n"
        + "section, for the full write-up.\n"
        + sep + "\n"
    )
