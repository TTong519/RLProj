"""TDD regression for SchemaWalker — locks the contract from CONTEXT.md D-05..D-08."""

from __future__ import annotations

from surg_rl.scene_definition import SceneDefinition


class TestSchemaWalkerBasics:
    def test_walk_top_level_object_emits_one_spec_per_field(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "untitled"},
                "count": {"type": "integer", "default": 0, "minimum": 0},
            },
            "required": ["name"],
        }
        w = SchemaWalker()
        specs = w.walk(schema)
        paths = {s.json_path for s in specs}
        assert paths == {"name", "count"}

    def test_spec_carries_default_and_required(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "x"},
                "n": {"type": "integer", "default": 0},
            },
            "required": ["name"],
        }
        w = SchemaWalker()
        specs = {s.json_path: s for s in w.walk(schema)}
        assert specs["name"].required is True
        assert specs["name"].default_value == "x"
        assert specs["n"].required is False
        assert specs["n"].default_value == 0


class TestSchemaWalkerNested:
    def test_walk_nested_object_via_dollar_ref(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "pose": {"$ref": "#/$defs/Position"},
            },
            "$defs": {
                "Position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "default": 0.0},
                        "y": {"type": "number", "default": 0.0},
                        "z": {"type": "number", "default": 0.0},
                    },
                },
            },
        }
        w = SchemaWalker()
        specs = w.walk(schema)
        paths = {s.json_path for s in specs}
        assert paths == {"pose.x", "pose.y", "pose.z"}
        for s in specs:
            assert s.type == "number"
            assert s.default_value == 0.0

    def test_walk_array_of_objects_emits_indexed_paths(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "instruments": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Instrument"},
                },
            },
            "$defs": {
                "Instrument": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "default": "inst-0"},
                        "type": {"type": "string", "enum": ["scalpel", "forceps"]},
                    },
                },
            },
        }
        w = SchemaWalker()
        specs = w.walk(schema)
        paths = {s.json_path for s in specs}
        assert "instruments.id" in paths
        assert "instruments.type" in paths


class TestSchemaWalkerEnum:
    def test_enum_string_field_carries_enum_values(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "enum": ["red", "green", "blue"],
                    "default": "red",
                },
            },
        }
        w = SchemaWalker()
        specs = {s.json_path: s for s in w.walk(schema)}
        assert specs["color"].enum_values == ["red", "green", "blue"]
        assert specs["color"].widget_hint == "enum-combobox"


class TestSchemaWalkerVec3:
    def test_position_class_emits_vec3_spinbox_hint(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "position": {"$ref": "#/$defs/Position"},
            },
            "$defs": {
                "Position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "default": 0.0},
                        "y": {"type": "number", "default": 0.0},
                        "z": {"type": "number", "default": 0.0},
                    },
                },
            },
        }
        w = SchemaWalker()
        specs = w.walk(schema)
        pos_specs = [s for s in specs if s.field_name in ("x", "y", "z")]
        assert all(s.widget_hint == "vec3-spinbox" for s in pos_specs)

    def test_euler_angles_class_emits_vec3_spinbox_hint(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "orientation": {"$ref": "#/$defs/EulerAngles"},
            },
            "$defs": {
                "EulerAngles": {
                    "type": "object",
                    "properties": {
                        "roll": {"type": "number", "default": 0.0},
                        "pitch": {"type": "number", "default": 0.0},
                        "yaw": {"type": "number", "default": 0.0},
                    },
                },
            },
        }
        w = SchemaWalker()
        specs = w.walk(schema)
        rpy_specs = [s for s in specs if s.field_name in ("roll", "pitch", "yaw")]
        assert len(rpy_specs) == 3
        assert all(s.widget_hint == "vec3-spinbox" for s in rpy_specs)

    def test_rgb_color_class_emits_color_picker_hint(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = {
            "type": "object",
            "properties": {
                "color": {"$ref": "#/$defs/RgbColor"},
            },
            "$defs": {
                "RgbColor": {
                    "type": "object",
                    "properties": {
                        "r": {"type": "number", "default": 1.0, "minimum": 0.0, "maximum": 1.0},
                        "g": {"type": "number", "default": 1.0, "minimum": 0.0, "maximum": 1.0},
                        "b": {"type": "number", "default": 1.0, "minimum": 0.0, "maximum": 1.0},
                        "a": {"type": "number", "default": 1.0, "minimum": 0.0, "maximum": 1.0},
                    },
                },
            },
        }
        w = SchemaWalker()
        specs = w.walk(schema)
        rgba_specs = [s for s in specs if s.field_name in ("r", "g", "b", "a")]
        assert len(rgba_specs) == 4
        assert all(s.widget_hint == "color-picker" for s in rgba_specs)


class TestSchemaWalker62Classes:
    def test_walk_full_scene_definition_covers_all_classes(self) -> None:
        from surg_rl.editor.schema_walker import SchemaWalker

        schema = SceneDefinition.model_json_schema()
        w = SchemaWalker()
        specs = w.walk(schema)
        assert len(specs) >= 100, f"Walker emitted only {len(specs)} specs; expected 100+"
        paths = [s.json_path for s in specs]
        assert len(paths) == len(set(paths)), "Duplicate json_paths in walker output"
        assert all(p for p in paths), "Walker emitted an empty json_path"
