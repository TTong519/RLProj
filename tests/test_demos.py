"""Regression tests for the demos/ suite (Phase 32 — Demo Suite Polish).

Covers:
- 3 subprocess-based demo smoke tests (DEMO-04): each demo runs
  `--headless --steps 0` and asserts exit 0 + expected banner substring.
- 1 narration template compliance test: the NARRATION_TEMPLATE.md exists
  and has the 5 stage headings in order (DEMO-05 enforcement).
- 1 knot_tying fixture byte-identical test: the fixture copy in
  tests/fixtures/scenes/ matches the source in scenes/.
- 1 needle_passing dual-arm test: the scene has a MultiAgentConfig with
  2 distinct ArmConfig entries (DEMO-03 prerequisite validation).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from surg_rl.scene_definition import load_scene


REPO_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = REPO_ROOT / "demos"
SCENES_DIR = REPO_ROOT / "scenes"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "scenes"
TEMPLATE_PATH = DEMOS_DIR / "NARRATION_TEMPLATE.md"

SUBPROCESS_TIMEOUT_S = 60


def _run_demo_subprocess(demo_name: str) -> subprocess.CompletedProcess:
    """Run a demo as a subprocess with --headless --steps 0.

    Args:
        demo_name: Name of the demo file without extension (e.g., 'suturing_demo').

    Returns:
        CompletedProcess with captured stdout and stderr.
    """
    demo_path = DEMOS_DIR / f"{demo_name}.py"
    assert demo_path.exists(), f"Demo file not found: {demo_path}"
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(REPO_ROOT / "src"))
    return subprocess.run(
        [sys.executable, str(demo_path), "--headless", "--steps", "0"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
    )


class TestDemoRegression:
    """Subprocess-based regression tests for the 3 demos (DEMO-04).

    Each test spawns the demo as a child process, runs `--headless --steps 0`
    (banner-only mode), and asserts:
    1. Exit code is 0 (no crash, no exception).
    2. Combined stdout+stderr contains the [Setup] marker (the 5-stage
       narration printed via Python `print()` goes to stdout; the Rich
       banner printed via `print_banner` goes to stderr).
    """

    @staticmethod
    def _combined_output(result: subprocess.CompletedProcess) -> str:
        return result.stdout + "\n" + result.stderr

    def test_suturing_demo_runs(self) -> None:
        """suturing_demo.py --headless --steps 0 exits 0 and prints [Setup]."""
        result = _run_demo_subprocess("suturing_demo")
        assert result.returncode == 0, (
            f"suturing_demo exited {result.returncode}\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        combined = self._combined_output(result)
        assert "[Setup]" in combined, (
            f"suturing_demo output missing [Setup] marker\n"
            f"COMBINED: {combined[:1000]}"
        )

    def test_knot_tying_demo_runs(self) -> None:
        """knot_tying_demo.py --headless --steps 0 exits 0 and prints [Setup]."""
        result = _run_demo_subprocess("knot_tying_demo")
        assert result.returncode == 0, (
            f"knot_tying_demo exited {result.returncode}\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        combined = self._combined_output(result)
        assert "[Setup]" in combined, (
            f"knot_tying_demo output missing [Setup] marker\n"
            f"COMBINED: {combined[:1000]}"
        )

    def test_needle_passing_demo_runs(self) -> None:
        """needle_passing_demo.py --headless --steps 0 exits 0 and prints [Setup]."""
        result = _run_demo_subprocess("needle_passing_demo")
        assert result.returncode == 0, (
            f"needle_passing_demo exited {result.returncode}\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        combined = self._combined_output(result)
        assert "[Setup]" in combined, (
            f"needle_passing_demo output missing [Setup] marker\n"
            f"COMBINED: {combined[:1000]}"
        )


class TestNarrationTemplate:
    """Template compliance test (DEMO-05 enforcement).

    Asserts that demos/NARRATION_TEMPLATE.md exists and documents the 5-stage
    structure (Setup / Action / Critical Moment / Outcome / Takeaway) in order.
    If the template is missing or the stage headings are reordered, this
    test fails — catching template drift early.
    """

    def test_template_has_5_stage_headings(self) -> None:
        """NARRATION_TEMPLATE.md exists with all 5 stage headings in order."""
        assert TEMPLATE_PATH.exists(), (
            f"NARRATION_TEMPLATE.md not found at {TEMPLATE_PATH}"
        )
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        expected_headings = [
            "## Setup",
            "## Action",
            "## Critical Moment",
            "## Outcome",
            "## Takeaway",
        ]
        last_pos = -1
        for heading in expected_headings:
            pos = content.find(heading)
            assert pos > last_pos, (
                f"Heading {heading!r} not found in order. "
                f"Last position: {last_pos}, content: {content[:500]!r}"
            )
            last_pos = pos


class TestKnotTyingFixture:
    """Fixture copy validation (DEMO-02 prereq).

    Asserts that tests/fixtures/scenes/knot_tying.json is a byte-identical
    copy of scenes/knot_tying.json. If either file changes, this test
    fails — catching accidental divergence.
    """

    def test_knot_tying_fixture_matches_source(self) -> None:
        """tests/fixtures/scenes/knot_tying.json is byte-identical to scenes/knot_tying.json."""
        source = SCENES_DIR / "knot_tying.json"
        fixture = FIXTURES_DIR / "knot_tying.json"
        assert source.exists(), f"Source not found: {source}"
        assert fixture.exists(), f"Fixture not found: {fixture}"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
        assert source_hash == fixture_hash, (
            f"Fixture diverged from source.\n"
            f"  Source SHA256: {source_hash}\n"
            f"  Fixture SHA256: {fixture_hash}"
        )


class TestNeedlePassingFixture:
    """Dual-arm scene validation (DEMO-03 prereq).

    Asserts that scenes/needle_passing.json has a MultiAgentConfig with 2
    distinct ArmConfig entries (surgeon + assistant) — the dual-arm
    structure that the demo narrates.
    """

    def test_needle_passing_scene_has_multi_agent_config(self) -> None:
        """scenes/needle_passing.json has a MultiAgentConfig with 2 distinct arms."""
        scene_path = SCENES_DIR / "needle_passing.json"
        assert scene_path.exists(), f"Scene not found: {scene_path}"
        scene = load_scene(scene_path)
        assert scene.multi_agent is not None, (
            "Expected multi_agent field on SceneDefinition"
        )
        assert len(scene.multi_agent.arm_configs) >= 2, (
            f"Expected at least 2 arm_configs, got {len(scene.multi_agent.arm_configs)}"
        )
        roles = {arm.role.value for arm in scene.multi_agent.arm_configs}
        assert "surgeon" in roles, (
            f"Expected 'surgeon' role in arm_configs, got {roles}"
        )
        assert "assistant" in roles, (
            f"Expected 'assistant' role in arm_configs, got {roles}"
        )