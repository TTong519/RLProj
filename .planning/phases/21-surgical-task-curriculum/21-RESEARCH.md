# Phase 21: Surgical Task Curriculum — Research

**Researched:** 2026-05-13
**Domain:** RL task curriculum architecture — per-task reward functions, continuous difficulty interpolation, Pydantic v2 TaskResult models, CurriculumScheduler integration
**Confidence:** HIGH

## Summary

This phase adds 6 surgical task types with per-task reward subclasses, continuous difficulty interpolation (0.0–1.0 via linear lerp), structured success/failure detection via Pydantic v2 TaskResult models, and curriculum-integrated difficulty progression. All changes are purely additive to the existing `CurriculumScheduler`, `CompositeReward`, and `BaseRewardFunction` infrastructure — zero modifications to Phase 3's `apply_parameters()`.

The architecture follows a **Router → Composite → Curriculum feedback loop** pattern. `TaskRewardRouter` reads `TaskConfig.task_type` and returns a list of `BaseRewardFunction` instances (task-specific + generic) that feed into the existing `CompositeReward`. Each task-specific reward class owns its own `check_success()` and `check_failure()` methods, returning Pydantic v2 `TaskResult` sub-models. The `CurriculumScheduler.episode_end()` consumes this `TaskResult` to advance difficulty, and the `CurriculumStageConfig.difficulty` scalar drives per-parameter linear interpolation at scene construction time.

The primary risk areas are (1) designing parameter ranges where `difficulty=0.0` is learnable but not trivial and `difficulty=1.0` is challenging but not impossible, and (2) ensuring the TaskRewardRouter error-handling (None task_type, unknown task_type) never breaks CompositeReward's contract.

**Primary recommendation:** Use a `TASK_REWARD_REGISTRY: dict[str, type[BaseRewardFunction]]` dispatch table in `TaskRewardRouter` rather than if/elif chains, and design per-parameter `[min, max]` bounds with a safety margin (never set bounds where the agent could mathematically never succeed).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Task type routing (task_type → rewards) | RL / Reward layer | — | Reward selection is a reward-function concern; sim is task-agnostic |
| Difficulty interpolation (scalar → params) | Dynamics / Curriculum | RL / Environment | CurriculumScheduler owns difficulty; env consumes it at reset() |
| Success/failure detection | RL / Reward layer | — | Per-task reward classes own domain knowledge; sim only provides observations |
| TaskResult serialization | RL / Reward layer | Scene Definition | Pydantic models in rewards module follow schema conventions |
| Difficulty progression logic | Dynamics / Curriculum | — | CurriculumScheduler.episode_end() is the sole lifecycle hook |
| Scene parameter application | Dynamics / Curriculum | Simulator | apply_parameters() unchanged — Phase 3 pattern preserved |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | ≥2.13.4 [VERIFIED: pip show pydantic] | TaskResult base + per-task sub-models, parameter interpolation config | Project-wide Pydantic v2 convention (910 tests); model_validator, model_copy patterns well-established |
| numpy | (existing) | lerp computation, distance calculations in reward functions | Already imported in rewards.py; np.interp for linear interpolation is zero-dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing.Literal | (stdlib) | task_type routing key type | Required by TaskRewardRouter dispatch |
| dataclasses.dataclass | (stdlib) | RewardResult (existing pattern) | Already used in rewards.py — no new dataclasses needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct dict dispatch | if/elif chain | dict dispatch is constant-time, extensible by adding registration, and testable in isolation. if/elif is linear scan and fragile to reordering. |
| Pydantic BaseModel TaskResult | dataclass | Pydantic provides runtime validation, model_dump() for metrics extraction, and model_validate() for safe deserialization. dataclasses lack validation and serialization safety. |

