"""Real-subprocess E2E smoke test for Phase 26 fixes; gated on (GPU + dreamerv3 + jax) per CONTEXT.md D-SKIP-01..03.

DMV3-E2E-01..05 v1 requirements. On macOS local (no GPU + no dreamerv3 + no jax) the entire module
SKIPS with a single descriptive reason that includes the remediation `pip install '.[dreamer]'`.
On a CI host with GPU + dreamerv3 + jax installed, the tests run and exercise the real
`_JsonStdout` pipe round-trip and `DREAMER_COLOR` constant end-to-end.
"""

from __future__ import annotations

import importlib.util

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

    def test_e2e_run_dreamer_training_against_stub(self, tmp_path) -> None:
        """DMV3-E2E-01/02: full run hits the stub's ERROR branch via the _JsonStdout pipe round-trip.

        With the Phase 24 `_build_agent` stub returning None, the subprocess emits
        ``{"type": "ERROR", "error": "Agent not configured"}`` and the parent raises
        ``RuntimeError("Training error: Agent not configured")``. This documents the current
        stub state; the test will START FAILING when real dreamerv3 is integrated — at that
        point it must be flipped to assert positive completion.
        """
        from surg_rl.dreamer.training import run_dreamer_training

        with pytest.raises(RuntimeError, match="Agent not configured"):
            run_dreamer_training(
                task="suturing",
                obs_type="state",
                total_steps=1000,
                eval_every=500,
                checkpoint_dir=str(tmp_path / "checkpoints"),
            )

    def test_e2e_checkpoint_files_not_written_in_stub_state(self, tmp_path) -> None:
        """DMV3-E2E-05: against the current stub, no checkpoint files are written.

        The run raises before reaching the final-checkpoint / metrics-write branches in
        ``training.py``. This documents the current state and signals (via failure) when
        real dreamerv3 is integrated and positive assertions should replace the negative ones.
        """
        from surg_rl.dreamer.training import run_dreamer_training

        ckpt_dir = tmp_path / "checkpoints"
        with pytest.raises(RuntimeError, match="Agent not configured"):
            run_dreamer_training(
                task="suturing",
                obs_type="state",
                total_steps=1000,
                eval_every=500,
                checkpoint_dir=str(ckpt_dir),
            )
        assert not (
            ckpt_dir / "final.pt"
        ).exists(), "final.pt written — stub reality has changed; flip this test to assert positive"
        assert not (
            ckpt_dir / "training_metrics.json"
        ).exists(), "training_metrics.json written — stub reality has changed"
