---
phase: 29-task-02-3-difficulty-levels
reviewed: 2026-06-12T18:45:00Z
depth: deep
reviewer: gsd-code-reviewer
files_reviewed: 9
files_reviewed_list:
  - src/surg_rl/rl/difficulty.py
  - src/surg_rl/rl/__init__.py
  - src/surg_rl/rl/rewards.py
  - src/surg_rl/rl/task_reward_router.py
  - src/surg_rl/scene_definition/schema.py
  - src/surg_rl/rl/environment.py
  - src/surg_rl/dynamics/curriculum.py
  - tests/test_difficulty_levels.py
  - tests/fixtures/scenes/suturing_difficulty_hard.json
findings:
  high: 0
  medium: 3
  low: 6
  total: 9
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-12T18:45:00Z
**Depth:** deep
**Files Reviewed:** 8 source files + 1 fixture
**Status:** issues_found

## Summary

Phase 29 introduces a `DifficultyLevel` enum (`EASY=0.0 / MEDIUM=0.5 / HARD=1.0`) threaded through `BaseRewardFunction` (no-op default + 6 task-subclass overrides), `TaskRewardRouter` (accepts enum or float, normalizes internally), `TaskConfig.difficulty_level` (Pydantic v2 field with float-value coercion), and `CurriculumStageConfig.difficulty` (widened union). The 5-commit TDD sequence is clean, the test suite is comprehensive (44 tests, all claimed passing), and the leaf-module import strategy for `difficulty.py` correctly avoids the immediate `rewards.py` ↔ `schema.py` cycle.

A deep cycle exists that the SUMMARY correctly identifies: `schema.py` (late import at line 1489) → `surg_rl.rl.difficulty` → `surg_rl.rl.__init__` → `environment.py` → `surg_rl.dynamics.environment_controller` → `surg_rl.scene_definition.schema` (partial). The 3-step pattern (string forward-ref + late import + `model_rebuild()`) correctly resolves it because `DomainRandomizationConfig` and `SceneDefinition` are both defined before the late import fires. A secondary cycle (via `loader.py` → `schema.py`) is broken by moving the `SceneLoader` import into a function-local import inside `SurgicalEnv._load_scene()`.

**The 9 findings below are all MEDIUM or LOW.** No HIGH/blocker issues were found. The implementation is correct for the documented use cases and the test suite covers the load-side of the schema integration comprehensively. The remaining concerns are about type-honesty (`current_difficulty` return type is a lie under union widening), fragility of the cycle-resolution pattern, missing end-to-end test coverage (env-construction with the fixture scene is not exercised), and minor docstring/comment drift.

**Overall recommendation:** **needs-fix (minor)**. The MEDIUM items should be addressed but do not block shipping; the LOW items can be deferred or are pre-existing patterns. No blocker for the phase to close.

---

## Critical Issues

*(none — no HIGH-severity findings)*

## Warnings

### WR-01: `CurriculumScheduler.current_difficulty` return type is a lie under union widening

**File:** `src/surg_rl/dynamics/curriculum.py:207-209`
**Issue:** The property is annotated `def current_difficulty(self) -> float`, but `CurriculumStageConfig.difficulty` is now `float | DifficultyLevel` (line 56). When a stage is constructed with `difficulty=DifficultyLevel.HARD`, `self._stages[stage].difficulty` returns the enum member (a `_FloatMixin` instance, which is a float subclass but is not a plain `float` in the type sense). The property then returns the enum member, violating its declared return type.

This is partially hidden by `_FloatMixin` semantics: `DifficultyLevel.HARD == 1.0` is True, `isinstance(..., float)` is True, `float(...)` works, and `int(...)` works — so numeric comparisons in `curriculum_info` and downstream consumers (lines 455, 465, 585) all behave as expected. But the type annotation is incorrect, and any consumer that does a strict `type(x) is float` check (like the test in `test_router_accepts_enum_normalizes_to_scalar` at test_difficulty_levels.py:266) would fail.

