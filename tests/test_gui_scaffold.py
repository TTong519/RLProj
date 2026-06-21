"""Regression tests for Phase 31 plan 04 — GUI scaffolding.

Verifies the 5 success-criterion conditions for Phase 31's GUI scaffolding
half (per .planning/REQUIREMENTS.md:55 + ROADMAP.md:55):

1. `pyproject.toml` declares the `[gui]` extra + `surg-rl-gui` console script.
2. `import surg_rl.editor` succeeds WITHOUT PySide6 installed; HAS_GUI is False.
3. `LazyImport` symbols raise ImportError with the install hint on attribute access.
4. `_is_running_under_mjpython()` returns a bool (env var, executable, argv signals).
5. `surg-rl --help` (the 14-subcommand CLI) exits 0 without importing PySide6.
6. `python -m surg_rl.editor.app --help` exits 0 with usage.
7. `python -m surg_rl.editor.app` (no args) exits 1 with the install hint.
8. `_ensure_mjpython_or_warn()` returns True on non-Darwin.

Reference: .planning/phases/31-tech-debt-foundation/31-04-PLAN.md
Source of truth: src/surg_rl/editor/{__init__,app,_platform_guard}.py
"""

import contextlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SRC_DIR = REPO_ROOT / "src"


class TestGuiPyprojectSpec:
    """pyproject.toml declares the [gui] extra + surg-rl-gui console script."""

    def test_gui_extra_declares_pyside6(self) -> None:
        """The [gui] extra in pyproject.toml contains PySide6>=6.8.0,<7.0."""
        toml_text = PYPROJECT.read_text()
        assert (
            "PySide6>=6.8.0,<7.0" in toml_text
        ), "pyproject.toml must declare PySide6>=6.8.0,<7.0 in the [gui] extra"

    def test_gui_extra_declares_markdown_it_py(self) -> None:
        """The [gui] extra in pyproject.toml contains markdown-it-py>=3.0.0."""
        toml_text = PYPROJECT.read_text()
        assert (
            "markdown-it-py>=3.0.0" in toml_text
        ), "pyproject.toml must declare markdown-it-py>=3.0.0 in the [gui] extra"

    def test_surg_rl_gui_console_script_registered(self) -> None:
        """The [project.scripts] table registers surg-rl-gui as a SEPARATE entry."""
        toml_text = PYPROJECT.read_text()
        assert (
            'surg-rl-gui = "surg_rl.editor.app:main"' in toml_text
        ), "pyproject.toml must register surg-rl-gui as a console script"

    def test_pyproject_toml_parses(self) -> None:
        """pyproject.toml parses cleanly via tomllib."""
        import tomllib

        data = tomllib.loads(PYPROJECT.read_text())
        assert "project" in data
        assert "gui" in data["project"]["optional-dependencies"]
        assert "surg-rl-gui" in data["project"]["scripts"]


class TestEditorImport:
    """import surg_rl.editor succeeds without PySide6; HAS_GUI is False."""

    def test_import_succeeds_without_pyside6(self) -> None:
        """`import surg_rl.editor` does not raise ImportError."""
        import surg_rl.editor  # noqa: F401

    def test_has_gui_is_false_when_pyside6_missing(self) -> None:
        """HAS_GUI is False on a system WITHOUT PySide6 installed."""
        import surg_rl.editor

        if surg_rl.editor.QtWidgets.available:
            pytest.skip("PySide6 is installed — HAS_GUI is True, not False")
        assert surg_rl.editor.HAS_GUI is False

    def test_qt_symbols_are_lazy_import_objects(self) -> None:
        """QtWidgets, QtCore, QtGui are LazyImport instances, NOT modules."""
        import surg_rl.editor
        from surg_rl.utils.lazy_imports import LazyImport

        assert isinstance(surg_rl.editor.QtWidgets, LazyImport)
        assert isinstance(surg_rl.editor.QtCore, LazyImport)
        assert isinstance(surg_rl.editor.QtGui, LazyImport)

    def test_lazy_import_raises_import_error_with_install_hint(self) -> None:
        """Accessing a LazyImport attribute raises ImportError with the install hint.

        Only runs when PySide6 is NOT installed (the install-hint path).
        """
        import surg_rl.editor

        if surg_rl.editor.QtWidgets.available:
            pytest.skip("PySide6 is installed — LazyImport will succeed, not raise")
        with pytest.raises(ImportError) as exc_info:
            surg_rl.editor.QtWidgets.QApplication  # noqa: B018
        msg = str(exc_info.value)
        assert (
            "pip install surg-rl[gui]" in msg
        ), f"ImportError must contain install hint; got: {msg!r}"