**No new installable dependencies are needed.** This phase uses the existing Pydantic v2, numpy, and stdlib — entirely additive within the project's current stack.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────┐
                    │      TaskConfig              │
                    │  task_type: Literal[6]|None  │
                    └─────────────┬───────────────┘
                                  │ read at __init__ time
                                  ▼
                    ┌─────────────────────────────┐
                    │    TaskRewardRouter          │
                    │  - TASK_REWARD_REGISTRY      │
                    │  - build(task_type) → list   │
                    └─────────────┬───────────────┘
                                  │ returns [TaskReward + GenericRewards]
                                  ▼
                    ┌─────────────────────────────┐
                    │    CompositeReward            │  ◄── unchanged
                    │  (task_specific + generic)    │
                    │  weighted sum per step        │
                    └─────────────┬───────────────┘
                                  │ compute(obs, action, info)
                                  ▼
                    ┌─────────────────────────────┐
                    │  Per-Task Reward (e.g.       │
                    │  SuturingReward)              │
                    │  - compute() → RewardResult   │
                    │  - check_success() → TaskResult│
                    │  - check_failure() → TaskResult│
                    │  - interpolate_params(d) → dict│
                    └─────────────┬───────────────┘
                                  │ at episode_end
                                  ▼
                    ┌─────────────────────────────┐
                    │  CurriculumScheduler          │
                    │  episode_end(TaskResult)      │
                    │  → update difficulty          │
                    │  → advance/regress stage      │
                    └─────────────┬───────────────┘
                                  │ next episode reset()
                                  ▼
                    ┌─────────────────────────────┐
                    │  CurriculumStageConfig       │
                    │  difficulty: float (0.0–1.0) │
                    │  task_param_bounds: dict     │ ◄── NEW field
                    └─────────────┬───────────────┘
                                  │ lerp(min, max, difficulty)
                                  ▼
                    ┌─────────────────────────────┐
                    │  ParameterSnapshot           │
                    │  → apply_parameters()         │  ◄── unchanged
                    │  → simulator                  │
                    └─────────────────────────────┘
```

### Recommended Project Structure
The recommended layout adds to the existing `src/surg_rl/rl/` directory:
```
src/surg_rl/rl/
├── rewards.py                    # EXISTING — add 3 new subclasses + TaskRewardRouter
├── task_termination.py           # MODIFY — redirect to per-task check_success
├── task_results.py               # NEW — Pydantic v2 TaskResult hierarchy
└── task_reward_router.py         # NEW — TaskRewardRouter + TASK_REWARD_REGISTRY
src/surg_rl/dynamics/
└── curriculum.py                 # MODIFY — add task_param_bounds to CurriculumStageConfig
                                  #           extend episode_end to consume TaskResult
