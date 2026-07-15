# Phase 36: Difficulty Schema + Discrete Curriculum - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 5 (2 new src, 1 extend src, 2 new tests)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/surg_rl/rl/difficulty.py` (EXTEND) | model (Pydantic leaf) | transform (validation) | same file `DifficultyLevel` block + `schema.py` `TaskConfig` field pattern | exact (self-analog) |
| `src/surg_rl/dynamics/difficulty_wiring.py` (NEW) | config + utility (registry dict + Pydantic wrapper + composer) | transform (interpolate-then-override) | `src/surg_rl/rl/task_reward_router.py` (registry) + `rewards.py::interpolate_params` (baseline) | role-match (registry) + exact (composer baseline) |
| `src/surg_rl/dynamics/curriculum.py` (EDIT, additive) | service (scheduler state machine) | event-driven (episode-gated transitions) | same file `advance_stage`/`_should_advance`/`current_difficulty` | exact (self-analog) |
| `tests/test_difficulty_config.py` (NEW) | test | request-response (parametrized I/O) | `tests/test_difficulty_levels.py` | exact (style + leaf-audit) |
| `tests/test_discrete_curriculum.py` (NEW) | test | request-response (state transitions) | `tests/test_dynamics.py::TestCurriculumScheduler` (lines 336-484) | exact (suite parity) |

## Pattern Assignments

### `src/surg_rl/rl/difficulty.py` (EXTEND — model, Pydantic leaf)

**Analog:** the existing `DifficultyLevel` block in the SAME file (`rl/difficulty.py:1-50`) — the leaf pattern to mirror. Plus `scene_definition/schema.py:1087-1121` for the Pydantic `BaseModel` field/validator idiom.

