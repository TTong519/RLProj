"""PySide6 scene editor package — scaffolding for Phase 33.

Phase 31 plan 04 ships the import-gated skeleton: `LazyImport` for PySide6
symbols + a `HAS_GUI` sentinel. Phase 33 builds the actual `QMainWindow`,
schema walker, viewport, tree/form editors, LLM panel, and undo/redo on
top of this scaffolding.

Optional dependency: PySide6 6.8+ (~120 MB wheel).
Install: pip install "surg-rl[gui]"

Usage:

.. code-block:: python

    from surg_rl.editor import HAS_GUI, QtWidgets

    if HAS_GUI:
        app = QtWidgets.QApplication(sys.argv)
        # ... Phase 33 wires MainWindow ...
    else:
        # Print install hint, exit 1
        ...

The package imports cleanly even when PySide6 is NOT installed — `HAS_GUI`
is `False` in that case and the `LazyImport` symbols raise `ImportError`
with the install-hint message on first attribute access. This guarantees
that the existing 14-subcommand `surg-rl` CLI never triggers PySide6
import (Pitfall P10 + P6).
"""

from surg_rl.utils.lazy_imports import LazyImport

# Lazy imports — defer PySide6 load to first attribute access.
# Mirrors src/surg_rl/dreamer/__init__.py:12 and
# src/surg_rl/benchmark/__init__.py:9-12 (the modern LazyImport pattern).
QtWidgets = LazyImport("PySide6.QtWidgets", "gui")
QtCore = LazyImport("PySide6.QtCore", "gui")
QtGui = LazyImport("PySide6.QtGui", "gui")

# Sentinel — True iff PySide6 is importable. `.available` does NOT raise;
# it returns False if the import would fail (see lazy_imports.py:28-38).
HAS_GUI: bool = QtWidgets.available

__all__ = [
    "HAS_GUI",
    "QtWidgets",
    "QtCore",
    "QtGui",
]