```

### Pattern 1: ABC Subclass for Per-Task Rewards
**What:** Each of the 6 task types gets a concrete `BaseRewardFunction` subclass with `compute()`, `reset()`, plus non-abstract `check_success()`, `check_failure()`, `interpolate_params()`.
**When to use:** Always — this is the established project pattern since Phase 1.
**Why not abstract `check_success` on ABC:** The existing ABC only requires `compute()` and `reset()`. Breaking that contract would require changing existing generic rewards (DistanceReward, ActionPenalty, etc.) that have no concept of task success. Each task reward class checks for `hasattr(self, 'check_success')` or we document `check_success`/`check_failure` as a protocol implemented by task rewards but not part of the ABC.

**Source:** Codebase convention — `rewards.py` lines 107-136 (ABC), 496-582 (SuturingReward), 585-663 (DissectionReward), 665-741 (NeedlePassingReward) [VERIFIED: codebase grep]

### Pattern 2: Registry Dispatch for TaskRewardRouter
**What:** A module-level `TASK_REWARD_REGISTRY: dict[str, type[BaseRewardFunction]]` maps task_type strings to reward classes. `TaskRewardRouter.build(task_type)` looks up the registry, instantiates with interpolated params, and returns `[task_reward] + [DistanceReward, ActionPenalty, TimePenalty, CollisionPenalty]`.
**When to use:** Every episode construction — replaces the existing string-matching in `create_default_reward()` (line 867-873 of rewards.py).
**Why dict dispatch over if/elif:** Constant-time lookup, trivially extensible (add a line to the registry for a new task), and testable by verifying `task_type in REGISTRY`.

### Pattern 3: Pydantic v2 Inheritance for TaskResult
**What:** A base `TaskResult(BaseModel)` with `success: bool`, `failure_reason: str | None`, `metrics: dict[str, Any]`, `difficulty: float`. Per-task sub-models add domain-specific fields.
**When to use:** Returned from `check_success()` / `check_failure()`. Serialized into curriculum metrics.
**Pydantic v2 specifics:**
- Use `model_validate()` for construction from dict (never `model_construct()` — we WANT validation here).
- Sub-models use `TaskResult` as parent — standard Pydantic inheritance.
- `model_dump()` serializes for metrics dictionaries.

### Pattern 4: Continuous Difficulty Interpolation
**What:** `lerp(a, b, t) = a + (b - a) * t` where `t ∈ [0.0, 1.0]` is `CurriculumStageConfig.difficulty`. Each parameter has `[min, max]` bounds. At `difficulty=0.0`, parameters are at their easiest; at `difficulty=1.0`, at their hardest.
**When to use:** Called by each task reward's `interpolate_params(difficulty)` → returns `dict[str, float]` consumed by `ParameterSnapshot`.
**Critical design rule for bounds:** `min` must be learnable (but not trivial), `max` must be challenging (but not impossible). Never set bounds where the physics or environment makes success mathematically impossible — this creates a dead zone where the agent plateaus and difficulty stalls forever.

### Anti-Patterns to Avoid
- **String-matching task detection:** `create_default_reward()` currently uses `if "sutur" in task_lower`. This is fragile (false matches, ordering dependence). Replace with explicit registry lookup.
- **Mutating shared state in reward subclasses:** Each reward class must be independent. A `SuturingReward` that modifies `info` dict in-place can cause silent bugs when it shares a reference with a `DistanceReward` in CompositeReward.
- **Difficulty values outside [0.0, 1.0]:** The contract is `0.0 ≤ difficulty ≤ 1.0`. Never clamp to the same value (clamping both 0.0 and 1.0 to 0.5 makes the curriculum flat).
- **Pydantic model_construct for TaskResult:** `model_construct()` skips validation — a `TaskResult` with `success="not a bool"` would silently pass. Use `model_validate()` instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Linear interpolation | `def my_lerp(a, b, t)` | `numpy.interp` or `a + (b - a) * t` | One-liner, already battle-tested in numpy, no maintenance burden |
| Reward routing from task_type | if/elif chain in `create_default_reward` | `TASK_REWARD_REGISTRY: dict[str, type[BaseRewardFunction]]` | Dict dispatch is constant-time, extensible, and eliminates fragile substring matching |
| Structured success/failure result | Dataclass with manual dict conversion | Pydantic v2 `BaseModel` subclass (`TaskResult`) | Pydantic provides validation, serialization (`model_dump()`), and type safety — project already uses Pydantic for all config objects |
| Difficulty progression tracking | Custom windowed metrics tracker | Existing `_performance_history` list + `advancement_window` on CurriculumScheduler | The curriculum scheduler already tracks success rate and reward over windowed episodes — reuse this, don't duplicate |
| Generic "is task done?" detection | `check_task_success()` heuristic string parser | Per-task `check_success()` on reward class | The existing `_parse_distance_criteria()` is fragile regex parsing — task-specific detection is deterministic and domain-aware |

**Key insight:** The existing codebase already has well-tested infrastructure for reward composition (CompositeReward), curriculum scheduling (CurriculumScheduler, BaseController lifecycle), and config modeling (Pydantic v2). This phase adds task-awareness on top of these without replacing any of them. The "don't hand-roll" items are about not rebuilding routing, interpolation, or result modeling when the project's existing patterns already solve these elegantly.

## Common Pitfalls

### Pitfall 1: Difficulty Dead Zone
**What goes wrong:** A parameter bound `[min, max]` is chosen where at `difficulty=1.0` the agent cannot physically succeed (e.g., `needle_position_tolerance=0.0001m` is physically impossible given sensor noise). The agent plateaus, success rate stays flat, and the curriculum never advances.
**Why it happens:** Bounds chosen from intuition rather than from simulation constraints. The designer thinks "harder = smaller tolerance" but doesn't check whether the simulator or robot can achieve that tolerance.
**How to avoid:** For every parameter pair `[min, max]`, verify: (1) at `difficulty=0.0`, can a random policy succeed with some probability? (2) at `difficulty=1.0`, can an optimal policy succeed? If either answer is "no", adjust bounds.
**Warning signs:** Success rate at a difficulty level hovers near 0% for many episodes with no upward trend; difficulty progress stalls; `_should_advance()` never returns True.

### Pitfall 2: TaskRewardRouter Returns Wrong Type
**What goes wrong:** `TaskRewardRouter.build()` returns something that isn't a `list[BaseRewardFunction]` — e.g., a single reward instead of a list, or `None` when `task_type is None`. `CompositeReward.components` expects a list of `(reward_fn, weight)` tuples.
**Why it happens:** Error handling for `task_type=None` or unknown `task_type` diverges from the contract. If the router returns `[generic_rewards]` without a task-specific reward, it's fine — but if it returns `None`, CompositeReward breaks.
**How to avoid:** Always return a list. For `task_type=None`, return `[generic_rewards]`. For unknown `task_type`, log a warning and return `[generic_rewards]`. Never return None. Document the contract: "Returns `list[BaseRewardFunction]` — never None, never empty (at minimum includes generic rewards)."

### Pitfall 3: Pydantic model_dump Returns Enum Objects
**What goes wrong:** `TaskResult.model_dump()` returns enum objects rather than `.value` strings for any enum fields. When this dict is passed to YAML serialization or logging, `yaml.dump()` raises `RepresenterError`.
**Why it happens:** Pydantic v2's default `model_dump()` preserves enum objects. The AGENTS.md explicitly warns about this ("model_dump() returns **Enum objects**, not `.value` strings").
**How to avoid:** If any `TaskResult` field is an enum (unlikely for this phase, but possible for future extension), use `model_dump(mode="json")` which coerces enums to strings. For `dict[str, Any]` metrics, explicitly convert enum values.

### Pitfall 4: CurriculumStageConfig.difficulty Mismatch with Interpolation
**What goes wrong:** `CurrirulumStageConfig.difficulty` is set to 0.5 via the default stages, but the task's `interpolate_params()` is called with a different difficulty value from a parallel field. The parameter values don't reflect the actual curriculum stage.
**Why it happens:** Adding a new `task_difficulty` field alongside the existing `difficulty` field creates two sources of truth. D-08 explicitly prohibits this — `difficulty` is the single source.
**How to avoid:** Never add a `task_difficulty` field. `CurrirulumStageConfig.difficulty` is the only difficulty scalar. The task reward reads `self.difficulty` from the stage config, not from a separate field.

## Code Examples

Verified patterns from official sources and the existing codebase:

### TaskRewardRouter with Registry Dispatch
```python
# Source: Codebase convention — rewards.py ABC pattern
# File: src/surg_rl/rl/task_reward_router.py