class TestPlatformGuard:
    """_is_running_under_mjpython + _ensure_mjpython_or_warn contract."""

    def test_is_running_under_mjpython_returns_bool(self) -> None:
        """_is_running_under_mjpython() returns a bool."""
        from surg_rl.editor._platform_guard import _is_running_under_mjpython

        result = _is_running_under_mjpython()
        assert isinstance(result, bool)

    def test_is_running_under_mjpython_env_var_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting MJPYTHON_BIN env var makes _is_running_under_mjpython() return True."""
        from surg_rl.editor._platform_guard import (
            _MJPYTHON_ENV_VAR,
            _is_running_under_mjpython,
        )

        monkeypatch.setenv(_MJPYTHON_ENV_VAR, "/fake/path/mjpython")
        assert _is_running_under_mjpython() is True

    def test_ensure_mjpython_or_warn_returns_true_on_non_darwin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_ensure_mjpython_or_warn() returns True on non-Darwin (Linux CI runner)."""
        import platform

        from surg_rl.editor._platform_guard import _ensure_mjpython_or_warn

        if platform.system() == "Darwin":
            pytest.skip("Test is non-Darwin-only; macOS handled by separate path")
        assert _ensure_mjpython_or_warn() is True

    def test_platform_guard_does_not_import_pyside6(self) -> None:
        """Importing the platform guard module does NOT trigger PySide6 import."""
        import surg_rl.editor._platform_guard  # noqa: F401

        assert "PySide6" not in sys.modules


