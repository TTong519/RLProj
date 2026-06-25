# Phase 37: Scene-Level difficulty_blocks + Env Wiring - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 9 (3 src modify, 1 new test, 2 docs modify, 6 fixtures verify, 4 src read-only reuse)
**Analogs found:** 9 / 9 (every file has a strong analog — this phase is pure assembly over P36 + P35 primitives)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/surg_rl/scene_definition/schema.py` (EDIT — additive) | model (Pydantic v2) | transform (validation + round-trip) | same file: `TaskConfig.difficulty_level` field + late-import + `model_rebuild()` block (P35 v0.4.2 canon) | exact (self-analog) |
| `src/surg_rl/rl/environment.py` (EDIT — additive branch) | controller (Gymnasium env) | request-response (env-construction) | same file: `_setup_rewards` resolution chain (`environment.py:484-521`) + `_load_scene` lazy local import (`environment.py:262-277`) | exact (self-analog) |
| `src/surg_rl/rl/rewards.py` (EDIT — refactor) | service (reward transforms) | transform (params → ctor fields) | same file: `apply_difficulty` on 6 task rewards + `BaseRewardFunction.apply_difficulty` no-op | exact (self-analog) |
| `tests/test_difficulty_blocks.py` (NEW) | test | request-response (parametrized I/O) | `tests/test_difficulty_levels.py::TestDifficultyIntegration` (lines 316-401) + `tests/test_difficulty_config.py::TestComposeDifficultyOverrides` (lines 137-215) | exact (style + idiom) |
| `.planning/PROJECT.md` (EDIT — line 82) | docs | n/a | same file line 82 (`difficulty_levels` → `difficulty_blocks`) | exact (self-analog) |
| `.planning/STATE.md` (EDIT — lines 82, 131) | docs | n/a | same file line 82 historical drift note | exact (self-analog) |
| `scenes/{simple_suturing,knot_tying,needle_insertion,grasping,cutting,dissection}.json` (VERIFY — read-only) | fixture | file I/O (JSON round-trip) | `tests/fixtures/scenes/suturing_difficulty_hard.json` (v0.4.2 back-compat fixture) | exact (same shape) |
| `src/surg_rl/rl/difficulty.py` (REUSE — read-only) | model (leaf) | transform | same file (P36-01 shipped) | exact (reuse) |
| `src/surg_rl/dynamics/difficulty_wiring.py` (REUSE — read-only) | config + utility | transform (interpolate-then-override) | same file (P36-02 shipped) | exact (reuse) |

## Pattern Assignments

### `src/surg_rl/scene_definition/schema.py` (EDIT — model, Pydantic v2 forward-ref)

**Analog:** the existing `difficulty_level` field in the SAME file (`schema.py:1113-1121`) + the late-import + `model_rebuild()` block at `schema.py:1491-1506`. P37 adds `difficulty_blocks` as a sibling field using the exact same idiom — this is the project canon (v0.4.2, P35, P36-03 confirmed).

**Imports discipline — extend the existing late-import block, do NOT duplicate (`schema.py:1491-1506`):**
```python
# Phase 29 (D-SCHEMA-01): Late import of DifficultyLevel to break the
# surg_rl.scene_definition.schema -> surg_rl.rl -> surg_rl.dynamics.environment_controller
# -> surg_rl.scene_definition.schema import cycle. With `from __future__ import
# annotations` + string annotation on TaskConfig.difficulty_level, the type
# is not resolved at class body time. We import DifficultyLevel AFTER all
# classes are defined, then call model_rebuild() to resolve the forward ref.
# The TYPE_CHECKING import at the top is for type checkers only; the runtime
# import here is what makes the validation work. We bind the name
# `DifficultyLevel` (not aliased) so model_rebuild() can resolve the string
# forward reference in TaskConfig.
from surg_rl.rl.difficulty import (  # noqa: E402
    DifficultyLevel,
)  # noqa: F401 — module-level binding for forward ref resolution

# Resolve the forward reference in TaskConfig.difficulty_level.
TaskConfig.model_rebuild()
```
Add `DifficultyLevelConfig` to the same `from surg_rl.rl.difficulty import (...)` tuple. NO `dynamics.*` import (Pitfall 4 — would re-open `scene_definition → dynamics` edge). Both `DifficultyLevel` and `DifficultyLevelConfig` already live in the leaf `rl.difficulty` (verified P36-01: zero in-project imports), so the one-way edge `schema → rl.difficulty` is unchanged. The single existing `TaskConfig.model_rebuild()` call resolves BOTH forward refs.

**Core field pattern to mirror (`schema.py:1113-1121` — the existing `difficulty_level` field, copy this shape verbatim for `difficulty_blocks`):**
```python
difficulty_level: "DifficultyLevel | None" = (
    Field(  # noqa: F821 — forward ref resolved at bottom of file
        default=None,
        description="Surgical difficulty preset (EASY/MEDIUM/HARD). "
        "None = use the float difficulty path. Pydantic v2 validates "
        "the enum literal (by float value 0.0/0.5/1.0); downstream code "
        "uses the scalar .value via interpolate_params(level.value).",
    )
)
```
Target shape for the new field (RESEARCH.md:473-484):
```python
difficulty_blocks: "dict[DifficultyLevel, DifficultyLevelConfig] | None" = (
    Field(  # noqa: F821 — forward ref resolved at bottom of file
        default=None,
        description="Per-level difficulty override blocks keyed by DifficultyLevel "
        "(EASY/MEDIUM/HARD). None = no overrides; use the float difficulty path. "
        "Each value is a DifficultyLevelConfig carrying 0-4 SET override fields. "
        "When present, SurgicalEnv._setup_rewards composes overrides additively "
        "over interpolate_params(level.value) via compose_difficulty_overrides.",
    )
)
```
Place it inside `class TaskConfig(BaseModel)` immediately after `difficulty_level` (after `schema.py:1121`, before `BenchmarkConfig` at `:1124`). The `# noqa: F821` mirrors the existing field — Pydantic resolves the string forward ref at `model_rebuild()` time. Type as `dict[DifficultyLevel, DifficultyLevelConfig] | None` (NOT `DiscreteCurriculumConfig | None`) — keeps only `rl.difficulty` symbols in scope (Pitfall 4).

