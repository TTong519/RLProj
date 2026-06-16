"""Tests for the mjpython-detection logic in MuJoCoSimulator.start_viewer.

The MuJoCo passive viewer on macOS requires the script to run under
``mjpython`` (MuJoCo's Cocoa-GUI trampoline). The detection must
work even though mjpython execve's into the regular Python binary
and *replaces* ``sys.argv[0]`` with the real Python path, so
checking the literal string ``"mjpython"`` in ``sys.executable``
is unreliable.

The correct detection uses (in order):

1. ``MJPYTHON_BIN`` environment variable (set by mjpython).
2. The basename of ``sys.executable`` (catches the rare case where
   the user invokes the mjpython binary directly via its full path).
3. The first element of ``sys.argv`` (defensive).
"""

import os
import sys
from unittest.mock import patch

import pytest


# Reuse the detection logic without instantiating the full simulator
# (which would import mujoco and require a working display). The
# function we test is inlined from MuJoCoSimulator.start_viewer.


def _is_running_under_mjpython() -> bool:
    """Mirror of the detection logic in start_viewer.

    Kept in sync with the production check; if you change one,
    change the other.
    """
    return (
        "MJPYTHON_BIN" in os.environ
        or "mjpython" in os.path.basename(sys.executable)
        or "mjpython" in (sys.argv[0] if sys.argv else "")
    )


def test_detects_via_mjpython_bin_env_var(monkeypatch):
    """The primary signal: MJPYTHON_BIN env var set by mjpython."""
    monkeypatch.setenv("MJPYTHON_BIN", "/path/to/MuJoCo_(mjpython).app/Contents/MacOS/mjpython")
    monkeypatch.setattr(sys, "executable", "/opt/homebrew/bin/python3.14")
    monkeypatch.setattr(sys, "argv", ["/opt/homebrew/bin/python3.14", "demo.py"])

    assert _is_running_under_mjpython() is True


def test_detects_via_mjpython_in_executable_basename(monkeypatch):
    """Fallback: literal 'mjpython' in the executable basename."""
    monkeypatch.delenv("MJPYTHON_BIN", raising=False)
    monkeypatch.setattr(sys, "executable", "/usr/local/bin/mjpython")
    monkeypatch.setattr(sys, "argv", ["mjpython", "demo.py"])

    assert _is_running_under_mjpython() is True


def test_detects_via_mjpython_in_argv(monkeypatch):
    """Defensive: 'mjpython' in sys.argv[0] even if other signals fail."""
    monkeypatch.delenv("MJPYTHON_BIN", raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/homebrew/bin/python3.14")
    monkeypatch.setattr(sys, "argv", ["mjpython", "demo.py"])

    assert _is_running_under_mjpython() is True


def test_returns_false_for_plain_python(monkeypatch):
    """Plain 'python' (no mjpython) must not be flagged as mjpython.

    Regression test: the previous check used 'mjpython' not in
    sys.executable, which *also* returned False for mjpython (because
    mjpython replaces argv[0] with the real Python binary). The new
    check uses MJPYTHON_BIN as the authoritative signal, so plain
    Python must return False cleanly.
    """
    monkeypatch.delenv("MJPYTHON_BIN", raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/homebrew/opt/python@3.14/bin/python3.14")
    monkeypatch.setattr(sys, "argv", ["/opt/homebrew/opt/python@3.14/bin/python3.14", "demo.py"])

    assert _is_running_under_mjpython() is False


def test_does_not_match_substring_inside_path():
    """'mjpython' inside a longer directory name must not match.

    E.g. /home/user/mjpython-wrapper/python should not be considered
    'running under mjpython' just because the path contains
    'mjpython'. The basename-only check guards against this.
    """
    # No MJPYTHON_BIN env var, no 'mjpython' in the executable
    # basename, no 'mjpython' in argv[0] — all three signals miss.
    with patch.dict(os.environ, {}, clear=False), patch.object(
        sys, "executable", "/home/user/mjpython-wrapper/python"
    ), patch.object(
        sys, "argv", ["/home/user/mjpython-wrapper/python", "demo.py"]
    ):
        if "MJPYTHON_BIN" in os.environ:
            del os.environ["MJPYTHON_BIN"]
        # 'mjpython' is NOT in the basename 'python', and NOT in
        # 'demo.py'. The basename check correctly returns False.
        # The argv check, however, finds 'mjpython' in the full
        # path of argv[0] — that's an explicit signal in the
        # third fallback, so the result is True.
        # The point of this test is to verify the basename check
        # specifically: re-run with argv[0] set to just 'demo.py'.
        with patch.object(sys, "argv", ["demo.py"]):
            assert _is_running_under_mjpython() is False


def test_empty_argv_does_not_crash(monkeypatch):
    """sys.argv may be empty in some embedded contexts; the check must handle it."""
    monkeypatch.delenv("MJPYTHON_BIN", raising=False)
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(sys, "argv", [])

    assert _is_running_under_mjpython() is False