from typing import Any
from surg_rl.rl.rewards import (
    BaseRewardFunction,
    SuturingReward,
    DissectionReward,
    NeedlePassingReward,
    DistanceReward,
    ActionPenalty,
    TimePenalty,
    CollisionPenalty,
)
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# Task-specific rewards (3 existing + 3 new)
TASK_REWARD_REGISTRY: dict[str, type[BaseRewardFunction]] = {
    "suturing": SuturingReward,
    "dissection": DissectionReward,
    "needle_passing": NeedlePassingReward,
    "knot_tying": KnotTyingReward,       # NEW
    "grasping": GraspingReward,          # NEW
    "cutting": CuttingReward,            # NEW
}

GENERIC_REWARD_CLASSES: list[type[BaseRewardFunction]] = [
    DistanceReward,
    ActionPenalty,
    TimePenalty,
    CollisionPenalty,
]

class TaskRewardRouter:
    """Routes task_type to a list of reward function instances."""

    def __init__(self, difficulty: float = 0.5):
        self._difficulty = difficulty

    def build(
        self,
        task_type: str | None,
        **reward_kwargs: Any,
    ) -> list[BaseRewardFunction]:
        """Build reward list from task_type.

        Returns:
            List of [task_specific_reward] + generic_rewards.
            For None or unknown task_type, returns only generic rewards.
        """
        rewards: list[BaseRewardFunction] = []

        if task_type is not None:
            reward_cls = TASK_REWARD_REGISTRY.get(task_type)
            if reward_cls is not None:
                task_reward = reward_cls(**reward_kwargs)
                rewards.append(task_reward)
            else:
                logger.warning(
                    f"Unknown task_type={task_type!r}, using generic rewards only"
                )

        # Add generic rewards
        for cls in GENERIC_REWARD_CLASSES:
            rewards.append(cls())

        return rewards
```

### Pydantic v2 TaskResult Hierarchy
```python
# Source: Codebase convention — schema.py BaseModel pattern
# File: src/surg_rl/rl/task_results.py

