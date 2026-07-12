"""Real-subprocess E2E smoke test for Phase 26 fixes; gated on (GPU + dreamerv3 + jax) per CONTEXT.md D-SKIP-01..03.

DMV3-E2E-01..05 v1 requirements. On macOS local (no GPU + no dreamerv3 + no jax) the entire module
SKIPS with a single descriptive reason that includes the remediation `pip install '.[dreamer]'`.
On a CI host with GPU + dreamerv3 + jax installed, the tests run and exercise the real
`_JsonStdout` pipe round-trip and `DREAMER_COLOR` constant end-to-end.

DMV3-09 sentinel flip (Phase 40): the two negative stub-reality assertions from Phase 30 are
inverted to positive real-agent completion assertions. The module-level `pytestmark skipif`
below STAYS (GPU + dreamerv3 + jax gate per INV-8) — on macOS the flipped tests SKIP, not
ERROR. DMV3-10: the flipped assertions are STRUCTURAL ONLY (finite + non-explosive loss,
checkpoint exists, training completes) — there is NO convergence threshold (no MSE
floor, no reward-error floor) — smoke-vs-convergence split per DMV3-10.
"""

from __future__ import annotations

import importlib.util
import math

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
        "Skipped: DreamerV3 E2E requires GPU + dreamerv3 + jax. "
        "Remediation: pip install '.[dreamer]' (jax with CUDA) on a GPU host; "
        "on macOS the test is expected to skip per STATE.md Blocker #4."
    ),
)


class TestDreamerV3SubprocessE2E:
    """End-to-end smoke test for the DreamerV3 real-subprocess path."""

    def test_e2e_dreamer_color_constant(self) -> None:
        """DMV3-E2E-03: DREAMER_COLOR survives a full import round-trip at #FF8C00."""
        from surg_rl.benchmark.plots import DREAMER_COLOR

        assert DREAMER_COLOR == "#FF8C00"

    def test_e2e_run_dreamer_training_real_agent(self, tmp_path) -> None:
        """DMV3-09 sentinel flip (negative→positive): real DreamerV3 agent trains end-to-end.

        Phase 30 asserted the stub-era ``RuntimeError("Agent not configured")``; Phase 40
        inverts that to a positive real-agent completion assertion. DMV3-10: assertions are
        STRUCTURAL ONLY — the loss must be finite (not NaN/Inf) and non-explosive (last <=
        first * tolerance), training must complete, and at least one METRICS step must be
        collected. There is NO convergence threshold (no MSE floor, no reward-error
        floor) — smoke-vs-convergence split per 40-CONTEXT.md D-10 / 40-RESEARCH.md.
        """
        from surg_rl.dreamer.training import run_dreamer_training

        metrics = run_dreamer_training(
            task="suturing",
            obs_type="state",
            total_steps=1000,
            eval_every=500,
            checkpoint_dir=str(tmp_path / "checkpoints"),
        )

        # Training completed and returned a metrics dict with the expected top-level shape.
        assert metrics is not None, "run_dreamer_training returned None — training did not complete"
        assert "training_curves" in metrics, "metrics dict missing 'training_curves' key"
        assert "eval_results" in metrics, "metrics dict missing 'eval_results' key"

        # At least one METRICS step was collected over the pipe (non-empty total_loss list).
        total_losses = metrics["training_curves"]["total_loss"]
        assert len(total_losses) > 0, "no METRICS steps collected — training loop yielded nothing"

        # DMV3-10 structural assertion 1: every total_loss value is finite (not NaN, not Inf).
        for loss in total_losses:
            assert math.isfinite(
                loss
            ), f"total_loss value is not finite (NaN/Inf): {loss!r} — training is broken, not 'hard'"

        # DMV3-10 structural assertion 2: loss is non-explosive (last <= first * tolerance).
        # tolerance=2.0 is a NON-convergence structural bound — it only rejects divergence
        # (loss blowing up by >2x), NOT a threshold that the policy has learned anything.
        tolerance = 2.0
        first_loss = float(total_losses[0])
        last_loss = float(total_losses[-1])
        # Guard against a zero first_loss causing a misleading 0*2.0 bound; only apply the
        # non-explosive check when the first loss is meaningful (>0).
        if first_loss > 0.0:
            assert last_loss <= first_loss * tolerance, (
                f"total_loss is explosive: first={first_loss}, last={last_loss}, "
                f"ratio={last_loss / first_loss:.2f} > tolerance={tolerance} — training diverged"
            )

    def test_e2e_checkpoint_files_written(self, tmp_path) -> None:
        """DMV3-09 sentinel flip (negative→positive): checkpoint + metrics files ARE written.

        Phase 30 asserted that ``final.pt`` and ``training_metrics.json`` were NOT written
        (stub reality — the run raised before reaching the file-write branches). Phase 40
        inverts that: a real training run MUST write at least one checkpoint
        (``checkpoint.ckpt`` — the embodied.Checkpoint native format from 40-01's
        ``_build_agent``; OR ``final.pt`` — training.py line 333's legacy path, retired by
        40-03) and the ``training_metrics.json`` summary (training.py line 345). DMV3-10:
        structural-only (files exist), NOT a convergence threshold.
        """
        from surg_rl.dreamer.training import run_dreamer_training

        ckpt_dir = tmp_path / "checkpoints"
        run_dreamer_training(
            task="suturing",
            obs_type="state",
            total_steps=1000,
            eval_every=500,
            checkpoint_dir=str(ckpt_dir),
        )

        # At least one checkpoint file exists. The .ckpt path is the embodied.Checkpoint
        # native format (40-01's _build_agent registers cp at ckpt_dir/checkpoint.ckpt);
        # the .pt path is training.py line 333's final_checkpoint, retired by 40-03.
        # Accepting either keeps the assertion robust across the 40-02/40-03 boundary.
        ckpt_exists = (ckpt_dir / "checkpoint.ckpt").exists()
        final_pt_exists = (ckpt_dir / "final.pt").exists()
        assert (
            ckpt_exists or final_pt_exists
        ), "neither checkpoint.ckpt nor final.pt written — real training did not persist a checkpoint"

        # training.py line 345 writes the metrics summary on completion.
        assert (
            ckpt_dir / "training_metrics.json"
        ).exists(), (
            "training_metrics.json not written — training did not reach the completion branch"
        )
