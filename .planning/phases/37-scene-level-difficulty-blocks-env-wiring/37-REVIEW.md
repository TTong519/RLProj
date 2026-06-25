---
phase: 37-scene-level-difficulty-blocks-env-wiring
reviewed: 2026-06-24T00:00:00Z
depth: deep
files_reviewed: 3
files_reviewed_list:
  - src/surg_rl/scene_definition/schema.py
  - src/surg_rl/rl/rewards.py
  - src/surg_rl/rl/environment.py
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 37: Code Review Report

**Reviewed:** 2026-06-24T00:00:00Z
**Depth:** deep
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the three production files for Phase 37 (scene-level `difficulty_blocks` + env wiring): the new `TaskConfig.difficulty_blocks` field + Pydantic v2 cycle-break, the extracted `apply_params` on the 6 task-reward subclasses, and the additive `_setup_rewards` branch in `SurgicalEnv`.

Deep verification performed by executing the Pydantic coercion edge cases (enum-name strings, stringified floats, float keys, enum keys, invalid names) and the YAML roundtrip — all coercion paths work correctly. The Pydantic v2 cycle-break (`from __future__ import annotations` + string forward-refs + late local import + `TaskConfig.model_rebuild()`) is correct: both `DifficultyLevel` and `DifficultyLevelConfig` are bound at module scope before the rebuild call, no model is left partially built, and `surg_rl.rl.difficulty` is a true leaf (no in-project imports). The Q4 `isinstance(difficulty, DifficultyLevel)` guard is correct because `CurriculumScheduler.current_difficulty` is typed `-> float` (verified in `dynamics/curriculum.py:228`), so continuous-curriculum difficulty always fails the guard and the blocks branch is inert — exactly the documented precedence.

No Critical issues found. Two Warnings relate to YAML serialization portability and a misleading override surface. Five Info items are style/defensive-coding nits.

## Warnings

### WR-01: `difficulty_blocks` enum keys produce non-portable YAML that `yaml.safe_load` cannot roundtrip

**File:** `src/surg_rl/scene_definition/schema.py:1122-1131` (and downstream `TaskConfig.model_dump()` consumers)
**Issue:** `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] | None` keeps `DifficultyLevel` enum objects as dict keys in `model_dump()`. Because `DifficultyLevel` is a `_FloatMixin(float, Enum)`, `yaml.dump()` does NOT raise `RepresenterError` (unlike the CLAUDE.md pitfall for plain Enums) — instead it emits `!!python/object/apply:surg_rl.rl.difficulty.DifficultyLevel` tags. Verified empirically: `yaml.safe_load(yaml.dump(tc.model_dump()))` raises `ConstructorError: could not determine a constructor for the tag 'tag:yaml.org,2002:python/object/apply:surg_rl.rl.difficulty.DifficultyLevel'`. Scene authors who persist scenes to YAML (a primary use case per `scene_definition/loader.py`) get output that cannot be reloaded with `safe_load`, and the output is non-portable to any non-Python consumer. The new `difficulty_blocks` field makes this worse than the pre-existing `difficulty_level` case because enum *keys* serialize to tagged Python objects, breaking even Python `safe_load`.
**Fix:** Add a `model_serializer` or a `to_yaml`-facing accessor on `TaskConfig` that converts enum keys/values to their `.value` (float) before YAML emission, or document that scenes with `difficulty_blocks` must be serialized via `model_dump(mode="json")` (which stringifies enum keys):
```python
# Scene authors should serialize via:
yaml.safe_dump(tc.model_dump(mode="json"), f)
# model_dump(mode="json") turns DifficultyLevel keys into "0.0"/"0.5"/"1.0"
# strings, which Pydantic's _coerce_difficulty_blocks_keys then re-accepts on load.
```
Alternatively, add a `@model_serializer(mode="wrap")` on `TaskConfig` that emits `difficulty_blocks` keyed by `level.value` for any serializer that requests `mode="python"`.

### WR-02: `apply_params` silently drops 3 of 4 override fields — override surface is misleading

