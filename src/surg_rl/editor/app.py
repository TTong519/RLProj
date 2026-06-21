"""Console-script entrypoint for `surg-rl-gui`.

This module exposes the `main()` function that pip registers as a
console-script entry point in `pyproject.toml [project.scripts]`:

    surg-rl-gui = "surg_rl.editor.app:main"

The function performs 3 gate checks BEFORE attempting to launch the
Qt main window (Phase 33 wires the actual QApplication + MainWindow):

1. **PySide6 install gate** — checks `surg_rl.editor.HAS_GUI`. If False
   (PySide6 not installed), prints the install hint to stderr and exits
   non-zero. Verified by `surg-rl-gui --help` on a PySide6-free system.
2. **macOS detection gate** — logs whether the process is running under
   the stock interpreter or `mjpython`. The Qt GUI no longer re-execs under
   `mjpython` because `mjpython` runs Python on a secondary thread and
   breaks PySide6's main-thread requirement.
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
- P1 (mjpython check): detected but no re-exec for Qt GUI; `_is_running_under_mjpython()` still used by `start_viewer()`.
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
    2. macOS detection (informational logging only; no re-exec)
    3. Phase 33 wires MainWindow here.

    Exits with code 1 when PySide6 is not installed.
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

        fixtures_dir = _Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "scenes"
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

    # Gate 2: macOS detection (informational only — no re-exec).
    #
    # Earlier builds re-execed under `mjpython` so MuJoCo's GL context would
    # be on the Cocoa main thread. That works for MuJoCo's passive viewer
    # but breaks PySide6: mjpython runs the Python interpreter in a secondary
    # thread, while Qt requires QApplication to live on the process main
    # thread. The result was a dock icon with no window and an unresponsive
    # app. The GUI therefore stays in the current interpreter on macOS.
    #
    # We still call `_ensure_mjpython_or_warn()` so macOS users without
    # mjpython see the warning banner, but we never re-exec or exit here.
    # The 3D viewport uses MuJoCo's offscreen `Renderer`; render errors are
    # caught and displayed in the canvas instead of hanging.
    from surg_rl.editor._platform_guard import _ensure_mjpython_or_warn

    _ensure_mjpython_or_warn()  # Returns False on macOS without mjpython; warning already printed.

    # Gate 3: Phase 33 wires MainWindow here.
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from surg_rl.editor.main_window import EditorWindow

    app = QApplication(sys.argv)
    window = EditorWindow(
        scene_path=(
            Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "--headless" else None
        )
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