**`task_type` Literal keys to key the dict by (`schema.py:1106-1112`):** the 6 keys (`suturing`, `knot_tying`, `needle_insertion`, `grasping`, `cutting`, `dissection`) — the same 6 keys `ABSTRACT_TO_CONCRETE` and `TASK_REWARD_REGISTRY` use. Scene authors put `difficulty_blocks` on `TaskConfig` alongside `task_type` and `difficulty_level`.

**Validation inheritance — NO new validators needed.** `DifficultyLevelConfig` already carries 4 `field_validator` range checks (D-07 global union bounds, P36-01 shipped, `rl/difficulty.py:71-97`). Pydantic v2 validates nested `DifficultyLevelConfig` automatically when `TaskConfig` is constructed via `SceneDefinition(**data)` (loader path, `loader.py:587`). The `DifficultyLevel` dict-key enum membership is also validated by Pydantic v2 by float value (P35 verified). Out-of-range or malformed `difficulty_blocks` raise `ValidationError` at scene-load time (ASVS V5) — no new code required.

**Key differences from analog:**
- Field type is a dict (not scalar enum), so YAML round-trip of a scene WITH blocks may raise `RepresenterError` on `DifficultyLevel` dict keys (Pitfall 5). The 6 task fixtures are JSON (JSON keys are strings — safe). The SC#1 round-trip test should cover both JSON (must work) and YAML (may need a `DifficultyLevel` representer in `loader.py` — verify, document, defer if out of scope).
- `None` default keeps the 6 v0.4.0 scenes loading unchanged (no `difficulty_blocks` key present → field is `None` → existing float path applies).

---

### `src/surg_rl/rl/environment.py` (EDIT — controller, request-response env-construction)

**Analog:** the existing `_setup_rewards` body in the SAME file (`environment.py:484-521`) — the single reward-difficulty resolution site. Plus the lazy local `SceneLoader` import at `environment.py:272-277` — the exact idiom for a function-body local import that breaks a cycle.

**`_setup_rewards` current shape — the chain to extend (`environment.py:484-521`):**
```python
def _setup_rewards(self) -> None:
    """Build the reward function and resolve the difficulty scalar.
    ...
    """
    task_name = None
    task_type = None
    if self._scene.task is not None:
        task_name = self._scene.task.name
        task_type = getattr(self._scene.task, "task_type", None)

    # Resolve difficulty scalar from task -> config -> curriculum -> default.
    difficulty: float | DifficultyLevel
    if self._scene.task is not None and self._scene.task.difficulty_level is not None:
        difficulty = self._scene.task.difficulty_level
    else:
        # SurgicalEnvConfig may or may not have a difficulty field; getattr is safe
        difficulty = getattr(self.config, "difficulty", 0.5)

    # If curriculum drives difficulty, normalize the scheduler's current value.
    if (
        self.config.use_curriculum
        and self._controller is not None
        and self._controller._curriculum is not None
    ):
        difficulty = self._controller._curriculum.current_difficulty

    # Phase 29: coerce enum or float to a scalar float for all reward builders.
    difficulty_float = float(difficulty.value) if isinstance(difficulty, DifficultyLevel) else float(difficulty)
    self._task_difficulty = difficulty_float

    if task_type is not None:
        router = TaskRewardRouter(difficulty=difficulty_float)
        reward_list = router.build(task_type)
        self._reward_fn = CompositeReward([(r, 1.0) for r in reward_list])
    else:
        self._reward_fn = create_default_reward(self.config.reward_config, task_name=task_name)
```
The new blocks branch is an ADDITIVE early-return grafted AFTER `self._task_difficulty = difficulty_float` and BEFORE the existing `if task_type is not None:` router branch. Per RESEARCH.md:517-540 + Pitfall 6: blocks apply ONLY when `difficulty` is a `DifficultyLevel` (discrete path); when `use_curriculum=True` drives a continuous scalar, blocks do NOT apply (fall through to the existing router — continuous path byte-identical, TASK-09). Mirror the existing `if self._scene.task is not None:` guard at `:492` for the new `blocks = getattr(task, "difficulty_blocks", None)` read.

**Lazy local import idiom to mirror for `compose_difficulty_overrides` (`environment.py:272-277`):**
```python
if self.config.scene_path is not None:
    # Lazy import to break the import cycle:
    # environment.py -> loader.py -> schema.py -> rl.__init__
    # The SceneLoader is only needed at runtime (not at module load).
    from surg_rl.scene_definition.loader import SceneLoader

    return SceneLoader().load(self.config.scene_path)
```
Use the same function-body-local import for `compose_difficulty_overrides` and `TASK_REWARD_REGISTRY` inside the new blocks branch (NOT a module-level import — keeps the module-import graph clean, per RESEARCH.md Pitfall 4 / A2):
```python
from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides
from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY
```

