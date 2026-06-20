"""Console-script entrypoint for `surg-rl-gui`.

This module exposes the `main()` function that pip registers as a
console-script entry point in `pyproject.toml [project.scripts]`:

    surg-rl-gui = "surg_rl.editor.app:main"

The function performs 3 gate checks BEFORE attempting to launch the
Qt main window (Phase 33 wires the actual QApplication + MainWindow):

1. **PySide6 install gate** — checks `surg_rl.editor.HAS_GUI`. If False
   (PySide6 not installed), prints the install hint to stderr and exits
   non-zero. Verified by `surg-rl-gui --help` on a PySide6-free system.
2. **macOS mjpython gate** — on macOS, calls
   `surg_rl.editor._platform_guard._ensure_mjpython_or_warn()`. If the
   process is not running under `mjpython`, the helper prints a banner
   and returns False; `main()` exits non-zero.
3. **Phase 33 MainWindow gate** — the `# Phase 33 wires MainWindow here`
   placeholder is where Phase 33 inserts the QApplication + MainWindow
   + app.exec() sequence. This plan does NOT ship the QMainWindow —
   it ships only the gates.

Usage:

.. code-block:: bash

    $ pip install ".[gui]"
    $ surg-rl-gui --help
    $ surg-rl-gui                  # launch the editor (Phase 33)
    $ surg-rl-gui path/scene.json  # open a scene at startup (Phase 33)
    $ surg-rl-gui --headless       # print available scenes and exit

Pitfalls addressed (per .planning/research/PITFALLS-v0.5.0.md):
- P1 (mjpython re-exec): macOS check via `_ensure_mjpython_or_warn()`.
- P6 (optional-dep regression): PySide6 only imported via HAS_GUI gate.
- P9 ([gui] extra bloat): no PySide6 import unless `surg-rl-gui` is run.
- P10 (GUI as Typer subcommand): this is a SEPARATE console script.

Reference: .planning/research/PITFALLS-v0.5.0.md:325-339, 438
"""

import sys

from surg_rl.editor import HAS_GUI


def main() -> None:
    """Console-script entrypoint for `surg-rl-gui`.

    Gate order (short-circuits on first failure):
    1. PySide6 installed? (`HAS_GUI`)
    2. macOS + mjpython? (`_ensure_mjpython_or_warn()`)
    3. Phase 33 wires MainWindow here (placeholder in this plan).

    Exits with code 1 on install/mjpython gate failure.
    Exits with code 0 on `--headless` mode.
    Phase 33 will replace the placeholder with `sys.exit(app.exec())`.
    """
    # Handle --help / --headless BEFORE the PySide6 gate so users can
    # run `surg-rl-gui --help` on a PySide6-free system to see the
    # install hint without crashing on a missing dep.
    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "surg-rl-gui — PySide6 scene editor (Phase 33)\n"
            "\n"
            "Usage:\n"
            "  surg-rl-gui                   Launch the editor\n"
            "  surg-rl-gui PATH/scene.json   Open a scene at startup\n"
            "  surg-rl-gui --headless        List available scenes and exit\n"
            "  surg-rl-gui --help            Show this help and exit\n"
            "\n"
            'Install with: pip install "surg-rl[gui]"\n'
        )
        sys.exit(0)

    if "--headless" in sys.argv:
        # Phase 33 lists scenes from tests/fixtures/scenes/ + scenes/.
        # Both directories live at repo root, NOT under src/. app.py lives at
        # src/surg_rl/editor/app.py, so 4 parent levels reach the repo root:
        #   __file__  -> src/surg_rl/editor/app.py
        #   parent    -> src/surg_rl/editor/
        #   parent^2  -> src/surg_rl/
        #   parent^3  -> src/                  (WRONG — no scenes/ here)
        #   parent^4  -> <repo root>           (CORRECT — scenes/ lives here)
        from pathlib import Path as _Path

        fixtures_dir = (
            _Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "scenes"
        )
        repo_scenes = _Path(__file__).parent.parent.parent.parent / "scenes"
        candidate_dirs = []
        if fixtures_dir.is_dir():
            candidate_dirs.append(fixtures_dir)
        if repo_scenes.is_dir():
            candidate_dirs.append(repo_scenes)
        print("Available demo scenes:")
        found = False
        for d in candidate_dirs:
            for f in sorted(d.glob("*.json")):
                print(f"  {f}")
                found = True
        if not found:
            print("  (no demo scenes found)")
        sys.exit(0)

    # Gate 1: PySide6 installed?
    if not HAS_GUI:
        sys.stderr.write(
            "surg-rl GUI requires PySide6.\n" 'Install with: pip install "surg-rl[gui]"\n'
        )
        sys.exit(1)

    # Gate 2: macOS mjpython re-exec (hardened against crash + infinite loop).
    # On macOS, MuJoCo's GL context requires running under `mjpython` (the
    # MuJoCo-bundled Python interpreter). If the current process is NOT
    # already under mjpython, we re-exec under it. Two guards prevent the
    # two failure modes identified in UAT Gap 2:
    #
    #   1. `shutil.which("mjpython")` check before `os.execvp` — prevents
    #      FileNotFoundError crash when mjpython is not installed on macOS
    #      (the user gets a warning and the editor continues without the 3D
    #      viewport rather than crashing).
    #   2. `_SURG_RL_GUI_REEXECED=1` env var loop guard — set before
    #      execvp, checked at the top of Gate 2. If the re-exec'd process
    #      fails to detect mjpython (e.g. _is_running_under_mjpython()
    #      returns False after re-exec), the env var prevents an infinite
    #      re-exec loop by skipping the re-exec and falling through with a
    #      warning.
    #
    # On non-macOS platforms, Gate 2 is a no-op (the `platform.system() ==
    # "Darwin"` check short-circuits).
    import os
    import platform
    import shutil

    from surg_rl.editor._platform_guard import _is_running_under_mjpython

    if platform.system() == "Darwin" and not _is_running_under_mjpython():
        # Loop guard: if we already re-execed, don't try again (prevents
        # infinite re-exec loop if _is_running_under_mjpython() fails to
        # detect mjpython after re-exec).
        already_reexeced = os.environ.get("_SURG_RL_GUI_REEXECED") == "1"

        if not already_reexeced and shutil.which("mjpython") is not None:
            # mjpython is installed — re-exec under it for MuJoCo GL context.
            print(
                "surg-rl-gui: not running under mjpython; re-execing under "
                "mjpython for MuJoCo GL context...",
                file=sys.stderr,
            )
            os.environ["_SURG_RL_GUI_REEXECED"] = "1"
            os.execvp("mjpython", ["mjpython", "-m", "surg_rl.editor.app"] + sys.argv[1:])
        else:
            # mjpython not installed OR already re-execed — continue with a
            # warning. The viewport will catch GL-context errors gracefully
            # (Plan 33-07 hardens the viewport against render failures).
            reason = (
                "mjpython not found on PATH"
                if shutil.which("mjpython") is None
                else "re-exec did not detect mjpython"
            )
            print(
                f"surg-rl-gui: warning — {reason}. MuJoCo 3D viewport may not "
                "initialize. Install mjpython (bundled with `pip install "
                "mujoco`) for full 3D support. Continuing without re-exec...",
                file=sys.stderr,
            )

    # Gate 3: Phase 33 wires MainWindow here.
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from surg_rl.editor.main_window import EditorWindow

    app = QApplication(sys.argv)
    window = EditorWindow(
        scene_path=Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "--headless" else None
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