class TestAppMain:
    """src/surg_rl/editor/app.py main() entrypoint gate behavior."""

    def test_app_module_imports_without_pyside6(self) -> None:
        """`import surg_rl.editor.app` succeeds on PySide6-free systems."""
        import surg_rl.editor.app  # noqa: F401

    def test_app_does_not_import_pyside6_at_module_level(self) -> None:
        """Importing app.py does NOT add PySide6 to sys.modules."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import surg_rl.editor.app; import sys; assert 'PySide6' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert result.returncode == 0, (
            f"app.py must not import PySide6 at module level. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_help_flag_exits_zero(self, flag: str) -> None:
        """`python -m surg_rl.editor.app --help` exits 0 + prints Usage:."""
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app", flag],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert (
            result.returncode == 0
        ), f"--help must exit 0; got {result.returncode}. stderr={result.stderr!r}"
        assert "Usage:" in result.stdout

    def test_no_args_exits_one_with_install_hint_when_pyside6_missing(self) -> None:
        """`python -m surg_rl.editor.app` exits 1 + prints install hint when PySide6 missing."""
        check = subprocess.run(
            [sys.executable, "-c", "import surg_rl.editor; print(surg_rl.editor.HAS_GUI)"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        if check.stdout.strip() == "True":
            pytest.skip("PySide6 is installed — install-hint path is unreachable")
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert (
            result.returncode == 1
        ), f"No-args must exit 1 when PySide6 missing; got {result.returncode}"
        assert "pip install" in result.stderr
        assert "surg-rl[gui]" in result.stderr

    def test_headless_flag_lists_demo_scenes(self) -> None:
        """`python -m surg_rl.editor.app --headless` exits 0 with a non-empty scene list.

        Gap 3 closure (UAT Test 6): the --headless branch MUST resolve both
        `scenes/` (at repo root) and `tests/fixtures/scenes/` directories via
        4-level path traversal (`parent.parent.parent.parent`), and MUST NOT
        print "(no demo scenes found)" when scene files exist.
        """
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app", "--headless"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert (
            result.returncode == 0
        ), f"--headless must exit 0; got {result.returncode}. stderr={result.stderr!r}"
        # Must report the "Available demo scenes" header.
        assert "Available demo scenes" in result.stdout, (
            f"--headless stdout must contain 'Available demo scenes' header; "
            f"got stdout={result.stdout!r}"
        )
        # Must NOT print the empty-list sentinel (the bug being fixed).
        assert "(no demo scenes found)" not in result.stdout, (
            f"--headless must list scenes, not print '(no demo scenes found)'; "
            f"got stdout={result.stdout!r}"
        )
        # Must include at least one .json filename line (scenes are listed).
        assert any(".json" in line for line in result.stdout.splitlines()), (
            f"--headless stdout must include at least one .json filename line; "
            f"got stdout={result.stdout!r}"
        )

    def test_headless_finds_repo_scenes_dir(self) -> None:
        """`--headless` lists at least one scene from `scenes/` at repo root.

        Gap 3 closure (UAT Test 6): `repo_scenes = Path(__file__).parent.parent.parent.parent / "scenes"`
        must reach the repo-root scenes/ directory (4 levels up from app.py,
        NOT 3 levels which lands on src/ with no scenes/ subdir).
        """
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app", "--headless"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert result.returncode == 0, f"--headless must exit 0; stderr={result.stderr!r}"
        # suturing_demo.json and simple_suturing.json both exist ONLY in scenes/
        # (not in tests/fixtures/scenes/), so they prove the repo-root scenes/
        # dir is being scanned — NOT just the fixtures dir.
        repo_only_filenames = ["suturing_demo.json", "simple_suturing.json", "needle_passing.json"]
        assert any(name in result.stdout for name in repo_only_filenames), (
            f"--headless must list at least one scene unique to scenes/ at repo "
            f"root (proves 4-level path fix, not just fixtures dir); expected one "
            f"of {repo_only_filenames}; got stdout={result.stdout!r}"
        )

    def test_headless_finds_fixtures_scenes_dir(self) -> None:
        """`--headless` lists at least one scene from `tests/fixtures/scenes/`.

        Gap 3 closure (UAT Test 6): the fixtures lookup must use a filesystem
        path (`Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "scenes"`),
        NOT `importlib.resources.files("tests.fixtures.scenes")` which fails
        because `tests/` is at repo root, not an importable package under src/.
        """
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.editor.app", "--headless"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert result.returncode == 0, f"--headless must exit 0; stderr={result.stderr!r}"
        # knot_tying.json exists in tests/fixtures/scenes/ (and also in scenes/).
        # suturing_difficulty_hard.json is unique to tests/fixtures/scenes/.
        # Assert the fixtures-specific one to prove the fixtures dir is scanned.
        assert "suturing_difficulty_hard.json" in result.stdout, (
            f"--headless must list suturing_difficulty_hard.json from "
            f"tests/fixtures/scenes/; got stdout={result.stdout!r}"
        )


class TestMjpythonNoReexec:
    """Gate 2 no longer re-execs under mjpython on macOS.

    Earlier builds re-execed under `mjpython` so MuJoCo's GL context would
    be on the Cocoa main thread. That breaks PySide6 because `mjpython` runs
    Python in a secondary thread, while Qt requires QApplication to live on
    the process main thread. The result was a dock icon with no window and an
    unresponsive app.

    The hardened Gate 2 now:
    1. Detects the platform/mjpython state for logging only.
    2. Never calls `os.execvp("mjpython", ...)`.
    3. Always falls through to Gate 3 so the Qt GUI runs under the current
       interpreter. The viewport catches MuJoCo render errors gracefully.

    These tests call `main()` directly with mocked values. A fake PySide6
    module is injected into sys.modules so Gate 3's import succeeds but
    QApplication raises SystemExit(0) — proving Gate 2 fell through to
    Gate 3 and did NOT re-exec.
    """

    @staticmethod
    def _fake_pyside6_qapp_exit() -> dict:
        """Build a sys.modules patch dict with a fake PySide6.QtWidgets that
        raises SystemExit(0) when QApplication() is instantiated.

        This lets Gate 3's `from PySide6.QtWidgets import QApplication` +
        `app = QApplication(sys.argv)` succeed in importing but exit cleanly
        at the QApplication() call — proving Gate 2 fell through (did NOT
        os.execvp) and execution continued to Gate 3.

        Also fakes PySide6.QtCore and surg_rl.editor.main_window so the
        Gate 3 `from surg_rl.editor.main_window import EditorWindow` import
        does not fail on the missing PySide6.QtCore submodule.
        """

        class _FakeQApp:
            def __init__(self, *_args, **_kwargs) -> None:
                raise SystemExit(0)

        class _FakeQtWidgets:
            QApplication = _FakeQApp

        class _FakeQtCore:
            QByteArray = type("QByteArray", (), {})
            QSettings = type("QSettings", (), {})

        class _FakePySide6:
            QtWidgets = _FakeQtWidgets
            QtCore = _FakeQtCore

        class _FakeEditorWindow:
            def __init__(self, *_args, **_kwargs) -> None:
                raise SystemExit(0)

        class _FakeMainWindowMod:
            EditorWindow = _FakeEditorWindow

        return {
            "PySide6": _FakePySide6,
            "PySide6.QtWidgets": _FakeQtWidgets,
            "PySide6.QtCore": _FakeQtCore,
            "surg_rl.editor.main_window": _FakeMainWindowMod,
        }

    def test_mjpython_never_reexecs_on_darwin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On macOS, main() never re-execs under mjpython (PySide6 safety)."""
        monkeypatch.setattr(sys, "argv", ["surg-rl-gui"])
        execvp_mock = MagicMock(side_effect=RuntimeError("os.execvp should NOT be called"))
        with (
            patch("platform.system", return_value="Darwin"),
            patch(
                "surg_rl.editor._platform_guard._is_running_under_mjpython",
                return_value=False,
            ),
            patch("os.execvp", execvp_mock),
            patch("surg_rl.editor.app.HAS_GUI", True),
            patch.dict(sys.modules, self._fake_pyside6_qapp_exit()),
        ):
            from surg_rl.editor.app import main

            with contextlib.suppress(SystemExit):
                main()  # Gate 3 fake QApplication -> SystemExit(0), expected
        # os.execvp must NOT be called on macOS now that re-exec is removed.
        assert (
            execvp_mock.call_count == 0
        ), f"os.execvp must NOT be called on macOS; call_count={execvp_mock.call_count}"

    def test_mjpython_no_reexec_even_if_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Even with mjpython on PATH, main() stays in the current interpreter.

        Regression: the old Gate 2 re-execed whenever `shutil.which('mjpython')`
        found the binary. That path is gone; availability must not trigger re-exec.
        """
        monkeypatch.setattr(sys, "argv", ["surg-rl-gui"])
        execvp_mock = MagicMock(side_effect=RuntimeError("os.execvp should NOT be called"))
        with (
            patch("platform.system", return_value="Darwin"),
            patch(
                "surg_rl.editor._platform_guard._is_running_under_mjpython",
                return_value=False,
            ),
            patch("shutil.which", return_value="/fake/mjpython"),
            patch("os.execvp", execvp_mock),
            patch("surg_rl.editor.app.HAS_GUI", True),
            patch.dict(sys.modules, self._fake_pyside6_qapp_exit()),
        ):
            from surg_rl.editor.app import main

            with contextlib.suppress(SystemExit):
                main()
        assert execvp_mock.call_count == 0, (
            f"os.execvp must NOT be called even when mjpython is available; "
            f"call_count={execvp_mock.call_count}"
        )

    def test_mjpython_no_reexec_skips_non_darwin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On non-Darwin platforms, the mjpython gate is a no-op."""
        monkeypatch.setattr(sys, "argv", ["surg-rl-gui"])
        execvp_mock = MagicMock(side_effect=RuntimeError("os.execvp should NOT be called"))
        with (
            patch("platform.system", return_value="Linux"),
            patch("os.execvp", execvp_mock),
            patch("surg_rl.editor.app.HAS_GUI", True),
            patch.dict(sys.modules, self._fake_pyside6_qapp_exit()),
        ):
            from surg_rl.editor.app import main

            with contextlib.suppress(SystemExit):
                main()  # Gate 3 fake QApplication -> SystemExit(0), expected
        # os.execvp must NOT have been called (non-Darwin).
        assert execvp_mock.call_count == 0, (
            f"os.execvp must NOT be called on non-Darwin; " f"call_count={execvp_mock.call_count}"
        )


class TestSurgRlCliIndependence:
    """The 14-subcommand `surg-rl` CLI must NOT import PySide6."""

    def test_surg_rl_help_exits_zero(self) -> None:
        """`surg-rl --help` exits 0 on a PySide6-free system."""
        result = subprocess.run(
            [sys.executable, "-m", "surg_rl.cli", "--help"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert result.returncode == 0, (
            f"surg-rl --help must exit 0; got {result.returncode}. " f"stderr={result.stderr!r}"
        )

    def test_surg_rl_help_does_not_import_pyside6(self) -> None:
        """`surg-rl --help` must NOT trigger PySide6 import (the install-hint must NOT appear)."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from surg_rl.cli import app; "
                "import typer.testing; r = typer.testing.CliRunner().invoke(app, ['--help']); "
                "print('HELP_OK'); print('exit_code=' + str(r.exit_code)); "
                "sys.exit(0 if r.exit_code == 0 and 'PySide6' not in sys.modules else 1)",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )
        assert result.returncode == 0, (
            f"surg-rl --help must NOT import PySide6. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "PySide6" not in sys.modules
