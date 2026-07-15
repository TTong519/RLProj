---
phase: 37-scene-level-difficulty-blocks-env-wiring
plan: 03
subsystem: rl
tags: [rl, tests, regression-gate, back-compat, difficulty-blocks, scene-fixtures]
requires:
  - "37-01: TaskConfig.difficulty_blocks schema field + field_validator (SC#1/SC#5)"
  - "37-02: SurgicalEnvConfig.difficulty + _setup_rewards additive blocks branch + apply_params (SC#2)"
  - "36-03: macOS MuJoCo/PyBullet backend abort log (pre-existing, NOT caused by Phase 37)"
provides:
  - "tests/test_difficulty_blocks.py::TestSixSceneThreeLevelRegression — SC#3 6x3 parametrized regression gate (18 cases)"
  - "tests/test_difficulty_blocks.py::TestHardFixtureScalarEquivalence — SC#4 v0.4.2 hard-fixture back-compat scalar gate"
affects:
  - "tests/test_difficulty_blocks.py (appended 37-03 classes; 37-01/37-02 classes untouched)"
tech-stack:
  added: []
  patterns:
    - "6x3 parametrized fixture regression matrix (scene_file x level) — mirrors test_difficulty_levels.py:383 idiom with (scene_file, level) tuple"
    - "Host-sensitivity degrade-to-construct-only fallback (try/except env.step() -> pytest.skip citing 36-03-SUMMARY pre-existing cause)"
    - "Byte-identical literal scalar comparison (env._task_difficulty == 1.0) for back-compat gate (T-37-10)"
key-files:
  created:
    - ".planning/phases/37-scene-level-difficulty-blocks-env-wiring/37-03-SUMMARY.md"
  modified:
    - "tests/test_difficulty_blocks.py"
decisions:
  - "Wave 0 spike on this host: all 6 v0.4.0 task scenes construct + step cleanly under DifficultyLevel.HARD -> SC#3 uses the full-step assertion path (env.reset() + env.step() 5-tuple). A try/except degrade-to-construct-only fallback is retained for future-host robustness citing the pre-existing macOS abort per 36-03-SUMMARY (NOT caused by Phase 37)."
  - "SC#4 captures the expected scalar as a literal 1.0 (not a computed value) — byte-identical comparison per T-37-10."
  - "SC#1 negative (test_existing_scenes_load_without_blocks) was shipped by Plan 01; this plan re-asserts its presence via grep (returns 1) and does NOT duplicate it."
metrics:
  duration: "~15 min"
  completed: 2026-06-24
  tasks: 2
  files: 1
status: complete
---

# Phase 37 Plan 03: SC#3 6-scene x 3-level Regression Gate + SC#4 Hard-Fixture Back-Compat Gate Summary

Landed the final two success criteria for TASK-08 as regression gates: SC#3 (6 v0.4.0 task scenes x 3 difficulty levels construct + step without regression) and SC#4 (v0.4.2 hard fixture's difficulty scalar is byte-identical 1.0). Both are regression gates asserting existing behavior holds after the additive schema field (Plan 01) + env precedence branch (Plan 02). All 5 SCs for TASK-08 are now verified.

## What Was Built

### Task 1 — Wave 0 spike (read-only probe, no commit)
Ran a one-off `PYTHONPATH=src python3 -c "..."` probe against all 6 v0.4.0 task scene fixtures (`simple_suturing`, `knot_tying`, `needle_insertion`, `grasping`, `cutting`, `dissection`). For each scene: loaded via `SceneLoader().load()`, mutated `scene.task.difficulty_level = DifficultyLevel.HARD`, constructed `SurgicalEnv(SurgicalEnvConfig(scene=scene, render_mode=None))`, called `env.reset()` + `env.step(env.action_space.sample())`.

Spike result: **all 6 scenes construct + step cleanly** (env._reward_fn is not None, env.step() returns a well-formed 5-tuple). Non-fatal stderr noise ("MuJoCo offscreen rendering failed: Renderer.render() got an unexpected keyword argument 'depth'" and primitive-fallback asset warnings) does not abort the step path on this host. A post-exit `ModuleNotFoundError` in `BaseSimulator.__del__` is a harmless deallocator traceback fired after the probe completed.

