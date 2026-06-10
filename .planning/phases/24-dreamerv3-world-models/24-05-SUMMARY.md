---
phase: 24-dreamerv3-world-models
plan: 05
type: execute
wave: 5
depends_on: ["24-02"]
completed: 2026-06-09
requirements: ["DMV3-02", "DMV3-04"]
---

## Summary

**Objective:** Close the gap from UAT Test 12: Add support for the 3 missing DreamerV3 training task types — knot_tying, needle_insertion, and dissection — in the `_create_scene_for_task` function in training.py.

## Changes Made

### 1. Added Missing InstrumentType Enum Values (src/surg_rl/scene_definition/schema.py)
- Added `KNOT_TIER = "knot_tier"` for knot tying tasks
- Added `NEEDLE = "needle"` for needle insertion tasks

### 2. Added DreamerConfig to SceneDefinition (src/surg_rl/scene_definition/schema.py)
- Added `dreamer: DreamerConfig | None` field to SceneDefinition class to store DreamerV3 configuration

### 3. Implemented Task Support in _create_scene_for_task (src/surg_rl/dreamer/training.py)
- **knot_tying**: Uses `InstrumentType.KNOT_TIER` with "knot_tier" instrument, `TissueType.CUSTOM` suture pad tissue
- **needle_insertion**: Uses `InstrumentType.NEEDLE` with "needle" instrument, `TissueType.ORGAN` organ tissue (reuses liver mesh)
- **dissection**: Uses `InstrumentType.SCISSORS` with "dissection_scissors" instrument, `TissueType.MUSCLE` dissection tissue

All 3 new tasks follow the exact same pattern as existing tasks (suturing, grasping, cutting) with proper InstrumentConfig, TissueConfig, TaskConfig, and DreamerConfig.

### 4. Created Test File (tests/test_dreamer_training.py)
- 10 test cases covering all 6 task types
- Validates instrument types, tissue types, task_type matching, DreamerConfig presence, and no CUSTOM fallback
- All 10 tests pass

## Verification

```python
from surg_rl.dreamer.training import _create_scene_for_task
for task in ['suturing', 'knot_tying', 'needle_insertion', 'grasping', 'cutting', 'dissection']:
    scene = _create_scene_for_task(task, 'state', (64, 64))
    print(f'{task}: instrument={scene.instruments[0].type.value}, tissue={scene.tissues[0].type.value}')
```

Output:
```
suturing: instrument=needle_driver, tissue=organ
knot_tying: instrument=knot_tier, tissue=custom
needle_insertion: instrument=needle, tissue=organ
grasping: instrument=forceps, tissue=skin
cutting: instrument=scissors, tissue=skin
dissection: instrument=scissors, tissue=muscle
```

## UAT Status

**Test 12: All 6 Task Types Supported** → **PASS** (was "issue", now resolved)

All 12 UAT tests now pass.

## Files Modified

- `src/surg_rl/scene_definition/schema.py` — Added KNOT_TIER, NEEDLE to InstrumentType; added dreamer field to SceneDefinition
- `src/surg_rl/dreamer/training.py` — Added 3 new task types to _create_scene_for_task
- `tests/test_dreamer_training.py` — New test file with 10 test cases