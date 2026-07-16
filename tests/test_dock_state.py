"""Phase 41 — dock layout reset + in-place update_scene regression tests.

Covers GUI-18 / SC#1, SC#2, SC#4 (Plan 01):
  - TestDockObjectNames (SC#4): every QDockWidget child of EditorWindow has a
    non-empty, unique objectName so saveState()/restoreState() round-trip.
  - TestDockRoundTrip (SC#1/#2): factory-default capture at first showEvent +
    Reset Layout restores it; rearrange -> load scene -> close -> reopen
    restores the user's saved arrangement.
  - TestUpdateScene (SC#2): _refresh_viewport_and_tree does NOT recreate the
    ViewportPanel / SceneTreeView widgets (the bug #3 root cause).

Offscreen harness mirrors tests/test_viewport.py:13-67 (standalone single-file
variant) + tests/gui/conftest.py:1-35 (qapp + isolated_home). The
``isolated_home`` fixture is mandatory for any test constructing EditorWindow
so QSettings does not pollute the developer's real
``~/Library/Preferences/com.SurgRL.SceneEditor.plist``.
"""

from __future__ import annotations

import os
import sys

import pytest

# Force offscreen Qt for all tests in this file (must run before any
# QApplication is constructed).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HAVE_PYSIDE6 = True
try:
    import PySide6  # noqa: F401
except ImportError:
    _HAVE_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, reason="PySide6 not installed")


@pytest.fixture(scope="session")
def qapp():
    if not _HAVE_PYSIDE6:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME + XDG_CONFIG_HOME to tmp_path so QSettings stays isolated."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    yield tmp_path


@pytestmark
class TestDockObjectNames:
    """SC#4 / D-07: every QDockWidget has a non-empty, unique objectName.

    This passes immediately against the current 3 docks (dock_scene_tree,
    dock_properties, dock_llm) and is the regression guard for future phases.
    """

    def test_every_dock_has_unique_nonempty_objectname(self, qapp, isolated_home) -> None:
        from PySide6.QtWidgets import QDockWidget

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        try:
            docks = w.findChildren(QDockWidget)
            names = [d.objectName() for d in docks]
            assert docks, "EditorWindow should construct at least one QDockWidget"
            assert all(names), (
                f"Every QDockWidget must have a non-empty objectName; got {names}"
            )
            assert len(names) == len(set(names)), (
                f"QDockWidget objectNames must be unique; got {names}"
            )
        finally:
            w.close()


@pytestmark
class TestDockRoundTrip:
    """SC#1 / SC#2 / D-08: saveState/restoreState round-trip + Reset Layout.

    RED in Task 1: ``surg_rl.editor.dock_state`` does not exist yet, so the
    DockStateManager import surfaces as an ImportError (the honest RED
    baseline — no pytest.skip / xfail). Task 2 (DockStateManager + showEvent
    capture + reset_to_default wiring) drives these GREEN.
    """

    def test_reset_layout_restores_factory_default(self, qapp, isolated_home) -> None:
        from surg_rl.editor.dock_state import DockStateManager  # noqa: F401

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        factory = w.saveState()
        # Rearrange: tabify the tree + properties docks (a state the crude
        # re-addDockWidget reset ignored, but restoreState(factory) restores).
        w.tabifyDockWidget(w._tree_dock, w._properties_dock)
        qapp.processEvents()
        try:
            assert w.saveState().data() != factory.data(), (
                "tabify should change the saved state before reset"
            )
            w._action_reset_layout()
            qapp.processEvents()
            after = w.saveState()
            assert after.data() == factory.data(), (
                "Reset Layout must restore the factory-default arrangement "
                "(incl. tabification), not just re-addDockWidget to areas"
            )
        finally:
            w.close()

    def test_rearrange_close_reopen(self, qapp, isolated_home) -> None:
        from surg_rl.editor.dock_state import DockStateManager  # noqa: F401

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        # Rearrange: tabify tree + properties.
        w.tabifyDockWidget(w._tree_dock, w._properties_dock)
        qapp.processEvents()
        rearranged = w.saveState()
        # Trigger a scene load via the refresh path. With the old widget-
        # recreation body this is the bug #3 trigger; with the Task 3
        # update_scene in-place swap the dock geometry survives.
        w._refresh_viewport_and_tree()
        qapp.processEvents()
        # close -> closeEvent saves the arrangement via EditorSettings.save_window
        w.close()
        qapp.processEvents()
        # Reopen with the same isolated_home so QSettings persists.
        w2 = EditorWindow()
        w2.show()
        qapp.processEvents()
        try:
            restored = w2.saveState()
            assert restored.data() == rearranged.data(), (
                "rearrange -> load scene -> close -> reopen must restore the "
                "user's saved arrangement (SC#2), not a broken/default state"
            )
        finally:
            w2.close()