**`SurgicalEnvConfig` — where to add `difficulty: float = 0.5` if planner takes RESEARCH.md Open Q2 recommendation (`environment.py:79-96`):**
```python
@dataclass
class SurgicalEnvConfig:
    scene_path: str | None = None
    scene: SceneDefinition | None = None
    simulator_type: str = "mujoco"
    timestep: float = 0.002
    frame_skip: int = 1
    max_episode_steps: int = 1000
    render_mode: str | None = None
    render_fps: float = 30.0
    reward_config: RewardConfig | None = None
    observation_config: ObservationConfig | None = None
    action_config: ActionConfig | None = None
    use_curriculum: bool = False
    use_adaptive_difficulty: bool = False
    controller_config: EnvironmentControllerConfig | None = None
    seed: int | None = None
    ros2_bridge_config: Ros2BridgeConfig | None = None
    use_ros2_control: bool = False
    controller_yaml: str | None = None
```
Currently NO `difficulty` field (verified — Pitfall 1). `getattr(self.config, "difficulty", 0.5)` at `:502` always returns 0.5. If planner adds `difficulty: float = 0.5` (one-line additive dataclass field, mirrors the existing `timestep: float = 0.002` idiom), the SC#2 chain `difficulty_blocks[level] > task.difficulty_level > config.difficulty > default 0.5` becomes a real 4-level truth table. Default 0.5 preserves v0.5.0 behavior (regression-safe).

**`__init__` ordering — `_setup_rewards` runs AFTER `_setup_controller` (`environment.py:195-204`):** the curriculum is live when `_setup_rewards` reads `self._controller._curriculum.current_difficulty`. The new blocks branch MUST respect this — it runs in the same `_setup_rewards` call, after the existing curriculum branch, so `self._controller._curriculum` is available (the existing `if ... is not None` guard at `:505-510` already handles the None case). Verify `_setup_rewards` is still called in `__init__` after `_setup_controller` (planner to grep `self._setup_rewards()` in `environment.py:__init__` before editing — the call site is the contract).

**`reset()` curriculum read — DO NOT touch (`environment.py:561-564`):**
```python
# Phase 21: Update task difficulty from curriculum
if self._controller is not None:
    try:
        self._task_difficulty = self._controller.get_difficulty() or 0.5
```
The blocks path applies at env CONSTRUCTION (`_setup_rewards`), not at `reset()`. `reset()`'s curriculum read is the continuous-path state update and stays byte-identical (TASK-09). Blocks do not re-apply on `reset()` — they shape the reward function once at construction.

**Key differences from analog:**
- New branch is additive (early return when blocks apply); existing router branch is the fallthrough. Observable output for any scene WITHOUT `difficulty_blocks` is byte-identical (regression gate, TASK-09).
- Lazy local import of `compose_difficulty_overrides` is inside the new branch (only reached when blocks present) — mirrors `SceneLoader` lazy import but in a tighter scope.

---

### `src/surg_rl/rl/rewards.py` (EDIT — service, transform params → ctor fields)

**Analog:** the existing `apply_difficulty` method on each of the 6 task rewards in the SAME file + the `BaseRewardFunction.apply_difficulty` no-op default. P37 extracts the mapping body into a new `apply_params(params: dict[str, float])` method (RESEARCH.md Pattern 3 Option A — pure refactor, observable output unchanged → regression-safe). All 6 task rewards get the SAME refactor; the base no-op gains a default `apply_params` no-op.

**`BaseRewardFunction.apply_difficulty` no-op — the default to mirror for `apply_params` (`rewards.py:161-184`):**
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Default implementation is a no-op for generic rewards (DistanceReward,
    ActionPenalty, TimePenalty, CollisionPenalty, OrientationReward,
    SuccessReward, CompositeReward). Task-specific subclasses
    (SuturingReward, DissectionReward, NeedlePassingReward,
    KnotTyingReward, GraspingReward, CuttingReward) override this
    method to map `interpolate_params(difficulty)` results to their
    own ctor fields. Called by TaskRewardRouter.build() after
    reward construction.
    ...
    """
    # Intentional no-op default per D-PLUMB-06. The override pattern in
    # the 6 task-specific subclasses keeps this method load-bearing
    # while preserving the safe default for the 4 generic ones.
    return None  # noqa: B027
```
Add a sibling `apply_params(self, params: dict[str, float]) -> None` no-op on `BaseRewardFunction` with the same `# noqa: B027` and the same D-PLUMB-06 rationale (generic rewards must not consume difficulty — neither the scalar form nor the composed-dict form).

**`interpolate_params` classmethod — the additive baseline, DO NOT EDIT (`rewards.py:675-681`, identical on all 6 task reward classes):**
```python
@classmethod
def interpolate_params(cls, difficulty: float) -> dict[str, float]:
    """Compute per-parameter values from difficulty scalar."""
    return {
        name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
        for name, bounds in cls.PARAM_BOUNDS.items()
    }
```
`compose_difficulty_overrides` (P36-02, reused) calls this read-only to establish the additive baseline, then replaces mapped keys with absolute override values (D-06). P37 does NOT edit `interpolate_params` or any `PARAM_BOUNDS` (anti-pattern, RESEARCH.md).

**The 6 `apply_difficulty` bodies to refactor — each becomes `apply_params(params)` + `apply_difficulty` delegates (`rewards.py`):**

SuturingReward (`:696-704`):
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02:
    partial mapping is acceptable). Unmapped keys are skipped.
    """
    params = self.interpolate_params(difficulty)
    if "needle_position_tolerance" in params and hasattr(self, "position_threshold"):
        self.position_threshold = params["needle_position_tolerance"]
```

DissectionReward (`:852-859`):
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
    """
    params = self.interpolate_params(difficulty)
    if "force_precision" in params and hasattr(self, "force_threshold"):
        self.force_threshold = params["force_precision"]
```