**Imports discipline (the leaf contract — success criterion #5):** the file MUST stay zero in-project imports. Verified current state, `rl/difficulty.py:1-14`:
```python
"""Difficulty level presets for surgical tasks.

This module is intentionally a leaf (no imports from `surg_rl.*`) to keep
`rewards.py` importable from `schema.py` without a circular import
(per CONTEXT.md §Circular import risk).
"""

from enum import Enum
```
The new `DifficultyLevelConfig` adds only `typing.Optional` + `pydantic.BaseModel` + `pydantic.field_validator` — both external. NO `from surg_rl...` and NO `from surg_rl.dynamics...` (that direction would create the cycle the leaf exists to prevent). `DiscreteCurriculumConfig` MUST NOT live here (D-08) precisely because it needs `DifficultyLevel` + `DifficultyLevelConfig` and belongs to the dynamics layer.

**Core leaf pattern to mirror** (`rl/difficulty.py:17-50` — the float-mixin enum):
```python
class _FloatMixin(float, Enum):
    """Enum whose members are also float instances."""

class DifficultyLevel(_FloatMixin):
    EASY = 0.0
    MEDIUM = 0.5
    HARD = 1.0
```
`DifficultyLevelConfig` extends the file below `DifficultyLevel` using the standard Pydantic v2 `BaseModel` + `field_validator` idiom from `schema.py`. Target shape (RESEARCH.md:479-507):
```python
from typing import Optional
from pydantic import BaseModel, field_validator

class DifficultyLevelConfig(BaseModel):
    """Per-level override config. Leaf: zero in-project imports."""
    tissue_stiffness: Optional[float] = None
    target_precision_tolerance: Optional[float] = None
    tool_position_noise: Optional[float] = None
    time_limit: Optional[float] = None

    @field_validator("tissue_stiffness")
    @classmethod
    def _check_tissue(cls, v):
        if v is not None and not (50.0 <= v <= 300.0):
            raise ValueError("tissue_stiffness out of global union bounds [50.0, 300.0]")
        return v
    # analogous for the other three using the verified bounds:
    #   target_precision_tolerance: [0.002, 0.3]
    #   tool_position_noise:         [0.01, 0.08]
    #   time_limit:                  [30.0, 180.0]
```

**Validation idiom (Pydantic v2 `field_validator`):** copy from `schema.py` (e.g. `_cap_resolution`, `schema.py:1480-1488`) — `@field_validator("field")` + `@classmethod` + raise `ValueError` + `return v`. Use the **`min/max over all endpoints`** bounds from RESEARCH.md Pitfall 1 (NOT D-07's "min lo / max hi" — that inverts for down-family `time_limit` and `target_precision_tolerance`).

**Key differences from analog:**
- `DifficultyLevel` is an Enum; `DifficultyLevelConfig` is a Pydantic `BaseModel` — different base, but same leaf-import discipline.
- Fields are `Optional[float] = None` (not Enum scalars) so the model is serialization-safe (Pitfall 5).
- Range validators are per-field `field_validator`, not `model_validator`, since each field has independent bounds.

---

### `src/surg_rl/dynamics/difficulty_wiring.py` (NEW — config + utility, registry + composer)

**Analogs:** `src/surg_rl/rl/task_reward_router.py` (registry pattern) + `rewards.py::interpolate_params` (the additive baseline the composer wraps, `rewards.py:675-681`).

**Registry pattern** — copy the `TASK_REWARD_REGISTRY` shape from `task_reward_router.py:7-35`:
```python
from typing import Any

from surg_rl.rl.difficulty import DifficultyLevel
from surg_rl.rl.rewards import (
    BaseRewardFunction,
    ...
)

# D-02: Registry maps task_type -> reward class
TASK_REWARD_REGISTRY: dict[str, type[BaseRewardFunction]] = {
    "suturing": SuturingReward,
    "dissection": DissectionReward,
    "needle_insertion": NeedlePassingReward,
    "knot_tying": KnotTyingReward,
    "grasping": GraspingReward,
    "cutting": CuttingReward,
}
```
Mirror this exactly for `ABSTRACT_TO_CONCRETE: dict[str, dict[str, str]]` — same 6 `task_type` Literal keys (NOT `TaskConfig.name` — RESEARCH.md Pitfall 2; the keys match `TASK_REWARD_REGISTRY` and `TaskConfig.task_type` Literal at `schema.py:1106-1112`). D-05 (authoritative, do not re-derive) gives the cell values — see RESEARCH.md:509-535 for the full dict literal.

**Warning-on-miss pattern** — copy from `task_reward_router.py:93-94`:
```python
            else:
                logger.warning(f"Unknown task_type={task_type!r}, using generic rewards only")
```
Apply verbatim for D-04 (set override field with no mapping for the loaded task → `logger.warning` + keep interpolated value, do NOT raise).

**Logger setup** — copy `task_reward_router.py:23-25`:
```python
from surg_rl.utils.logging import get_logger
logger = get_logger(__name__)
```

**Composer baseline (the additive primitive to wrap — DO NOT EDIT)** — `rewards.py:675-681` (identical classmethod on all 6 task reward classes; also at 836-841, 983-988, 1147-1152, 1313-1318, 1475-1480):
```python
@classmethod
def interpolate_params(cls, difficulty: float) -> dict[str, float]:
    return {
        name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
        for name, bounds in cls.PARAM_BOUNDS.items()
    }
```
`compose_difficulty_overrides(task_type, level, config, reward_cls)` calls `reward_cls.interpolate_params(level.value)` first, then for each SET (non-None) override field on `config` looks up `ABSTRACT_TO_CONCRETE[task_type].get(abstract_field)`; if missing → warn (D-04); if present → replace that key's value with the absolute override (D-06, NOT a delta/multiplier). Return the composed dict. The wiring module SHOULD accept `reward_cls` (or the interpolated dict) as a parameter so it need not import `task_reward_router` (RESEARCH.md Open Q3 recommendation) — keeps the edge one-way `dynamics.difficulty_wiring → rl.difficulty` only.

**Pydantic wrapper pattern** — `DiscreteCurriculumConfig` uses the standard `BaseModel + Field(default_factory=dict)` idiom from `schema.py`:
```python
from pydantic import BaseModel, Field
from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig

class DiscreteCurriculumConfig(BaseModel):
    levels: dict[DifficultyLevel, DifficultyLevelConfig] = Field(default_factory=dict)
    # default empty == pure interpolate_params(level.value) baseline (D-08)
```
`DifficultyLevel` (the `_FloatMixin(float, Enum)`) is used directly as the dict key — Pydantic v2 validates enum membership by float value (RESEARCH.md Pattern 3).

**Key differences from analogs:**
- Registry maps `task_type → {abstract_field → concrete_key_string}` (nested dict, pure data), not `task_type → class`.
- The composer is a module-level helper function, not a class — it operates on the read-only `interpolate_params` classmethod via the passed-in `reward_cls`.
- Imports `DifficultyLevel` + `DifficultyLevelConfig` from `rl.difficulty` (one-way edge; no cycle — verified RESEARCH.md Pattern 1).

---

### `src/surg_rl/dynamics/curriculum.py` (EDIT, additive — service, event-driven)

**Analog:** the existing `advance_stage` / `_should_advance` / `current_difficulty` in the SAME file (exact self-analog), plus `scene_definition/schema.py:1491-1506` for the `model_rebuild()` late-import cycle pattern.

**`current_difficulty` — the property to branch on `progression_mode`** (`curriculum.py:206-210`):
```python
@property
def current_difficulty(self) -> float:
    """Current difficulty level (0.0 to 1.0)."""
    d = self._stages[self._current_stage].difficulty
    return float(d.value) if isinstance(d, DifficultyLevel) else float(d)
```
Add a mode branch: in `"discrete"` mode return `float(self._current_level.value)`; in `"continuous"` mode keep the existing body byte-identical (regression gate, success criterion #4).

**`advance_stage` — the byte-identical continuous path DO NOT TOUCH** (`curriculum.py:228-242`):
```python
def advance_stage(self) -> bool:
    if self._current_stage not in self._stage_order:
        return False
    current_idx = self._stage_order.index(self._current_stage)
    if current_idx < len(self._stage_order) - 1:
        self._stage_entry_episode = self._episode
        self._current_stage = self._stage_order[current_idx + 1]
        self._stage_history.append(self._current_stage)
        return True
    return False
```
`advance_level` mirrors this structure but operates on a separate `_level_order = [EASY, MEDIUM, HARD]` and `_current_level` (D-10: separate state — never share `_current_stage`). Top-level (HARD) returns `False` (D-12).

**`_should_advance` — the stage-coupled gate to refactor, NOT reuse directly** (`curriculum.py:470-508`):
```python
def _should_advance(self) -> bool:
    stage_cfg = self._stages[self._current_stage]
    episodes_at_stage = self._episode - self._stage_entry_episode
    if episodes_at_stage < stage_cfg.episode_threshold:
        return False
    if self._current_stage not in self._stage_order:
        return False
    current_idx = self._stage_order.index(self._current_stage)
    if current_idx >= len(self._stage_order) - 1:
        return False
    recent_metrics = self._performance_history[-self.curriculum_config.advancement_window :]
    if not recent_metrics:
        return False
    success_rate = sum(m.get("success", 0) for m in recent_metrics) / len(recent_metrics)
    if success_rate >= stage_cfg.success_threshold:
        return True
    ...
```
RESEARCH.md Pitfall 3: `_should_advance` is hardwired to the continuous stage path (`stage_cfg.success_threshold`, `stage_cfg.episode_threshold`, `_stage_order.index(...)`). It does NOT accept a threshold argument. Per D-11 ("one threshold mechanism shared"), extract a pure helper:
```python
def _meets_success_threshold(self, threshold: float) -> bool:
    recent = self._performance_history[-self.curriculum_config.advancement_window :]
    if not recent:
        return False
    success_rate = sum(m.get("success", 0) for m in recent) / len(recent)
    return success_rate >= threshold
```
Refactor `_should_advance` to call `_meets_success_threshold(stage_cfg.success_threshold)` (observable output unchanged — regression-safe); `advance_level` calls `_meets_success_threshold(self.curriculum_config.min_success_rate)`. The success-rate arithmetic and the `advancement_window` slice are copied verbatim from `_should_advance:491-500`.

**Hysteresis reference** — `_should_regress:564-568` shows the `difficulty_hysteresis` usage idiom (referenced by RESEARCH.md for the shared helper, but the helper itself does not need hysteresis for `advance_level` — D-11 only shares the success-rate gate):
```python
success_rate = sum(m.get("success", 0) for m in recent_metrics) / len(recent_metrics)
hysteresis = self.curriculum_config.difficulty_hysteresis
regression_threshold = stage_cfg.success_threshold - 0.2 - hysteresis
return success_rate < regression_threshold
```

**`CurriculumConfig` dataclass — the place to add fields** (`curriculum.py:64-86`):
```python
@dataclass
class CurriculumConfig:
    enabled: bool = True
    initial_stage: CurriculumStage = CurriculumStage.EASY
    auto_advance: bool = True
    advancement_window: int = 50
    min_success_rate: float = 0.7
    difficulty_hysteresis: float = 0.05
    stage_configs: dict[CurriculumStage, CurriculumStageConfig] = field(default_factory=dict)
```
Add (Pitfall 4 — use dataclass field syntax, NOT `pydantic.Field`):
```python
progression_mode: Literal["continuous", "discrete"] = "continuous"
discrete_config: Optional["DiscreteCurriculumConfig"] = None  # forward ref + model_rebuild
```
Default `"continuous"` + `None` keeps v0.5.0 `advance_stage` output byte-identical (additive-regression gate, success criterion #4). Requires adding `from typing import Literal` to the existing `from typing import Any` import at `curriculum.py:12`.

**`__init__` additive state** (`curriculum.py:163-199`) — add alongside the existing `_current_stage` block:
```python
self._current_level: DifficultyLevel = DifficultyLevel.EASY
self._level_entry_episode: int = 0
```
Mirror the `_stage_entry_episode` pattern at `curriculum.py:186`.

**`model_rebuild()` late-import cycle pattern** — copy verbatim from `scene_definition/schema.py:1491-1506`:
```python
# Late import of DifficultyLevel to break the ... import cycle. With
# `from __future__ import annotations` + string annotation on
# CurriculumConfig.discrete_config, the type is not resolved at class body
# time. We import DiscreteCurriculumConfig AFTER all classes are defined,
# then call model_rebuild() to resolve the forward ref.
from surg_rl.dynamics.difficulty_wiring import (  # noqa: E402
    DiscreteCurriculumConfig,
)  # noqa: F401 — module-level binding for forward ref resolution
CurriculumConfig.__init_subclass__  # (no-op; dataclass, not Pydantic model)
```
IMPORTANT nuance: `CurriculumConfig` is a `@dataclass`, NOT a Pydantic `BaseModel` (Pitfall 4), so `model_rebuild()` does NOT apply to it. The forward-ref string on `discrete_config: Optional["DiscreteCurriculumConfig"]` resolves at runtime through the late import binding alone (dataclass field annotations are evaluated lazily under `from __future__ import annotations`, which `curriculum.py` does NOT currently have — planner must add it at the top of `curriculum.py`). Add `from __future__ import annotations` as the first import line, mirroring `schema.py:5`. The late import block at the module bottom binds `DiscreteCurriculumConfig` so anything that introspects the annotation (e.g. `typing.get_type_hints`) resolves it. `DiscreteCurriculumConfig` itself (Pydantic) needs NO `model_rebuild` here because its `levels` field references only `DifficultyLevel` + `DifficultyLevelConfig`, both imported eagerly at the top of `difficulty_wiring.py` (one-way edge, no cycle — RESEARCH.md Pattern 1).

**Key differences from analog:**
- `advance_level` operates on `_level_order = [EASY, MEDIUM, HARD]` (3 levels, `DifficultyLevel` scalars 0.0/0.5/1.0) — NOT `_stage_order` (4 stages, scalars 0.25/0.5/0.75/1.0). D-10: the two paths must not share state.
- `current_difficulty` gains a mode branch; continuous body unchanged.
- The `model_rebuild()` pattern is referenced but adapted: `CurriculumConfig` is a dataclass, so only the late-import binding + `from __future__ import annotations` apply (no `model_rebuild()` call for the dataclass itself).

---

### `tests/test_difficulty_config.py` (NEW — test, parametrized I/O)

**Analog:** `tests/test_difficulty_levels.py` (the additive-regression gate style + the `DifficultyLevel` import surface).

**Imports + module docstring pattern** — copy from `test_difficulty_levels.py:1-25`:
```python
"""Tests for DifficultyLevel enum and its re-export.
...
"""
import pytest

from surg_rl.rl import DifficultyLevel
from surg_rl.rl.rewards import (
    SuturingReward, DissectionReward, NeedlePassingReward,
    KnotTyingReward, GraspingReward, CuttingReward,
)
```
For the new file import `DifficultyLevelConfig` from `surg_rl.rl.difficulty` and `DiscreteCurriculumConfig` + `compose_difficulty_overrides` + `ABSTRACT_TO_CONCRETE` from `surg_rl.dynamics.difficulty_wiring`. Use `TASK_REWARD_REGISTRY` from `surg_rl.rl.task_reward_router` to resolve the reward class per `task_type` in the truth-table test (RESEARCH.md Open Q3 recommendation).

**Parametrized direction/up-family test style** — copy the `@pytest.mark.parametrize` shape from `test_difficulty_levels.py:83-167`:
```python
@pytest.mark.parametrize(
    "reward_cls,down_keys,up_keys",
    [ (...), ... ],
)
def test_difficulty_direction(reward_cls, down_keys, up_keys):
    cls_map = {...}
    cls = cls_map[reward_cls]
    easy = cls.get_params_for_difficulty(DifficultyLevel.EASY)
    hard = cls.get_params_for_difficulty(DifficultyLevel.HARD)
    for name in down_keys:
        assert hard[name] < easy[name], (...)
    for name in up_keys:
        assert hard[name] > easy[name], (...)
```
Mirror this layout for the truth-table parametrization over `(task_type, level, single_field_override)`: assert the composed dict differs from pure `interpolate_params(level.value)` ONLY on the mapped concrete key; all other keys equal. Plus the empty-`levels` case (RESEARCH.md SC#2).

**Acceptance/rejection test style** (for `field_validator` range checks) — copy the simple assert-raises idiom; use `pytest.raises(ValueError)` (Pydantic v2 raises `ValidationError` whose `__cause__`/message carries the `ValueError`). The leaf-audit test (SC#5) introspects `surg_rl.rl.difficulty` module source for `surg_rl.` substrings (per RESEARCH.md Validation Architecture SC#5).

**Test class organization** — copy the `class TestDifficultyLevel:` / `class TestDifficultyWiring:` / `class TestDifficultyIntegration:` pattern (`test_difficulty_levels.py:28, 256, 316`).

**Key differences from analog:**
- New file tests `DifficultyLevelConfig` (Pydantic model), not the `DifficultyLevel` enum.
- Adds the truth-table test (parametrized over compose outputs) — new pattern, but uses the same `@pytest.mark.parametrize` shape.
- Adds the leaf-import audit (SC#5) — grep the module source for `surg_rl.` outside comments.

---

### `tests/test_discrete_curriculum.py` (NEW — test, state transitions)

**Analog:** `tests/test_dynamics.py::TestCurriculumScheduler` (`test_dynamics.py:336-484`).

**Scheduler test style** — copy the `CurriculumScheduler()` construction + `advance_stage`/`set_stage` assertions from `test_dynamics.py:342-380`:
```python
class TestCurriculumScheduler:
    def test_init(self):
        scheduler = CurriculumScheduler()
        assert scheduler.current_stage == CurriculumStage.EASY
        assert scheduler.current_difficulty == 0.25

    def test_stage_progression(self):
        scheduler = CurriculumScheduler()
        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.MEDIUM
        ...
        assert scheduler.advance_stage() is False  # Already at max
```
Mirror this exactly for `advance_level`: EASY → MEDIUM → HARD → `False` (D-12). Construct with `CurriculumConfig(progression_mode="discrete")` and assert `current_difficulty` == `_current_level.value` at each step.

**Auto-advancement test style** — copy `test_dynamics.py:393-411`:
```python
def test_auto_advancement(self):
    curriculum_config = CurriculumConfig(auto_advance=True, advancement_window=10)
    scheduler = CurriculumScheduler(curriculum_config=curriculum_config)
    scheduler.start()
    for _i in range(60):
        scheduler.reset()
        scheduler.episode_end({"success": 1, "reward": 100}, simulator=None)
    assert scheduler.current_stage != CurriculumStage.EASY or scheduler._episode < 50
```
Adapt for `advance_level` driven by `_meets_success_threshold(curriculum_config.min_success_rate)`.

**Regression-parity test (SC#4)** — the new file MUST include a `test_advance_stage_unchanged` that snapshots the continuous path and asserts byte-identical output to v0.5.0. Reuse `TestCurriculumScheduler::test_stage_progression` (`test_dynamics.py:349-360`) as the parity reference — the existing `test_dynamics.py` suite stays green unchanged (additive-regression gate).

**Imports** — copy `test_dynamics.py` top imports (the test file already imports `CurriculumConfig`, `CurriculumStage`, `CurriculumScheduler` — verify by reading `test_dynamics.py:1-30` at implement time).

**Key differences from analog:**
- Tests the discrete path (`progression_mode="discrete"`, `advance_level`, `set_difficulty_level`) in addition to the continuous parity test.
- The continuous-path tests in `test_dynamics.py` MUST stay unchanged (additive) — the parity test in the new file is additive coverage, not an edit.

---

## Shared Patterns

### Leaf-model + late-import + `model_rebuild()` cycle resolution (v0.4.2 canon)
**Source:** `src/surg_rl/scene_definition/schema.py:5` (`from __future__ import annotations`), `:12-19` (TYPE_CHECKING block), `:1113-1121` (string forward-ref field), `:1491-1506` (late import + `model_rebuild()`).
**Apply to:**
- `src/surg_rl/rl/difficulty.py` EXTEND — keep zero in-project imports (the leaf contract). No late import needed in the leaf itself; it is the leaf.
- `src/surg_rl/dynamics/curriculum.py` EDIT — add `from __future__ import annotations` at top; add a late import of `DiscreteCurriculumConfig` at module bottom to bind the forward ref used by `CurriculumConfig.discrete_config: Optional["DiscreteCurriculumConfig"]`. NOTE: `CurriculumConfig` is a `@dataclass` (Pitfall 4), so NO `model_rebuild()` call — only the late-import binding resolves the string annotation under PEP 563.
- `src/surg_rl/dynamics/difficulty_wiring.py` NEW — imports `DifficultyLevel` + `DifficultyLevelConfig` eagerly from `rl.difficulty` (one-way edge, no cycle, no forward ref needed).

Concrete excerpt (`schema.py:1491-1506`):
```python
from surg_rl.rl.difficulty import (  # noqa: E402
    DifficultyLevel,
)  # noqa: F401 — module-level binding for forward ref resolution
TaskConfig.model_rebuild()
```

### Pydantic v2 `field_validator` range validation
**Source:** `src/surg_rl/scene_definition/schema.py:1480-1488` (`_cap_resolution`).
**Apply to:** all 4 override fields on `DifficultyLevelConfig`.
```python
@field_validator("resolution")
@classmethod
def _cap_resolution(cls, v):
    if v[0] > 128 or v[1] > 128:
        raise ValueError("Resolution capped at 128 per dimension")
    return v
```
Use the **`min/max over all endpoints`** bounds from RESEARCH.md Pitfall 1 (NOT D-07's "min lo / max hi"):
- `tissue_stiffness`: [50.0, 300.0]
- `target_precision_tolerance`: [0.002, 0.3]
- `tool_position_noise`: [0.01, 0.08]
- `time_limit`: [30.0, 180.0]

### Registry dict keyed by `task_type` Literal
**Source:** `src/surg_rl/rl/task_reward_router.py:28-35` (`TASK_REWARD_REGISTRY`).
**Apply to:** `ABSTRACT_TO_CONCRETE` in `difficulty_wiring.py`. Same 6 keys (`suturing`, `dissection`, `needle_insertion`, `knot_tying`, `grasping`, `cutting`) — matches `TaskConfig.task_type` Literal at `schema.py:1106-1112`. Do NOT key by `TaskConfig.name` (RESEARCH.md Pitfall 2).

### Warning-on-miss logging
**Source:** `src/surg_rl/rl/task_reward_router.py:93-94`.
**Apply to:** `compose_difficulty_overrides` D-04 path (set override field with no mapping for the loaded task).
```python
logger.warning(f"Unknown task_type={task_type!r}, using generic rewards only")
```

### Additive-regression gate (no edits to existing tests)
**Source:** `tests/test_difficulty_levels.py` + `tests/test_dynamics.py::TestCurriculumScheduler`.
**Apply to:** both new test files. The existing suites MUST stay green unchanged; new files are purely additive. `progression_mode` defaults to `"continuous"`, `discrete_config` defaults to `None`, `DifficultyLevelConfig` is additive in the leaf — all v0.5.0 behavior preserved.

### Dataclass field syntax (NOT Pydantic Field)
**Source:** `src/surg_rl/dynamics/curriculum.py:64-86` (`CurriculumConfig` `@dataclass`).
**Apply to:** the new `progression_mode` + `discrete_config` fields on `CurriculumConfig`. Use `field(default_factory=...)` / `Optional[...] = None` / `Literal[...] = "continuous"` — do NOT use `pydantic.Field` (Pitfall 4: `CurriculumConfig` is a stdlib `@dataclass`, not `pydantic.dataclasses`).

## No Analog Found

None — every file has a strong analog. Files 1 and 3 are self-analogs (the leaf to mirror is in the same file; the scheduler methods to mirror are in the same file). File 2 combines two exact primitives (`TASK_REWARD_REGISTRY` shape + `interpolate_params` baseline). Files 4 and 5 mirror existing test suites in the same directory.

## Metadata

**Analog search scope:** `src/surg_rl/rl/`, `src/surg_rl/dynamics/`, `src/surg_rl/scene_definition/`, `tests/`. Files read in full this session: `rl/difficulty.py`, `rl/task_reward_router.py`, `dynamics/curriculum.py` (617 lines), `scene_definition/schema.py` (targeted: 1080-1122, 1480-1507, top), `rl/rewards.py` (targeted: 545-706, grep over all `PARAM_BOUNDS`/`interpolate_params` sites), `tests/test_difficulty_levels.py` (406 lines), `tests/test_dynamics.py` (targeted: 336-484).
**Files scanned:** 7 source + 2 test analogs.
**Pattern extraction date:** 2026-06-24.