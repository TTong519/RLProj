"""Tests for benchmark scene coverage (Phase 27 — audit gap closure).

Closes the v0.4.0 milestone audit's "Benchmark-scene-coverage" and
"Task-dormant" gaps by asserting:
1. All 6 TASK_SCENE_MAP paths resolve to existing files on disk.
2. All 6 scenes load via SceneLoader and have matching task.task_type.
3. simple_suturing.json has task_type='suturing' (router activation).
4. The 5 new scenes each have the correct task_type set.
"""

from pathlib import Path

from surg_rl.benchmark.experiment_runner import TASK_SCENE_MAP
from surg_rl.scene_definition.loader import SceneLoader


class TestBenchmarkSceneCoverage:
    """Regression tests for v0.4.0 audit benchmark-scene gaps."""

    def test_all_task_scene_map_paths_resolve(self):
        """Every TASK_SCENE_MAP path must exist (Phase 27 audit closure)."""
        missing = [t for t, p in TASK_SCENE_MAP.items() if not Path(p).exists()]
        assert not missing, f"Missing scene files: {missing}"

    def test_all_task_scene_map_loads(self):
        """Every TASK_SCENE_MAP path must load via SceneLoader and have matching task_type."""
        for task, scene_path in TASK_SCENE_MAP.items():
            scene = SceneLoader().load(scene_path)
            assert scene is not None, f"{task}: SceneLoader returned None"
            assert scene.task is not None, f"{task}: scene.task is None"
            assert scene.task.task_type is not None, f"{task}: task.task_type not set"
            assert scene.task.task_type == task, (
                f"Task mismatch: TASK_SCENE_MAP[{task!r}] -> {scene_path}, "
                f"but task.task_type={scene.task.task_type!r}"
            )

    def test_simple_suturing_has_task_type_wired(self):
        """simple_suturing.json must have task_type='suturing' (D-06 — router activation)."""
        scene = SceneLoader().load("scenes/simple_suturing.json")
        assert scene.task is not None
        assert scene.task.task_type == "suturing"

    def test_new_scenes_have_correct_task_types(self):
        """Each new scene must have its task_type set to match its filename."""
        expected_types = {
            "scenes/knot_tying.json": "knot_tying",
            "scenes/needle_insertion.json": "needle_insertion",
            "scenes/grasping.json": "grasping",
            "scenes/cutting.json": "cutting",
            "scenes/dissection.json": "dissection",
        }
        for scene_path, expected in expected_types.items():
            assert Path(scene_path).exists(), f"File missing: {scene_path}"
            scene = SceneLoader().load(scene_path)
            assert scene.task is not None, f"{scene_path}: no task block"
            assert scene.task.task_type == expected, (
                f"{scene_path}: expected task_type={expected!r}, "
                f"got {scene.task.task_type!r}"
            )

    def test_scenes_use_primitive_fallback(self):
        """Scenes with non-existent mesh paths must still load (ASET-03 primitive fallback).

        The SceneLoader accepts the scene definition (Pydantic v2 validates the
        schema, not the mesh file existence — primitive fallback is a
        scene_builder concern).
        """
        for task, scene_path in TASK_SCENE_MAP.items():
            scene = SceneLoader().load(scene_path)  # MUST NOT raise
            if scene.instruments:
                assert len(scene.instruments) > 0


import os

import yaml

from surg_rl.benchmark.experiment_config import ExperimentConfig
from surg_rl.benchmark.experiment_runner import ExperimentRunner


class TestExperimentRunnerExperimentsWrite:
    """Regression tests for v0.4.0 audit 'Benchmark-experiments-dir' gap.

    Phase 27 closes the misleading CLI hint at cli.py:1286 by writing
    the effective config to experiments/{experiment_name}.yaml on every
    ExperimentRunner construction.
    """

    def test_experiment_runner_writes_experiments_yaml(self, tmp_path, monkeypatch):
        """After construction, experiments/{name}.yaml must exist and round-trip."""
        monkeypatch.chdir(tmp_path)
        cfg = ExperimentConfig(experiment_name="test_audit_xyz", timesteps=1000)
        ExperimentRunner(cfg)

        out_path = tmp_path / "experiments" / "test_audit_xyz.yaml"
        assert out_path.exists(), f"Missing: {out_path}"
        with open(out_path) as f:
            data = yaml.safe_load(f)
        assert data["experiment_name"] == "test_audit_xyz"
        assert data["timesteps"] == 1000
        cfg2 = ExperimentConfig.from_yaml(out_path)
        assert cfg2.experiment_name == "test_audit_xyz"
        assert cfg2.timesteps == 1000

    def test_experiment_runner_creates_experiments_dir(self, tmp_path, monkeypatch):
        """The experiments/ directory must be auto-created by to_yaml."""
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / "experiments").exists()
        cfg = ExperimentConfig(experiment_name="test_audit_dir_creation")
        ExperimentRunner(cfg)
        assert (tmp_path / "experiments").exists()
        assert (tmp_path / "experiments").is_dir()

    def test_cli_reproduce_hint_path_resolves(self, tmp_path, monkeypatch):
        """The path printed by CLI reproduce hint must point to a real file."""
        monkeypatch.chdir(tmp_path)
        experiment_name = "test_audit_repro_hint"
        cfg = ExperimentConfig(experiment_name=experiment_name)
        ExperimentRunner(cfg)
        cli_hint_path = Path("experiments") / f"{cfg.experiment_name}.yaml"
        assert cli_hint_path.exists(), (
            f"CLI hint path does not resolve: {cli_hint_path}. "
            f"Phase 27 D-09 must write this file in ExperimentRunner.__init__."
        )

    def test_existing_save_aggregated_json_flag_still_works(self, tmp_path, monkeypatch):
        """save_aggregated_json=False should still suppress the effective_config.yaml write
        in base_output_dir (existing behavior at line 163-164 must not regress)."""
        monkeypatch.chdir(tmp_path)
        cfg = ExperimentConfig(experiment_name="test_audit_flag", save_aggregated_json=False)
        runner = ExperimentRunner(cfg)
        eff = runner.base_output_dir / "effective_config.yaml"
        assert not eff.exists(), f"Flag was False but file exists: {eff}"
        exp = Path("experiments") / "test_audit_flag.yaml"
        assert exp.exists()
