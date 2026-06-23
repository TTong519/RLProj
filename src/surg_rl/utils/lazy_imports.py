"""Lazy import helper — defers ImportError to first attribute access.

Replaces the legacy HAS_* module-level boolean pattern (see ros2/__init__.py).
Used by v0.4.0 optional dependency packages: assets, benchmark, marl, dreamer.
"""

from importlib import import_module
from typing import Any


class LazyImport:
    """Defers module import until first attribute access.

    On first access, attempts ``importlib.import_module(module_name)``.
    - Success: returns the requested attribute, caches for future access
    - Failure: raises ``ImportError`` with a ``pip install surg-rl[{package_name}]`` hint

    The ``.available`` property checks importability without raising — returns
    ``True`` if the module imports successfully, ``False`` otherwise.
    """

    def __init__(self, module_name: str, package_name: str) -> None:
        self._module_name = module_name
        self._package_name = package_name
        self._module: Any = None
        self._import_attempted: bool = False

    @property
    def available(self) -> bool:
        """Check whether the underlying module is importable.

        Does NOT raise — returns ``True`` if the module appears installable,
        ``False`` otherwise. Uses ``importlib.util.find_spec`` on the top-level
        package to avoid actually importing the module (which matters for heavy
        optional deps like PySide6).
        """
        if self._import_attempted:
            return self._module is not None
        from importlib.util import find_spec
        top_level = self._module_name.split(".")[0]
        try:
            return find_spec(top_level) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    def _ensure_import(self) -> None:
        """Attempt the import if not already done. Raises ImportError on failure."""
        if self._import_attempted:
            if self._module is None:
                raise ImportError(self._error_message())
            return
        self._import_attempted = True
        try:
            self._module = import_module(self._module_name)
        except ImportError:
            raise ImportError(self._error_message()) from None

    def _error_message(self) -> str:
        return (
            f"{self._module_name} is not installed. "
            f"Install with: pip install surg-rl[{self._package_name}]"
        )

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the underlying module."""
        self._ensure_import()
        assert self._module is not None
        return getattr(self._module, name)

    def __repr__(self) -> str:
        status = "available" if self.available else "not installed"
        return f"LazyImport({self._module_name!r}, status={status})"
