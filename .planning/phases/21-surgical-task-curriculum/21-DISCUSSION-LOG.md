# Phase 21: Surgical Task Curriculum — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 21-surgical-task-curriculum
**Areas discussed:** Reward function architecture, Difficulty parametrization, Success/failure detection, CurriculumScheduler integration

---

## Reward function architecture

### Question 1: How should reward functions dispatch per task type?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-task class + router | Each task type gets its own BaseRewardFunction subclass, TaskRewardRouter dispatches | ✓ |
| Single configurable class | One SurgicalTaskReward configured from TaskConfig fields | |
| CompositeReward knows tasks | Extend CompositeReward with task_type awareness | |

**User's choice:** Per-task class + router (Recommended)

### Question 2: How does the task reward router plug into existing CompositeReward?

| Option | Description | Selected |
|--------|-------------|----------|
| Router returns reward list | Returns list of BaseRewardFunction instances, CompositeReward wraps them | ✓ |
| Router as BaseRewardFunction | Router is a BaseRewardFunction subclass, delegates compute() | |

**User's choice:** Router returns reward list — zero changes to CompositeReward

---

## Difficulty parametrization

### Question 1: How should difficulty levels parametrize scene parameters?

| Option | Description | Selected |
|--------|-------------|----------|
| Declarative tables | Per-task × difficulty param tables | |
| Continuous scalar mapping | 0.0–1.0 scalar with interpolation | ✓ |
| Scene override files | JSON/YAML scene overrides per difficulty | |

**User's choice:** Continuous scalar mapping

### Question 2: How should task-specific parameters map from the scalar difficulty?

| Option | Description | Selected |
|--------|-------------|----------|
| 3-band from float | 0.0–0.33=easy, 0.33–0.66=medium, 0.67–1.0=hard | |
| True continuous interpolation | lerp(min, max, difficulty) per parameter | ✓ |
| Scalar multiplier per param | param = difficulty * base | |

**User's choice:** True continuous interpolation

### Question 3: What parameters does difficulty interpolate for each task type?

| Option | Description | Selected |
|--------|-------------|----------|
| Generic base + task extensions | Common params (stiffness, tolerance) + task-specific | |
| Fully per-task independent | Each task defines its own complete param vocabulary | ✓ |
| Schema-driven | Params from existing schema fields | |

**User's choice:** Fully per-task independent

---

## Success/failure detection

### Question 1: Who owns per-task success/failure detection logic?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-task reward owns detection | Each reward class has check_success()/check_failure() | ✓ |
| Separate detector classes | TaskDetector hierarchy mirrors rewards | |
| Extend existing check_task_success | Single function with per-task_type branching | |

**User's choice:** Per-task reward owns detection (Recommended)

### Question 2: What's in the structured success/failure result?

| Option | Description | Selected |
|--------|-------------|----------|
| ROADMAP spec only | success, failure_reason, metrics dict | |
| Extended task details | Plus completion_time, task_progress, etc. | |
| Pydantic result model | TaskResult BaseModel + per-task sub-models | ✓ |

**User's choice:** Pydantic result model

---

## CurriculumScheduler integration

### Question 1: How does task_difficulty relate to existing CurriculumStageConfig.difficulty?

| Option | Description | Selected |
|--------|-------------|----------|
| Unified with existing float | task_difficulty IS the existing difficulty field | ✓ |
| New discrete field alongside float | Separate Literal field in parallel | |
| TaskConfig owns difficulty | Difficulty field moved to TaskConfig | |

**User's choice:** Unified with existing float (Recommended)

### Question 2: How does the curriculum scheduler trigger difficulty changes?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-advance + difficulty hook | Existing auto-advance bumps difficulty, Phase 21 adds hook for param recalc | ✓ |
| Independent difficulty + stage | Two separate levers, difficulty decoupled from stage | |
| Separate difficulty controller | New TaskDifficultyController manages difficulty | |

**User's choice:** Auto-advance + difficulty hook

### Question 3: Implementation approach for difficulty change mechanism?

| Option | Description | Selected |
|--------|-------------|----------|
| Hook-based notification | on_difficulty_change callback dict | |
| Scheduler owns the loop | episode_end() auto-reads TaskResult, updates difficulty directly | ✓ |
| You decide | | |

**User's choice:** Scheduler owns the loop

---

## Deferred Ideas

- Task chain/sequence composer (grasp → cut → suture) — TASK-05, v0.5.0
- RLlib-backed centralized critic for MARL — MARL-05, Phase 22 uses independent SB3 policies
- Visual task demonstrations — out of scope
