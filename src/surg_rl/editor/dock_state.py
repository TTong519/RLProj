"""DockStateManager — factory-default dock layout capture + reset (GUI-18).

Owns the factory-default dock layout per CONTEXT.md D-01:
  - Primary: a ``QByteArray`` snapshot taken once at the first ``showEvent``
    via ``QMainWindow.saveState()`` (always reflects the actual built layout
    even if code defaults drift).
  - Fallback: a code-level ``_rebuild_default_layout`` that re-adds the docks
    in the factory arrangement when the snapshot is missing/corrupt.

The factory default is recomputed each launch from the built docks — it is
NOT persisted to QSettings (D-01). Only the user's saved layout round-trips
via the existing ``EditorSettings.save_window``/``load_window`` keys.

Import discipline (mirrors ``editor/undo_stack.py`` + ``editor/__init__.py``):
Qt symbols are imported via the ``surg_rl.editor`` LazyImport proxies, NOT
``from PySide6 import ...`` at module top, so this module stays cheap to import
and never triggers PySide6 load on its own.
"""

from __future__ import annotations

from surg_rl.editor import QtCore, QtWidgets

__all__ = ["DockStateManager"]


class DockStateManager:
    """Owns the factory-default dock layout: first-show ``QByteArray`` snapshot
    (primary) plus a code-level rebuild fallback (D-01).

    The capture is guarded by a one-shot bool (Pitfall 5): ``showEvent`` can
    fire multiple times (e.g. minimize/restore on some platforms), and an
    unguarded capture would overwrite the factory snapshot with the user's
    rearranged layout — so ``Reset Layout`` would reset to the wrong thing.
    """

    def __init__(self) -> None:
        self._factory_state: QtCore.QByteArray | None = None
        self._captured: bool = False  # Pitfall 5 one-shot guard

    def capture_factory_default(self, window: QtWidgets.QMainWindow) -> None:
        """Capture ``saveState()`` at first ``showEvent``. Idempotent (D-01).

        Subsequent calls are no-ops so the factory snapshot is never
        overwritten by the user's rearranged layout.
        """
        if self._captured:
            return
        self._factory_state = window.saveState()
        self._captured = True

    def reset_to_default(self, window: QtWidgets.QMainWindow) -> bool:
        """Reset Layout (D-02): restore the factory-default arrangement.

        Primary: ``restoreState(factory QByteArray)`` — restores
        tabification/floating/closed state, not just area assignment.
        Fallback: code-level rebuild re-adds docks in the factory arrangement,
        then re-captures the snapshot. Returns True when the primary restore
        succeeded.
        """
        if self._factory_state is not None and window.restoreState(self._factory_state):
            return True
        # Fallback: code-level rebuild (re-add docks to factory areas).
        self._rebuild_default_layout(window)
        self._factory_state = window.saveState()
        self._captured = True
        return True

    def _rebuild_default_layout(self, window: QtWidgets.QMainWindow) -> None:
        """Code-level fallback: re-add docks in the factory arrangement (D-01).

        This is the ONLY place the crude re-``addDockWidget`` body from the
        pre-Phase-41 ``_action_reset_layout`` is preserved — kept as the
        fallback, NOT the primary path. The primary path is
        ``restoreState(factory QByteArray)`` which captures
        tabification/floating/closed state that this crude re-add ignores.
        """
        # Re-add each dock to its factory area. ``addDockWidget`` is idempotent
        # if the dock is already there (Qt moves it back to the requested
        # area). The dock objectNames are preserved (set at construction in
        # ``EditorWindow._build_dock_widgets``), so saveState/restoreState
        # continue to round-trip after the rebuild.
        tree_dock = getattr(window, "_tree_dock", None)
        properties_dock = getattr(window, "_properties_dock", None)
        llm_dock = getattr(window, "_llm_dock", None)
        if tree_dock is not None:
            window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, tree_dock)
            tree_dock.show()
        if properties_dock is not None:
            window.addDockWidget(
                QtCore.Qt.DockWidgetArea.RightDockWidgetArea, properties_dock
            )
            properties_dock.show()
        if llm_dock is not None:
            window.addDockWidget(
                QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, llm_dock
            )
            llm_dock.show()
