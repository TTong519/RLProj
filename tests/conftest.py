"""Shared pytest fixtures and utilities."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from surg_rl.scene_definition import SceneLoader

# PyBullet is an optional dependency (no macOS arm64 wheel). Tests whose node id
# contains "pybullet" (test name or class name) are skipped when pybullet is not
# importable, rather than erroring at runtime inside PyBulletSimulator methods.
# This keeps the macOS CI job (which installs only mujoco, not pybullet) green
# while leaving the full pybullet suite running on Linux where pybullet is
# installed via the `physics` extra. See debug session ci-failures-lint-pybullet.
_PYBULLET_AVAILABLE = importlib.util.find_spec("pybullet") is not None


def pytest_collection_modifyitems(config, items):
    """Skip pybullet-named tests when pybullet is not installed."""
    if _PYBULLET_AVAILABLE:
        return
    skip_pybullet = pytest.mark.skip(reason="pybullet not installed (surg-rl[physics] extra)")
    for item in items:
        if "pybullet" in item.nodeid.lower():
            item.add_marker(skip_pybullet)


@pytest.fixture(autouse=True)
def _reap_editor_sim_runtimes(request):
    """Stop + join any leaked editor sim runtime (QThread + render loop) after
    every test.

    EditorWindow.__init__ starts a SimStepWorker QThread + a RenderPollLoop
    self-rescheduling singleShot chain. Tests that construct EditorWindow
    WITHOUT calling close() leak both: the singleShot chain holds the loop →
    the loop's simulator_ref lambda holds the EditorWindow, so the window is
    never unreachable and a weakref.finalize safety net never fires. The
    leaked thread + render-poll then run until interpreter shutdown →
    ``QThread: Destroyed while thread is still running`` (SIGABRT) or a
    pybullet teardown segfault (Phase 42 regression). The module-level
    registry in sim_step_worker + this reaper is the reliable fix: no sim
    runtime outlives a test. Lazy import (cached after first use) keeps
    non-editor tests cheap; the registry is empty for them so reap is a
    no-op. Subprocess CLI-independence tests check their own sys.modules, so
    importing PySide6 in the main pytest process is safe.
    """
    yield
    try:  # noqa: SIM105 — broad guard: PySide6 missing / import error → no-op
        from surg_rl.editor.sim_step_worker import (
            _ACTIVE_SIM_RUNTIMES,
            reap_all_sim_runtimes,
        )
    except Exception:  # noqa: BLE001
        return
    if _ACTIVE_SIM_RUNTIMES:
        reap_all_sim_runtimes()
        # The reaper called close() (full teardown: thread joined, sim closed,
        # render-poll stopped). But the render-poll's 33 ms singleShot is the
        # window's last external ref, and it is not READY yet, so a plain
        # processEvents returns without firing it. QTest.qWait SPINS the event
        # loop for 50 ms (> 33 ms), so the singleShot fires, early-returns
        # (stop() set _running=False), and drops its bound-method ref — only
        # then is the EditorWindow QObject graph unreachable. gc.collect then
        # collects the fully-torn-down graph in this controlled context
        # (shiboken deletion is safe: thread finished, sim closed) instead of
        # letting it leak to a later mock-driven cyclic GC that segfaulted
        # traversing a stale wrapper (the Phase 42 test_stops_cleanly crash).
        try:  # noqa: SIM105 — best-effort event drain
            from PySide6.QtTest import QTest

            QTest.qWait(50)
        except Exception:  # noqa: BLE001
            pass
        import gc

        gc.collect()


# Ensure src/ is on the path for pytest collection
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def cli_runner():
    """Fixture to run CLI commands via subprocess with correct PYTHONPATH."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")

    def _run(*args, check: bool = False) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "surg_rl.cli", *args]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, check=check)

    return _run


@pytest.fixture
def cli_env():
    """Return a copy of os.environ with PYTHONPATH set for CLI subprocesses."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")
    return env


@pytest.fixture
def minimal_scene():
    """Load the minimal scene from scenes/minimal_scene.json."""
    loader = SceneLoader()
    scene_path = Path(__file__).parent.parent / "scenes" / "minimal_scene.json"
    return loader.load(scene_path)


@pytest.fixture
def suturing_scene():
    """Load the suturing scene from scenes/simple_suturing.json."""
    loader = SceneLoader()
    scene_path = Path(__file__).parent.parent / "scenes" / "simple_suturing.json"
    return loader.load(scene_path)


@pytest.fixture
def tetgen_cube_mesh(tmp_path):
    """Fixture: tetgen .node and .ele files for a small tetrahedralized cube."""
    node_path = tmp_path / "cube.1.node"
    ele_path = tmp_path / "cube.1.ele"
    node_path.write_text(
        "9  3  0  0\n"
        "1  0.0 0.0 0.0\n"
        "2  1.0 0.0 0.0\n"
        "3  1.0 1.0 0.0\n"
        "4  0.0 1.0 0.0\n"
        "5  0.0 0.0 1.0\n"
        "6  1.0 0.0 1.0\n"
        "7  1.0 1.0 1.0\n"
        "8  0.0 1.0 1.0\n"
        "9  0.5 0.5 0.5\n"
    )
    ele_path.write_text(
        "12  4  0\n"
        "1  1 2 3 9\n"
        "2  1 3 4 9\n"
        "3  1 2 6 9\n"
        "4  1 6 5 9\n"
        "5  1 5 8 9\n"
        "6  1 8 4 9\n"
        "7  2 3 7 9\n"
        "8  2 7 6 9\n"
        "9  3 4 8 9\n"
        "10 3 8 7 9\n"
        "11 5 6 7 9\n"
        "12 5 7 8 9\n"
    )
    return node_path, ele_path
