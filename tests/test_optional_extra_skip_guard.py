"""Regression guard for the optional-physics-dep skip hook (conftest).

The macOS CI job does not install the `physics` extra (pybullet has no macOS
arm64 wheel; its sdist fails under modern Xcode). tests/conftest.py defines
`pytest_collection_modifyitems`, which skips any test whose node id contains
the physics-backend name when that backend is not importable. This test
verifies that hook's logic directly so the guard does not silently regress.

The test file and function names deliberately avoid the backend name so the
hook does not skip this guard itself. See debug session
ci-failures-lint-pybullet.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import tests.conftest as conftest_mod

_BACKEND_NAME = "pybullet"


class _FakeItem:
    """Minimal stand-in for a pytest Item exposing nodeid + add_marker."""

    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid
        self.markers: list[pytest.Mark] = []

    def add_marker(self, marker: pytest.Mark) -> None:
        self.markers.append(marker)


@pytest.fixture
def restore_flag():
    """Restore _PYBULLET_AVAILABLE after each test so monkeypatching is local."""
    original = conftest_mod._PYBULLET_AVAILABLE
    yield
    conftest_mod._PYBULLET_AVAILABLE = original


def test_physics_tests_skipped_when_backend_absent(restore_flag):
    """When the physics backend is unavailable, its named items get a skip marker."""
    conftest_mod._PYBULLET_AVAILABLE = False

    items = [
        _FakeItem("tests/test_simulators.py::TestPyBulletSimulator::test_init"),
        _FakeItem("tests/test_simulators.py::TestPyBulletBugs::test_pybullet_reset_resets_joints"),
        _FakeItem("tests/test_simulators.py::TestMuJoCoSimulator::test_init"),
        _FakeItem("tests/test_rl_environment.py::TestSurgicalEnvDefaults::test_default"),
    ]

    conftest_mod.pytest_collection_modifyitems(config=MagicMock(), items=items)

    skipped = [it for it in items if it.markers]
    skipped_ids = {it.nodeid for it in skipped}
    # Both backend-named items are skipped ...
    assert any("TestPyBulletSimulator" in n for n in skipped_ids)
    assert any("test_pybullet_reset_resets_joints" in n for n in skipped_ids)
    # ... and the marker is a skip naming the backend.
    marker = skipped[0].markers[0]
    assert marker.mark.name == "skip"
    assert _BACKEND_NAME in marker.mark.kwargs["reason"]
    # Non-backend items are NOT skipped.
    not_skipped = [it for it in items if not it.markers]
    assert len(not_skipped) == 2
    assert all(_BACKEND_NAME not in it.nodeid.lower() for it in not_skipped)


def test_physics_tests_run_when_backend_present(restore_flag):
    """When the physics backend is available, no items are skipped by the hook."""
    conftest_mod._PYBULLET_AVAILABLE = True

    items = [
        _FakeItem("tests/test_simulators.py::TestPyBulletSimulator::test_init"),
        _FakeItem("tests/test_simulators.py::TestPyBulletBugs::test_pybullet_reset_resets_joints"),
    ]

    conftest_mod.pytest_collection_modifyitems(config=MagicMock(), items=items)

    assert all(not it.markers for it in items), "backend items must NOT be skipped when installed"