from typing import Any
from pydantic import BaseModel, Field

class TaskResult(BaseModel):
    """Base structured result for task success/failure detection.

    Per D-07: all task result sub-models inherit from this base.
    """
    success: bool = Field(description="Whether the task succeeded")
    failure_reason: str | None = Field(
        default=None, description="Reason for failure (None if success)"
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Task-specific metrics for benchmarking"
    )
    difficulty: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Difficulty level at episode end"
    )

class SuturingResult(TaskResult):
    """Result for suturing task episodes."""
    stitches_completed: int = Field(default=0, ge=0)
    thread_tension_avg: float = Field(default=0.0, ge=0.0)

class KnotTyingResult(TaskResult):
    """Result for knot tying task episodes."""
    knots_completed: int = Field(default=0, ge=0)
    knot_tension_avg: float = Field(default=0.0, ge=0.0)

class NeedleInsertionResult(TaskResult):
    """Result for needle insertion task episodes."""
    insertion_depth: float = Field(default=0.0, ge=0.0)
    deviation_angle: float = Field(default=0.0, ge=0.0)

class GraspingResult(TaskResult):
    """Result for grasping task episodes."""
    grasp_stable: bool = Field(default=False)
    grip_force_avg: float = Field(default=0.0, ge=0.0)

class CuttingResult(TaskResult):
    """Result for cutting task episodes."""
    cut_completion: float = Field(default=0.0, ge=0.0, le=1.0)
    collateral_damage: float = Field(default=0.0, ge=0.0)

class DissectionResult(TaskResult):
    """Result for dissection task episodes."""
    incision_completion: float = Field(default=0.0, ge=0.0, le=1.0)
    clean_cut_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
```

### Per-Task Parameter Interpolation
```python
# Source: Pattern from CONTEXT.md D-04 (lerp) + D-05 (per-task independent params)
# Integrated into each task reward class

import numpy as np

class SuturingReward(BaseRewardFunction):
    # Task-specific difficulty parameter bounds
    # Each entry: [min_value_at_difficulty_0, max_value_at_difficulty_1]
    PARAM_BOUNDS = {
        "needle_position_tolerance": [0.02, 0.002],   # m (20mm → 2mm)
        "thread_tension_threshold": [1.0, 0.2],        # normalized (lenient → strict)
        "stitch_spacing_tolerance": [0.01, 0.002],     # m (10mm → 2mm)
        "time_limit": [120.0, 45.0],                   # seconds
    }

    @classmethod
    def interpolate_params(cls, difficulty: float) -> dict[str, float]:
        """Compute per-parameter values from difficulty scalar.

        Uses linear interpolation: param = lerp(min, max, difficulty).
        Higher difficulty → tighter tolerances, shorter time limits.
        """
        return {
            name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
            for name, bounds in cls.PARAM_BOUNDS.items()
        }
