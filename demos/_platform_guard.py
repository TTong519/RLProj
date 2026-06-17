#!/usr/bin/env python3
"""Detect known-incompatible mjpython+AppleSilicon+MPS combinations.

The combination of mjpython's Cocoa-GL trampoline + PyTorch's MPS
backend on Apple Silicon is unstable: it can segfault during SB3
training startup (typically right after ``Monitor``/``DummyVecEnv``
wrapping). See the Troubleshooting section of ``demos/README.md`` for
the full write-up.

This module exposes a single function, ``is_risky_render_combination``,
that the demos consult before honoring ``--render``. When the
combination is detected, the demo prints a clear error pointing to
the four documented workarounds and exits non-zero — better than
segfaulting, since the user can actually see and act on the
message.
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


def _mps_will_be_used(device: str | None) -> bool:
    """Decide whether PyTorch's MPS backend will actually be selected.

    Args:
        device: The ``--device`` value from the demo's CLI (one of
            ``"auto"``, ``"cpu"``, ``"cuda"``, ``"mps"``, or ``None``
            if the demo doesn't take a ``--device`` flag).

    Returns:
        True iff MPS will actually be used. False if the user has
        explicitly forced CPU/CUDA, or if MPS isn't even available.

    SB3's ``device="auto"`` picks CUDA > MPS > CPU on Apple Silicon
    when MPS is available. So ``"auto"`` + MPS-available triggers the
    risk; ``"cpu"`` and ``"cuda"`` don't; ``"mps"`` does.
    """
    if device in (None, "auto"):
        # Resolve auto: would SB3 pick MPS?
        try:
            import torch
        except ImportError:
            return False
        try:
            mps = getattr(torch.backends, "mps", None)
            return bool(mps) and bool(mps.is_available())
        except Exception:
            return False
    if device == "mps":
        try:
            import torch
        except ImportError:
            return False
        try:
            mps = getattr(torch.backends, "mps", None)
            return bool(mps) and bool(mps.is_available())
        except Exception:
            return False
    # cpu / cuda: MPS won't be used.
    return False


def is_risky_render_combination(device: str | None = None) -> bool:
    """True for the known-unstable combination.

    Returns True when ALL of the following are true:

    1. Running under mjpython (the Cocoa-GL trampoline).
    2. macOS Apple Silicon (arm64).
    3. PyTorch's MPS backend will actually be used given the requested
       ``device``. The ``--device cpu`` and ``--device cuda`` flags
       force SB3 off MPS, so they make the segfault risk go away even
       on Apple Silicon.

    The check is intentionally conservative: it only flags the
    combination we have observed to segfault. Other configurations
    (Linux + mjpython, Intel Mac + mjpython, Apple Silicon + mjpython
    + ``--device cpu``) are not flagged.
    """
    if not is_under_mjpython():
        return False
    if not is_apple_silicon():
        return False
    return _mps_will_be_used(device)


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
        + "On:      macOS arm64 with PyTorch's MPS backend available.\n"
        + "\n"
        + "This combination is known to segfault during SB3 training\n"
        + "startup (after Monitor/DummyVecEnv wrapping). The cause is\n"
        + "mjpython's Cocoa-GL trampoline interacting with PyTorch's MPS\n"
        + "backend on Apple Silicon.\n"
        + "\n"
        + "Use one of these workarounds instead:\n"
        + "\n"
        + "  1. Drop --render and use plain Python (the OMP shim\n"
        + "     handles the duplicate-runtime issue):\n"
        + "       python demos/demo.py --headless --steps 1000\n"
        + "\n"
        + "  2. Force CPU on the same mjpython command:\n"
        + "       mjpython demos/demo.py --render --device cpu --steps 1000\n"
        + "\n"
        + "  3. Use the CLI (same flags, simpler code path):\n"
        + "       mjpython -m surg_rl.cli train \\\n"
        + "           --scene scenes/suturing_demo.json --render-human\n"
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
