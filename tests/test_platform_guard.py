"""Tests for the mjpython+AppleSilicon render-guard.

The combination of mjpython's Cocoa-GL trampoline + PyTorch's bundled
``libomp.dylib`` on Apple Silicon segfaults during SB3 training
startup: mjpython runs the Python interpreter on a non-main Cocoa
thread, and libomp's pthread_mutex_init segfaults from that thread.

The OMP shim (``demos/_omp_compat.py``) works around this by setting
``OMP_NUM_THREADS=1`` (and the MKL/OpenBLAS equivalents) so libomp
never enters the problematic pthread_mutex_init path. The platform
guard detects when those env vars are NOT in effect under
mjpython+AppleSilicon and the demos exit with a clear error before
trying to start the viewer (which would segfault).

The guard must be conservative: it only flags the exact combination
observed to crash and only when the shim's workaround is missing.
Other configurations (plain Python, Linux, Intel Mac, mjpython +
AppleSilicon with the shim's env vars set) must be allowed.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

GUARD_PATH = Path(__file__).parent.parent / "demos" / "_platform_guard.py"


def _load_guard_fresh():
    """Load _platform_guard in isolation, fresh from disk."""
    sys.modules.pop("_platform_guard", None)
    spec = importlib.util.spec_from_file_location("_platform_guard", GUARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patch_mjpython_apple_silicon(monkeypatch):
    """Set up the test environment as mjpython+AppleSilicon."""
    monkeypatch.setenv("MJPYTHON_BIN", "/Applications/mujoco.app/Contents/MacOS/mjpython")
    monkeypatch.setattr(sys, "executable", "/Applications/mjpython.app/Contents/MacOS/python")
    monkeypatch.setattr(sys, "argv", ["python", "demo.py"])


def _unpatch_omp_shim_env(monkeypatch):
    """Pretend the OMP shim never ran (no thread=1 env vars set)."""
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("KMP_DUPLICATE_LIB_OK", raising=False)


def _patch_omp_shim_env(monkeypatch):
    """Pretend the OMP shim ran (all thread=1 env vars set)."""
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.setenv("MKL_NUM_THREADS", "1")
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "1")
    monkeypatch.setenv("KMP_DUPLICATE_LIB_OK", "TRUE")


def test_plain_python_apple_silicon_not_flagged(monkeypatch):
    """Plain python on Apple Silicon must not be flagged.

    Plain python does not have mjpython's Cocoa-GL trampoline, so
    the segfault risk does not apply.
    """
    monkeypatch.delenv("MJPYTHON_BIN", raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/homebrew/bin/python3.14")
    monkeypatch.setattr(sys, "argv", ["python3.14", "demo.py"])
    _unpatch_omp_shim_env(monkeypatch)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_under_mjpython() is False
        assert g.is_apple_silicon() is True
        assert g.is_risky_render_combination() is False


def test_mjpython_linux_not_flagged(monkeypatch):
    """mjpython on Linux is fine — only Apple Silicon has the segfault."""
    monkeypatch.setenv("MJPYTHON_BIN", "/opt/mujoco/bin/mjpython")
    _unpatch_omp_shim_env(monkeypatch)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Linux"), patch.object(
        g.platform, "machine", return_value="x86_64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is False
        assert g.is_risky_render_combination() is False


def test_mjpython_intel_mac_not_flagged(monkeypatch):
    """mjpython on Intel Mac is fine — only Apple Silicon has the segfault."""
    monkeypatch.setenv("MJPYTHON_BIN", "/Applications/mujoco.app/Contents/MacOS/mjpython")
    _unpatch_omp_shim_env(monkeypatch)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="x86_64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is False
        assert g.is_risky_render_combination() is False


def test_mjpython_apple_silicon_no_shim_flagged(monkeypatch):
    """The bad combination: mjpython+AppleSilicon and the OMP shim's
    thread=1 env vars are NOT set. This is what would actually segfault.
    """
    _patch_mjpython_apple_silicon(monkeypatch)
    _unpatch_omp_shim_env(monkeypatch)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is True
        assert g.is_risky_render_combination() is True
        # device argument is accepted but unused — all devices segfault
        # without the shim.
        assert g.is_risky_render_combination(device="cpu") is True
        assert g.is_risky_render_combination(device="cuda") is True
        assert g.is_risky_render_combination(device="mps") is True
        assert g.is_risky_render_combination(device="auto") is True


def test_mjpython_apple_silicon_with_shim_not_flagged(monkeypatch):
    """The good case: mjpython+AppleSilicon but the OMP shim's thread=1
    env vars ARE in effect. The shim's workaround prevents the segfault,
    so the user should be allowed through.
    """
    _patch_mjpython_apple_silicon(monkeypatch)
    _patch_omp_shim_env(monkeypatch)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is True
        # The shim's env vars prevent the segfault; not risky.
        assert g.is_risky_render_combination() is False
        assert g.is_risky_render_combination(device="cpu") is False
        assert g.is_risky_render_combination(device="mps") is False
        assert g.is_risky_render_combination(device="auto") is False


def test_mjpython_apple_silicon_partial_shim_env_still_flagged(monkeypatch):
    """If only some of the shim's env vars are set, the workaround is
    incomplete. The guard should still flag the combination so the user
    gets a clear error rather than a partial segfault risk.
    """
    _patch_mjpython_apple_silicon(monkeypatch)
    # Set only OMP, leave MKL and OPENBLAS unset.
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.delenv("MKL_NUM_THREADS", raising=False)
    monkeypatch.delenv("OPENBLAS_NUM_THREADS", raising=False)
    monkeypatch.delenv("KMP_DUPLICATE_LIB_OK", raising=False)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_risky_render_combination() is True


def test_mjpython_apple_silicon_shim_env_with_wrong_value_still_flagged(monkeypatch):
    """If the env vars are set to non-"1" values, the workaround isn't
    active. The guard should still flag.
    """
    _patch_mjpython_apple_silicon(monkeypatch)
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    monkeypatch.setenv("MKL_NUM_THREADS", "4")
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "4")
    monkeypatch.setenv("KMP_DUPLICATE_LIB_OK", "TRUE")

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        # thread=4 doesn't trigger the shim's workaround; still risky.
        assert g.is_risky_render_combination() is True


def test_format_risky_render_message_contains_workarounds():
    """The error message must explain the cause and the workarounds.

    Users seeing this message need actionable instructions. The
    format is verified to contain the key information: the OMP
    error signature, the cause (non-main thread + libomp), and
    the workarounds (set env vars, drop --render, headless training).
    """
    g = _load_guard_fresh()
    msg = g.format_risky_render_message()
    assert "RENDER REQUESTED UNDER A KNOWN-UNSTABLE COMBINATION" in msg
    # The OMP error signature so users can google it.
    assert "OMP: Error #179" in msg
    assert "pthread_mutex_init" in msg
    # The workarounds.
    assert "OMP_NUM_THREADS=1" in msg
    assert "MKL_NUM_THREADS=1" in msg
    assert "OPENBLAS_NUM_THREADS=1" in msg
    assert "KMP_DUPLICATE_LIB_OK=TRUE" in msg
    assert "Drop --render" in msg
    assert "headless" in msg
    # Separator lines for readability
    assert msg.count("=" * 72) >= 2


def test_omp_thread_singletons_in_effect_helper(monkeypatch):
    """The internal helper that decides whether the shim's env vars are
    in effect must be precise: all four vars at the right values, case
    insensitive on KMP_DUPLICATE_LIB_OK.
    """
    g = _load_guard_fresh()
    _unpatch_omp_shim_env(monkeypatch)
    assert g._omp_thread_singletons_in_effect() is False

    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    assert g._omp_thread_singletons_in_effect() is False  # not all set

    monkeypatch.setenv("MKL_NUM_THREADS", "1")
    assert g._omp_thread_singletons_in_effect() is False  # not all set

    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "1")
    assert g._omp_thread_singletons_in_effect() is False  # KMP missing

    monkeypatch.setenv("KMP_DUPLICATE_LIB_OK", "TRUE")
    assert g._omp_thread_singletons_in_effect() is True

    # Case-insensitive on KMP_DUPLICATE_LIB_OK
    monkeypatch.setenv("KMP_DUPLICATE_LIB_OK", "true")
    assert g._omp_thread_singletons_in_effect() is True

    monkeypatch.setenv("KMP_DUPLICATE_LIB_OK", "FALSE")
    assert g._omp_thread_singletons_in_effect() is False