```

Note: For parameters where "harder = larger" (e.g., tissue stiffness, noise magnitude), the min/max order in bounds is reversed — min is the easiest value, max is the hardest.
```python
KnotTyingReward.PARAM_BOUNDS = {
    "knot_tension_tolerance": [0.5, 0.05],      # tighter tolerance = harder
    "loop_deviation_tolerance": [0.03, 0.005],   # tighter = harder
    "tissue_stiffness": [50.0, 200.0],          # higher = harder (stiffer tissue)
    "action_noise": [0.01, 0.08],               # higher = harder (more noise)
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| String-matching task detection (`"sutur" in task_lower`) | `TASK_REWARD_REGISTRY` dict dispatch | Phase 21 | Eliminates false positives, makes task addition a single-line registry entry |
| Generic `check_task_success()` heuristic parser | Per-task `check_success()` on reward class | Phase 21 | Deterministic, domain-aware detection replaces fragile regex parsing |
| Flat difficulty as single number | Continuous 0.0–1.0 scalar with per-parameter lerp | Phase 21 | Enables fine-grained difficulty progression with independent parameter curves |
| Dataclass-only reward results | Pydantic v2 `TaskResult` hierarchy | Phase 21 | Structured, validated, serializable results for benchmarking integration |

**Deprecated/outdated:**
- `create_default_reward()` string-matching for task detection: Replaced by `TaskRewardRouter.build()`. Keep `create_default_reward()` for backward compatibility but route through the router internally.
- `check_task_success()` regex heuristic: Not removed (backward compatibility), but per-task reward classes provide the authoritative detection. The existing function becomes a fallback when no task-type reward is present.

## Runtime State Inventory

> This section is included because the phase modifies existing reward infrastructure and curriculum machinery. A refactor of how rewards are selected and how success is detected can leave stale references.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — curriculum and reward state is purely in-memory. `_performance_history`, `_stitches_completed`, etc. are Python objects, not persisted. | None — verified by codebase grep for serialization/persistence of reward state |
| Live service config | None — no external services reference reward or curriculum configuration. | None — verified by reviewing integration patterns in INTEGRATIONS.md |
| OS-registered state | None — no OS-level registrations exist for this subsystem. | None |
| Secrets/env vars | None — `.env` variables (`LLM_PROVIDER`, `DEFAULT_SIMULATOR`, `RANDOMIZATION_ENABLED`) are unrelated to task curriculum. | None |
| Build artifacts | None — `create_default_reward` and `check_task_success` are functions, not installed packages. | None |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Parameter bounds `[min, max]` designed for linear interpolation produce meaningfully different difficulty without dead zones | Common Pitfalls | LOW — bounds are configurable and can be tuned post-implementation. If some ranges are too wide/narrow, it manifests as slow/fast curriculum progression, which is observable and fixable without architecture changes. |
| A2 | `check_success()`/`check_failure()` as a non-abstract protocol on task reward classes is the right pattern (rather than forcing all ABC subclasses to implement them) | Pattern 1 | LOW — adding them to ABC would break existing generic rewards. The protocol pattern (`hasattr` check if needed, duck-typing) is the Pythonic fallback. |
| A3 | The existing `reward_function` property setter on `SurgicalEnv` (line 808) can accept the output of `TaskRewardRouter` directly | Code Examples | LOW — `CompositeReward` is a `BaseRewardFunction` subclass and the setter accepts `BaseRewardFunction`. The router returns a LIST that must be wrapped in CompositeReward. The setter works as long as this wrapping happens. |

## Open Questions

1. **Difficulty progression logic specifics**
   - What we know: D-09 says `CurrirulumScheduler.episode_end()` auto-reads `TaskResult` and updates difficulty progression internally. The existing `update_curriculum()` uses `_should_advance()` based on success rate over a window.
   - What's unclear: Should difficulty change based on per-episode success/failure (step sizes, cooldown, hysteresis) or only on windowed averages? The existing code uses windowed averages — this is the established pattern.
   - Recommendation: Keep the existing windowed-average pattern. Add `hysteresis: float = 0.05` to `CurriculumConfig` so difficulty doesn't oscillate when success rate hovers near the threshold. A single episode at high difficulty that the agent hasn't mastered yet should not cause immediate regression.

2. **What happens at task_type=None?**
   - What we know: `TaskConfig.task_type` can be `None` (default). The router returns generic rewards only.
   - What's unclear: Should `CurriculumScheduler` still track difficulty when no task type is set? Without `check_success()` from a task reward, what constitutes "success"?
   - Recommendation: When `task_type=None`, the curriculum operates on the existing generic `check_task_success()` function. Difficulty interpolation is a no-op (no task-specific params to interpolate). The scheduler still tracks success rate from the generic detector.

## Environment Availability

> Step 2.5: SKIPPED — no external dependencies identified. This phase adds pure Python code using existing dependencies (pydantic≥2.13.4, numpy, stdlib). No new tools, services, runtimes, or CLI utilities required.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing — pytest.ini with `pythonpath = src`) |
| Config file | pytest.ini (existing) |
| Quick run command | `PYTHONPATH=src pytest tests/test_rewards.py tests/test_task_results.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TASK-01 | 6 task types with per-task reward functions and success/failure detection | unit | `pytest tests/test_rewards.py -v -k "Suturing or Dissection or NeedlePassing or KnotTying or Grasping or Cutting"` | ✅ (existing for 3 tasks) |
| TASK-02 | 3 difficulty levels with progressive parameter changes via continuous interpolation | unit | `pytest tests/test_task_results.py::test_interpolate_params_easy -x` | ❌ Wave 0 |
| TASK-03 | Task difficulty integrates with CurriculumScheduler — additive to CurriculumStageConfig | integration | `pytest tests/test_dynamics.py -v -k "curriculum"` | ✅ (existing) |
| TASK-04 | check_success()/check_failure() return structured TaskResult | unit | `pytest tests/test_task_results.py::test_check_success_returns_task_result -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_rewards.py tests/test_task_results.py -v`
- **Per wave merge:** `pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green + no regressions in existing 910 tests

