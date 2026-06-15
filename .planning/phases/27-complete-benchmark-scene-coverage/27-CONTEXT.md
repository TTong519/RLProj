# Phase 27: Complete Benchmark Scene Coverage — Context

**Gathered:** 2026-06-10
**Status:** Ready for planning
**Source:** v0.4.0 milestone audit (`v0.4.0-MILESTONE-AUDIT.md`) — three benchmark-scene gaps extracted from the audit's "Benchmark-scene-coverage" / "Task-dormant" / "Benchmark-experiments-dir" entries. Follows the same gap-closure pattern as Phases 25 and 26.

<domain>
## Phase Boundary

Close the three benchmark-scene gaps from the v0.4.0 milestone audit so `surg-rl benchmark --task {grasping,cutting,knot_tying,needle_insertion,dissection}` runs end-to-end (no scene-load crash), the TaskRewardRouter pipeline activates on real scenes (no longer dormant), and the "Reproduce with: surg-rl benchmark --config experiments/{name}.yaml" hint printed at the end of a benchmark run is actually true. No new functionality, no benchmark architecture changes — only narrow scene-file additions + a one-line CLI save-on-run + the task_type field on the canonical suturing scene.

</domain>

<decisions>
## Implementation Decisions

### Scene file completeness (BENCH-01 prerequisite)
- **D-01:** Create 5 new scene JSON files that complete the `TASK_SCENE_MAP` lookup in `src/surg_rl/benchmark/experiment_runner.py:40-47`:
  - `scenes/knot_tying.json`
  - `scenes/needle_insertion.json`
  - `scenes/grasping.json`
  - `scenes/cutting.json`
  - `scenes/dissection.json`
  Each MUST validate against `SceneDefinition` (Pydantic v2) on `SceneLoader.load()` and MUST set the `task.task_type` field to the matching `Literal` enum value from `TaskConfig.task_type` (`src/surg_rl/scene_definition/schema.py:1084-1090`).
