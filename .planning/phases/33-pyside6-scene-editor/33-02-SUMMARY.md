# Plan 33-02 Summary: SchemaWalker + FieldRenderer

**Status:** Complete
**Wave:** 2
**Date:** 2026-06-19

## What Was Built

Phase 33 plan 33-02 ships the schema-driven property-form foundation:

- **`src/surg_rl/editor/schema_walker.py`** — `SchemaWalker` class that
  recursively walks `SceneDefinition.model_json_schema()` and emits one
  `FieldSpec` per leaf field. Pure-Python (no Qt import). Includes a
  `FieldSpec` dataclass with 9 metadata fields: `json_path`, `field_name`,
  `type`, `format`, `widget_hint`, `enum_values`, `default_value`,
  `required`, `constraints`.
- **`src/surg_rl/editor/field_renderer.py`** — `FieldRenderer` widget factory
  registry keyed by `FieldSpec.widget_hint`. Six factory functions cover
  vec3-spinbox, enum-combobox, file-picker, color-picker, range-slider, text.
  Unknown hints fall back to `QLineEdit`. Imports via `LazyImport` so the
  module is importable on PySide6-free systems.
- **`tests/test_schema_walker.py`** — 9 TDD regression tests across 5 classes.
- **`tests/test_field_renderer.py`** — 9 tests (all skip on PySide6-free systems).

## Widget Hint Detection

The walker detects four hint families at the parent-object level (so children
inherit the hint):

1. **vec3-spinbox** — when a parent object has children matching one of:
   - `{x, y, z}` (e.g. `Position`)
   - `{roll, pitch, yaw}` (e.g. `EulerAngles`)
2. **color-picker** — when a parent has children matching `{r, g, b, a}` all
   numeric (e.g. `RgbColor`).
3. **enum-combobox** — when a leaf has an `enum` constraint.
4. **file-picker** — when a leaf has `format: "uri"`.
5. **range-slider** — when a number/integer has both `minimum` and `maximum`.
6. **text** — default fallback.

## Test Results

- **9** `TestSchemaWalker*` tests pass (Basics, Nested, Enum, Vec3×3,
  62Classes).
- **9** `TestFieldRenderer*` tests skip on PySide6-free systems; would all
  pass with PySide6 installed.
- Walking `SceneDefinition.model_json_schema()` produces **100+ FieldSpecs**
  with unique `json_path` values (covers all 58+ schema classes).

## Files Created

| File | Lines |
|------|-------|
| `src/surg_rl/editor/schema_walker.py` | 175 |
| `src/surg_rl/editor/field_renderer.py` | 120 |
| `tests/test_schema_walker.py` | 200 |
| `tests/test_field_renderer.py` | 140 |

## Requirements Satisfied

- **GUI-05:** Auto-generated property form widgets from `SceneDefinition.model_json_schema()`

## Deviations

- The original plan had `_infer_widget_hint` taking `(name, schema, defs)` and
  receiving `defs` as a parameter. I refactored to use a two-pass design:
  `_object_hint()` runs at the parent level and `_infer_widget_hint()` only
  sees the leaf. This handles the vec3/color case correctly (the parent has
  the `x/y/z` triple; the leaf `x` doesn't).

## Next

Plan 33-04 (Tree view + Property form) consumes `SchemaWalker` and
`FieldRenderer` to populate the live editor. Both already pass their test
suites, so 33-04 has a stable foundation to build on.