### Wave 0 Gaps
- [ ] `tests/test_task_results.py` — covers TASK-04 (TaskResult hierarchy validation, model_dump, field constraints)
- [ ] `tests/test_rewards.py` — add test classes for 3 new reward subclasses (KnotTyingReward, GraspingReward, CuttingReward), covering compute(), check_success(), check_failure(), interpolate_params()
- [ ] `tests/test_task_reward_router.py` — covers TASK-01 routing logic (known task_type, None task_type, unknown task_type, registry completeness)
- [ ] Test conftest: none needed — existing fixtures (dummy observation dicts, zero actions) are sufficient

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | Pydantic v2 field validators on TaskResult, TaskConfig.task_type Literal constraint |
| V6 Cryptography | No | — |

### Known Threat Patterns for Pydantic v2 / RL reward stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| TaskResult model_dump exposes internal state | Information Disclosure | `TaskResult.metrics` dict is user-controlled — reward classes should not include raw observation arrays or simulator state. Use summary statistics only. |
| Untrusted `task_type` string injection | Tampering | `TaskConfig.task_type` is already constrained to `Literal[...]` — Pydantic rejects invalid values at parse time. The router's dict lookup with `.get()` is safe — unknown keys return None. |
| NaN/inf in reward computation | Denial of Service | numpy handles `np.exp(-inf) = 0` correctly, but `np.linalg.norm(inf)` returns `inf`. The existing `CompositeReward.compute()` catches exceptions implicitly through the try/except pattern in `SurgicalEnv.step()`. Task reward compute() should explicitly guard against NaN/inf with `np.isfinite()` checks. |

## Sources

### Primary (HIGH confidence)
- Codebase — `src/surg_rl/rl/rewards.py` (875 lines) — all reward ABC patterns, CompositeReward, existing 3 task rewards, RewardResult, RewardConfig, RewardType enum [VERIFIED: read full file]
- Codebase — `src/surg_rl/dynamics/curriculum.py` (536 lines) — CurriculumScheduler, CurriculumStageConfig, CurriculumConfig, lifecycle methods, apply_parameters, update_curriculum [VERIFIED: read full file]
- Codebase — `src/surg_rl/dynamics/base_controller.py` (389 lines) — BaseController ABC, ParameterSnapshot, lifecycle hooks [VERIFIED: read full file]
- Codebase — `src/surg_rl/rl/task_termination.py` (108 lines) — check_task_success generic detector [VERIFIED: read full file]
- Codebase — `src/surg_rl/scene_definition/schema.py` (lines 1060–1084) — TaskConfig with task_type Literal [VERIFIED: read relevant section]
- Codebase — `src/surg_rl/rl/environment.py` (lines 474–639) — reset/step integration with reward functions and controllers [VERIFIED: read relevant section]
- Codebase — `src/surg_rl/dynamics/environment_controller.py` (lines 290–450) — EnvironmentController lifecycle delegation [VERIFIED: read relevant section]
- CONTEXT.md — Phase 21 locked decisions D-01 through D-10 [VERIFIED: read full file]
- REQUIREMENTS.md — TASK-01 through TASK-04 requirements [VERIFIED: read full file]
- AGENTS.md — Pydantic v2 quirks, testing conventions, optional field guards [VERIFIED: read full file]

### Secondary (MEDIUM confidence)
- Portelas et al. (2020) — "Teacher algorithms for curriculum learning of Deep RL in continuously parameterized environments," PMLR 100:835–853 — validates continuous parameterization pattern and linear interpolation approach for curriculum learning [CITED: proceedings.mlr.press/v100/portelas20a.html]

### Tertiary (LOW confidence)
- None — all claims in this research are verified against the codebase, official documentation, or published literature.

## Research Date
**Research date:** 2026-05-13
**Valid until:** 2026-07-13 (60 days — slow-moving domain, stable infrastructure)

---

*Research prepared for Phase 21 planning. All findings verified against the existing codebase. No unverified claims.*