**Fix:** Update the annotation and normalize at the source:

```python
@property
def current_difficulty(self) -> float:
    """Current difficulty level (0.0 to 1.0)."""
    d = self._stages[self._current_stage].difficulty
    return float(d.value) if isinstance(d, DifficultyLevel) else float(d)
```

This keeps the property's contract honest regardless of which union arm was used at stage construction.

---

### WR-02: No end-to-end test that constructs `SurgicalEnv` from the HARD fixture scene

**File:** `tests/test_difficulty_levels.py:364-371` (gap) and `src/surg_rl/rl/environment.py:202-209` (untested wiring)
**Issue:** The 29-02 PLAN stated (success criterion #4, line 24 of the plan): *"`TaskRewardRouter` ... `build(task_type)` ... produce equivalent reward instances on every mapped field"* and the integration test goal was to *"load a fixture scene JSON with `task.difficulty_level = 1.0` and assert the env wires the router correctly"*. The implementation only tests the `SceneLoader.load(...)` half of the contract — `test_scene_load_with_difficulty_level_hard` asserts `scene.task.difficulty_level == DifficultyLevel.HARD` but does not construct a `SurgicalEnv` from that scene to verify that:
1. The lazy `SceneLoader` import inside `_load_scene()` works
2. `_setup_rewards()` correctly reads `task.difficulty_level` and passes it to `TaskRewardRouter`
3. The built `SuturingReward` has `position_threshold == 0.002` (HARD-interpolated)
4. `SurgicalEnv._task_difficulty == 1.0` (TaskResult population)

This is a real test coverage gap. The 4 pieces of wiring code (lines 199-224 of environment.py) and the lazy import (line 287) are both untested.

**Fix:** Add a test that exercises the full chain:

```python
def test_env_constructs_with_difficulty_level_hard(self):
    """End-to-end: HARD fixture → SurgicalEnv → router applies HARD."""
    from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
    config = SurgicalEnvConfig(
        scene_path=str(self.HARD_FIXTURE),
        simulator_type="mujoco",  # or skip if no simulator
        use_curriculum=False,
        use_adaptive_difficulty=False,
    )
    env = SurgicalEnv(config)
    try:
        assert env._task_difficulty == pytest.approx(1.0, abs=1e-6)
        # The router-built task reward (first in composite) should be HARD-interpolated
        assert env._reward_fn.components[0][0].position_threshold == pytest.approx(0.002, abs=1e-6)
    finally:
        env.close()
```

The MuJoCo simulator dependency makes this a potential integration test (or `@pytest.mark.slow`); but at minimum, the test should run with a headless MuJoCo instance, or with a stub that prevents the simulator from starting (e.g., short-circuit by setting `scene_path=None` and only testing the env config wiring with a pre-loaded `SceneDefinition`).

---

### WR-03: `CurriculumStageConfig.difficulty` union widening leaks through to consumer without normalization

**File:** `src/surg_rl/dynamics/curriculum.py:56` (the field) and `src/surg_rl/rl/environment.py:222`
**Issue:** The dataclass field is widened to `float | DifficultyLevel`, but the environment code path that reads it (`SurgicalEnv._setup_rewards` line 207, `getattr(self.config, "difficulty", 0.5)`) does NOT cover the curriculum path. If a future plan wires `CurriculumScheduler.current_difficulty` into the env's `_task_difficulty` (D-CURR-02 in CONTEXT.md deferred to "CurriculumScheduler integration test (out of scope for Phase 29)"), the env would receive a `DifficultyLevel` member, and `getattr(self.config, "difficulty", 0.5)` (which always returns a float) would not match.

This is a **latent bug**: the union widening is incomplete. The plan acknowledges (29-02-PLAN.md lines 256-257): *"The `getattr` / `hasattr` guards handle the case where `SurgicalEnvConfig` does NOT have a `difficulty` field — in that case, the env config doesn't contribute a difficulty and the fallback is the curriculum controller's `CurriculumStageConfig.difficulty`"*. But the actual implementation only handles the env config (always returning 0.5), never reading from the curriculum scheduler.

**Fix:** Either (a) add normalization in environment.py to handle both union arms:

```python
# When env config doesn't have difficulty, fall back to curriculum
elif self._controller is not None and self._controller._curriculum is not None:
    d = self._controller._curriculum.current_difficulty
    self._task_difficulty = float(d.value) if isinstance(d, DifficultyLevel) else float(d)
```

…or (b) document explicitly that the union widening for `CurriculumStageConfig.difficulty` is a stub and that the curriculum-to-env wiring is deferred.

---

## Info

### IN-01: Docstring/comment in `task_reward_router.py` contradicts the code

**File:** `src/surg_rl/rl/task_reward_router.py:86-91`
**Issue:** The comment says *"The call must happen AFTER the task reward is appended so apply_difficulty can mutate the live instance."* but the code (line 91) calls `apply_difficulty` BEFORE `rewards.append(task_reward)` (line 92). The behavior is correct — mutating the live instance works regardless of order — but the comment is misleading. A future maintainer reading "AFTER" would expect line 91 and 92 to be swapped, then might "fix" the code to match the comment, which would have no effect but is a documentation trap.

**Fix:** Either move the call to AFTER the append, or correct the comment to "BEFORE" (preferred — the current order is fine):

```python
task_reward = reward_cls(**reward_kwargs)
# D-PLUMB-01: Apply difficulty to the constructed reward before
# appending so that downstream consumers reading the rewards list
# see the difficulty-interpolated values. The 4 generic rewards
# inherit the no-op default from BaseRewardFunction (D-PLUMB-06),
# so this call is a no-op for them.
task_reward.apply_difficulty(self._difficulty)
rewards.append(task_reward)
```

---

### IN-02: `MAPPED_FIELDS` test dictionary is a parallel source of truth, not linked to the implementation

**File:** `tests/test_difficulty_levels.py:173-180`
**Issue:** The `MAPPED_FIELDS` dict encodes which `PARAM_BOUNDS` key maps to which ctor field in each of the 6 task reward `apply_difficulty` overrides. If a future change renames a ctor field (e.g., `position_threshold` → `suturing_position_threshold`), the test would silently start failing because the dict is hand-maintained, not derived from the implementation. There's no compile-time link between the dict and the `apply_difficulty` body.

This is a LOW concern because pytest will catch the drift, but the fix would be more robust.

**Fix:** Either (a) add a class attribute to each task reward (e.g., `SuturingReward.MAPPED_FIELD = "position_threshold"`) and have the test read it, or (b) use `inspect` to verify the implementation actually mutates a field whose name appears in the PARAM_BOUNDS dict.

---

### IN-03: `loader.save()` for JSON uses `mode="python"` instead of `mode="json"`

**File:** `src/surg_rl/scene_definition/loader.py:704`
**Issue:** `data = scene.model_dump(mode="python")` returns enum objects (in our case, `DifficultyLevel.HARD`). The `json.dumps` call at line 707 with `default=str` would only invoke `str()` on types json doesn't recognize, but since `_FloatMixin` is a `float` subclass, `json.dumps` recognizes it directly and serializes to the value `1.0` (verified empirically). So JSON roundtrip is correct, but using `mode="python"` for the JSON branch is a code smell — the safer pattern is `mode="json"` for JSON and `mode="python"` (with the enum converter) for YAML.

**Fix:** Use `mode="json"` for the JSON branch:

```python
if format == "json":
    data = scene.model_dump(mode="json")  # coerces enums to values
    content = json.dumps(data, indent=2)
```

This is purely defensive; current code works due to float-mixin's JSON behavior.

---

### IN-04: Cycle resolution pattern is correct but fragile; documenting the invariant is important

**File:** `src/surg_rl/scene_definition/schema.py:1479-1494`
**Issue:** The 3-step pattern (string forward-ref + late import + `model_rebuild()`) is correct and well-commented. However, the comment block (1479-1488) doesn't document the *invariant* that must be preserved by future edits:
- The late import (line 1489) MUST be after all `class` definitions in the file
- `TaskConfig.model_rebuild()` (line 1494) MUST come after the late import
- The string forward-ref at line 1101 MUST be `"DifficultyLevel | None"` (not a real annotation), or the model_rebuild won't find a string to resolve

A future refactor that, e.g., moves the late import earlier in the file (because "it's just an import") would silently break the cycle resolution. The Pydantic v2 behavior on unresolved forward refs is "lazy — the field is unresolved until first access" in some versions, or "ValidationError on first use" in others, depending on configuration.

**Fix:** Add an explicit invariant comment to the bottom of schema.py:

```python
# === CYCLE RESOLUTION INVARIANT ===
# The 3-step pattern above (string forward-ref at line 1101 + late import
# at line 1489 + model_rebuild at line 1494) breaks the
# schema -> rl.difficulty -> rl.__init__ -> environment -> dynamics.environment_controller
# -> schema import cycle. To preserve the cycle resolution:
#   1. The forward-ref at line 1101 MUST be a STRING, not the resolved annotation.
#      Pydantic v2 will not resolve a forward-ref that's not a string.
#   2. The late import (line 1489) MUST be AFTER all class definitions in
#      this file. Earlier imports re-trigger the cycle before the partial
#      module has the required names.
#   3. TaskConfig.model_rebuild() MUST be the LAST statement in this file.
#      It re-evaluates string forward-refs against the module namespace;
#      if called before the late import, DifficultyLevel is not yet bound.
```

---

### IN-05: `_FloatMixin(float, Enum)` produces unsafe `!!python/object/apply:` tags in raw `yaml.dump` output

**File:** `src/surg_rl/scene_definition/loader.py:723-724` (defensive converter) — but unsafe in other code paths
**Issue:** I verified empirically that `yaml.dump({"difficulty_level": DifficultyLevel.HARD})` produces `difficulty_level: !!python/object/apply:__main__.DifficultyLevel\n- 1.0` — an unsafe Python object construction tag. This is a known PyYAML behavior for unknown types. The `loader.py` save path correctly handles this with a custom `convert_tuples` function that does `obj.value` for `Enum` instances. But any other code path that does `yaml.dump(scene.model_dump(mode="python"))` (e.g., a future CLI export, a test snapshot, or a logging call) would produce unsafe YAML.

This is a pre-existing concern with Enum + PyYAML, but the new `_FloatMixin` field makes it more likely to surface because more code now passes enums through dict serialization.

**Fix:** Either (a) make `loader.py`'s `convert_tuples` function reusable (move to `surg_rl.utils.serialization`), or (b) add a `ruamel.yaml` or `safe_dump` wrapper for project-wide use.

---

### IN-06: `apply_difficulty` annotation `difficulty: float` accepts `DifficultyLevel` members due to float-mixin

**File:** `src/surg_rl/rl/rewards.py:161, 696, 852, 999, 1163, 1329, 1491`
**Issue:** The `apply_difficulty(self, difficulty: float)` annotation is technically correct (the router normalizes to `float(self._difficulty)` before calling), but if a future caller passes a `DifficultyLevel` member directly, the type checker would reject it even though the math would work (because `DifficultyLevel.HARD * 1.5` works fine via float-mixin). This is a footgun, not a bug.

The router's contract (normalize enum → float in `__init__`, never call `apply_difficulty` with an enum) is the right defense. A static type checker would flag direct calls to `reward.apply_difficulty(DifficultyLevel.HARD)` as wrong, which is the safer default.

**Fix:** No change needed. The annotation is correct for the intended contract. Optionally widen to `difficulty: float | DifficultyLevel` with a `float()` coercion inside the method to be duck-typed, but this weakens the type contract for marginal gain.

---

_Reviewed: 2026-06-12T18:45:00Z_
_Reviewer: gsd-code-reviewer (gsd-code-review workflow)_
_Depth: deep_
