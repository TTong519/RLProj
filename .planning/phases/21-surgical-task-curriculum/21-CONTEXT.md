# Phase 21: Surgical Task Curriculum — Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Define 6 surgical task types with per-task reward functions, 3 difficulty levels via continuous scalar interpolation, structured success/failure detection via Pydantic TaskResult models, and integration with the existing `CurriculumScheduler`. All additions are purely additive — the Phase 3 `CurriculumScheduler.apply_parameters()` is never modified.

</domain>

<decisions>
## Implementation Decisions

### Reward function architecture
- **D-01:** Per-task `BaseRewardFunction` subclasses for all 6 task types: 3 existing (`SuturingReward`, `DissectionReward`, `NeedlePassingReward`) + 3 new (`KnotTyingReward`, `GraspingReward`, `CuttingReward`)
- **D-02:** `TaskRewardRouter` reads `TaskConfig.task_type`, returns a list of `[task_specific_reward(s)] + [generic_rewards]` (DistanceReward, ActionPenalty, TimePenalty, etc.)
- **D-03:** Router returns list of `BaseRewardFunction` instances — plugs into existing `CompositeReward` without any changes to CompositeReward

### Difficulty parametrization
- **D-04:** Continuous scalar difficulty `0.0–1.0` with linear interpolation per parameter: `param = lerp(min, max, difficulty)` where `min`/`max` are per-parameter bounds
- **D-05:** Fully per-task independent parameter sets — each task type defines its own complete vocabulary of interpolated scene parameters (e.g. suturing defines needle_position_tolerance, thread_tension_threshold, stitch_spacing; grasping defines jaw_aperture, grip_force, approach_angle)

### Success/failure detection
- **D-06:** Per-task reward classes own `check_success()` and `check_failure()` methods — self-contained detection logic (suturing reward knows what suturing success looks like)
- **D-07:** Pydantic v2 `TaskResult` model as return type with base fields (`success: bool`, `failure_reason: str | None`, `metrics: dict[str, Any]`) + per-task sub-models (e.g. `SuturingResult(TaskResult)` adds `stitches_completed: int`, `thread_tension_avg: float`)

### CurriculumScheduler integration
- **D-08:** `CurriculumStageConfig.difficulty` float is the single source of truth — `task_difficulty` is this same field, not a new parallel field
- **D-09:** `CurriculumScheduler.episode_end()` auto-reads `TaskResult` from the environment, updates difficulty progression internally, and triggers parameter recalculation — no separate hook infrastructure needed
- **D-10:** Zero modifications to the Phase 3 `apply_parameters()` method — all task curriculum changes are additive fields + methods on `CurriculumScheduler` and `CurriculumStageConfig`

### OpenCode's Discretion
- Exact reward function implementation for `KnotTyingReward`, `GraspingReward`, `CuttingReward` (reward signal design per task semantics)
- Per-task parameter vocabulary and interpolation bounds for difficulty levels
- `TaskResult` model hierarchy design (base class + per-task sub-models)
- `TaskRewardRouter` implementation details (generic reward selection, error handling for None task_type)
- Difficulty progression logic (advancement thresholds, step sizes, cooldown between difficulty changes)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 21 — success criteria (TASK-01..TASK-04)
- `.planning/REQUIREMENTS.md` — TASK-01 through TASK-04 requirements

### Schema contracts (from Phase 19)
- `src/surg_rl/scene_definition/schema.py` — `TaskConfig` (line 1060, has `task_type: Literal[...] | None`), `TaskObjective` (line 1009), `ConstraintConfig` (line 1017), `RewardShaping` (line 1047)

### Existing reward infrastructure
- `src/surg_rl/rl/rewards.py` (875 lines) — `BaseRewardFunction` ABC (line 107), `CompositeReward` (line 744), existing task rewards: `SuturingReward` (line 496), `DissectionReward` (line 585), `NeedlePassingReward` (line 665)

### Existing curriculum infrastructure
- `src/surg_rl/dynamics/curriculum.py` (536 lines) — `CurriculumScheduler` (line 79), `CurriculumStageConfig` (line 36, has `difficulty: float = 0.5`), `CurriculumConfig` (line 59), `apply_parameters()` (line 294 — never modified)

### Task termination
- `src/surg_rl/rl/task_termination.py` (108 lines) — `check_task_success()` existing generic detector

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — RL layer, reward function hierarchy, dynamics controllers
- `.planning/phases/19-schema-foundation/19-CONTEXT.md` — D-04 (TaskConfig.task_type field contract)
- `.planning/phases/20-real-surgical-assets/20-CONTEXT.md` — real instruments available for task construction

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseRewardFunction` ABC with `compute()`, `reset()` interface — all 6 task rewards follow this
- `CompositeReward` — existing weighted sum container, zero changes needed
- `RewardResult` dataclass with `total`, `components`, `info` fields — task rewards return this
- `CurriculumScheduler.episode_end()` — existing lifecycle hook where difficulty update plugs in
- `CurriculumStageConfig.difficulty: float = 0.5` — the difficulty scalar, Phase 21 expands its semantics
- `TaskConfig.task_type: Literal[...] | None` — the routing key for `TaskRewardRouter`

### Established Patterns
- ABC + concrete subclass pattern for reward functions — consistent since Phase 1
- Composite pattern for reward aggregation — `CompositeReward` wraps sub-rewards
- `BaseController` lifecycle (`start`, `reset`, `step_update`, `episode_end`) for dynamics controllers
- Pydantic v2 models for config objects
- Additive extensions (never rewrites) for Phase 3 curriculum machinery

### Integration Points
- `SurgicalEnv._compute_reward()` — where `TaskRewardRouter` output feeds into `CompositeReward`
- `SurgicalEnv.reset()` — where difficulty params from `CurriculumScheduler` modify the scene
- `CurriculumScheduler.episode_end()` — where `TaskResult` feeds difficulty progression
- `CurriculumStageConfig` — extended with task-parameter interpolation dictionaries
- `rl/rewards.py` — 3 new reward subclasses added alongside existing ones

</code_context>

<deferred>
## Deferred Ideas

- Task chain/sequence composer (grasp → cut → suture) — TASK-05, deferred to v0.5.0 per REQUIREMENTS.md
- RLlib-backed centralized critic for MARL — MARL-05, Phase 22 uses independent SB3 policies only
- Visual task demonstrations / curriculum from recorded expert trajectories — out of scope

</deferred>

---

*Phase: 21-surgical-task-curriculum*
*Context gathered: 2026-05-13*
