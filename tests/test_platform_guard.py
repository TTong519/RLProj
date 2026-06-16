"""Tests for the mjpython+AppleSilicon+MPS render-guard.

The combination of mjpython's Cocoa-GL trampoline + PyTorch's MPS
backend on Apple Silicon segfaults during SB3 training startup.
The platform guard detects this combination and the demos exit
with a clear error before trying to start the viewer.

The guard must be conservative: it only flags the exact
combination observed to crash. Other configurations (Linux,
Intel Mac, Apple Silicon without MPS) must be allowed.
"""

import importlib.util
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


def test_plain_python_apple_silicon_not_flagged(monkeypatch):
    """plain python on Apple Silicon must not be flagged.

    Plain python does not have mjpython's Cocoa-GL trampoline, so
    the segfault risk does not apply even when MPS is available.
    """
    monkeypatch.delenv("MJPYTHON_BIN", raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/homebrew/bin/python3.14")
    monkeypatch.setattr(sys, "argv", ["python3.14", "demo.py"])

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

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="x86_64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is False
        assert g.is_risky_render_combination() is False


def test_mjpython_apple_silicon_with_mps_flagged(monkeypatch):
    """The exact bad combination: mjpython+Apple Silicon+MPS available."""
    monkeypatch.setenv("MJPYTHON_BIN", "/Applications/mujoco.app/Contents/MacOS/mjpython")
    monkeypatch.setattr(sys, "executable", "/Applications/mjpython.app/Contents/MacOS/python")
    monkeypatch.setattr(sys, "argv", ["python", "demo.py"])

    # Fake torch + mps.is_available() returning True
    fake_torch = type("FakeTorch", (), {})()
    fake_torch.backends = type(
        "FakeBackends", (), {"mps": type("FakeMps", (), {"is_available": staticmethod(lambda: True)})()}
    )()
    fake_torch_mod = type(sys)("torch")
    fake_torch_mod.backends = fake_torch.backends
    monkeypatch.setitem(sys.modules, "torch", fake_torch_mod)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is True
        assert g.is_risky_render_combination() is True


def test_mjpython_apple_silicon_no_torch_not_flagged(monkeypatch):
    """If PyTorch is not installed, there's no MPS to crash with."""
    monkeypatch.setenv("MJPYTHON_BIN", "/Applications/mujoco.app/Contents/MacOS/mjpython")

    # Make torch import raise ImportError
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _raise_on_torch(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("torch not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raise_on_torch)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_under_mjpython() is True
        assert g.is_apple_silicon() is True
        # No torch → no MPS → no segfault risk
        assert g.is_risky_render_combination() is False


def test_mjpython_apple_silicon_mps_unavailable_not_flagged(monkeypatch):
    """If torch is installed but MPS isn't available, SB3 falls back to CPU."""
    monkeypatch.setenv("MJPYTHON_BIN", "/Applications/mujoco.app/Contents/MacOS/mjpython")

    fake_torch_mod = type(sys)("torch")
    fake_torch_mod.backends = type("B", (), {})()
    fake_torch_mod.backends.mps = type(
        "Mps", (), {"is_available": staticmethod(lambda: False)}
    )()
    monkeypatch.setitem(sys.modules, "torch", fake_torch_mod)

    g = _load_guard_fresh()
    with patch.object(g.platform, "system", return_value="Darwin"), patch.object(
        g.platform, "machine", return_value="arm64"
    ):
        assert g.is_risky_render_combination() is False


def test_format_risky_render_message_contains_workarounds():
    """The error message must list the 4 documented workarounds.

    Users seeing this message need actionable instructions. The
    format is verified to contain all four workarounds explicitly.
    """
    g = _load_guard_fresh()
    msg = g.format_risky_render_message()
    assert "RENDER REQUESTED UNDER A KNOWN-UNSTABLE COMBINATION" in msg
    assert "Drop --render" in msg
    assert "--device cpu" in msg
    assert "surg_rl.cli train" in msg
    assert "headless, then render a saved model" in msg
    # Separator lines for readability
    assert msg.count("=" * 72) >= 2
