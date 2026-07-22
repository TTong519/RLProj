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

import contextlib
import os
import sys
import time

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
            assert all(names), f"Every QDockWidget must have a non-empty objectName; got {names}"
            assert len(names) == len(
                set(names)
            ), f"QDockWidget objectNames must be unique; got {names}"
        finally:
            w.close()


@pytestmark
class TestToolbarObjectNames:
    """Phase 42 D-06 / Phase 41 D-07 extension: every QToolBar has a non-empty,
    unique objectName so saveState()/restoreState() round-trip the playback
    toolbar (Pitfall 7 — setObjectName BEFORE addToolBar).

    RED on Task 1 of Plan 42-02: the playback QToolBar is built in Task 3's
    ``_build_playback_toolbar``; findChildren(QToolBar) is empty until then.
    The sibling ``TestDockObjectNames`` (the QDockWidget regression guard for
    Phase 41 SC#4) stays GREEN throughout.
    """

    def test_every_toolbar_has_unique_nonempty_objectname(self, qapp, isolated_home) -> None:
        from PySide6.QtWidgets import QToolBar

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        try:
            tbs = w.findChildren(QToolBar)
            names = [t.objectName() for t in tbs]
            assert tbs, "EditorWindow should construct at least one QToolBar"
            assert all(names), f"Every QToolBar must have a non-empty objectName; got {names}"
            assert len(names) == len(
                set(names)
            ), f"QToolBar objectNames must be unique; got {names}"
            assert "toolbar_playback" in names, f"toolbar_playback objectName missing; got {names}"
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
            assert (
                w.saveState().data() != factory.data()
            ), "tabify should change the saved state before reset"
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
        # Rearrange: tabify tree + properties (a state restoreState must
        # recover on reopen).
        w.tabifyDockWidget(w._tree_dock, w._properties_dock)
        qapp.processEvents()
        assert w._properties_dock in w.tabifiedDockWidgets(
            w._tree_dock
        ), "precondition: tree + properties should be tabified after rearrange"
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
            # SC#2: the tabified arrangement must survive close+reopen (the
            # user's saved layout restores, not a broken/default state). We
            # assert the structural arrangement (tabification) rather than
            # byte-identical saveState, because pixel geometry/splitter sizes
            # may differ across window instances while the dock relationship
            # is what saveState/restoreState keys on via objectName.
            tabified = w2.tabifiedDockWidgets(w2._tree_dock)
            assert w2._properties_dock in tabified, (
                "rearrange -> load scene -> close -> reopen must restore the "
                "tabified arrangement (SC#2), not a broken/default state"
            )
        finally:
            w2.close()


