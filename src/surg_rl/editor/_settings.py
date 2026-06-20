"""QSettings wrapper for the scene editor.

Persists across launches: window geometry, window state (dock layout),
recent files (max 5), last LLM provider.

Storage is platform-native via ``QSettings`` (registry on Windows,
``~/Library/Preferences/com.SurgRL.SceneEditor.plist`` on macOS,
``~/.config/SurgRL/SceneEditor.conf`` on Linux). No API keys are stored here
— those stay in ``.env`` via ``surg_rl.utils.config.Settings()`` per D-20.
"""
from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QByteArray, QSettings

_ORG: Final[str] = "SurgRL"
_APP: Final[str] = "SceneEditor"
_MAX_RECENT: Final[int] = 5


class EditorSettings:
    """QSettings wrapper for the scene editor.

    Storage is platform-native. No secrets stored.
    """

    def __init__(self) -> None:
        self._q: QSettings = QSettings(_ORG, _APP)

    def save_window(self, geometry: QByteArray, state: QByteArray) -> None:
        self._q.setValue("window/geometry", geometry)
        self._q.setValue("window/state", state)
        self._q.sync()

    def load_window(self) -> tuple[QByteArray | None, QByteArray | None]:
        return (
            self._q.value("window/geometry", type=QByteArray),
            self._q.value("window/state", type=QByteArray),
        )

    def add_recent_file(self, path: str | Path) -> list[str]:
        """Insert ``path`` at index 0, dedupe, cap at 5; return the new list."""
        existing = self._q.value("files/recent", [], type=list) or []
        s = str(path)
        deduped = [s] + [p for p in existing if p != s]
        capped = deduped[:_MAX_RECENT]
        self._q.setValue("files/recent", capped)
        self._q.sync()
        return list(capped)

    def recent_files(self) -> list[str]:
        return list(self._q.value("files/recent", [], type=list) or [])

    def set_last_provider(self, provider: str) -> None:
        self._q.setValue("llm/last_provider", provider)
        self._q.sync()

    def last_provider(self) -> str | None:
        return self._q.value("llm/last_provider", None, type=str)