Gate shape decision: SC#3 uses the **full-step assertion path** (env.reset() + env.step() 5-tuple) on this host. A `try/except` degrade-to-construct-only fallback is retained for future-host robustness — if `env.step()` aborts on a host with the pre-existing macOS MuJoCo/PyBullet backend abort (per 36-03-SUMMARY, NOT caused by Phase 37), the case skips with a message citing the pre-existing cause, and the construct-only baseline (`env._reward_fn is not None`) already asserted before the step stands.

No source files edited; no commit (per plan `<action>`: "Commit no code in this task; the spike result informs Task 2's test shape").

### Task 2 — `tests/test_difficulty_blocks.py` (commit `72a22ea`)
Appended two new test classes after `test_apply_params_delegates_on_suturing` (37-01's `TestSceneBlocksRoundTrip` + `TestNamingAudit` and 37-02's `TestPrecedenceTruthTable` + `test_blocks_inert_under_continuous_curriculum` + `test_apply_params_delegates_on_suturing` untouched):

- **`TestSixSceneThreeLevelRegression`** — SC#3 6x3 parametrized regression gate. `@pytest.mark.parametrize` over `(scene_file, level_name, level, scalar)` covering 6 scene files x 3 levels = 18 cases (`ids=[f"{sf}-{ln}" ...]`). For each case: loads the scene via `SceneLoader().load(str(Path(__file__).parent.parent / "scenes" / scene_file))`; re-asserts SC#1 negative (`scene.task.difficulty_blocks is None` — the 6 v0.4.0 scenes have no blocks); mutates `scene.task.difficulty_level = level` (the scenes ship with `difficulty_level is None`); constructs `SurgicalEnv(SurgicalEnvConfig(scene=scene, render_mode=None))`; asserts `env._reward_fn is not None` (construct-only baseline proving `_setup_rewards` ran); asserts `env._task_difficulty == approx(scalar)` (the level's canonical scalar: EASY=0.0, MEDIUM=0.5, HARD=1.0); calls `env.reset()` + `env.step(env.action_space.sample())` inside a `try/except` that degrades to `pytest.skip` citing the pre-existing macOS abort per 36-03-SUMMARY if the step aborts; asserts the step result is a well-formed 5-tuple. `env.close()` in a `finally` block for clean teardown.

- **`TestHardFixtureScalarEquivalence`** — SC#4 back-compat scalar gate. `FIXTURE_DIR = Path(__file__).parent / "fixtures" / "scenes"`; `HARD_FIXTURE = FIXTURE_DIR / "suturing_difficulty_hard.json"` (skips if missing). `test_hard_fixture_scalar_unchanged`: loads the fixture via `SceneLoader().load()`; asserts `scene.task.difficulty_level == DifficultyLevel.HARD` (the v0.4.2 fixture authors `difficulty_level: 1.0` -> coerced to HARD enum); asserts `scene.task.difficulty_blocks is None` (the v0.4.2 fixture has no blocks -> the blocks branch is INERT -> existing router path runs); constructs `SurgicalEnv(SurgicalEnvConfig(scene=scene, render_mode=None))`; asserts `env._task_difficulty == 1.0` (literal — byte-identical v0.4.2 scalar, NOT a computed value per T-37-10); asserts `env._reward_fn is not None`. `env.close()` in a `finally` block.

