# Phase 27 — Plan 01: Complete Benchmark Scene Coverage

**One-liner:** Closed 3 v0.4.0 audit gaps — created 5 missing task scene JSONs, wired `task_type` on all 6 scenes (activating the previously-dormant TaskRewardRouter), and made the CLI's "Reproduce with: --config experiments/{name}.yaml" hint actually functional.

**Date:** 2026-06-10
**Branch:** `phase-27-complete-benchmark-scene-coverage`
**Plan:** `.planning/phases/27-complete-benchmark-scene-coverage/27-01-PLAN.md`
**Audit gaps closed:** Benchmark-scene-coverage (high), Task-dormant (medium), Benchmark-experiments-dir (low) — all 3 from v0.4.0 audit
**Requirements closed:** BENCH-01 (targeted); TASK-02 partially (dormant-reward path activated; 3-difficulty-levels requirement not fully addressed — see Deviations)

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| Plan pre-fix | Correct baseline test count (1043 → 1053) | `74b49e9` | `27-01-PLAN.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` |
| 1 | Add `task_type` to simple_suturing.json + create 5 new task scene JSONs + scene-coverage tests | `bf7d9c4` (initial) | `scenes/simple_suturing.json`, 5 new scenes, `tests/test_benchmark_scenes.py` |
| 2 | Wire `experiments/{name}.yaml` write in `ExperimentRunner.__init__` + 4 tests | `c38ca96` | `src/surg_rl/benchmark/experiment_runner.py`, `tests/test_benchmark_scenes.py` |
| 2b | Align new scenes with Phase 24 dreamer_training test expectations + lint cleanup | `75b25b4` | 5 new scenes, `src/surg_rl/dreamer/training.py`, `tests/test_benchmark_scenes.py` |

**Branch setup:** Created `phase-27-...` from tip, reset `phase-26-...` to its last phase-26 commit (22b911f). No branch pollution.

## Decisions Implemented (D-01..D-16)

| Decision | Status | Where |
|----------|--------|-------|
| D-01..D-05: 5 new task scene JSONs (knot_tying, needle_insertion, grasping, cutting, dissection) | ✓ | `scenes/*.json` |
| D-06: `task_type: suturing` on `simple_suturing.json` | ✓ | `scenes/simple_suturing.json:155` |
| D-07: Each new scene has `task.task_type` matching its TASK_SCENE_MAP key | ✓ | verified by `test_all_task_scene_map_loads` |
| D-09: `ExperimentRunner.__init__` writes `experiments/{name}.yaml` | ✓ | `src/surg_rl/benchmark/experiment_runner.py:170-171` |
| D-12: All 6 TASK_SCENE_MAP paths exist | ✓ | verified by `test_all_task_scene_map_paths_resolve` |
| D-13: All 6 scenes load via SceneLoader + task_type matches | ✓ | verified by `test_all_task_scene_map_loads` |

## Deviations from Plan

1. **Test count fix pre-execution (commit `74b49e9`).** Plan cited "1043 baseline tests" but actual non-integration count is 1053 (per `pytest --collect-only` after Phase 26). Bulk-replaced 10 occurrences of 1043 → 1053 in 27-01-PLAN.md.

2. **Branch reorganization (pre-execution).** All Phase 27 planning commits initially landed on the `phase-26-...` branch (the same planner bug as Phase 25/26). Created `phase-27-...` from tip, reset `phase-26-...` to its last phase-26 commit.

