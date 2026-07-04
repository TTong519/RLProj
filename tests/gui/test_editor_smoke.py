"""GUI smoke test: open EditorWindow, process events, capture 3 screenshots, exit."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Module-level skip if PySide6 not installed
_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")


SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.joinpath(".gitkeep").touch()


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path


def test_editor_window_opens_and_closes(qapp, isolated_home) -> None:
    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    w.show()
    qapp.processEvents()
    from PySide6.QtCore import QTimer

    QTimer.singleShot(500, qapp.quit)
    qapp.exec()
    w.close()


def test_capture_three_screenshots(qapp, isolated_home) -> None:
    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    w.resize(1280, 800)
    w.show()
    qapp.processEvents()
    w._viewport_panel.grab().save(str(SCREENSHOTS_DIR / "viewport.png"))
    w._tree_dock.widget().grab().save(str(SCREENSHOTS_DIR / "tree_form.png"))
    w._llm_dock.widget().grab().save(str(SCREENSHOTS_DIR / "llm_panel.png"))
    w.close()
    for name in ("viewport.png", "tree_form.png", "llm_panel.png"):
        p = SCREENSHOTS_DIR / name
        assert p.exists(), f"{name} was not captured"
        assert p.stat().st_size > 0, f"{name} is empty"
