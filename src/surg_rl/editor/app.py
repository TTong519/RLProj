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
from surg_rl.editor._platform_guard import _ensure_mjpython_or_warn


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
        # Phase 33 will replace this with a real listing of scenes
        # from `surg_rl/scene_definition/SceneLoader`.
        print("Phase 33 will list available demo scenes here.")
        print("(Currently in scaffolding mode — see Phase 31 plan 04.)")
        sys.exit(0)

    # Gate 1: PySide6 installed?
    if not HAS_GUI:
        sys.stderr.write(
            "surg-rl GUI requires PySide6.\n" 'Install with: pip install "surg-rl[gui]"\n'
        )
        sys.exit(1)

    # Gate 2: macOS mjpython re-exec (replaces warn-and-exit).
    # On macOS without mjpython, transparently re-exec the editor under mjpython
    # so MuJoCo's GL context can initialize. On macOS-with-mjpython and on
    # non-macOS this is a no-op.
    import platform
    from surg_rl.editor._platform_guard import _is_running_under_mjpython
    if platform.system() == "Darwin" and not _is_running_under_mjpython():
        import os
        print(
            "surg-rl-gui: not running under mjpython; re-execing under mjpython for "
            "MuJoCo GL context...",
            file=sys.stderr,
        )
        os.execvp("mjpython", ["mjpython", "-m", "surg_rl.editor.app"] + sys.argv[1:])

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