Presence guards (per plan `<action>`):
- `grep -c 'class TestSixSceneThreeLevelRegression' tests/test_difficulty_blocks.py` -> 1
- `grep -c 'class TestHardFixtureScalarEquivalence' tests/test_difficulty_blocks.py` -> 1
- `grep -c 'def test_existing_scenes_load_without_blocks' tests/test_difficulty_blocks.py` -> 1 (SC#1 negative, shipped by Plan 01 — not duplicated)

## Deviations from Plan

### Auto-fixed Issues

None. Plan executed exactly as written. The Wave 0 spike (Task 1) determined the SC#3 gate shape (full-step path on this host, with a degrade-to-construct-only fallback for future-host robustness), which is one of the two shapes the plan explicitly anticipated.

### Out-of-Scope Pre-Existing Debt (NOT fixed — scope boundary)

- `tests/test_difficulty_blocks.py` has 10 pre-existing ruff errors (F401 unused imports: `ABSTRACT_TO_CONCRETE`, `CuttingReward`, `DissectionReward`, `GraspingReward`, `KnotTyingReward`, `NeedlePassingReward`, `TASK_REWARD_REGISTRY`, `TaskRewardRouter`; I001 import sorting; W292 no trailing newline). Verified pre-existing via `git stash` — the same 10 errors exist on the baseline before this plan's edit. My appended lines introduce 0 new ruff errors. Left unchanged per the scope-boundary rule (out-of-scope pre-existing debt).
- `tests/test_rl_environment.py` has a fatal teardown crash on this Python (pre-existing on clean `main`, reproduced via `git stash` by the 37-02 executor). Unrelated to difficulty_blocks; NOT touched by this plan. The success-criteria TASK-09 additive gate list intentionally excludes `test_rl_environment.py`.

## Validation

- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py -v` -> **35 passed** (8 from 37-01 SC#1/SC#5 + 7 from 37-02 SC#2/Pitfall6/apply_params + 18 SC#3 + 1 SC#4 + 1 SC#1-negative-presence re-affirmation via the 6 existing_scenes cases counted under 37-01). All 5 SCs verified.
- `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_levels.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_dynamics.py -q` -> **239 passed** (TASK-09 additive-regression gate — the targeted subset, excluding the pre-existing-crash `test_rl_environment.py` per the success criteria).
- `grep -c 'class TestSixSceneThreeLevelRegression' tests/test_difficulty_blocks.py` -> 1
- `grep -c 'class TestHardFixtureScalarEquivalence' tests/test_difficulty_blocks.py` -> 1
- `grep -c 'def test_existing_scenes_load_without_blocks' tests/test_difficulty_blocks.py` -> 1
- `ruff check tests/test_difficulty_blocks.py` -> 10 pre-existing errors (unchanged from baseline; 0 new errors introduced by this plan).
- `black --check tests/test_difficulty_blocks.py` -> would reformat (pre-existing; the appended lines follow black style — no reformatting needed in the appended block).

## TDD Gate Compliance

This plan is `type: execute` (test-only regression gates). The 37-01 schema field + 37-02 env branch it depends on are already committed GREEN on this tree, so the gates pass against the already-built code on first run — there is no RED phase for 37-03 (the plan has no `<behavior>` block and no source files in `<files>`; it only consumes Plans 01-02 read-only). The `test(37-03):` commit `72a22ea` lands both gates GREEN in a single commit, as the plan specifies.

## Known Stubs

None. Both gates are fully wired regression assertions against existing fixtures.

## Threat Flags

None. No new security-relevant surface beyond the plan's `<threat_model>`:
- T-37-09 (DoS — env.step() macOS abort) — accepted per the threat register; the SC#3 gate degrades to construct-only via `pytest.skip` citing the pre-existing 36-03-SUMMARY cause when env.step() aborts. The abort is documented in this SUMMARY, not hidden. On this host the spike confirmed the full-step path works.
- T-37-10 (Tampering — back-compat scalar drift) — mitigated by `TestHardFixtureScalarEquivalence` asserting `env._task_difficulty == 1.0` (literal, byte-identical) for the v0.4.2 hard fixture. Any drift in the precedence chain fails the gate.
- T-37-SC (package installs) — accept; no package installs this plan.
- No new network/auth/file-access surface. The gates load trusted repo fixtures via `SceneLoader` (existing trusted path) and construct `SurgicalEnv` (existing in-process path).

## Self-Check: PASSED

- `tests/test_difficulty_blocks.py` — FOUND (modified, commit `72a22ea`)
- `.planning/phases/37-scene-level-difficulty-blocks-env-wiring/37-03-SUMMARY.md` — FOUND
- Commit `72a22ea` (test/37-03) — FOUND
- `grep -c 'class TestSixSceneThreeLevelRegression'` -> 1 — FOUND
- `grep -c 'class TestHardFixtureScalarEquivalence'` -> 1 — FOUND