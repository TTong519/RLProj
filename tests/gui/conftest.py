"""GUI pytest fixtures: force offscreen Qt and isolated HOME for QSettings."""

from __future__ import annotations

import os
import sys

import pytest

# Force offscreen Qt for all tests in this directory.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False


@pytest.fixture(scope="session")
def qapp():
    if not _HAVE_PYSIDE6:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path
