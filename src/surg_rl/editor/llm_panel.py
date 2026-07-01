"""LLMPanel - the LLM-prompt-to-JSON dock widget (per GUI-07 + D-13..D-16)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from surg_rl.editor import QtCore, QtWidgets
from surg_rl.editor._safe_error import safe_error_message

if TYPE_CHECKING:
    from surg_rl.scene_definition import SceneDefinition


class TextParserWorker(QtCore.QObject):
    """QObject worker that calls TextParser.parse_sync() on a QThread (per D-13).

    Signals:
        finished(SceneDefinition) - parse succeeded
        failed(str) - parse raised; payload is the redacted error message
    """

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, provider: str | None, api_key: str | None) -> None:
        super().__init__()
        self._provider = provider
        self._api_key = api_key
        from surg_rl.scene_generation.text_parser import TextParser

        self._parser = TextParser(provider=provider, api_key=api_key)

    @QtCore.Slot(str)
    def run(self, prompt: str) -> None:
        try:
            result = self._parser.parse_sync(prompt)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(safe_error_message(exc))
            return
        self.finished.emit(result)


class LLMPanel(QtWidgets.QWidget):
    """QWidget with prompt input, Generate/Accept/Reject buttons, JSON preview."""

    scene_accepted = QtCore.Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._thread: QtCore.QThread | None = None
        self._worker: TextParserWorker | None = None
        self._current_scene: SceneDefinition | None = None

        self._prompt = QtWidgets.QPlainTextEdit()
        self._prompt.setPlaceholderText("Describe a surgical scene...")
        self._preview = QtWidgets.QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("(JSON preview appears here after Generate)")

        self._btn_generate = QtWidgets.QPushButton("Generate")
        self._btn_cancel = QtWidgets.QPushButton("Cancel")
        self._btn_cancel.setEnabled(False)
        self._btn_accept = QtWidgets.QPushButton("Accept")
        self._btn_accept.setEnabled(False)
        self._btn_reject = QtWidgets.QPushButton("Reject")
        self._btn_reject.setEnabled(False)
        self._provider_combo = QtWidgets.QComboBox()
        self._provider_combo.addItems(["openai", "anthropic", "ollama"])
        try:
            from surg_rl.editor._settings import EditorSettings

            last_provider = EditorSettings().last_provider()
            if last_provider:
                idx = self._provider_combo.findText(last_provider)
                if idx >= 0:
                    self._provider_combo.setCurrentIndex(idx)
        except ImportError:
            pass
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(QtWidgets.QLabel("Provider:"))
        button_row.addWidget(self._provider_combo)
        button_row.addStretch(1)
        button_row.addWidget(self._btn_generate)
        button_row.addWidget(self._btn_cancel)
        button_row.addWidget(self._btn_accept)
        button_row.addWidget(self._btn_reject)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addWidget(QtWidgets.QLabel("Prompt:"))
        outer.addWidget(self._prompt, 1)
        outer.addWidget(QtWidgets.QLabel("Preview:"))
        outer.addWidget(self._preview, 2)
        outer.addLayout(button_row)

        self._btn_generate.clicked.connect(self._on_generate)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_accept.clicked.connect(self._on_accept)
        self._btn_reject.clicked.connect(self._on_reject)

    def _on_generate(self) -> None:
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            return
        try:
            from surg_rl.utils.config import get_settings

            settings = get_settings()
        except Exception:
            settings = None
        provider = self._provider_combo.currentText()
        api_key = getattr(settings, "llm_api_key", None) if settings else None
        self._thread = QtCore.QThread()
        self._worker = TextParserWorker(provider=provider, api_key=api_key)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(lambda: self._worker.run(prompt))
        self._worker.finished.connect(self._on_parse_finished)
        self._worker.failed.connect(self._on_parse_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._btn_generate.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._thread.start()

    def _on_cancel(self) -> None:
        if self._worker is not None:
            self._worker.setProperty("_cancelled", True)
        if self._thread is not None:
            self._thread.quit()

    def _on_parse_finished(self, scene: SceneDefinition) -> None:
        import json

        self._current_scene = scene
        self._preview.setPlainText(json.dumps(scene.model_dump(mode="json"), indent=2))
        self._btn_generate.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._btn_accept.setEnabled(True)
        self._btn_reject.setEnabled(True)

    def _on_parse_failed(self, msg: str) -> None:
        self._preview.setPlainText(f"Parse failed:\n{msg}")
        self._btn_generate.setEnabled(True)
        self._btn_cancel.setEnabled(False)

    def _on_accept(self) -> None:
        if self._current_scene is not None:
            self.scene_accepted.emit(self._current_scene)
            self._reset_preview()

    def _on_reject(self) -> None:
        self._reset_preview()

    def _on_provider_changed(self, provider: str) -> None:
        try:
            from surg_rl.editor._settings import EditorSettings

            EditorSettings().set_last_provider(provider)
        except ImportError:
            pass

    def _reset_preview(self) -> None:
        self._current_scene = None
        self._preview.clear()
        self._btn_accept.setEnabled(False)
        self._btn_reject.setEnabled(False)
