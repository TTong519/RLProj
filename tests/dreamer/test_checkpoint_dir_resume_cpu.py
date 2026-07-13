"""CPU-runnable checkpoint_dir resume wiring test (DMV3-08 gap closure, D-03).

This module deliberately does NOT carry the module-level ``pytestmark skipif``
that the GPU-gated sibling ``test_dreamerv3_checkpoint_resume.py`` uses
(D-03 — deliberate contrast). It stubs ``DreamerSubprocess`` via
``unittest.mock`` so no spawn / JAX / GPU occurs and the test runs on macOS +
CI. The GPU-gated sibling verifies the runtime resume; this CPU stub verifies
the *parent-path wiring* — that ``run_dreamer_training(resume=True,
checkpoint_dir=<custom>)`` actually calls ``subprocess.load_checkpoint`` with
the custom-dir ``.ckpt`` path (D-01).

Covers:
- D-01: ``_find_latest_checkpoint(task, obs_type, checkpoint_dir)`` returns the
  latest ``.ckpt`` from a custom dir; returns ``None`` when the custom dir is
  empty (falls through to the default dir which does not exist under tmp).
- D-03: ``run_dreamer_training(resume=True, checkpoint_dir=<custom>)`` calls
  ``subprocess.load_checkpoint`` with the custom-dir ``.ckpt`` path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_find_latest_checkpoint_custom_dir(tmp_path: Path) -> None:
    """D-01: _find_latest_checkpoint honors a custom checkpoint_dir.

    A custom dir with a ``checkpoint.ckpt`` returns that path; an empty custom
    dir returns ``None`` (the default ``models/dreamerv3/{task}_{obs_type}/``
    dir does not exist under tmp_path, so the fallback yields no checkpoints).
    """
    from surg_rl.dreamer.training import _find_latest_checkpoint

    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "checkpoint.ckpt").write_bytes(b"x")
    assert _find_latest_checkpoint("suturing", "state", str(custom)) == str(
        custom / "checkpoint.ckpt"
    )

    empty = tmp_path / "empty"
    empty.mkdir()
    assert _find_latest_checkpoint("suturing", "state", str(empty)) is None


def test_resume_custom_checkpoint_dir_calls_load_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-03: run_dreamer_training(resume=True, checkpoint_dir=<custom>) calls
    subprocess.load_checkpoint with the custom-dir .ckpt path.

    Stubs ``DreamerSubprocess`` (no spawn/JAX), ``check_spike_status`` (landmine
    A1 — run_dreamer_training raises if a spike failed), and the scene/env
    factories (the test's concern is the checkpoint_dir resume wiring, not
    scene/env creation). With ``resume=True`` + a custom ``checkpoint_dir``
    holding a ``checkpoint.ckpt``, the parent resume path must call
    ``subprocess.load_checkpoint(str(ckpt_dir / "checkpoint.ckpt"))``.
    """
    ckpt_dir = tmp_path / "custom_run"
    ckpt_dir.mkdir()
    (ckpt_dir / "checkpoint.ckpt").write_bytes(b"fake")

    fake_sp = MagicMock()
    fake_sp.train.return_value = iter([])  # no METRICS -> TRAIN_COMPLETE immediately
    # evaluate() return value is serialized into training_metrics.json at the end
    # of run_dreamer_training; return a JSON-serializable dict so the test reaches
    # the load_checkpoint assertion rather than erroring at json.dump.
    fake_sp.evaluate.return_value = {}

    monkeypatch.setattr(
        "surg_rl.dreamer.training.DreamerSubprocess",
        lambda config: fake_sp,
    )
    monkeypatch.setattr(
        "surg_rl.dreamer.training.check_spike_status",
        lambda: None,
    )
    monkeypatch.setattr(
        "surg_rl.dreamer.training._create_scene_for_task",
        lambda task, obs_type, pixel_resolution: MagicMock(),
    )
    monkeypatch.setattr(
        "surg_rl.dreamer.training._create_env",
        lambda scene: MagicMock(),
    )

    from surg_rl.dreamer.training import run_dreamer_training

    run_dreamer_training(
        task="suturing",
        obs_type="state",
        total_steps=100,
        resume=True,
        checkpoint_dir=str(ckpt_dir),
    )

    fake_sp.load_checkpoint.assert_called_once_with(str(ckpt_dir / "checkpoint.ckpt"))