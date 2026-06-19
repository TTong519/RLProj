"""macOS mjpython detection + re-exec warn helper for the GUI editor.

On macOS, MuJoCo's GL context requires running under `mjpython` (the
MuJoCo-bundled Python interpreter). Running the GUI under stock Python 3
on macOS crashes with "OpenGL context is not current" errors.

This module exposes:

- `_is_running_under_mjpython() -> bool` — 3-signal detection (env var
  `MJPYTHON_BIN`, basename `mjpython` in `sys.executable`, `mjpython` in
  `sys.argv[0]`). Extracted from the inline block at
  `src/surg_rl/simulators/mujoco_simulator.py:1294-1298` so the editor
  AND `start_viewer()` can share the same detection logic.
- `_ensure_mjpython_or_warn() -> bool` — on macOS without mjpython,
  prints a clear warning banner (mirrors the ros2_bridge macOS guard
  pattern at `src/surg_rl/cli.py:858-865`). Caller decides whether to
  re-exec via `os.execvp("mjpython", ...)` or exit.

Phase 31 plan 04 ships these helpers; Phase 33 wires `app.main()` to
call `_ensure_mjpython_or_warn()` and `os.execvp("mjpython", ...)`
on macOS. Phase 33 also refactors `mujoco_simulator.py:start_viewer()`
to call `_is_running_under_mjpython()` instead of the inline block.

Reference: .planning/research/PITFALLS-v0.5.0.md:38-91 (P1 mitigation)
"""

import os
import platform
import re
import sys
from typing import Final

# Authoritative signal: mjpython sets this env var before execve'ing
# the real Python binary. Source: src/surg_rl/simulators/mujoco_simulator.py:1295.
_MJPYTHON_ENV_VAR: Final[str] = "MJPYTHON_BIN"

# Banner printed to stderr when on macOS without mjpython.
# Mirrors the ros2_bridge macOS guard pattern at src/surg_rl/cli.py:859-864.
_MJPYTHON_WARN_BANNER: Final[str] = (
    "\n[bold yellow]surg-rl GUI: macOS detected but not running under mjpython.[/bold yellow]\n"
    "  MuJoCo's GL context requires the mjpython interpreter on macOS.\n"
    "  Install mjpython (bundled with `pip install mujoco`) and re-run:\n"
    "\n"
    "    mjpython -m surg_rl.editor.app        # if installed as a package\n"
    '    mjpython -m pip install -e ".[gui]"  # dev install\n'
    "\n"
    "  Continuing under stock Python may crash on first GL render.\n"
)


def _is_running_under_mjpython() -> bool:
    """Return True iff the current process is running under `mjpython`.

    Uses 3 signals (in priority order):
    1. `MJPYTHON_BIN` env var is set (authoritative — mjpython sets this
       before execve'ing the real Python binary).
    2. `os.path.basename(sys.executable)` contains `mjpython` (fallback
       for systems where the env var was scrubbed).
    3. `sys.argv[0]` contains `mjpython` if `sys.argv` is non-empty
       (last-resort fallback for unusual launch contexts).

    Returns:
        True if running under mjpython; False otherwise.

    Note:
        Extracted verbatim from
        `src/surg_rl/simulators/mujoco_simulator.py:1294-1298` so the
        editor AND `start_viewer()` share the same detection logic.
        Phase 33 will refactor `start_viewer()` to call this helper.
    """
    if _MJPYTHON_ENV_VAR in os.environ:
        return True
    if "mjpython" in os.path.basename(sys.executable):
        return True
    return bool(sys.argv and "mjpython" in sys.argv[0])


def _ensure_mjpython_or_warn() -> bool:
    """On macOS without mjpython, print a warning banner; otherwise pass.

    Returns:
        True if running on a platform where the check passes (non-macOS,
        or macOS with mjpython detected). False if on macOS without
        mjpython (the warning banner has been printed to stderr).

    The caller decides whether to `os.execvp("mjpython", ...)` or to
    exit with a non-zero code. Phase 33's `app.main()` will use:

    .. code-block:: python

        if not _ensure_mjpython_or_warn():
            sys.exit(1)
            # OR: os.execvp("mjpython", ["mjpython", "-m", "surg_rl.editor.app"] + sys.argv)

    On non-macOS platforms, this helper is a no-op (returns True) —
    the mjpython check is macOS-specific. This mirrors the ros2_bridge
    pattern at `src/surg_rl/cli.py:858` (which is also macOS-only).
    """
    if platform.system() != "Darwin":
        return True  # Non-macOS — no check needed.
    if _is_running_under_mjpython():
        return True  # macOS + mjpython — OK.
    # macOS without mjpython — print the banner.
    # Use Rich markup if available; fall back to plain text if not.
    try:
        from rich.console import Console

        console = Console(stderr=True)
        console.print(_MJPYTHON_WARN_BANNER)
    except ImportError:
        # Rich not available — strip markup tags and print plain.
        plain = re.sub(r"\[/?[a-z ]+\]", "", _MJPYTHON_WARN_BANNER)
        print(plain, file=sys.stderr)
    return False
