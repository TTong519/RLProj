# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-29)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Phase 5 planning complete — ready to execute

## Current Position

Phase: 5 of 5 (Experiment Tracking + Infrastructure)
Plan: 0 of 2 planned (plans revised and validated)
Status: Ready to execute
Last activity: 2026-05-02 — Phase 5 plans revised after code review, 5 issues fixed

Progress: [████████████████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: ~13 minutes
- Total execution time: ~2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Critical Bug Fixes | 3/3 | 3 | ~10 min |
| 2. Action Space + Gripper | 3/3 | 3 | ~20 min |
| 3. Simulator Robustness | 2/2 | 2 | ~18 min |
| 4. Task Geometry + Assets | 2/2 | 2 | ~15 min |

## Phase 4 Summary

### What was built

1. **Task geometry observation wiring (TASK-01, TASK-02)**:
   - `TaskObjective.target_body: str | None` — additive schema extension
   - `_resolve_task_observations()` in PyBullet + MuJoCo simulators
   - Objective.name → observation field mapping via `_obs_field_for_name()`
   - Unified `incision_progress` computed as completion ratio from success_criteria text
   - None guards on fallbacks prevent overwriting explicitly-set values

2. **Real asset loading (TASK-03, TASK-04)**:
   - `SceneBuilder._missing_assets: set[str]` for deduplicated single-shot warnings
   - `SceneBuilder.load_urdf_asset()` → returns `Path | None`
   - PyBullet: real URDF loading via `p.loadURDF`, OBJ visual mesh via `createVisualShape(GEOM_MESH)`
   - MuJoCo: MJCF `<mesh>` asset + `type="mesh"` geom for tissue/instrument geometry
   - Always falls back to procedural primitives when assets are missing

### Commits

- `5506276` — 04-01 T1: add target_body field to TaskObjective schema
- `b9d3387` — 04-01 T2: implement target_body observation resolution in both backends
- `2b7f1a6` — 04-01 SUMMARY
- `c96fa1f` — 04-02 T1: add failing tests for asset fallback
- `a11813a` — 04-02 T2: add _missing_assets tracking and load_urdf_asset helper
- `9b8ec81` — 04-02 T3: wire real URDF and mesh loading into PyBullet simulator
- `64b7b9b` — 04-02 T4: wire real mesh loading into MuJoCo MJCF generation
- `084d8ec` — 04-02 T5: add integration tests for real URDF and mesh loading
- `42f9dc7` — 04-02 SUMMARY
- `cb7e228` — 04-REVIEW: code review — clean, 0 findings, 600 tests pass

### Verification
- 600 tests passed (up from 579 baseline)
- 0 failures, 0 regressions
- 2 xfailed (expected), 4 xpassed (known macOS soft-body issue)
- 21 new tests added: 12 task_geometry + 9 real_assets

## Phase 5 Planning Status

**Revisions applied after code review:**

| Issue | Plan | Fix |
|-------|------|-----|
| CLI typer.Option invalid syntax | 05-01 | Changed `str \| typer.Option(...)` to `str \| None = typer.Option(...)` |
| wandb_api_key added but unused | 05-01 | Wired into `WandbCallback.__init__` and `wandb.init(key=...)` |
| Missing curriculum/randomization logging | 05-01 | Added controller state logging to both callbacks (reusing TensorBoardCallback pattern) |
| Test: sys.modules manipulation unreliable | 05-01 | Added `test_log_metrics_with_controller` using MagicMock; kept import-skip test for coverage but documented limitation |
| Dockerfile: COPY file to itself | 05-02 | Fixed `COPY pyproject.toml pytest.ini pytest.ini` to `COPY pyproject.toml pytest.ini ./` |

**Ready for execution.**

*Updated: 2026-05-02*