- **D-02:** Each new scene MUST use the same overall structure as `scenes/simple_suturing.json` (which is the working reference): `metadata` + `physics` + `environment` (lights/cameras/ground_plane) + `robots[]` + `tissues[]` + `instruments[]` + `task` (with `task_type` + `name` + `objectives[]` + `constraints[]` + `reward_shaping{}` + `max_episode_length` + `time_limit`) + `domain_randomization` + `simulator`. The simulator MUST be `"mujoco"` (the canonical reference backend) to match Phase 23's `effective_backends` default expansion.
- **D-03:** The geometry for tissues in the 5 new scenes MAY use `box` / `sphere` / `cylinder` primitives (matching `simple_suturing.json`'s `box` skin tissue). Real-asset paths (`assets/instruments/*.obj`) are optional — the scene must be loadable with the primitive fallback path (per ASET-03 from Phase 20), so any path that does not exist on disk must have a primitive geometry block that the loader can use.
- **D-04:** Each new scene's `instruments[]` array MUST include at least one instrument appropriate to the task type:
  - `knot_tying`: needle driver + suture thread (or needle driver + forceps as fallback)
  - `needle_insertion`: needle driver + curved needle
  - `grasping`: forceps (or graspable instrument)
  - `cutting`: scalpel (or scissors)
  - `dissection`: scissors + forceps (typical dissection setup)
  See `TissueType` / `InstrumentType` enums in `src/surg_rl/scene_definition/schema.py` for the allowed literals.
- **D-05:** Difficulty parameters (`tissue.physics.stiffness`, `time_limit`, `max_episode_length`, `task.reward_shaping.*`) MUST vary across the 5 scenes to exercise `TaskRewardRouter.interpolate_params(difficulty)` (D-08 from Phase 21). Concretely: each scene's parameters are at the "medium" difficulty point in `PARAM_BOUNDS` for its task reward class (the audit gap "TASK-02 partial" notes the curriculum path is dormant — these scenes activate the path at difficulty=0.5, the CurriculumScheduler default).

### task_type wiring on the canonical suturing scene
- **D-06:** Add `"task_type": "suturing"` to the `task` block of `scenes/simple_suturing.json` (between `task.name` and `task.description`, or at the end of the task block — both parse identically). The `task.task_type` field is `None` by default in `TaskConfig`, so adding the literal value activates the `TaskRewardRouter` path at `src/surg_rl/rl/environment.py:200-203` (which currently never triggers because no scene sets the field). After this fix, the first `SuturingReward` is appended to the `CompositeReward` instead of only the generic `DistanceReward + ActionPenalty + TimePenalty + CollisionPenalty`.
- **D-07:** Do NOT add `task_type` to `scenes/suturing_demo.json` or `scenes/minimal_scene.json` (those are tutorial / minimal-fixture scenes; setting a task type there would break their intent of "no specific task"). Only `simple_suturing.json` gets the wiring (it's the canonical reference and is the one referenced by `TASK_SCENE_MAP["suturing"]`).
- **D-08:** Do NOT modify `laparoscopic_dissection.yaml` (it's a YAML format scene from before the Pydantic v2 schema work; the 5 new JSONs are the canonical addition for `TASK_SCENE_MAP` coverage).

### experiments/ directory creation (CLI reproduce hint)
- **D-09:** After `ExperimentRunner.run()` completes, write a copy of the effective config to `experiments/{cfg.experiment_name}.yaml` in addition to the existing write to `base_output_dir / "effective_config.yaml"`. The CLI at `src/surg_rl/cli.py:1286` prints `surg-rl benchmark --config experiments/{cfg.experiment_name}.yaml` — that path must point to a real file. The current code writes the effective config ONLY to the results dir, so the printed hint is misleading. The fix is in `ExperimentRunner.__init__` (or as a new step in `run()`): after `self.base_output_dir.mkdir(parents=True, exist_ok=True)`, also create `Path("experiments")` and call `config.to_yaml(Path("experiments") / f"{cfg.experiment_name}.yaml")` (a single extra write — reuses the existing `to_yaml` method at `src/surg_rl/benchmark/experiment_config.py:116-126`).
- **D-10:** Do NOT add a new CLI flag for the experiments-dir location. Use the literal `"experiments"` path (matches the help-text example at `src/surg_rl/cli.py:1113-1114`). If the `experiments/` directory does not exist, the `to_yaml` call's internal `path.parent.mkdir(parents=True, exist_ok=True)` will create it (already present in `to_yaml` at line 119).
- **D-11:** Do NOT auto-load `experiments/{name}.yaml` when running `surg-rl benchmark` without `--config`. The CLI at line 1159-1161 already prints "Using defaults (no config file)" when `--config` is omitted — keep that behavior. The fix is one-directional: the hint the CLI prints must point to a real file, not a phantom.

### Verification
- **D-12:** All 6 `TASK_SCENE_MAP` keys (`suturing`, `knot_tying`, `needle_insertion`, `grasping`, `cutting`, `dissection`) MUST map to existing files. Verify with: `python -c "import json; from pathlib import Path; from surg_rl.benchmark.experiment_runner import TASK_SCENE_MAP; missing=[t for t,p in TASK_SCENE_MAP.items() if not Path(p).exists()]; assert not missing, f'missing: {missing}'; print('all 6 scene files present')"` — MUST exit 0.
- **D-13:** `SurgicalEnv.load_scene(scene_path)` for each of the 6 scenes (one of `mujoco` backend) MUST complete without raising (Pydantic v2 validation + scene_builder compilation). A new test in `tests/test_benchmark_scenes.py` (file may need creation) iterates `TASK_SCENE_MAP.items()` and runs `SceneLoader.load(scene_path)` on each path, asserting no exception. Use `with suppress(Exception)` only for the fail-path branch — the test MUST pass clean for all 6 scenes.
- **D-14:** `experiments/{name}.yaml` MUST exist after a `surg-rl benchmark --task suturing --timesteps 100 --experiment-name test_audit` run completes. Verify with `ls experiments/test_audit.yaml` after the CLI returns.
- **D-15:** The 4 failing integration tests in `tests/test_multi_agent_env.py` (from Phase 25) MUST remain green. The 10 new tests added in Phase 26 (dreamer training + subprocess + benchmark plots) MUST remain green. The full non-integration suite MUST pass at 100% (baseline was 1043 passed + 10 skipped + 20 deselected per Phase 26 SUMMARY).
- **D-16:** Phase 27 does NOT modify any code under `src/surg_rl/rl/rewards.py`, `src/surg_rl/rl/task_reward_router.py`, `src/surg_rl/rl/environment.py`, or `src/surg_rl/benchmark/experiment_runner.py` lines 50-506 (the existing benchmark runner body). Changes are confined to:
  - 5 new files: `scenes/{knot_tying,needle_insertion,grasping,cutting,dissection}.json`
  - 1 edit: `scenes/simple_suturing.json` (add `task.task_type`)
  - 1 edit: `src/surg_rl/benchmark/experiment_runner.py` (add the `experiments/{name}.yaml` write — modify `__init__` or `run()`, not the registry)
  - 1 new test: `tests/test_benchmark_scenes.py` (covers D-12 and D-13)

### OpenCode's Discretion
- Exact instrument type strings used in each new scene's `instruments[]` (must be valid `InstrumentType` literals — see `src/surg_rl/scene_definition/schema.py`)
- Exact reward shaping values per scene (the Phase 21 reward class PARAM_BOUNDS gives min/max ranges — the executor picks midpoints for medium difficulty)
- Whether to add a `--experiment-name` override for the `experiments/` write path (out of scope — the user already passes `--experiment-name` for the existing results-dir naming)
- Whether to add a `experiments/README.md` documenting the directory's purpose (out of scope — minimal-impact change only)
- Whether to also fix the CLI's "Reproduce with" path to be `results/{name}_{ts}/effective_config.yaml` instead (out of scope — D-11 explicitly preserves the current hint wording)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — BENCH-01..05 requirements (v1), traceability table at lines 77-83 (BENCH-01 → Phase 27)
- `.planning/ROADMAP.md` § Phase 27 — success criteria: "Complete Benchmark Scene Coverage (BENCH-01, 5 task scenes, task_type wiring, experiments/)"
- `.planning/v0.4.0-MILESTONE-AUDIT.md` — gap evidence, line numbers, severity ratings (Benchmark-scene-coverage, Task-dormant, Benchmark-experiments-dir)

### Source artifacts (Phase 23)
- `src/surg_rl/benchmark/experiment_runner.py:40-47` — `TASK_SCENE_MAP` registry (6 task types → scene paths)
- `src/surg_rl/benchmark/experiment_config.py:116-126` — `ExperimentConfig.to_yaml()` (uses `path.parent.mkdir(parents=True, exist_ok=True)` — auto-creates `experiments/`)
- `src/surg_rl/cli.py:1283-1287` — the "Reproduce with: surg-rl benchmark --config experiments/{name}.yaml" print (the misleading hint to fix)
- `src/surg_rl/benchmark/experiment_runner.py:142-167` — `ExperimentRunner.__init__` (where to add the `experiments/{name}.yaml` write)

### Source artifacts (Phase 21 — task type wiring)
- `src/surg_rl/scene_definition/schema.py:1084-1090` — `TaskConfig.task_type` (Literal["suturing", "knot_tying", "needle_insertion", "grasping", "cutting", "dissection"] | None)
- `src/surg_rl/rl/environment.py:192-205` — where `TaskRewardRouter` activates on `task_type != None` (currently dormant because no scene sets the field)
- `src/surg_rl/rl/task_reward_router.py:27-34` — `TASK_REWARD_REGISTRY` (the 6 task types that need scene coverage)

### Source artifacts (Phase 20 — assets)
- `src/surg_rl/scene_definition/schema.py` `TissueType` and `InstrumentType` enums (allowed literals for new scenes)
- ASET-03 primitive fallback (Phase 20): scenes with missing `.obj` paths must still load via primitive geometry

### Reference scene (the working template)
- `scenes/simple_suturing.json` (223 lines) — the canonical scene that Phase 23 already loads; the new 5 scenes follow this structure

### Tests
- `tests/test_benchmark_scenes.py` — does not exist; needs to be created (D-13 / D-15)
- `tests/test_loader.py` — existing scene loader tests; check for analogous test patterns to mirror
- `tests/test_task_termination.py` — existing task tests; check for per-task-type parametrized tests to mirror
- `tests/test_multi_agent_env.py` — Phase 25 4-failing-tests baseline (must remain green)
- `tests/test_dreamer_subprocess.py` / `test_dreamer_training.py` / `test_benchmark_plots.py` — Phase 26 10-new-tests baseline (must remain green)

### Prior phase context
- `.planning/phases/26-fix-dreamerv3-training-bugs/26-CONTEXT.md` — gap-closure phase pattern (this phase follows the same shape)
- `.planning/phases/25-fix-marl-runtime-wiring/25-CONTEXT.md` — gap-closure phase pattern
- `.planning/phases/23-performance-benchmarking/23-01-SUMMARY.md` — `ExperimentConfig` design and `to_yaml` behavior
- `.planning/phases/21-surgical-task-curriculum/21-02-SUMMARY.md` — `TaskRewardRouter` and `TASK_REWARD_REGISTRY`

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — scene → simulator → env data flow
- `.planning/codebase/CONVENTIONS.md` — pytest patterns, lazy imports, fixture conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scenes/simple_suturing.json`** (223 lines): the working reference. It has all required fields (`metadata`, `physics`, `environment`, `robots[]`, `tissues[]`, `instruments[]`, `task`, `domain_randomization`, `simulator`). The new 5 scenes can be derived from it by:
  - Changing the `metadata.name` / `metadata.description` / `metadata.tags` to match the new task
  - Changing the `task.name` / `task.description` / `task.objectives[]` to match the new task
  - Changing the `tissues[]` content (geometry, color) — primitives are fine
  - Changing the `instruments[]` content — different tool for each task (D-04)
  - Setting `task.task_type` to the matching Literal value
  - Varying the difficulty parameters per D-05
- **`TASK_SCENE_MAP`** at `src/surg_rl/benchmark/experiment_runner.py:40-47`: 6 entries, one per `task_type` Literal. Currently only `"suturing"` resolves to a real file. After Phase 27, all 6 entries resolve to real files.
- **`TaskConfig.task_type`** at `src/surg_rl/scene_definition/schema.py:1084-1090`: 6 Literal values + `None`. Adding the field to `simple_suturing.json` activates the dormant `TaskRewardRouter` code at `rl/environment.py:200-203`.
- **`ExperimentConfig.to_yaml()`** at `src/surg_rl/benchmark/experiment_config.py:116-126`: already handles `path.parent.mkdir(parents=True, exist_ok=True)` (line 119). The `experiments/` directory is auto-created on first write.
- **`TASK_REWARD_REGISTRY`** at `src/surg_rl/rl/task_reward_router.py:27-34`: 6 task_type entries with corresponding reward classes (SuturingReward, DissectionReward, NeedlePassingReward, KnotTyingReward, GraspingReward, CuttingReward). Each has `PARAM_BOUNDS` for difficulty interpolation (Phase 21 D-08).

### Established Patterns
- **JSON scene structure** (Phase 19 schema work): all fields are Pydantic v2 validated; missing fields use defaults; `task` is a nested object with sub-fields.
- **Primitive geometry fallback** (Phase 20 ASET-03): when `instruments[].mesh.path` doesn't resolve to a real file, the scene_builder substitutes a primitive `.obj` (cube/cylinder/sphere). All 6 scenes can use `assets/instruments/*.obj` paths that don't exist on disk — they will fall back to primitives transparently.
- **Tissue type literals** (Phase 20): `TissueType` enum includes `skin`, `liver`, `stomach`, `kidney`, `gallbladder`, `custom`. The new scenes can pick appropriate types per task (e.g., `kidney` for grasping, `liver` for dissection).
- **Gap-closure phases** (Phase 25, 26): 1 plan per phase, 2-3 tasks per plan, all CPU-only, all mocked. Phase 27 follows the same shape.

### Integration Points
1. **`scenes/*.json`** → `SceneLoader.load()` (`src/surg_rl/scene_definition/loader.py`) — each new scene must pass Pydantic v2 validation and produce a `SceneDefinition` instance. The loader is called from `ExperimentRunner._run_single_seed` via `TrainingConfig(scene_path=...)` → `TrainingManager.train()`.
2. **`scene.task.task_type`** → `SurgicalEnv._setup_rewards()` at `src/surg_rl/rl/environment.py:192-205` — when `task_type is not None`, the `TaskRewardRouter.build(task_type)` returns `[task_specific_reward] + [generic_rewards]`. Otherwise only the generic rewards are added.
3. **`cli.py:1286` print** → `experiments/{cfg.experiment_name}.yaml` file — the print claims the file exists; after Phase 27 the file is actually written by `ExperimentRunner.__init__` (or `run()`).

### Common Landmines
- **Do NOT modify the `TASK_SCENE_MAP` registry** (D-01..D-05 add files; D-09 is a one-line write in `__init__` / `run()`). The registry should remain the source of truth for which task types map to which scene paths.
- **Do NOT add `task_type` to all 4 existing scene files** — only `simple_suturing.json` (D-06, D-07). The other 3 (`suturing_demo.json`, `minimal_scene.json`, `laparoscopic_dissection.yaml`) are tutorial / pre-schema fixtures; adding the field there would either break tutorials (if the task_type doesn't match the demo's actual content) or fail Pydantic v2 validation (for the YAML file which uses the older format).
- **Do NOT rename or restructure the `TASK_SCENE_MAP` constants** — keep the dict literal intact. Only the `experiments/` write needs a small change to the surrounding `__init__` / `run()` body.
- **Do NOT add new dependency** — the 5 new scenes and the `experiments/` write use only existing libraries (json + pathlib). No `[benchmark]`, `[assets]`, etc. extras.
- **Do NOT add `task_type` to the `metadata` block** — it belongs in the `task` block (matching `TaskConfig.task_type` schema). `metadata.task_type` would be ignored by the loader and would not activate the router.

</code_context>

<specifics>
## Specific Ideas

- **D-01 file naming**: use the exact filenames in the audit's `TASK_SCENE_MAP`:
  ```python
  TASK_SCENE_MAP = {
      "suturing": "scenes/simple_suturing.json",          # already exists
      "knot_tying": "scenes/knot_tying.json",              # NEW
      "needle_insertion": "scenes/needle_insertion.json",  # NEW
      "grasping": "scenes/grasping.json",                  # NEW
      "cutting": "scenes/cutting.json",                    # NEW
      "dissection": "scenes/dissection.json",              # NEW
  }
  ```
- **D-06 minimal diff for `simple_suturing.json`**: insert `"task_type": "suturing",` after `"name": "suturing_task",` (line 155). That's the only change. The `task` block already has all other required fields.
- **D-09 minimal diff for `experiment_runner.py`**: add 2 lines at the end of `ExperimentRunner.__init__` (after line 167 where `self._aggregator = Aggregator()` is set):
  ```python
  # Phase 27: Write effective config to experiments/{name}.yaml so the CLI's
  # "Reproduce with: surg-rl benchmark --config experiments/{name}.yaml" hint
  # points to a real file (audit: Benchmark-experiments-dir).
  experiments_dir = Path("experiments")
  self.config.to_yaml(experiments_dir / f"{self.experiment_name}.yaml")
  ```
  (`self.experiment_name` is already a str set at line 153; `to_yaml` accepts a `Path` per its signature.)
- **D-13 test pattern** (analogous to existing `tests/test_loader.py`):
  ```python
  from pathlib import Path
  from surg_rl.benchmark.experiment_runner import TASK_SCENE_MAP
  from surg_rl.scene_definition.loader import SceneLoader

  class TestBenchmarkSceneCoverage:
      def test_all_task_scene_map_paths_resolve(self):
          """Every TASK_SCENE_MAP path must exist (Phase 27 audit closure)."""
          missing = [t for t, p in TASK_SCENE_MAP.items() if not Path(p).exists()]
          assert not missing, f"Missing scene files: {missing}"

      def test_all_task_scene_map_loads(self):
          """Every TASK_SCENE_MAP path must load via SceneLoader (Pydantic v2 validate)."""
          for task, scene_path in TASK_SCENE_MAP.items():
              scene = SceneLoader.load(scene_path)
              assert scene is not None
              assert scene.task is not None
              assert scene.task.task_type is not None, f"{task}: task.task_type not set"
              # The task.task_type must match the TASK_SCENE_MAP key
              assert scene.task.task_type == task, (
                  f"Task mismatch: TASK_SCENE_MAP[{task!r}] → {scene_path}, "
                  f"but task.task_type={scene.task.task_type!r}"
              )
  ```
  This is the minimum test that proves BENCH-01 scene coverage. The test uses `SceneLoader.load()` (Pydantic v2 validation only — no simulator spin-up), so it's CPU-only and fast.
- **D-12 verification command** (single line, runs from project root):
  ```bash
  PYTHONPATH=src python -c "
  from pathlib import Path
  from surg_rl.benchmark.experiment_runner import TASK_SCENE_MAP
  missing = [t for t, p in TASK_SCENE_MAP.items() if not Path(p).exists()]
  assert not missing, f'missing: {missing}'
  print('all 6 scene files present')
  "
  ```

## Deferred Ideas

- Real end-to-end `surg-rl benchmark --task {task_name}` run for non-suturing tasks (requires real training, hours of compute) — audit Medium severity #5, deferred to benchmark suite
- `experiments/.gitkeep` and `experiments/README.md` to document the directory's purpose (out of scope)
- CLI flag to override the `experiments/` directory location (out of scope; literal `"experiments"` matches the help text)
- Adding `task_type` to `suturing_demo.json` and `minimal_scene.json` (D-07 explicitly excludes these — they're tutorial/minimal fixtures)
- Renaming `simple_suturing.json` → `suturing.json` to match the `TASK_SCENE_MAP` convention (would break any existing references; out of scope)
- Phase 23 verification artifacts (`23-VERIFICATION.md`, `23-VALIDATION.md`, `23-UAT.md`) — Phase 28 retroactive verification

---

*Phase: 27-Complete Benchmark Scene Coverage*
*Context gathered: 2026-06-10 from v0.4.0 milestone audit (gap-closure phase, no discuss-phase)*
