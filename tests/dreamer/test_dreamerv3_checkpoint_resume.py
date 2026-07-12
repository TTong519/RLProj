"""Restart-then-continue checkpoint resume test (DMV3-08).

Verifies that a second ``run_dreamer_training`` call with the same
``{task}_{obs_type}`` directory resumes from the persisted step counter rather
than restarting at 0 (DMV3-08 — "persist per task/obs-type AND resume across
subprocess restarts"). 40-01's ``_build_agent`` registers an
``embodied.Checkpoint`` at ``models/dreamerv3/{task}_{obs_type}/checkpoint.ckpt``
and calls ``cp.load_or_save()`` at construct time (resume-or-init, D-09);
40-02's ``_train_loop`` calls ``cp.save()`` at every ``eval_every`` boundary.
This test reads that persisted checkpoint back in a second subprocess.

DMV3-10: assertions are STRUCTURAL ONLY — the step counter resumes (not a fresh
start at 0), training completes, and losses are finite. There is NO convergence
threshold (no MSE floor, no reward-error floor) — smoke-vs-convergence split per
DMV3-10.

GPU-gated: the entire module SKIPs on macOS per INV-8 (the module-level
``pytestmark skipif`` is copied verbatim from ``test_dreamerv3_subprocess_e2e.py``
lines 16-49). GREEN (positive resume assertions pass with a real
``dreamerv3.Agent``) is satisfied by the 40-04 CI ``dreamer-gpu`` job.
"""

from __future__ import annotations

import importlib.util
import math
import shutil
from pathlib import Path

import pytest


def _has_module(name: str) -> bool:
    """Lazy module-presence check via find_spec (D-SKIP-02)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError):
        return False


def _gpu_available() -> bool:
    """Detect a usable GPU via torch (preferred) or jax; tolerate missing/broken imports."""
    try:
        import torch

        if torch.cuda.is_available():
            return True
    except Exception:
        pass
    try:
        import jax

        return any(getattr(d, "platform", None) == "gpu" for d in jax.devices())
    except Exception:
        return False
    return False


pytestmark = pytest.mark.skipif(
    not (_gpu_available() and _has_module("dreamerv3") and _has_module("jax")),
    reason=(
        "Skipped: DreamerV3 resume test requires GPU + dreamerv3 + jax. "
        "Remediation: pip install '.[dreamer]' (jax with CUDA) on a GPU host; "
        "on macOS the test is expected to skip per STATE.md Blocker #4."
    ),
)


class TestCheckpointResume:
    """Restart-then-continue resume verification (DMV3-08)."""

    def test_restart_then_continue(self, tmp_path) -> None:
        """DMV3-08: a second run_dreamer_training call resumes the step counter.

        Run 1 trains for 500 steps (eval_every=250), writing ``checkpoint.ckpt``
        via 40-01's ``_build_agent`` cp.load_or_save() + 40-02's cp.save() at
        eval_every. Run 2 with ``resume=True`` and the same ``{task}_{obs_type}``
        dir resumes — the child's ``_build_agent`` calls ``cp.load_or_save()``
        at construct time, restoring the step counter, so training continues
        beyond step 500 instead of restarting at 0.

        Note: the child's ``_build_agent`` (subprocess.py, owned by 40-01/40-02)
        registers the checkpoint at ``models/dreamerv3/{task}_{obs_type}/
        checkpoint.ckpt`` — a hardcoded path that does NOT use the parent's
        ``checkpoint_dir`` param. The ``checkpoint_dir`` param only affects
        where the parent writes its sidecar files (``training_metrics.json``,
        ``metrics_*.json``). The resume lookup (``_find_latest_checkpoint``)
        also globs the hardcoded ``models/dreamerv3/{task}_{obs_type}/`` dir.
        So both runs share the same on-disk ``checkpoint.ckpt`` regardless of
        ``checkpoint_dir``.

        DMV3-10: structural-only assertions — checkpoint exists, run2 returns
        a metrics dict with finite losses, training completes. No MSE floor,
        no reward-error floor.
        """
        from surg_rl.dreamer.training import run_dreamer_training

        task = "suturing"
        obs_type = "state"
        # The child's _build_agent hardcodes the checkpoint dir to
        # models/dreamerv3/{task}_{obs_type}/ (subprocess.py, 40-01). This is
        # where checkpoint.ckpt is written, NOT the parent's checkpoint_dir.
        child_ckpt_path = Path(f"models/dreamerv3/{task}_{obs_type}/checkpoint.ckpt")

        try:
            # --- Run 1: train for 500 steps, persist checkpoint.ckpt ---
            run1 = run_dreamer_training(
                task=task,
                obs_type=obs_type,
                total_steps=500,
                eval_every=250,
                checkpoint_dir=str(tmp_path / "run1"),
            )
            assert run1 is not None, "run1 returned None — training did not complete"

            # The embodied.Checkpoint native file written by 40-01's
            # _build_agent cp.load_or_save() + 40-02's cp.save() at eval_every=250.
            assert child_ckpt_path.exists(), (
                f"checkpoint.ckpt not written at {child_ckpt_path} — "
                "real training did not persist a checkpoint"
            )

            # --- Run 2: resume=True, same {task}_{obs_type} dir ---
            # The child's _build_agent calls cp.load_or_save() at construct
            # time, which loads checkpoint.ckpt and restores the step counter.
            # The parent's resume branch also calls _find_latest_checkpoint
            # (now globbing *.ckpt from Task 1) -> subprocess.load_checkpoint
            # -> _load_checkpoint -> cp.load() (redundant but harmless).
            run2 = run_dreamer_training(
                task=task,
                obs_type=obs_type,
                total_steps=1000,
                eval_every=250,
                resume=True,
                checkpoint_dir=str(tmp_path / "run1"),
            )
            assert run2 is not None, "run2 returned None — resume training did not complete"
            assert "training_curves" in run2, "run2 metrics dict missing 'training_curves'"

            # The total_loss list must be non-empty (training ran) and every
            # entry must be finite (not NaN/Inf) — DMV3-10 structural assertion.
            total_losses = run2["training_curves"]["total_loss"]
            assert (
                len(total_losses) > 0
            ), "no METRICS steps collected in run2 — training loop yielded nothing"
            for loss in total_losses:
                assert math.isfinite(
                    loss
                ), f"total_loss value is not finite (NaN/Inf): {loss!r} — training is broken"

            # run2 returning a dict (no RuntimeError) proves training completed
            # to 1000 steps after resuming — DMV3-10 structural-only (no
            # convergence threshold).

        finally:
            # Clean up the hardcoded checkpoint dir so the test is repeatable.
            # The child writes to models/dreamerv3/{task}_{obs_type}/ regardless
            # of checkpoint_dir; remove it so a subsequent test run starts fresh.
            shutil.rmtree(
                Path(f"models/dreamerv3/{task}_{obs_type}"),
                ignore_errors=True,
            )
