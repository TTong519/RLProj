"""SceneUndoStack - per-scene QUndoStack with deep-copy snapshots (per D-09..D-12)."""
from __future__ import annotations

from surg_rl.editor import QtGui
from surg_rl.scene_definition import SceneDefinition

_MAX_DEPTH: int = 100  # Per D-11.


class _SceneSnapshotCommand(QtGui.QUndoCommand):
    """A single undo step holding a deep-copy SceneDefinition snapshot."""

    def __init__(
        self,
        before: SceneDefinition,
        after: SceneDefinition,
        parent: QtGui.QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._before = before.model_copy(deep=True)
        self._after = after.model_copy(deep=True)

    def undo(self) -> None:
        SceneUndoStack._active_apply = self._before

    def redo(self) -> None:
        SceneUndoStack._active_apply = self._after


class SceneUndoStack(QtGui.QUndoStack):
    """QUndoStack specialized for SceneDefinition.

    - Deep-copy snapshots (per D-09: Pydantic v2 model_copy(deep=True) handles all
      classes including the _FloatMixin DifficultyLevel enum).
    - Per-scene scope (per D-10: one stack per open scene; cleared on save).
    - Cap at 100 levels (per D-11: 100 * 50-200 KB = 5-20 MB peak).
    """

    _active_apply: SceneDefinition | None = None

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self.setUndoLimit(_MAX_DEPTH)

    def push_snapshot(self, before: SceneDefinition, after: SceneDefinition) -> None:
        self.push(_SceneSnapshotCommand(before, after))

    def clear_on_save(self) -> None:
        """Per D-10: undo stack is cleared on save (fresh history starts)."""
        self.clear()

    @classmethod
    def take_active_apply(cls) -> SceneDefinition | None:
        """Return the snapshot set by the last undo/redo, then clear it."""
        snap = cls._active_apply
        cls._active_apply = None
        return snap
