---
phase: 37
slug: scene-level-difficulty-blocks-env-wiring
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-24
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Plan / Wave columns populated from 37-01/02/03-PLAN.md (revision 1, 2026-06-24);
> the Requirement, Test Type, Automated Command, and Threat Ref columns are locked here.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via `pytest.ini`; `pythonpath = src`, `asyncio_mode = auto`) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_config.py tests/test_difficulty_levels.py tests/test_discrete_curriculum.py -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -v` — full suite has **pre-existing macOS aborts** in `test_rl.py`, `test_benchmark_*.py`, `test_dreamer_benchmark_integration.py`, `test_rl_callbacks.py`, `test_tracking_callbacks.py` (per 36-03-SUMMARY, NOT caused by this phase). The **targeted subset is the gate**, not the full suite. |
| **Estimated runtime** | ~30–60 seconds (targeted subset) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command above (the 4–5 difficulty test files).
- **After every plan wave:** `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_rl_environment.py -v` (targeted — avoids the macOS-aborting backend files).
- **Before `/gsd-verify-work`:** Targeted subset must be green PLUS a manual confirm that the full suite's only failures are the pre-existing macOS backend aborts (not caused by this phase).
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-SC1 | 01 | 1 | TASK-08 / SC#1 | T-37-V5 | `difficulty_blocks` rejected if malformed (Pydantic `ValidationError` at scene-load) | unit (TDD) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestSceneBlocksRoundTrip -v` | ❌ W0 (new) | ⬜ pending |
| 37-SC1-neg | 01 | 1 | TASK-08 / SC#1 | — | Scene without blocks loads with `difficulty_blocks is None`; 6 existing scenes unaffected | regression | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestSceneBlocksRoundTrip::test_existing_scenes_load_without_blocks tests/test_difficulty_levels.py::TestDifficultyIntegration -v` | ✅ existing + ❌ new | ⬜ pending |
| 37-SC2 | 02 | 2 | TASK-08 / SC#2 | T-37-V5 | Precedence truth table: `difficulty_blocks[level] > task.difficulty_level > config.difficulty > default 0.5` — 4 cases (one per precedence source) + Pitfall 3 time_limit-inert case | unit (TDD, parametrized) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestPrecedenceTruthTable -v` | ❌ W0 | ⬜ pending |
| 37-SC2-curric | 02 | 2 | TASK-08 / SC#2 | — | Blocks + `use_curriculum=True` continuous scalar → blocks NOT applied (Pitfall 6) | unit | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::test_blocks_inert_under_continuous_curriculum -v` | ❌ W0 | ⬜ pending |
| 37-SC3 | 03 | 3 | TASK-08 / SC#3 | — | 6 v0.4.0 task scenes × 3 difficulty levels construct + step (regression gate) | regression (parametrized 6×3) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestSixSceneThreeLevelRegression -v` | ❌ W0 | ⬜ pending |
| 37-SC4 | 03 | 3 | TASK-08 / SC#4 | — | `tests/fixtures/scenes/suturing_difficulty_hard.json` still loads; difficulty scalar unchanged (1.0 → HARD → 1.0) | regression (back-compat) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestHardFixtureScalarEquivalence::test_hard_fixture_scalar_unchanged tests/test_difficulty_levels.py::TestDifficultyIntegration::test_scene_load_with_difficulty_level_hard -v` | ✅ existing + ❌ new | ⬜ pending |
| 37-SC5 | 01 | 1 | TASK-08 / SC#5 | — | `difficulty_blocks` canonical across PROJECT.md, schema, STATE.md; `difficulty_levels` gone | structural (grep audit) | `grep -rn "difficulty_levels" .planning/PROJECT.md .planning/STATE.md src/surg_rl/` returns 0 (excluding milestone archives) | ❌ W0 | ⬜ pending |
| 37-SC9 | 02/03 | 2-3 | TASK-09 | — | Existing v0.4.0 + v0.4.2 curriculum + difficulty suite passes unchanged | regression | `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py -v` | ✅ existing (must stay green) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_difficulty_blocks.py` — **NEW**. Covers SC#1 round-trip, SC#2 precedence truth table (4 levels + curriculum-coexistence case), SC#3 6×3 regression matrix, SC#4 hard-fixture scalar equivalence, SC#5 naming audit. TDD RED gate for the `difficulty_blocks` field + `_setup_rewards` precedence branch + `apply_params` seam.
- [ ] Wave 0 spike: verify the 6 task scenes (`scenes/simple_suturing.json`, `knot_tying.json`, `needle_insertion.json`, `grasping.json`, `cutting.json`, `dissection.json`) construct + step under `SurgicalEnv` headless on the target host. If any abort, design the SC#3 gate as **construct-only** + log the abort as pre-existing.
- [ ] No framework install needed — pytest + pydantic already installed.

*If none: "Existing infrastructure covers all phase requirements." — N/A here; a new test file is required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full suite's only failures are the pre-existing macOS backend aborts | TASK-08 / SC#3 | The abovementioned backend files abort on macOS for reasons predating this phase (per 36-03-SUMMARY); cannot be made green by this phase | Run `PYTHONPATH=src pytest tests/ -v`; confirm failures are confined to `test_rl.py`, `test_benchmark_*.py`, `test_dreamer_benchmark_integration.py`, `test_rl_callbacks.py`, `test_tracking_callbacks.py` and that the targeted subset is green |

*All other phase behaviors have automated verification.*

---

## TDD Eligibility (`workflow.tdd_mode = true`)

| Task | TDD? | Rationale |
|------|------|-----------|
| `TaskConfig.difficulty_blocks` field + `model_rebuild()` resolution | `type: tdd` | Defined schema I/O: round-trip + validation; RED test asserts the field accepts 3-level blocks and rejects malformed |
| `_setup_rewards` precedence branch | `type: tdd` | 4-level truth table is the RED gate; defined I/O |
| `apply_params(params)` refactor on 6 task rewards | `type: tdd` (regression-anchored) | Refactor: RED = existing `apply_difficulty` tests stay green + new `apply_params` tests assert composed dict reaches ctor field |
| `compose_difficulty_overrides` reuse | standard (not TDD) | Already TDD-verified by P36-02's 54-case truth table; reused read-only |
| Naming-drift reconciliation (PROJECT.md/STATE.md edits) | standard | Doc edit; verified by grep audit (SC#5) |
| 6×3 fixture regression gate | standard (regression) | Asserts existing scenes still load/step; not new behavior |

---

## How Each Success Criterion Is Testably Verified

- **SC#1:** Round-trip test — author a scene JSON with `difficulty_blocks` for all 3 levels, `SceneLoader().load()`, assert `scene.task.difficulty_blocks` is a `dict[DifficultyLevel, DifficultyLevelConfig]` with authored values; assert `model_dump()`/JSON re-serialization preserves them. Negative: a scene without blocks loads with `difficulty_blocks is None`.
- **SC#2:** Parametrized truth table with 4 cases (one per precedence source ∈ {blocks, task_difficulty_level, config_difficulty, default}) — for each, construct the env with that source config and assert (a) `env._task_difficulty` matches expected scalar, (b) when blocks present, the composed params dict matches D-06 composition, (c) the reward ctor field that `apply_params` maps matches the override value. Plus the Pitfall 3 time_limit-inert case (path a — override composes but does NOT change TaskConfig.time_limit / env.max_episode_steps) and the curriculum-coexistence case (Pitfall 6). The 4 cases are sufficient to verify the precedence chain; the level dimension is exercised by SC#3's 6×3 matrix.
- **SC#3:** `@pytest.mark.parametrize` over the 6 scene files × 3 levels. For each, construct `SurgicalEnv(SurgicalEnvConfig(scene_path=..., render_mode=None))` with the level set, `env.reset()`, `env.step(action)`, assert no exception and a well-formed `(obs, reward, terminated, truncated, info)` tuple. If a scene aborts on the host, fall back to construct-only and assert `_setup_rewards` ran (`env._reward_fn is not None`).
- **SC#4:** Load `tests/fixtures/scenes/suturing_difficulty_hard.json`; assert `scene.task.difficulty_level == DifficultyLevel.HARD` and `float(env._task_difficulty) == 1.0` (the same scalar the v0.4.2 baseline produced). Capture the pre-phase scalar in the test for byte-identical comparison.
- **SC#5:** `grep -rn "difficulty_levels" .planning/PROJECT.md .planning/STATE.md src/surg_rl/` returns 0 hits (excluding historical milestone archives under `.planning/milestones/`). `grep -rn "difficulty_blocks" .planning/PROJECT.md .planning/STATE.md src/surg_rl/scene_definition/schema.py` returns the canonical hits.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`tests/test_difficulty_blocks.py` new)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-24