"""Regression tests for the tomllib compat shim (debug ci-failures-lint-pybullet C3).

The unguarded ``import tomllib`` pattern broke on Python 3.10 (``tomllib`` is
stdlib-only from 3.11+). ``surg_rl.utils.toml_compat`` exposes a unified
``tomllib`` module on every supported Python. These tests guard the shim so a
future refactor cannot silently reintroduce the unguarded import.
"""

from __future__ import annotations

import sys

import pytest

from surg_rl.utils import toml_compat


class TestTomlCompatShim:
    """The shim exposes a working tomllib on every Python 3.10+."""

    def test_tomllib_attribute_exposed(self) -> None:
        """`toml_compat.tomllib` is bound and importable."""
        assert hasattr(toml_compat, "tomllib")
        assert toml_compat.tomllib is not None

    def test_tomllib_has_loads_api(self) -> None:
        """The shimmed module exposes the `loads` callable (TOML string parse)."""
        assert callable(getattr(toml_compat.tomllib, "loads", None))

    def test_tomllib_has_load_api(self) -> None:
        """The shimmed module exposes the `load` callable (file-object parse)."""
        assert callable(getattr(toml_compat.tomllib, "load", None))

    def test_tomllib_parses_real_toml(self) -> None:
        """End-to-end: the shim parses a representative pyproject fragment."""
        data = toml_compat.tomllib.loads('[project]\nname = "surg-rl"\nversion = "0.1.0"\n')
        assert data["project"]["name"] == "surg-rl"
        assert data["project"]["version"] == "0.1.0"

    @pytest.mark.skipif(
        sys.version_info >= (3, 11),
        reason="tomli fallback only reachable on Python <3.11",
    )
    def test_tomli_is_the_fallback_on_python_310(self) -> None:
        """On Python <3.11 the shim must resolve to `tomli` (not stdlib tomllib)."""
        assert toml_compat.tomllib.__name__ == "tomli"

    @pytest.mark.skipif(
        sys.version_info < (3, 11),
        reason="stdlib tomllib only present on Python 3.11+",
    )
    def test_stdlib_tomllib_used_on_python_311_plus(self) -> None:
        """On Python 3.11+ the shim must resolve to stdlib `tomllib`."""
        assert toml_compat.tomllib.__name__ == "tomllib"