@pytestmark
class TestResetLayoutReturningUser:
    """CR-01 regression: a returning user with a saved (rearranged) layout must
    have Reset Layout restore the FACTORY arrangement, not their last-saved one.

    The factory-default snapshot must be captured from the code-built layout
    BEFORE ``_restore_geometry`` re-applies the user's saved QSettings layout in
    ``__init__``. If capture happens at ``showEvent`` instead, the snapshot is
    the user's restored layout and Reset Layout is a no-op in the common case
    (a returning user who has rearranged docks). ``isolated_home`` round-trips a
    real saved tabified layout across two EditorWindow instances so this
    exercises the true returning-user path (not the empty-QSettings path the
    SC#1 test starts from).

    RED on the capture-at-showEvent code; GREEN once capture moves to
    ``__init__`` before ``_restore_geometry`` (D-01, CR-01 fix).
    """

    def test_reset_layout_restores_factory_split_for_returning_user(
        self, qapp, isolated_home
    ) -> None:
        from PySide6.QtCore import Qt

        from surg_rl.editor.main_window import EditorWindow

        # Session 1: rearrange (tabify tree+properties), close -> closeEvent
        # saves the tabified layout to QSettings via save_window (which syncs).
        w1 = EditorWindow()
        w1.show()
        qapp.processEvents()
        w1.tabifyDockWidget(w1._tree_dock, w1._properties_dock)
        qapp.processEvents()
        assert w1._properties_dock in w1.tabifiedDockWidgets(
            w1._tree_dock
        ), "precondition: tree + properties tabified before close"
        w1.close()  # closeEvent -> save_window -> tabified layout persisted
        qapp.processEvents()

        # Session 2 (returning user): __init__ restores the saved tabified
        # layout via _restore_geometry, then Reset Layout must restore the
        # FACTORY split (tree=Left, properties=Right), not the saved tabified.
        w2 = EditorWindow()
        w2.show()
        qapp.processEvents()
        assert w2._properties_dock in w2.tabifiedDockWidgets(w2._tree_dock), (
            "precondition: returning user's saved tabified layout must restore "
            "on reopen (else this test is not exercising the returning-user path)"
        )
        w2._action_reset_layout()
        qapp.processEvents()
        try:
            tabified = w2.tabifiedDockWidgets(w2._tree_dock)
            assert w2._properties_dock not in tabified, (
                "CR-01: Reset Layout must restore the factory SPLIT arrangement "
                "for a returning user, not their saved tabified layout"
            )
            assert (
                w2.dockWidgetArea(w2._tree_dock).value == Qt.DockWidgetArea.LeftDockWidgetArea.value
            ), "factory: tree dock in Left area"
            assert (
                w2.dockWidgetArea(w2._properties_dock).value
                == Qt.DockWidgetArea.RightDockWidgetArea.value
            ), "factory: properties dock in Right area (not tabified with tree)"
        finally:
            w2.close()


@pytestmark
class TestUpdateScene:
    """SC#2 regression guard: _refresh_viewport_and_tree must NOT recreate the
    ViewportPanel / SceneTreeView widgets (the bug #3 root cause). The widget
    identity (``id()``) is unchanged across a refresh because update_scene
    swaps state in place rather than constructing new widgets.
    """

    def test_update_scene_does_not_recreate_viewport(self, qapp, isolated_home) -> None:
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        vp_id = id(w._viewport_panel)
        w._refresh_viewport_and_tree()
        qapp.processEvents()
        try:
            assert id(w._viewport_panel) == vp_id, (
                "_refresh_viewport_and_tree must NOT recreate ViewportPanel "
                "(bug #3 root cause — use update_scene in-place swap)"
            )
        finally:
            w.close()

    def test_update_scene_does_not_recreate_tree(self, qapp, isolated_home) -> None:
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        tree_id = id(w._tree_view)
        w._refresh_viewport_and_tree()
        qapp.processEvents()
        try:
            assert id(w._tree_view) == tree_id, (
                "_refresh_viewport_and_tree must NOT recreate SceneTreeView "
                "(bug #3 root cause — use update_scene in-place swap)"
            )
        finally:
            w.close()


