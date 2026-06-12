# Roadmap: Surg-RL v0.4.2 — Audit Leftovers

**Defined:** 2026-06-11
**Goal:** Close the 2 remaining items deferred from the v0.4.0 audit gap closure milestone (v0.4.1): TASK-02 3-difficulty-levels (easy/medium/hard presets per task) and DreamerV3 real-subprocess E2E test. Pure gap-closure — no new features, only the missing presets + a real-subprocess smoke test for the Phase 26 DreamerV3 fixes.

**Phases:** 29–30 (continuing from v0.4.1's Phase 28)
**Total Plans:** TBD (estimated 2–3 plans across both phases)
**Granularity:** standard (per `.planning/config.json`)
**Mode:** yolo
**Inherited tech debt (OUT OF SCOPE, deferred to v0.5.0+):** 421 ruff issues in `src/surg_rl/dreamer/`, cut cooldown test, fluid step hook, 3D fluid flag, K8s e2e, Dockerfile.ros2 amd64 hardcode, organ mesh source licensing, REQUIREMENTS.md BENCH-02..05 body checkboxes.

## Milestone Position

| Milestone | Status | Phases | Plans | Tests | Shipped |
|-----------|--------|--------|-------|-------|---------|
| v0.1.0 | ✅ SHIPPED | 1–5 | 12 | 607 | 2026-05-02 |
| v0.2.0 | ✅ SHIPPED | 6–9 | 19 | 775 | 2026-05-03 |
| v0.3.0 | ✅ SHIPPED | 10–13 | 18 | 826 | 2026-05-04 |
| v0.3.1 | ✅ SHIPPED | 14 | 1 | 833 | 2026-05-04 |
| v0.3.2 | ✅ SHIPPED | 15–18 | 9 | 910 | 2026-05-05 |
| v0.4.0 | ✅ SHIPPED | 19–24 | 21 | 1,043 | 2026-06-09 |
| v0.4.1 | ✅ SHIPPED | 25–28 | 4 | 1,053+ | 2026-06-11 |
| **v0.4.2** | 📋 PLANNING | **29–30** | TBD | TBD | TBD |
| v0.5.0 | 📋 not yet planned | — | — | — | — |

## Phases

- [x] **Phase 29: TASK-02 3-Difficulty-Levels Completion** (completed 2026-06-12) — Define easy/medium/hard presets per task type that drive the existing PARAM_BOUNDS + interpolate_params() pipeline; thread the new enum through TaskRewardRouter, TaskConfig, and CurriculumScheduler
- [ ] **Phase 30: DreamerV3 Real-Subprocess E2E Test** — Spawn a real `dreamerv3` subprocess via the existing process-isolated harness and verify the Phase 26 fixes (`_JsonStdout` wrapper, `indent` typo, `DREAMER_COLOR`) hold end-to-end. GPU + `dreamerv3` install are hard prereqs; otherwise skip with documented reason

## Phase Details

### Phase 29: TASK-02 3-Difficulty-Levels Completion

**Goal**: Each of the 6 task types supports EASY/MEDIUM/HARD difficulty levels via a new `DifficultyLevel` enum, drives observable parameter changes through the existing `PARAM_BOUNDS` + `interpolate_params()` machinery, and threads cleanly through `TaskRewardRouter`, `TaskConfig` (Pydantic v2), and `CurriculumScheduler` — all without breaking the existing float-based difficulty path.

**Depends on**: Phase 21 (Surgical Task Curriculum — provides the `interpolate_params()` + `PARAM_BOUNDS` foundation), Phase 27 (Complete Benchmark Scene Coverage — activates the TaskRewardRouter on real scenes)

**Requirements**: TASK-02-01, TASK-02-02, TASK-02-03, TASK-02-04, TASK-02-05, TASK-02-06

**Success Criteria** (what must be TRUE):
  1. Running `from surg_rl.rl import DifficultyLevel; DifficultyLevel.EASY/MEDIUM/HARD` returns an enum whose members map to scalar values 0.0, 0.5, 1.0 respectively — the value used internally is the scalar
  2. All 6 reward classes (`SuturingReward`, `KnotTyingReward`, `NeedlePassingReward`/`NeedleInsertionReward`, `GraspingReward`, `CuttingReward`, `DissectionReward`) expose a `get_params_for_difficulty(level: DifficultyLevel) -> dict[str, float]` method that delegates to the existing `interpolate_params(difficulty)` infrastructure (no duplicate math)
  3. For each of the 6 task types, `get_params_for_difficulty(DifficultyLevel.HARD) != get_params_for_difficulty(DifficultyLevel.EASY)` for at least 1 parameter in that task's `PARAM_BOUNDS` — verified by a single parametrized pytest that runs all 6 task types × 3 levels and asserts at least one of the `tissue_stiffness`-equivalent, `target_precision_tolerance`-equivalent, `tool_position_noise`-equivalent, or `time_limit`-equivalent parameters strictly changes between EASY and HARD
  4. `TaskRewardRouter` accepts a `DifficultyLevel` argument (in addition to the existing `float`) and the float-only path is preserved unchanged — `TaskRewardRouter(difficulty=0.5).build(task_type)` and `TaskRewardRouter(difficulty=DifficultyLevel.MEDIUM).build(task_type)` produce equivalent reward instances
  5. `TaskConfig` (Pydantic v2) gains an optional `difficulty_level: DifficultyLevel | None` field with default `None`; when set, the level's scalar value is used to construct the reward; when `None`, the existing float path is used; mixed scene JSONs (some with `difficulty_level`, some with the float field) load without migration
  6. `CurriculumStageConfig.task_difficulty` accepts either a `float` or `DifficultyLevel` value; when a `DifficultyLevel` is set, its scalar (0.0/0.5/1.0) is used at stage activation time; mixed-stage configs (some float, some enum) work without migration

**Plans**: 2 plans

Plans:
- [ ] 29-01-PLAN.md — DifficultyLevel enum + `get_params_for_difficulty()` on all 6 reward classes + `apply_difficulty()` no-op default on `BaseRewardFunction` + per-subclass field mapping + parametrized per-family direction tests
- [ ] 29-02-PLAN.md — Thread `DifficultyLevel` through `TaskRewardRouter` (with float backwards compat, calls `apply_difficulty` in `build()`) + `TaskConfig.difficulty_level` (Pydantic v2 optional field) + `CurriculumStageConfig.difficulty` (mixed float/enum support) + env wiring + scene JSON integration test

**Out of scope** (carried forward, explicitly excluded by user direction):
- Defining scene-level `difficulty_levels: list[3]` blocks in JSON scene files (deferred — adding a fourth field that doesn't exist today is scope creep)
- New `DifficultyLevelConfig` schema model with `tissue_stiffness` / `target_precision_tolerance` / `tool_position_noise` / `time_limit` overrides (deferred — TaskConfig-level enum field is sufficient for v0.4.2)
- Discretizing `CurriculumScheduler` continuous-difficulty progression into discrete level steps (deferred — scheduler accepts the enum but does not drive level progression)

### Phase 30: DreamerV3 Real-Subprocess E2E Test

**Goal**: A single pytest test (`tests/dreamer/test_dreamerv3_subprocess_e2e.py`) spawns a real `dreamerv3` subprocess via the existing process-isolated harness, runs 100 environment steps on the Phase 24 forceps+liver suturing feasibility scene, and verifies the three Phase 26 fixes (`_JsonStdout` wrapper, `indent=2` typo, `DREAMER_COLOR` constant) hold end-to-end — the test gates cleanly on (GPU + `dreamerv3` + `jax`) so it is skip-with-reason on macOS local but runs on CI with GPU.

**Depends on**: Phase 24 (DreamerV3 World Models — provides `DreamerSubprocess`, `_JsonStdout`, `run_dreamer_training`, `_create_scene_for_task`), Phase 26 (Fix DreamerV3 Training Bugs — the three fixes this test verifies)

**Requirements**: DMV3-E2E-01, DMV3-E2E-02, DMV3-E2E-03, DMV3-E2E-04, DMV3-E2E-05

**Success Criteria** (what must be TRUE):
  1. `pytest tests/dreamer/test_dreamerv3_subprocess_e2e.py` exists, is collected, and runs (or skips with descriptive reason) — the test is discoverable by pytest without errors
  2. The test spawns a real `dreamerv3` subprocess via `DreamerSubprocess` (or `run_dreamer_training` with `process_isolation=True`), runs 100 environment steps on the Phase 24 forceps+liver suturing scene (`task="suturing"`, `obs_type="state"`), and the subprocess completes without raising an exception (no `BlockingIOError`, no `TypeError: got an unexpected keyword argument 'indig'`, no `KeyError` on `DREAMER_COLOR`)
  3. The test captures the subprocess's stdout pipe output and asserts that every line consumed via the `_JsonStdout` wrapper is a complete JSONL record (no truncated lines, no `BlockingIOError` from `pipe.send()`) — the `_JsonStdout` wrapper is exercised end-to-end, not just unit-tested
  4. The test's log output (or captured subprocess output) contains the `DREAMER_COLOR` constant value (`#FF8C00`) somewhere in the run — verifying the post-Phase-26 fix is active, not the pre-fix `indigo` color value (`#4B0082`)
  5. The test is gated by `@pytest.mark.skipif` checking (a) GPU availability (via `torch.cuda.is_available()` or `jax.devices()` listing CUDA), (b) `dreamerv3` importable, (c) `jax` importable; the skip message is descriptive and includes remediation steps (e.g., `"Skipped: dreamerv3 not installed — pip install '.[dreamer]' to enable"`); on macOS local the test is xfail-skipped, on CI with GPU it runs
  6. On a successful run, a checkpoint is written to `models/dreamerv3/{task}_{obs_type}/` (e.g., `models/dreamerv3/suturing_state/`) and the test asserts the directory exists and contains at least one checkpoint file (`checkpoint_*.pt` or `training_metrics.json`) — the Phase 24 auto-discovery path is exercised end-to-end

**Plans**: 1 plan

Plans:
- [ ] 30-01: Add `tests/dreamer/test_dreamerv3_subprocess_e2e.py` with the 6 success criteria as test cases; gate the whole module with `@pytest.mark.skipif` on (GPU + `dreamerv3` + `jax`); verify locally that skip message renders on macOS; do NOT run the test on macOS (xfail-skip expected per `STATE.md` Blocker #4)

**Out of scope** (carried forward, explicitly excluded by user direction):
- Running the test on macOS local (xfail-skip expected — no GPU, no `dreamerv3` install)
- Adding GPU-based CI runner configuration (CI config is operations work, not code; assume CI with GPU exists or will be added separately)
- Cleaning up 421 ruff issues in `src/surg_rl/dreamer/` (deferred — would be a separate cleanup phase)
- Implementing `dreamerv3` offline training from recorded demos (DMV3-06 — v2)
- Real-time multi-user networked surgery, 3D fluid simulation, 3D DreamerV3 video prediction (all out of scope per `.planning/PROJECT.md`)

---

## Coverage Summary

| Requirement | Phase | Status |
|-------------|-------|--------|
| TASK-02-01 (DifficultyLevel enum) | Phase 29 | Pending |
| TASK-02-02 (per-task `get_params_for_difficulty()`) | Phase 29 | Pending |
| TASK-02-03 (TaskRewardRouter accepts DifficultyLevel + float) | Phase 29 | Pending |
| TASK-02-04 (observable param change EASY→HARD) | Phase 29 | Pending |
| TASK-02-05 (TaskConfig.difficulty_level Pydantic v2) | Phase 29 | Pending |
| TASK-02-06 (CurriculumScheduler accepts DifficultyLevel) | Phase 29 | Pending |
| DMV3-E2E-01 (spawn + 100 steps + no exception) | Phase 30 | Pending |
| DMV3-E2E-02 (`_JsonStdout` wrapper verified) | Phase 30 | Pending |
| DMV3-E2E-03 (DREAMER_COLOR verified) | Phase 30 | Pending |
| DMV3-E2E-04 (skipif gating) | Phase 30 | Pending |
| DMV3-E2E-05 (checkpoint written) | Phase 30 | Pending |

**Coverage:**
- v1 requirements: 11 total (6 TASK-02 + 5 DMV3-E2E)
- Mapped to phases: 11
- Unmapped: 0 ✓
- Out of scope items: 0 (all v0.4.2 requirements are mapped; `Out of Scope` items in REQUIREMENTS.md do not appear in any phase)

## Milestone Decisions

- **D-29-01**: Single phase for TASK-02 is appropriate. The 6 requirements form one tightly-coupled feature: enum → per-task methods → router → TaskConfig → CurriculumScheduler. Subdividing into "implementation" and "integration" plans within Phase 29 is acceptable (planner's choice), but splitting into two phases would over-engineer a gap-closure milestone.
- **D-29-02**: DifficultyLevel is enum-only, not Pydantic-validated scalar. The enum is the public API; internally, only the scalar (`0.0`/`0.5`/`1.0`) is used. Avoids confusing double-validation (Pydantic validates enum membership; downstream uses scalar).
- **D-29-03**: No new `DifficultyLevelConfig` schema model. TaskConfig gets a single optional `difficulty_level` field; per-level override blocks (tissue_stiffness, target_precision_tolerance, tool_position_noise, time_limit) are deferred. The 6 `PARAM_BOUNDS` already encode the progression — adding scene-level overrides is scope creep.
- **D-29-04**: `interpolate_params(difficulty)` remains the single source of truth. `get_params_for_difficulty(level)` is a thin wrapper that calls `interpolate_params(level.value)`. No duplicate math.
- **D-29-05**: Float path is preserved everywhere. `TaskRewardRouter(difficulty=0.5)` and `TaskRewardRouter(difficulty=DifficultyLevel.MEDIUM)` produce equivalent behavior. Mixed `CurriculumStageConfig.task_difficulty` (float in stage 1, enum in stage 2) works without migration.
- **D-30-01**: Single-phase, single-plan E2E test. Splitting into "subprocess spawn" and "assertions" is over-engineering for a test-only phase; all 5 requirements describe the same test.
- **D-30-02**: macOS local run is expected to skip — `STATE.md` Blocker #4 already documented this. The skip message must include `pip install '.[dreamer]'` as remediation so a developer with GPU can enable locally.
- **D-30-03**: Use the existing `DreamerSubprocess` and `_create_scene_for_task` infrastructure (Phase 24). Do not re-implement subprocess management in the test — only orchestrate.
- **D-30-04**: Test file lives in `tests/dreamer/` (not `tests/`), consistent with the other DreamerV3 test files. The directory is implied by existing layout; if `tests/dreamer/` does not exist as a directory, use `tests/test_dreamerv3_subprocess_e2e.py` at the top level (planner checks before plan execution).
- **D-30-05**: Phase 30 verifies the Phase 26 fixes hold end-to-end — the unit tests in `tests/test_dreamer_subprocess.py` (5 tests, `TestSubprocessStdoutProtocol`) and `tests/test_dreamer_training.py` (2 tests, `TestTrainingMetricsSave`) remain the primary regression coverage. The E2E test is a smoke test that runs the full code path on real hardware; it is the deferred DMV3-03 E2E validation.

## Risks

- **Phase 29 (TASK-02)**: The 6 `PARAM_BOUNDS` dictionaries encode progressive parameter changes (loose→strict), but the EASY/HARD scalar assignment (0.0/0.5/1.0) is a choice, not derivable. If `PARAM_BOUNDS[name] = [lo, hi]` with `lo < hi` (e.g., `time_limit: [30, 10]`), then 0.0 = loose (longer time) and 1.0 = strict (shorter time). If `lo > hi` (e.g., `tissue_stiffness: [0.5, 2.0]`), then 0.0 = strict and 1.0 = loose — INVERTED. The test must verify the *direction* is correct, not just that values differ. Implementation must choose EASY = 0.0 = loose, HARD = 1.0 = strict consistently; if any PARAM_BOUNDS is inverted, the implementation must flip its bounds or document the inversion.
- **Phase 30 (DreamerV3 E2E)**: Cannot be locally verified on macOS. The test is only meaningful on a GPU + dreamerv3 + jax environment. Risk of test being added but never run (silent skip on all dev machines). Mitigation: CI with GPU is the primary validation target; the test is the deferred DMV3-03 E2E, not a regression that needs local verification.

## Next Steps

1. `/gsd-discuss-phase 29` — clarify the TASK-02 design (enum vs scalar-internal, per-level override scope)
2. `/gsd-discuss-phase 30` — clarify the E2E test scope (100 steps is the floor; can it be lower for a smoke test?)
3. `/gsd-plan-phase 29` — decompose Phase 29 into 1–2 plans
4. `/gsd-plan-phase 30` — decompose Phase 30 into 1 plan
5. `/gsd-execute-phase 29` — implement and verify
6. `/gsd-execute-phase 30` — implement and verify (CI-only validation expected)
7. `/gsd-verify-work 29` + `/gsd-verify-work 30` — milestone close verification
8. `/gsd-complete-milestone` — archive and update PROJECT.md

---

*Roadmap defined: 2026-06-11 (v0.4.2 milestone start)*
*Last updated: 2026-06-11 after v0.4.2 roadmap creation*