NeedlePassingReward (`:999-1006`):
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
    """
    params = self.interpolate_params(difficulty)
    if "handoff_proximity_tolerance" in params and hasattr(self, "handoff_threshold"):
        self.handoff_threshold = params["handoff_proximity_tolerance"]
```

KnotTyingReward (`:1163-1170`):
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
    """
    params = self.interpolate_params(difficulty)
    if "loop_deviation_tolerance" in params and hasattr(self, "loop_deviation_threshold"):
        self.loop_deviation_threshold = params["loop_deviation_tolerance"]
```

GraspingReward (`:1329-1336`):
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
    """
    params = self.interpolate_params(difficulty)
    if "approach_tolerance" in params and hasattr(self, "grasp_threshold"):
        self.grasp_threshold = params["approach_tolerance"]
```

CuttingReward (`:1491-1498`):
```python
def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Maps a subset of PARAM_BOUNDS keys to ctor fields (D-PLUMB-02).
    """
    params = self.interpolate_params(difficulty)
    if "force_precision" in params and hasattr(self, "force_threshold"):
        self.force_threshold = params["force_precision"]
```

**Refactor template (Option A — apply to all 6 task rewards identically):**
```python
def apply_params(self, params: dict[str, float]) -> None:
    """Apply a composed params dict to ctor fields (D-PLUMB-02 partial mapping).

    Receives the output of either ``interpolate_params(difficulty)`` (existing
    scalar path) or ``compose_difficulty_overrides(...)`` (P36 + P37 blocks
    path). Maps the SAME single key ``apply_difficulty`` mapped; unmapped keys
    are skipped. Observable output of ``apply_difficulty`` is byte-identical
    to the pre-refactor implementation (regression-safe).
    """
    # SuturingReward body shown; replace the key/attr per task reward:
    if "needle_position_tolerance" in params and hasattr(self, "position_threshold"):
        self.position_threshold = params["needle_position_tolerance"]

def apply_difficulty(self, difficulty: float) -> None:
    """Apply interpolated difficulty parameters to this reward instance.

    Refactored to delegate to ``apply_params`` (P37). Observable output
    unchanged from the pre-P37 implementation.
    """
    self.apply_params(self.interpolate_params(difficulty))
```

**Per-task key/attribute mapping (Pitfall 2 — planner MUST decide whether `apply_params` maps ONLY this key or expands to all D-05 concrete keys):**

| Task reward | Concrete key (`PARAM_BOUNDS`) | Ctor attribute | Source line |
|-------------|-------------------------------|----------------|-------------|
| SuturingReward | `needle_position_tolerance` | `position_threshold` | `:703-704` |
| DissectionReward | `force_precision` | `force_threshold` | `:858-859` |
| NeedlePassingReward | `handoff_proximity_tolerance` | `handoff_threshold` | `:1005-1006` |
| KnotTyingReward | `loop_deviation_tolerance` | `loop_deviation_threshold` | `:1169-1170` |
| GraspingReward | `approach_tolerance` | `grasp_threshold` | `:1335-1336` |
| CuttingReward | `force_precision` | `force_threshold` | `:1497-1498` |

RESEARCH.md Pitfall 2 + Open Q1 recommendation: Option (a) — map ONLY the same single key this phase; document the inert override surface (e.g. a `difficulty_blocks` override on `tissue_stiffness` for suturing composes into the dict but never reaches a ctor field — `apply_params` does not map `tissue_stiffness` on SuturingReward). The SC#2 truth-table test asserts the composed DICT is correct (full D-06 composition) AND that the reward ctor field changes ONLY for the one mapped key. Defer Option (b) (expand the per-reward mapping to all D-05 concrete keys — invasive, needs new ctor attributes like `incision_path_threshold` on DissectionReward) to a future phase.

**Key differences from analog:**
- Refactor is a pure extraction (move the `if ... in params: self.attr = params[key]` body into `apply_params`; `apply_difficulty` becomes a one-line delegate). Existing `test_difficulty_levels.py::test_router_applies_difficulty_to_task_reward` (`:356-362`) and the parametrized direction tests stay green unchanged (regression-anchored).
- `apply_params` accepts a `dict[str, float]` (composed) instead of a `float` (scalar) — the only surface change.

---

### `tests/test_difficulty_blocks.py` (NEW — test, parametrized I/O)

**Analogs:** `tests/test_difficulty_levels.py::TestDifficultyIntegration` (`:316-401` — scene-load + 6-scene regression pattern) + `tests/test_difficulty_config.py::TestComposeDifficultyOverrides` (`:137-215` — parametrized truth-table + `caplog` D-04 warn pattern).

