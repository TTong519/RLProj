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


def test_close_breaks_qobject_cycle_window_refcount_collectable(qapp, isolated_home) -> None:
    """Regression guard for the Phase 42 shutdown segfault (commit 791b754).

    EditorWindow must be REFCOUNT-collectable after close() — no QObject
    reference cycle lingering for the cyclic garbage collector. Before the
    fix, ``ViewportPanel._on_fps_update`` stored the window's
    ``_update_fps_status`` bound method (a Python attribute = strong ref) →
    a window→panel→bound-method→window cycle only breakable by cyclic GC;
    cyclic GC then traversed a stale shiboken6 wrapper at interpreter
    teardown and segfaulted (full-suite exit 139).
    ``_break_qobject_cycles`` in closeEvent nulls that attribute + the
    render loop's window-ref lambdas so the graph is collected by refcount
    at close. This test fails if that cycle-break regresses (the window
    survives ``del`` and only cyclic GC reclaims it).
    """
    import gc
    import weakref

    from PySide6.QtTest import QTest

    from surg_rl.editor.main_window import EditorWindow

    w = EditorWindow()
    ref = weakref.ref(w)
    w.close()
    # Let the render-poll's ~33ms self-rescheduling singleShot fire + drop
    # its bound-method ref so the only thing that could keep the window alive
    # is a reference cycle (the regression).
    QTest.qWait(50)
    del w
    assert ref() is None, (
        "EditorWindow survived `del` after close() — a QObject reference cycle "
        "was not broken in closeEvent, so the graph lingers for cyclic GC to "
        "traverse (regression of the Phase 42 shutdown segfault, commit 791b754)"
    )
    # Belt-and-braces: a stale wrapper must not exist for a later cyclic GC.
    gc.collect()
    assert ref() is None
