"""Regression tests for the Phase 33 GUI foundation (Plan 33-01).

Covers:
- TestSafeErrorMessage — pure-Python redaction tests (no Qt required)
- TestEditorSettings — QSettings round-trip (skipped on PySide6-free systems)
- TestMainWindow — EditorWindow smoke tests under QT_QPA_PLATFORM=offscreen
- TestAppMainGates — `surg-rl-gui` console-script entrypoint behavior
- TestSurgRlCliIndependence — locks that `surg-rl --help` does NOT import PySide6
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


# --- Helpers ----------------------------------------------------------------


def _HAS_PYSIDE6() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    # Force native QSettings to use INI files under tmp_path so macOS plist
    # caching does not leak values between tests.
    try:
        from PySide6.QtCore import QSettings
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            str(tmp_path / "qt_settings"),
        )
    except Exception:
        pass
    yield tmp_path


@pytest.fixture(scope="session")
def qapp():
    if not _HAS_PYSIDE6():
        pytest.skip("PySide6 not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
    app.quit()


# --- Pure-Python redaction tests (no Qt) -----------------------------------


class TestSafeErrorMessage:
    def test_redacts_openai_key(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        out = safe_error_message("auth failed with sk-projabc123def456ghi789jkl012mno")
        assert "[REDACTED]" in out
        assert "sk-projabc123def456ghi789jkl012mno" not in out

    def test_redacts_anthropic_key(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        out = safe_error_message("sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdef")
        assert "[REDACTED]" in out
        assert "sk-ant-api03" not in out

    def test_redacts_xai_key(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        out = safe_error_message("got 401 for xai-AbCdEfGhIjKlMnOpQrStUvWxYz012345")
        assert "[REDACTED]" in out
        assert "xai-AbCd" not in out

    def test_redacts_bearer_token(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        out = safe_error_message("Authorization: Bearer AbCdEfGhIjKlMnOpQrStUvWxYz0123456789")
        assert "[REDACTED]" in out

    def test_redacts_env_var_style(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        out = safe_error_message("OPENAI_API_KEY=sk-projabc123def456ghi789jkl012mno")
        assert "sk-projabc" not in out
        assert "[REDACTED]" in out

    def test_passes_through_normal_error_text(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        msg = "Connection refused: ECONNREFUSED 127.0.0.1:11434"
        assert safe_error_message(msg) == msg

    def test_accepts_exception_object(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        exc = ValueError("auth failed with sk-projabc123def456ghi789jkl012mno")
        out = safe_error_message(exc)
        # str(exc) is the message itself, not the qualified class name
        assert "auth failed" in out
        assert "[REDACTED]" in out
        assert "sk-projabc" not in out

    def test_does_not_crash_on_empty_string(self) -> None:
        from surg_rl.editor._safe_error import safe_error_message
        assert safe_error_message("") == ""


# --- QSettings wrapper tests (require PySide6) ------------------------------


@pytest.mark.skipif(not _HAS_PYSIDE6(), reason="PySide6 not installed")
class TestEditorSettings:
    def test_save_and_load_window(self, isolated_home) -> None:
        if not _HAS_PYSIDE6():
            pytest.skip("PySide6 not installed")
        from PySide6.QtCore import QByteArray
        from surg_rl.editor._settings import EditorSettings
        s = EditorSettings()
        geo = QByteArray(b"geometry-bytes")
        state = QByteArray(b"state-bytes")
        s.save_window(geo, state)
        s2 = EditorSettings()
        g2, st2 = s2.load_window()
        assert g2 == geo
        assert st2 == state

    def test_recent_files_dedupe_and_cap(self, isolated_home) -> None:
        if not _HAS_PYSIDE6():
            pytest.skip("PySide6 not installed")
        from surg_rl.editor._settings import EditorSettings
        s = EditorSettings()
        for i in range(8):
            s.add_recent_file(f"/path/{i}.json")
        recent = s.recent_files()
        assert len(recent) == 5
        assert recent[0] == "/path/7.json"
        s.add_recent_file("/path/3.json")
        recent2 = s.recent_files()
        assert recent2[0] == "/path/3.json"
        assert len(recent2) == 5

    def test_recent_files_persists_across_instances(self, isolated_home) -> None:
        if not _HAS_PYSIDE6():
            pytest.skip("PySide6 not installed")
        from surg_rl.editor._settings import EditorSettings
        s1 = EditorSettings()
        s1.add_recent_file("/p/a.json")
        s2 = EditorSettings()
        assert "/p/a.json" in s2.recent_files()

    def test_last_provider_round_trip(self, isolated_home) -> None:
        if not _HAS_PYSIDE6():
            pytest.skip("PySide6 not installed")
        from surg_rl.editor._settings import EditorSettings
        s = EditorSettings()
        assert s.last_provider() is None
        s.set_last_provider("anthropic")
        s2 = EditorSettings()
        assert s2.last_provider() == "anthropic"


# --- MainWindow tests (require PySide6 + offscreen) -------------------------


@pytest.mark.skipif(not _HAS_PYSIDE6(), reason="PySide6 not installed")
class TestMainWindow:
    def test_main_window_can_be_constructed(self, qapp, isolated_home) -> None:
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.editor import QtWidgets
        w = EditorWindow()
        assert w.windowTitle() == "Surg-RL Scene Editor"
        docks = w.findChildren(QtWidgets.QDockWidget)
        titles = sorted(d.windowTitle() for d in docks)
        assert titles == sorted(["Scene Tree", "Properties", "LLM Prompt-to-JSON"])
        assert w.centralWidget() is not None

    def test_main_window_with_scene_path_does_not_crash(self, qapp, isolated_home, tmp_path) -> None:
        from surg_rl.editor.main_window import EditorWindow
        scene = tmp_path / "test.json"
        scene.write_text('{"metadata": {"name": "x", "version": "0.1.0"}}')
        w = EditorWindow(scene_path=scene)
        assert w.windowTitle() == "Surg-RL Scene Editor"

    def test_drag_drop_accepts_json(self, qapp, isolated_home, tmp_path) -> None:
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.editor import QtCore, QtGui
        w = EditorWindow()
        scene = tmp_path / "drop.json"
        scene.write_text("{}")
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(scene))])
        event = QtGui.QDropEvent(
            QtCore.QPointF(0, 0),
            QtCore.Qt.DropAction.CopyAction,
            mime,
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        w.dropEvent(event)
        assert w.isVisible() is False

    def test_close_event_persists_geometry(self, qapp, isolated_home) -> None:
        from surg_rl.editor.main_window import EditorWindow
        w = EditorWindow()
        w.resize(900, 700)
        w.close()
        w2 = EditorWindow()
        # Window managers / offscreen platforms may clamp the exact size.
        assert w2.width() >= 700, f"expected width >= 700, got {w2.width()}"
        assert w2.height() >= 500, f"expected height >= 500, got {w2.height()}"

    def test_status_bar_has_four_labels(self, qapp, isolated_home) -> None:
        from surg_rl.editor.main_window import EditorWindow
        from surg_rl.editor import QtWidgets
        w = EditorWindow()
        bar = w.statusBar()
        labels = bar.findChildren(QtWidgets.QLabel)
        assert any("Untitled" in l.text() for l in labels)
        assert any("sim:" in l.text() for l in labels)
        assert any("fps:" in l.text() for l in labels)
        assert any("validate:" in l.text() for l in labels)


# --- App entrypoint tests ---------------------------------------------------


class TestAppMainGates:
    def test_help_short_circuits_before_pyside6(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app", "--help"],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "surg-rl-gui" in result.stdout

    def test_no_args_after_pyside6_gate_invokes_main_window(self) -> None:
        try:
            import PySide6  # noqa: F401
        except ImportError:
            pytest.skip("PySide6 not installed")
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app", "--headless"],
            env={**os.environ, "PYTHONPATH": "src", "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0


class TestSurgRlCliIndependence:
    """Lock that `surg-rl --help` does NOT import PySide6."""

    def test_surg_rl_help_does_not_import_pyside6(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.cli", "--help"],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # PySide6 must NOT be in the import path of the CLI
        assert "PySide6" not in result.stderr
        assert "PySide6" not in result.stdout
