"""Tests for LazyImport — defers ImportError to first attribute access."""

import pytest

from surg_rl.utils.lazy_imports import LazyImport


class TestLazyImportConstruction:
    """RED: LazyImport should construct without importing the underlying module."""

    def test_constructs_without_importing(self):
        """LazyImport("trimesh", "assets") constructs without importing trimesh."""
        li = LazyImport("trimesh", "assets")
        assert li._import_attempted is False


class TestLazyImportAvailable:
    """RED: .available property returns bool without raising."""

    def test_available_false_when_package_missing(self):
        """available returns False when package not installed."""
        li = LazyImport("nonexistent_pkg_xyz_123", "test")
        assert li.available is False

    def test_available_true_when_package_installed(self):
        """available returns True when package IS installed (e.g., 'os' stdlib)."""
        li = LazyImport("os.path", "test")
        assert li.available is True


class TestLazyImportGetattr:
    """RED: __getattr__ forwards to underlying module or raises ImportError."""

    def test_getattr_raises_import_error_with_pip_hint(self):
        """__getattr__ on a missing module raises ImportError with pip install hint."""
        li = LazyImport("nonexistent_pkg_xyz_123", "test")
        with pytest.raises(ImportError) as exc_info:
            li.some_attr
        msg = str(exc_info.value)
        assert "pip install" in msg, f"Missing pip hint: {msg}"
        assert "[test]" in msg, f"Missing package name in hint: {msg}"

    def test_getattr_returns_module_attribute(self):
        """__getattr__ on an available module returns the actual attribute."""
        li = LazyImport("os.path", "test")
        result = li.join
        assert result is not None
        import os.path

        assert result is os.path.join

    def test_getattr_caches_after_success(self):
        """After successful __getattr__, subsequent access returns cached result."""
        li = LazyImport("os.path", "test")
        # First access triggers the import
        first = li.join
        assert li._import_attempted is True
        # Second access should use cache (no re-import)
        second = li.join
        assert first is second


class TestLazyImportRepr:
    """RED: __repr__ includes status information."""

    def test_repr_includes_status(self):
        """__repr__ returns a string with status info."""
        li = LazyImport("os.path", "test")
        r = repr(li)
        assert "LazyImport" in r
        assert "available" in r