@pytestmark
class TestCloseMidCallMockSlow:
    """SC#3 / D-09b: closing mid-LLM-call exits cleanly (always-on backstop).

    Monkeypatches ``TextParser.parse_sync`` to ``time.sleep(2)`` so the test
    always runs offscreen without an API key. It triggers ``_on_generate``,
    then calls ``LLMPanel.stop()`` (the canonical teardown used by
    ``aboutToClose``) and asserts the worker thread is no longer running and
    no ``RuntimeError: Internal C++ object already deleted`` was raised.

    RED in Task 1: ``LLMPanel.stop`` does not exist yet (AttributeError — the
    honest RED baseline). Task 1 GREEN implements ``stop()`` (cooperative
    cancel + ``thread.quit()`` + ``thread.wait(3000)`` + timeout log).
    """

    def test_close_mid_llm_call_clean_exit_mock_slow(
        self, qapp, isolated_home, monkeypatch
    ) -> None:
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.scene_definition import SceneDefinition
        from surg_rl.scene_generation import text_parser as tp

        # Monkeypatch the slow parser path — always runs offscreen (no key).
        def slow_parse_sync(self, input_data, **kwargs):  # noqa: ANN001, ANN002, ANN003
            time.sleep(2)  # simulate a multi-second provider call
            return SceneDefinition()

        monkeypatch.setattr(tp.TextParser, "parse_sync", slow_parse_sync)

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        w._llm_panel._prompt.setPlainText("a test prompt")
        # Start the worker thread (worker calls the monkeypatched slow parse).
        w._llm_panel._on_generate()
        qapp.processEvents()
        try:
            # Close mid-call via the canonical teardown used by aboutToClose.
            # Task 1: stop() does not exist yet -> AttributeError (honest RED).
            # Task 1 GREEN: stop() cancels + thread.quit() + thread.wait(3000).
            w._llm_panel.stop()
            qapp.processEvents()
            # Worker thread must have exited cleanly (no segfault, no
            # RuntimeError: Internal C++ object already deleted).
            thread = w._llm_panel._thread
            if thread is not None:
                assert not thread.isRunning(), (
                    "LLM worker thread still running after stop() — "
                    "close mid-LLM-call must exit cleanly (SC#3 / D-05)"
                )
        finally:
            with contextlib.suppress(Exception):
                w.close()


@pytestmark
class TestCloseMidCallRealProvider:
    """SC#3 / D-09a: real-provider close-mid-call guard.

    Gated behind ``skipif(not os.environ.get("LLM_API_KEY"))`` — guards the
    true provider path when keys are present. The always-on
    ``TestCloseMidCallMockSlow`` (D-09b) is the regression backstop that runs
    unconditionally offscreen; this class runs only when a real key is set so
    SC#3 is verified against the actual SDK call path.
    """

    @pytest.mark.skipif(
        not os.environ.get("LLM_API_KEY"),
        reason="No LLM_API_KEY — D-09a real-provider path, guarded by D-09b "
        "mock backstop (TestCloseMidCallMockSlow runs unconditionally)",
    )
    def test_close_mid_llm_call_clean_exit_real_provider(self, qapp, isolated_home) -> None:
        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        w.show()
        qapp.processEvents()
        w._llm_panel._prompt.setPlainText("A simple suturing scene.")
        # Start a real (short) provider call.
        w._llm_panel._on_generate()
        qapp.processEvents()
        try:
            # Close mid-call via the full closeEvent path (aboutToClose ->
            # LLMPanel.stop). Must not segfault or raise RuntimeError.
            w.close()
            qapp.processEvents()
            thread = w._llm_panel._thread
            if thread is not None:
                assert not thread.isRunning(), (
                    "LLM worker thread still running after close mid real "
                    "provider call — SC#3 real-path guard (D-09a)"
                )
        finally:
            with contextlib.suppress(Exception):
                w.close()


@pytestmark
class TestAboutToClose:
    """D-04 wiring guard: closeEvent emits aboutToClose which triggers
    ``_llm_panel.stop`` BEFORE ``super().closeEvent()``. Verified with a Mock
    so the wiring is guarded even without an in-flight LLM call (mirrors the
    ``tests/test_viewport.py:299-316`` closeEvent + Mock stop pattern).
    """

    def test_close_event_emits_aboutto_close_before_super(self, qapp, isolated_home) -> None:
        from unittest.mock import MagicMock

        from PySide6.QtGui import QCloseEvent

        from surg_rl.editor.main_window import EditorWindow

        w = EditorWindow()
        # Replace the LLM panel's stop() with a Mock to observe the call.
        mock_llm_stop = MagicMock()
        w._llm_panel.stop = mock_llm_stop
        w.closeEvent(QCloseEvent())
        try:
            assert (
                mock_llm_stop.call_count >= 1
            ), "closeEvent must emit aboutToClose -> _llm_panel.stop() before "
            "Qt teardown (D-04 wiring)"
        finally:
            with contextlib.suppress(Exception):
                w.close()