**Imports + module docstring pattern — copy from `test_difficulty_levels.py:1-25`:**
```python
"""Tests for DifficultyLevel enum and its re-export.
...
"""
import pytest

from surg_rl.rl import DifficultyLevel
from surg_rl.rl.rewards import (
    ActionPenalty,
    CollisionPenalty,
    CuttingReward,
    DissectionReward,
    DistanceReward,
    GraspingReward,
    KnotTyingReward,
    NeedlePassingReward,
    SuturingReward,
    TimePenalty,
)
```
Add: `from pathlib import Path` (for fixture paths), `from surg_rl.scene_definition.loader import SceneLoader`, `from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig`, `from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides, ABSTRACT_TO_CONCRETE`, `from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY` (reuse the truth-table imports from `test_difficulty_config.py:1-30` — verify by reading that file's top at implement time).

**Test class organization — mirror `test_difficulty_levels.py:316` + `test_difficulty_config.py:137`:**
```python
class TestSceneBlocksRoundTrip:        # SC#1 — scene JSON round-trip
class TestPrecedenceTruthTable:        # SC#2 — 4-level parametrized truth table
class TestSixSceneThreeLevelRegression:  # SC#3 — 6×3 fixture matrix
class TestHardFixtureScalarEquivalence:  # SC#4 — back-compat scalar gate
class TestNamingAudit:                  # SC#5 — grep audit
```

**SC#1 round-trip — mirror `TestDifficultyIntegration::test_scene_load_with_difficulty_level_hard` (`test_difficulty_levels.py:364-371`):**
```python
def test_scene_load_with_difficulty_level_hard(self):
    """D-TEST-05: scene JSON with task.difficulty_level = 1.0 loads to enum."""
    if not self.HARD_FIXTURE.exists():
        pytest.skip("Fixture not yet created")
    scene = SceneLoader().load(str(self.HARD_FIXTURE))
    assert scene.task is not None
    assert scene.task.difficulty_level == DifficultyLevel.HARD
    assert scene.task.task_type == "suturing"
```
Adapt: author a scene JSON with `difficulty_blocks` for all 3 levels (use the RESEARCH.md:558-572 fixture shape), `SceneLoader().load()`, assert `scene.task.difficulty_blocks` is a `dict[DifficultyLevel, DifficultyLevelConfig]` with the authored values; assert `model_dump()`/JSON re-serialization preserves them. Plus the negative: a scene WITHOUT blocks loads with `difficulty_blocks is None` (mirror `test_scene_load_without_difficulty_level_defaults_to_none` at `:373-381`).

**SC#3 6×3 fixture regression matrix — mirror `TestDifficultyIntegration::test_all_phase27_scenes_load_with_difficulty_level_none` (`test_difficulty_levels.py:383-401`):**
```python
@pytest.mark.parametrize(
    "scene_file",
    [
        "simple_suturing.json",
        "knot_tying.json",
        "needle_insertion.json",
        "grasping.json",
        "cutting.json",
        "dissection.json",
    ],
)
def test_all_phase27_scenes_load_with_difficulty_level_none(self, scene_file):
    """D-BC-02: all 6 Phase 27 benchmark scenes still load without difficulty_level."""
    scene_path = Path(__file__).parent.parent / "scenes" / scene_file
    if not scene_path.exists():
        pytest.skip(f"scenes/{scene_file} not found")
    scene = SceneLoader().load(str(scene_path))
    assert scene.task is not None
    assert scene.task.difficulty_level is None
```
Adapt: parametrize over `(scene_file, level)` (6×3 = 18 cases). For each, construct `SurgicalEnv(SurgicalEnvConfig(scene_path=..., render_mode=None))` with the level set, `env.reset()`, `env.step(action)`, assert no exception and a well-formed `(obs, reward, terminated, truncated, info)` tuple. RESEARCH.md A5 + 36-03-SUMMARY: macOS aborts in `test_rl.py`/`test_benchmark_*.py` are pre-existing (MuJoCo/PyBullet backend loading). Design the gate to DEGRADE to construct-only + assert `env._reward_fn is not None` if `env.step(action)` aborts; flag the abort as pre-existing (not caused by this phase). Verify the 6 task scenes construct + step in Wave 0 before committing to the step path.

**SC#2 precedence truth table — mirror `TestComposeDifficultyOverrides::test_compose_truth_table` (`test_difficulty_config.py:144-171`):**
```python
@pytest.mark.parametrize(
    ("task_type", "level", "abstract_field", "override_value"),
    _TRUTH_TABLE_CASES,
)
def test_compose_truth_table(self, task_type, level, abstract_field, override_value):
    """SC#2: overriding one field changes ONLY the mapped concrete key.
    ...
    """
    reward_cls = TASK_REWARD_REGISTRY[task_type]
    baseline = reward_cls.interpolate_params(level.value)
    cfg = DifficultyLevelConfig(**{abstract_field: override_value})
    composed = compose_difficulty_overrides(task_type, level, cfg, reward_cls)

    concrete_key = ABSTRACT_TO_CONCRETE[task_type][abstract_field]
    assert composed[concrete_key] == override_value
    for key, baseline_val in baseline.items():
        if key == concrete_key:
            continue
        assert composed[key] == baseline_val, (...)
    assert set(composed.keys()) == set(baseline.keys())
```
Adapt: parametrize over `(level, source, expected_scalar, blocks, expect_override_applied)` per RESEARCH.md:576-588. For each, construct the env with that source configuration and assert (a) `env._task_difficulty` matches the expected scalar, (b) when blocks present, the composed params dict (intercept via `compose_difficulty_overrides` call or a spy) matches D-06 composition, (c) the reward ctor field that `apply_params` maps matches the override value. Plus the curriculum-coexistence case (Pitfall 6): `use_curriculum=True + difficulty_blocks present + continuous scalar` → blocks NOT applied (assert the blocks-override ctor field does NOT change).

**`caplog` D-04 warning assertion — mirror `test_difficulty_config.py:195-213`** if the truth table covers the D-04 unmapped-override path (likely yes — at minimum assert no warning is raised when blocks map cleanly, and the existing D-04 test in `test_difficulty_config.py` stays green unchanged).

**SC#4 hard-fixture back-compat — mirror `TestDifficultyIntegration::HARD_FIXTURE` + `test_scene_load_with_difficulty_level_hard` (`test_difficulty_levels.py:319-320, 364-371`):**
```python
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "scenes"
HARD_FIXTURE = FIXTURE_DIR / "suturing_difficulty_hard.json"
```
The hard fixture (`tests/fixtures/scenes/suturing_difficulty_hard.json:305-307`) has `"difficulty_level": 1.0` and NO `difficulty_blocks` key. The SC#4 test loads it before/after the phase and asserts `scene.task.difficulty_level == DifficultyLevel.HARD` and `float(env._task_difficulty) == 1.0` (byte-identical to v0.4.2 baseline). Capture the pre-phase scalar in the test for byte-identical comparison.

**SC#5 naming audit — grep-based, no pytest analog needed:**
```python
def test_no_difficulty_levels_in_canonical_docs(self):
    """SC#5: difficulty_levels spelling gone from PROJECT.md/STATE.md/src."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "difficulty_levels",
         ".planning/PROJECT.md", ".planning/STATE.md", "src/surg_rl/"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, f"difficulty_levels still present:\n{result.stdout}"
```
Mirror the leaf-import substring audit idiom from P36-01's `TestLeafImportAudit.test_leaf_no_inproject_imports` (substring grep on canonical paths).

**Key differences from analog:**
- New file tests `difficulty_blocks` (per-level dict), not `difficulty_level` (scalar enum) — different field, same round-trip idiom.
- Adds the SC#2 precedence truth table (parametrized over sources × levels) — new pattern, uses the same `@pytest.mark.parametrize` shape as `test_difficulty_config.py:144`.
- Adds the 6×3 env-construct/step regression matrix — new pattern, uses the same `@pytest.mark.parametrize` shape as `test_difficulty_levels.py:383` but with `(scene_file, level)` instead of just `scene_file`.
- TDD: RED tests assert the field accepts 3-level blocks, the precedence branch composes overrides, and `apply_params` reaches the ctor field. GREEN lands the schema field + env branch + reward refactor.

---

### `.planning/PROJECT.md` (EDIT — line 82, docs)

**Analog:** the same line in the same file — a one-token spelling reconciliation (RESEARCH.md:600-601, SC#5).

**Current (`PROJECT.md:82`):**
```
- TASK-02 scene-level `difficulty_levels: list[3]` blocks — D-29-03 explicit exclusion
```
**Target:**
```
- TASK-02 scene-level `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig]` — Phase 37 (TASK-08) ships; D-29-03 exclusion lifted
```
Also check `PROJECT.md:23` — already uses `difficulty_blocks` (verified: `TASK-02 per-level schema ... scene-level difficulty_blocks: list[3] in scene JSON`). The `list[3]` shape there is the old research shape; RESEARCH.md Open Q3 recommends `dict[DifficultyLevel, DifficultyLevelConfig] | None` instead. Planner should reconcile `:23` to the dict shape as well (SC#5 canonical).

**Key differences from analog:** none — pure text edit, no code.

---

### `.planning/STATE.md` (EDIT — lines 82, 131, docs)

**Analog:** the same lines in the same file — historical drift note + roadmap row (RESEARCH.md:600-601, SC#5).

**Current (`STATE.md:82`):**
```
- [v0.6.0 research]: Naming drift — `difficulty_blocks` (PROJECT.md) vs `difficulty_levels` (STATE.md) → canonical = `difficulty_blocks`; reconcile in Phase 36.
```
**Target:** update the note to past-tense + Phase 37 attribution (the reconciliation was deferred from P36 to P37 per the file's own note):
```
- [v0.6.0 research]: Naming drift — `difficulty_blocks` (PROJECT.md) vs `difficulty_levels` (STATE.md) → canonical = `difficulty_blocks`; reconciled in Phase 37 (TASK-08/SC#5). `difficulty_levels` spelling removed from PROJECT.md and STATE.md.
```

**Current (`STATE.md:131`):**
```
| TASK-02 | Scene-level `difficulty_blocks: list[3]` blocks | Phase 37 (TASK-08) | Naming reconciled to `difficulty_blocks` |
```
**Target:** update the shape to the dict form (RESEARCH.md Open Q3):
```
| TASK-02 | Scene-level `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] \| None` | Phase 37 (TASK-08) | Naming reconciled to `difficulty_blocks`; shape = dict-keyed (RESEARCH.md Open Q3) |
```

**Key differences from analog:** none — pure text edit.

---

### `scenes/{simple_suturing,knot_tying,needle_insertion,grasping,cutting,dissection}.json` (VERIFY — read-only fixtures)

**Analog:** `tests/fixtures/scenes/suturing_difficulty_hard.json` (v0.4.2 back-compat fixture, verified `:305-307` has `"difficulty_level": 1.0` and no `difficulty_blocks` key).

The 6 v0.4.0 task scenes are READ-ONLY this phase (verified via RESEARCH.md:803-806 — all have `task.task_type` set, `task.difficulty_level` null, no `difficulty_blocks`). They are the SC#3 regression gate input — the gate asserts they STILL load with `difficulty_blocks is None` (the new field's default) and construct/step cleanly. NO fixture edits this phase. If the planner wants an example scene WITH blocks for SC#1, create it under `tests/fixtures/scenes/` (new file), NOT under `scenes/` (production).

**Round-trip JSON shape to verify (RESEARCH.md:558-572):**
```json
{
  "task": {
    "name": "suturing_task",
    "description": "Suturing with hard-mode blocks",
    "task_type": "suturing",
    "difficulty_level": 1.0,
    "difficulty_blocks": {
      "EASY":   {"target_precision_tolerance": 0.02},
      "MEDIUM": {"target_precision_tolerance": 0.005},
      "HARD":   {"target_precision_tolerance": 0.002}
    }
  }
}
```
Pydantic v2 coerces JSON string keys (`"EASY"/"MEDIUM"/"HARD"`) to `DifficultyLevel` enum members by float value (A6 — verify in SC#1 round-trip test). Override values (`0.02`, `0.005`, `0.002`) MUST be inside D-07 global union bounds (`target_precision_tolerance: [0.002, 0.3]`) — verified.

**Key differences from analog:** none — read-only verification, no edits.

---

### `src/surg_rl/rl/difficulty.py` (REUSE — read-only, P36-01 shipped)

**Analog:** the file itself (P36-01 shipped, commit `166a52b`). P37 consumes `DifficultyLevel` + `DifficultyLevelConfig` read-only via the existing late import in `schema.py:1501` (extended to add `DifficultyLevelConfig`) and via `compose_difficulty_overrides` in `difficulty_wiring.py`.

**Leaf contract — verified (`rl/difficulty.py:1-18`):** zero in-project imports (only `enum`, `pydantic`). P37 MUST NOT edit this file — the SC#5 leaf audit from P36-01 (`test_difficulty_config.py::TestLeafImportAudit.test_leaf_no_inproject_imports`) stays green unchanged.

**`DifficultyLevelConfig` shape (`rl/difficulty.py:56-97`):** four `Optional[float] = None` override fields (`tissue_stiffness`, `target_precision_tolerance`, `tool_position_noise`, `time_limit`) with four `@field_validator(...) @classmethod` range checks against D-07 global union bounds. This is the value type for `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] | None` — Pydantic v2 validates each value automatically when `TaskConfig` is constructed.

---

### `src/surg_rl/dynamics/difficulty_wiring.py` (REUSE — read-only, P36-02 shipped)

**Analog:** the file itself (P36-02 shipped, commit `42ee64c`). P37 consumes `compose_difficulty_overrides` + `ABSTRACT_TO_CONCRETE` read-only via a lazy local import inside `SurgicalEnv._setup_rewards`'s new blocks branch.

**`compose_difficulty_overrides` signature + body (`difficulty_wiring.py:85-135`):**
```python
def compose_difficulty_overrides(
    task_type: str,
    level: DifficultyLevel,
    config: DifficultyLevelConfig,
    reward_cls: Any,
) -> dict[str, float]:
    """Compose per-level overrides additively over interpolate_params (D-06).
    ...
    """
    composed: dict[str, float] = reward_cls.interpolate_params(level.value)
    task_map = ABSTRACT_TO_CONCRETE.get(task_type, {})
    for abstract_field in _ABSTRACT_FIELDS:
        override_value = getattr(config, abstract_field)
        if override_value is None:
            continue
        concrete_key = task_map.get(abstract_field)
        if concrete_key is None:
            logger.warning(
                "override field %r has no mapping for task_type=%r; " "keeping interpolated value",
                abstract_field,
                task_type,
            )
            continue
        composed[concrete_key] = override_value
    return composed
```
The env's new blocks branch calls this with `reward_cls = TASK_REWARD_REGISTRY[task.task_type]` and `config = blocks[difficulty]`. The returned `composed` dict is applied via the new `reward.apply_params(composed)` seam (Pattern 3 Option A). NO re-implementation — RESEARCH.md Don't Hand-Roll table.

**`ABSTRACT_TO_CONCRETE` (`difficulty_wiring.py:30-61`):** the D-05 mapping, task_type-keyed. P37 does NOT edit this. The inert-override surface (Pitfall 2) is a consequence of `apply_params` mapping only ONE key per task reward — document in the truth table, defer expansion.

**One-way edge verification (`difficulty_wiring.py:8-14`):** `dynamics.difficulty_wiring → rl.difficulty` only. NO `scene_definition` import, NO `curriculum` import. P37's lazy local import inside `_setup_rewards` (`rl.environment → dynamics.difficulty_wiring`) is a new one-way edge from the env layer to the wiring layer — safe (no reverse edge). Verify with: `grep -c 'from surg_rl.scene_definition' src/surg_rl/dynamics/difficulty_wiring.py` = 0; `grep -c 'from surg_rl.dynamics.curriculum' src/surg_rl/dynamics/difficulty_wiring.py` = 0.

---

## Shared Patterns

### String forward-ref + late import + `model_rebuild()` (v0.4.2 canon, P35 + P36-03 confirmed)
**Source:** `src/surg_rl/scene_definition/schema.py:5` (`from __future__ import annotations`), `:1113-1121` (string forward-ref field), `:1491-1506` (late import + `TaskConfig.model_rebuild()`).
**Apply to:** `src/surg_rl/scene_definition/schema.py` EDIT — extend the existing late-import tuple with `DifficultyLevelConfig`; add `difficulty_blocks` as a string forward-ref field inside `TaskConfig`. The single existing `TaskConfig.model_rebuild()` call resolves BOTH forward refs. NO `dynamics.*` import in `schema.py` (Pitfall 4).
```python
from surg_rl.rl.difficulty import (  # noqa: E402
    DifficultyLevel,
    DifficultyLevelConfig,  # NEW — P37
)  # noqa: F401 — module-level binding for forward ref resolution
TaskConfig.model_rebuild()  # already present; resolves both forward refs
```

### Function-body lazy local import (cycle-breaker)
**Source:** `src/surg_rl/rl/environment.py:272-277` (`SceneLoader` lazy import inside `_load_scene`).
**Apply to:** `src/surg_rl/rl/environment.py` EDIT — the new blocks branch inside `_setup_rewards` lazy-imports `compose_difficulty_overrides` from `dynamics.difficulty_wiring` and `TASK_REWARD_REGISTRY` from `rl.task_reward_router`. Function-body local, NOT module-level (keeps the module-import graph clean — RESEARCH.md A2).
```python
from surg_rl.scene_definition.loader import SceneLoader  # existing pattern
# Mirror for P37:
from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides
from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY
```

### Additive early-return branch (regression-safe)
**Source:** `src/surg_rl/dynamics/curriculum.py::update_curriculum` (P36-03 deviation #1 — additive early-return for discrete mode; continuous path byte-identical, SC#4).
**Apply to:** `src/surg_rl/rl/environment.py::_setup_rewards` EDIT — the new blocks branch is an additive early-return grafted before the existing `if task_type is not None:` router branch. Any scene WITHOUT `difficulty_blocks` falls through to the existing router — observable output byte-identical (TASK-09 regression gate). Mirror the P36-03 `update_curriculum` discrete-routing branch structure.

### Pure-helper extraction (refactor, observable output unchanged)
**Source:** `src/surg_rl/dynamics/curriculum.py::_meets_success_threshold` (P36-03 — extracted from `_should_advance`; `_should_advance` refactored to call the helper; observable output byte-identical, SC#4).
**Apply to:** `src/surg_rl/rl/rewards.py` EDIT — extract the `if key in params: self.attr = params[key]` body of each task reward's `apply_difficulty` into `apply_params(params)`; `apply_difficulty` delegates via `self.apply_params(self.interpolate_params(difficulty))`. Observable output of `apply_difficulty` byte-identical (regression-anchored to `test_difficulty_levels.py:356-362`).

### Registry dict keyed by `task_type` Literal (6 keys)
**Source:** `src/surg_rl/rl/task_reward_router.py:28-35` (`TASK_REWARD_REGISTRY`) + `src/surg_rl/dynamics/difficulty_wiring.py:30-61` (`ABSTRACT_TO_CONCRETE`).
**Apply to:** the new blocks branch in `_setup_rewards` — resolve `reward_cls` via `TASK_REWARD_REGISTRY.get(task.task_type)` (mirrors `task_reward_router.py:83`). The 6 keys (`suturing`, `dissection`, `needle_insertion`, `knot_tying`, `grasping`, `cutting`) match `TaskConfig.task_type` Literal at `schema.py:1106-1112`.

### Additive-regression gate (no edits to existing tests)
**Source:** `tests/test_difficulty_levels.py` + `tests/test_difficulty_config.py` + `tests/test_discrete_curriculum.py` + `tests/test_dynamics.py` (all stayed green through P36).
**Apply to:** `tests/test_difficulty_blocks.py` NEW — the existing difficulty suites MUST stay green unchanged; the new file is purely additive. `difficulty_blocks` defaults to `None`, `apply_difficulty` delegates to `apply_params` (observable output unchanged), the new `_setup_rewards` branch is additive early-return — all v0.5.0 behavior preserved. The targeted regression subset (RESEARCH.md Validation Architecture): `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_levels.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_dynamics.py -v`.

### `caplog` for `logger.warning` assertions (NOT `pytest.warns`)
**Source:** `tests/test_difficulty_config.py:195-213` (P36-02 deviation #1 — `caplog.at_level("WARNING", logger="surg_rl.dynamics.difficulty_wiring")` because the project uses `logging.getLogger`, not `warnings.warn`).
**Apply to:** `tests/test_difficulty_blocks.py` — any D-04 unmapped-override warning assertion in the SC#2 truth table uses `caplog`, not `pytest.warns`. Mirror the `caplog.at_level(...)` + `caplog.records` filter idiom verbatim.

## No Analog Found

None — every file has a strong analog. The 3 src edits are self-analogs (the field/method to mirror is in the same file). The 1 new test mirrors two existing test classes in the same directory. The 2 doc edits are one-token reconciliations on the same lines. The 6 fixtures + 2 read-only src files are reused verbatim from P36. This phase is pure assembly over existing primitives — no new pattern is invented.

## Metadata

**Analog search scope:** `src/surg_rl/scene_definition/` (`schema.py`, `loader.py`), `src/surg_rl/rl/` (`environment.py`, `rewards.py`, `difficulty.py`, `task_reward_router.py`), `src/surg_rl/dynamics/` (`difficulty_wiring.py`), `tests/` (`test_difficulty_levels.py`, `test_difficulty_config.py`), `.planning/` (`PROJECT.md`, `STATE.md`), `scenes/` + `tests/fixtures/scenes/`.

**Files read this session:**
- `src/surg_rl/scene_definition/schema.py` (targeted: 1080-1122, 1470-1507)
- `src/surg_rl/rl/environment.py` (targeted: 75-204, 262-281, 475-565)
- `src/surg_rl/rl/rewards.py` (targeted: 155-184, 670-704, 852-859, 999-1006, 1163-1170, 1329-1336, 1491-1498)
- `src/surg_rl/rl/difficulty.py` (full, 98 lines)
- `src/surg_rl/rl/task_reward_router.py` (full, 100 lines)
- `src/surg_rl/dynamics/difficulty_wiring.py` (full, 135 lines)
- `src/surg_rl/scene_definition/loader.py` (targeted: 545-610)
- `tests/test_difficulty_levels.py` (targeted: 1-100, 310-401)
- `tests/test_difficulty_config.py` (targeted: 137-215)
- `tests/fixtures/scenes/suturing_difficulty_hard.json` (targeted: 300-314)
- `.planning/PROJECT.md` (targeted: 80-84)
- `.planning/STATE.md` (targeted: 80-84)
- `.planning/phases/36-.../36-PATTERNS.md` (full)
- `.planning/phases/36-.../36-01-SUMMARY.md`, `36-02-SUMMARY.md`, `36-03-SUMMARY.md` (full)
- `.planning/phases/37-.../37-RESEARCH.md` (full)

**Pattern extraction date:** 2026-06-24