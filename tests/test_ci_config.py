"""MACOS-01: validate CI workflow config contains macOS runner and mjpython."""

from __future__ import annotations

from pathlib import Path

import yaml

CI_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _load_ci() -> dict:
    """Parse the CI workflow YAML."""
    with open(CI_WORKFLOW) as f:
        return yaml.safe_load(f)


def test_ci_has_macos_runner():
    """MACOS-01: CI matrix includes macos-latest runner."""
    ci = _load_ci()
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]["include"]
    os_values = [entry["os"] for entry in matrix]
    assert "macos-latest" in os_values, f"No macos-latest in CI matrix. OS: {os_values}"


def test_macos_runner_python_311():
    """MACOS-01: macOS runner uses Python 3.11."""
    ci = _load_ci()
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]["include"]
    for entry in matrix:
        if entry["os"] == "macos-latest":
            assert (
                entry["python-version"] == "3.11"
            ), f"Expected 3.11, got {entry['python-version']}"
            break
    else:
        pytest.fail("macos-latest entry not found in matrix")


def test_ci_has_mjpython_step():
    """MACOS-03: CI includes mjpython path resolution step."""
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert any(
        "mjpython" in name for name in step_names
    ), f"No mjpython step found. Steps: {step_names}"


def test_ci_ignores_ros2_on_macos():
    """MACOS-04: macOS CI pytest step ignores ROS2 test files."""
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    for step in steps:
        if step.get("name") == "Test with mjpython (macOS)":
            run_cmd = step.get("run", "")
            assert (
                "--ignore=tests/test_ros2_" in run_cmd
            ), f"ROS2 ignore flag missing from macOS test step: {run_cmd[:200]}"
            break
    else:
        pytest.fail("Test with mjpython (macOS) step not found")


def test_ci_fail_fast_disabled():
    """MACOS-01: fail-fast is disabled so macOS doesn't block ubuntu."""
    ci = _load_ci()
    strategy = ci["jobs"]["test"]["strategy"]
    assert (
        strategy.get("fail-fast") is False
    ), f"fail-fast must be false, got {strategy.get('fail-fast')}"
