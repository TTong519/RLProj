# Plan 01-02 Task 3: LightConfig Immutable Validator

## Objective
Fix the `LightConfig` Pydantic v2 `model_validator(mode="before")` so it does not mutate the caller's input `dict` in place.

## Changes

### `src/surg_rl/scene_definition/schema.py`
- Added `data = dict(data)` inside `validate_light_type` when `isinstance(data, dict)` so any subsequent mutation affects a copy, not the original dict.

### `tests/test_schema.py`
- Added `test_light_config_does_not_mutate_input_dict` regression test:
  ```python
  original = {"type": "directional"}
  LightConfig(**original)
  assert "direction" not in original
  ```

## Verification
- `PYTHONPATH=src pytest tests/test_schema.py -k "light_config" -xvs` → 2 passed
- `PYTHONPATH=src pytest tests/test_schema.py tests/test_scene_generation.py::TestPromptTemplates -x -q` → 62 passed

## Commit
**fix(phase-01-02): prevent LightConfig validator from mutating input dict**
- Hash: `1d7fdbe`
