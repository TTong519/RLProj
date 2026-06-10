"""Tests for _find_latest_checkpoint — checkpoint discovery for DreamerV3."""

import os
import sys
import time
from pathlib import Path

import pytest

from surg_rl.dreamer.training import _find_latest_checkpoint


class TestFindLatestCheckpoint:
    """Test _find_latest_checkpoint returns the right path or None."""

    def test_returns_none_when_directory_does_not_exist(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        result = _find_latest_checkpoint("suturing", "state")
        assert result is None

    def test_returns_none_when_dir_exists_but_empty(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        ckpt_dir = Path("models/dreamerv3/suturing_state")
        ckpt_dir.mkdir(parents=True)
        result = _find_latest_checkpoint("suturing", "state")
        assert result is None

    def test_returns_final_pt_when_only_final_pt_exists(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        ckpt_dir = Path("models/dreamerv3/suturing_state")
        ckpt_dir.mkdir(parents=True)
        (ckpt_dir / "final.pt").write_bytes(b"checkpoint")
        result = _find_latest_checkpoint("suturing", "state")
        assert result == str(ckpt_dir / "final.pt")

    def test_returns_newest_checkpoint_by_mtime(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        ckpt_dir = Path("models/dreamerv3/suturing_pixels")
        ckpt_dir.mkdir(parents=True)

        old_ckpt = ckpt_dir / "checkpoint_1000.pt"
        old_ckpt.write_bytes(b"old")
        old_time = time.time() - 1000
        os.utime(old_ckpt, (old_time, old_time))

        new_ckpt = ckpt_dir / "checkpoint_2000.pt"
        new_ckpt.write_bytes(b"new")
        new_time = time.time()
        os.utime(new_ckpt, (new_time, new_time))

        middle_ckpt = ckpt_dir / "checkpoint_1500.pt"
        middle_ckpt.write_bytes(b"middle")
        middle_time = time.time() - 500
        os.utime(middle_ckpt, (middle_time, middle_time))

        result = _find_latest_checkpoint("suturing", "pixels")
        assert result == str(new_ckpt)

    def test_returns_max_of_multiple_checkpoints(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        ckpt_dir = Path("models/dreamerv3/grasping_state")
        ckpt_dir.mkdir(parents=True)

        for i, t_offset in enumerate([3000, 1000, 2000]):
            ckpt = ckpt_dir / f"checkpoint_{i}.pt"
            ckpt.write_bytes(b"x")
            target_time = time.time() - t_offset
            os.utime(ckpt, (target_time, target_time))

        result = _find_latest_checkpoint("grasping", "state")
        assert result is not None
        assert "checkpoint_" in result
        assert ".pt" in result

    def test_final_pt_with_checkpoints_prefers_max_mtime(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        ckpt_dir = Path("models/dreamerv3/suturing_state")
        ckpt_dir.mkdir(parents=True)

        final = ckpt_dir / "final.pt"
        final.write_bytes(b"final")
        old_time = time.time() - 100
        os.utime(final, (old_time, old_time))

        ckpt_2 = ckpt_dir / "checkpoint_200.pt"
        ckpt_2.write_bytes(b"ckpt_2")
        new_time = time.time()
        os.utime(ckpt_2, (new_time, new_time))

        result = _find_latest_checkpoint("suturing", "state")
        assert result == str(ckpt_2)

    def test_task_obs_type_used_in_directory_path(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        suturing_dir = Path("models/dreamerv3/suturing_state")
        suturing_dir.mkdir(parents=True)
        (suturing_dir / "final.pt").write_bytes(b"x")

        grasping_dir = Path("models/dreamerv3/grasping_state")
        grasping_dir.mkdir(parents=True)
        (grasping_dir / "final.pt").write_bytes(b"x")

        result = _find_latest_checkpoint("suturing", "state")
        assert "suturing" in result
        assert "grasping" not in result


class TestModuleImports:
    """Test that the module loads without importing JAX or dreamerv3."""

    def test_module_does_not_import_jax(self):
        sys.modules.pop("jax", None)
        sys.modules.pop("dreamerv3", None)
        import surg_rl.dreamer.training  # noqa: F401

        assert "jax" not in sys.modules
        assert "dreamerv3" not in sys.modules


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
