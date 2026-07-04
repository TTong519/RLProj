"""tomllib compatibility shim.

``tomllib`` is stdlib-only on Python 3.11+. On Python 3.10 the ``tomli``
package (declared as a core dependency via ``tomli>=2.0.0; python_version < '3.11'``
in ``pyproject.toml``) exposes the identical API. This shim unifies the two so
callers can ``from surg_rl.utils.toml_compat import tomllib`` on every supported
Python without guarding ``import tomllib`` themselves — the unguarded form is a
real bug on Python 3.10 (``ModuleNotFoundError: No module named 'tomllib'``).

See debug session ``ci-failures-lint-pybullet`` (Class C3).
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):  # pragma: no cover - exercised on Python 3.11+
    import tomllib  # noqa: F401
else:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]  # noqa: F401

__all__ = ["tomllib"]