**File:** `src/surg_rl/rl/rewards.py:736-745, 903-906, 1056-1059, 1226-1229, 1398-1401, 1566-1569`
**Issue:** Each of the 6 task-reward `apply_params` overrides maps EXACTLY ONE `PARAM_BOUNDS` key to a ctor field (Q1 MINIMAL Option a — documented). But `DifficultyLevelConfig` exposes 4 SET override fields (`tissue_stiffness`, `target_precision_tolerance`, `tool_position_noise`, `time_limit`), and `compose_difficulty_overrides` faithfully composes ALL of them into the params dict. The result: a scene author who sets `time_limit: 45.0` (or `tissue_stiffness`/`tool_position_noise` where unmapped) in a `difficulty_blocks[HARD]` block sees the override silently dropped — the reward behaves identically to the interpolated baseline for that key. For example, `CuttingReward.apply_params` only consumes `force_precision`; setting `tissue_stiffness` in a cutting block has zero effect on the reward (only `compose_difficulty_overrides` logs nothing for mapped-but-unconsumed keys). This is a false-sense-of-control hazard: the schema accepts the input, the wiring layer composes it, and the reward silently ignores it.
**Fix:** Either (a) widen each `apply_params` to consume all mapped PARAM_BOUNDS keys that have ctor fields (e.g. `SuturingReward` could also map `thread_tension_threshold` -> `tension_threshold`), or (b) have `compose_difficulty_overrides` log a WARNING when a SET override field has a concrete mapping in `ABSTRACT_TO_CONCRETE[task_type]` but the reward's `apply_params` will not consume it (the warning currently fires only for *unmapped* abstract fields, not for mapped-but-unconsumed ones). At minimum, surface the limitation in the `DifficultyLevelConfig` field docstrings so authors know which overrides are inert per task type.

## Info

### IN-01: Stale/misplaced `# noqa: UP037` suppression on `difficulty_blocks` annotation

**File:** `src/surg_rl/scene_definition/schema.py:1122`
**Issue:** `UP037` flags `Optional[X]` / `Union[X, Y]` usage and recommends `X | Y`. The annotation `"dict[DifficultyLevel, DifficultyLevelConfig] | None"` already uses the modern `| None` form, so UP037 would never fire here. The suppression is unnecessary (and since the annotation is a string, ruff does not even parse it for UP037).
**Fix:** Drop the `# noqa: UP037` comment; keep only the `# noqa: F821` (which IS needed for the forward-ref undefined name).

### IN-02: Lazy-local import of `compose_difficulty_overrides` is more conservative than the cycle requires

**File:** `src/surg_rl/rl/environment.py:542`
**Issue:** The comment cites "Pitfall 4 — NOT module-level" to avoid a cross-package import cycle. Tracing the import graph: `dynamics.difficulty_wiring` imports only `surg_rl.rl.difficulty` (a verified leaf, zero in-project imports) and `surg_rl.utils.logging`. Neither imports back into `surg_rl.rl.environment`, so a module-top `from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides` would be cycle-safe. The lazy-local import is harmless (and defensible as belt-and-suspenders defense against future drift in `difficulty_wiring`'s import set), but the stated rationale does not match the actual import graph.
**Fix:** Either move the import to module top (simpler, removes per-`_setup_rewards`-call import overhead — though cached in `sys.modules` so the overhead is negligible) OR update the comment to reflect that the laziness is defensive rather than cycle-required.

### IN-03: Redundant lazy import of `TASK_REWARD_REGISTRY` and redundant `hasattr` guard

**File:** `src/surg_rl/rl/environment.py:543, 559`
**Issue:** `from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY` is performed lazily inside `_setup_rewards`, but `task_reward_router` is already imported at module top (line 52: `from .task_reward_router import TaskRewardRouter`). The registry could be added to that top-level import with no cycle risk. Separately, `if hasattr(reward_list[0], "apply_params"):` is always True because `apply_params` is defined on `BaseRewardFunction` (rewards.py:186) and never removed by subclasses — the guard never short-circuits.
**Fix:** Add `TASK_REWARD_REGISTRY` to the existing module-top `from .task_reward_router import ...` line and drop the `hasattr` guard, calling `reward_list[0].apply_params(params)` directly.

### IN-04: `getattr(self._scene.task, "difficulty_blocks", None)` is redundant with the declared field

**File:** `src/surg_rl/rl/environment.py:530-534`
**Issue:** `difficulty_blocks` is now a declared Pydantic field on `TaskConfig`, so `self._scene.task.difficulty_blocks` always exists (default `None`). The `getattr(..., None)` fallback can never trigger.
**Fix:** Simplify to `blocks = self._scene.task.difficulty_blocks if self._scene.task is not None else None` — equivalent and clearer about the real guard (task being None).

### IN-05: Line 518 exceeds the project's 100-char line-length guideline

**File:** `src/surg_rl/rl/environment.py:518`
**Issue:** `        difficulty_float = float(difficulty.value) if isinstance(difficulty, DifficultyLevel) else float(difficulty)` is 116 characters. `ruff` ignores `E501` per CLAUDE.md, so this does not fail lint, but it diverges from the project's stated 100-char style.
**Fix:**
```python
difficulty_float = (
    float(difficulty.value) if isinstance(difficulty, DifficultyLevel)
    else float(difficulty)
)
```

---

_Reviewed: 2026-06-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_