"""SchemaWalker — recursive walker over Pydantic v2 JSON Schema -> FieldSpec list.

Per CONTEXT.md D-05..D-08: walks the schema tree over all schema classes,
emits one FieldSpec per leaf field with full path / type / default / required /
constraint metadata. The walker is pure-Python (no Qt import) so it's
independently testable.

Widget hints are inferred from:
  - enum: "enum-combobox"
  - {x,y,z} triple on a Position/Orientation-like class: "vec3-spinbox"
  - {roll,pitch,yaw} triple: "vec3-spinbox"
  - URI format: "file-picker"
  - color hex pattern: "color-picker"
  - confloat with ge+le constraints: "range-slider"
  - default: "text"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldSpec:
    """One leaf field in the scene schema."""

    json_path: str  # e.g. "instruments.0.pose.position.x"
    field_name: str  # e.g. "x"
    type: str  # e.g. "string", "number", "integer", "boolean", "array", "object"
    format: str | None = None
    widget_hint: str = "text"
    enum_values: list[Any] = field(default_factory=list)
    default_value: Any = None
    required: bool = False
    constraints: dict[str, Any] = field(default_factory=dict)


# Heuristic: detect small coordinate tuples so they get the 3-spinbox widget.
_VEC3_TRIPLES: tuple[frozenset[str], ...] = (
    frozenset({"x", "y", "z"}),
    frozenset({"roll", "pitch", "yaw"}),
)
_COLOR_QUADS: frozenset[str] = frozenset({"r", "g", "b", "a"})

_CONSTRAINT_KEYS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "multipleOf",
)


class SchemaWalker:
    """Recursively walks a JSON Schema dict, emitting one FieldSpec per leaf."""

    def __init__(self) -> None:
        self._counter = 0

    def walk(self, schema: dict[str, Any]) -> list[FieldSpec]:
        """Walk the top-level schema. Returns a list of FieldSpec (one per leaf)."""
        self._counter = 0
        out: list[FieldSpec] = []
        self._walk_object(
            schema,
            prefix="",
            out=out,
            required_set=set(schema.get("required", [])),
            defs=schema.get("$defs", {}),
        )
        return out

    def _walk_object(
        self,
        schema: dict[str, Any],
        prefix: str,
        out: list[FieldSpec],
        required_set: set[str],
        defs: dict[str, Any],
    ) -> None:
        # If this object matches a vec3/color pattern, emit a single hint
        # for the parent and tag all children with the same hint.
        object_hint = self._object_hint(schema, defs)
        props = schema.get("properties", {})
        for name, sub in props.items():
            full_path = f"{prefix}.{name}" if prefix else name
            sub_required = name in required_set
            self._walk_field(
                sub, full_path, name, out, required=sub_required, defs=defs, parent_hint=object_hint
            )

    def _walk_field(
        self,
        schema: dict[str, Any],
        path: str,
        name: str,
        out: list[FieldSpec],
        required: bool,
        defs: dict[str, Any],
        parent_hint: str | None = None,
    ) -> None:
        # Resolve $ref to its $def entry.
        if "$ref" in schema:
            ref_name = schema["$ref"].rsplit("/", 1)[-1]
            schema = defs.get(ref_name, schema)

        if schema.get("type") == "object":
            self._walk_object(
                schema,
                prefix=path,
                out=out,
                required_set=set(schema.get("required", [])),
                defs=defs,
            )
            return
        if schema.get("type") == "array":
            items = schema.get("items", {"type": "string"})
            self._walk_field(items, path, name, out, required=False, defs=defs)
            return

        # Leaf field.
        widget_hint = parent_hint or self._infer_widget_hint(name, schema)
        spec = FieldSpec(
            json_path=path,
            field_name=name,
            type=schema.get("type", "string"),
            format=schema.get("format"),
            widget_hint=widget_hint,
            enum_values=list(schema.get("enum", [])),
            default_value=schema.get("default"),
            required=required,
            constraints={k: schema[k] for k in _CONSTRAINT_KEYS if k in schema},
        )
        out.append(spec)

    def _object_hint(self, schema: dict[str, Any], defs: dict[str, Any]) -> str | None:
        """If this object matches a vec3/color pattern, return the matching hint."""
        if "$ref" in schema:
            ref_name = schema["$ref"].rsplit("/", 1)[-1]
            schema = defs.get(ref_name, schema)
        if schema.get("type") != "object":
            return None
        props = schema.get("properties", {})
        for triple in _VEC3_TRIPLES:
            if triple.issubset(props.keys()) and all(
                props[a].get("type") == "number" for a in triple
            ):
                return "vec3-spinbox"
        if _COLOR_QUADS.issubset(props.keys()) and all(
            props[a].get("type") == "number" for a in _COLOR_QUADS
        ):
            return "color-picker"
        return None

    def _infer_widget_hint(self, name: str, schema: dict[str, Any]) -> str:
        if "enum" in schema and schema.get("type") == "string":
            return "enum-combobox"

        if schema.get("format") == "uri":
            return "file-picker"

        if schema.get("type") == "string" and name in ("color", "colour", "hex_color", "hex"):
            return "color-picker"

        if (
            schema.get("type") in ("number", "integer")
            and "minimum" in schema
            and "maximum" in schema
        ):
            return "range-slider"

        return "text"