3. **Scene alignment with Phase 24 test contract (commit `75b25b4`)** — **significant deviation**. The plan didn't account for the existing `tests/test_dreamer_training.py` test parametrize that pins instrument/tissue types per task. Initial Phase 27 scenes used:
   - `needle_driver` for needle_insertion (test expects `needle`)
   - `scalpel` for cutting (test expects `scissors`)
   - `scissors+forceps` for dissection (test expects `scissors` only)
   - `skin` for knot_tying (test expects `CUSTOM`/suture_pad)
   - `muscle` for needle_insertion (test expects `ORGAN`)
   - `organ` for grasping (test expects `SKIN`)
   - `organ+fat` 2-tissue for dissection (test expects single `MUSCLE` tissue)
   
   Updated all 5 new scenes to match Phase 24 canonical types. Also added a `dreamer` block (with `process_isolation=True, memory_fraction=0.4`) to each new scene — Phase 24 tests assert `scene.dreamer is not None`. The `_create_scene_for_task` function now overrides `dreamer.obs_type` and `dreamer.pixel_resolution` from the call-site params so the same scene file satisfies both `obs_type='pixels'` and `obs_type='state'` test calls (the JSON's dreamer block stores them as None).

4. **TASK-02 partial closure caveat.** The plan's `requirements: [BENCH-01, TASK-02]` frontmatter overclaims. Setting `task_type` on the 6 scenes activates the previously-dormant reward router pipeline (D-06), but the actual TASK-02 requirement is "Each task type supports 3 difficulty levels (easy/medium/hard) with progressive parameter changes" — that's a separate concern not addressed in Phase 27. The `<must_haves>` correctly frames the closure as "TaskRewardRouter activates on simple_suturing.json (task_type='suturing' is set), no longer dormant" — the audit's evidence was about dormancy, not difficulty levels.

5. **Test 1 timestep bump (task 2).** Plan's `timesteps=100` failed `ExperimentConfig` validation (ge=1000). Used `timesteps=1000` instead. Pydantic v2 caught this immediately on first test run.

6. **Plan referenced `test_scene_definition.py` (file does not exist).** Skipped that step; ran the closest substitutes (`test_loader.py`, `test_schema.py`) instead. Both pass.

## Test Results

### Per-file (Phase 27 affected)

| File | Before | After | New |
|------|--------|-------|-----|
| `test_benchmark_scenes.py` (new) | 0 | 9 | +9 (TestBenchmarkSceneCoverage + TestExperimentRunnerExperimentsWrite) |
| `test_dreamer_training.py` (Phase 24) | 12 | 12 | 0 (5 were failing; now pass after scene alignment) |
| **Total Phase 27** | **12** | **21** | **+9 net** |

### Full dreamer + benchmark sweep

```
$ PYTHONPATH=src python -m pytest tests/test_dreamer_training.py tests/test_benchmark_scenes.py
21 passed in 6.5s
```

### Broad regression (Phase 25 + 26 + 27)

```
$ PYTHONPATH=src python -m pytest tests/ -m "not integration" \
    --ignore=tests/test_rllib_ --ignore=tests/test_ros2_ \
    --ignore=tests/test_kubernetes_manifests.py --ignore=tests/test_gpu_integration.py
1052 passed, 10 skipped, 20 deselected in 52.44s
```

**Zero failures.** Phase 25 MARL, Phase 26 Dreamer, Phase 24 training tests, and all adjacent tests remain green.

## Audit Gap Closure

| Audit Gap | Severity | Status |
|-----------|----------|--------|
| Benchmark-scene-coverage (5 of 6 scene files missing) | high | ✓ closed — 5 new scenes created, all 6 paths resolve |
| Task-dormant (no scene sets `task_type`) | medium | ✓ closed — all 6 scenes have `task_type` matching their TASK_SCENE_MAP key |
| Benchmark-experiments-dir (CLI hint points to non-existent file) | low | ✓ closed — `experiments/{name}.yaml` written by `ExperimentRunner.__init__` |

## File Modifications

```
scenes/simple_suturing.json                   (+1)       D-06 wiring
scenes/knot_tying.json                        (new)      D-04
scenes/needle_insertion.json                  (new)      D-04
scenes/grasping.json                          (new)      D-04
scenes/cutting.json                           (new)      D-04
scenes/dissection.json                        (new)      D-04
src/surg_rl/benchmark/experiment_runner.py   (+7)       D-09
src/surg_rl/dreamer/training.py               (+9 -1)    align with Phase 24
tests/test_benchmark_scenes.py                (new)      9 tests
.planning/phases/27-complete-benchmark-scene-coverage/27-01-PLAN.md (test counts fix)
```

## Success Criteria

- [x] `scenes/{simple_suturing,knot_tying,needle_insertion,grasping,cutting,dissection}.json` all exist
- [x] Each of the 6 scenes has `"task_type"` in the `task` block matching its TASK_SCENE_MAP key
- [x] `scenes/simple_suturing.json` has `"task_type": "suturing"` (D-06 — TaskRewardRouter activation)
- [x] `src/surg_rl/benchmark/experiment_runner.py` has the new 2-line `experiments/{name}.yaml` write
- [x] `tests/test_benchmark_scenes.py` exists with 9 tests across 2 test classes
- [x] All 9 new tests pass
- [x] Full non-integration suite (1052 tests) passes with zero new failures
- [x] Phase 25 MARL 4 originally-failing tests + Phase 26 dreamer 10 new tests + Phase 24 training tests all pass

## Next Steps

- Re-run v0.4.0 milestone audit to confirm `passed` status
- Phase 28 (Audit Gap Closure: retroactive verification for Phases 21-23, REQUIREMENTS checkboxes)
- Or `/gsd-verify-work 27` for goal-backward verification

---

*Phase 27 plan 27-01 executed 2026-06-10. 4 commits on `phase-27-complete-benchmark-scene-coverage`.*
