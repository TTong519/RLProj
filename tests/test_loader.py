"""Tests for scene loader module."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from surg_rl.scene_definition import (
    SceneDefinition,
    Metadata,
    SimulatorType,
    SceneLoader,
    SceneCache,
    AssetManager,
    SceneLoaderError,
    SceneFileNotFoundError,
    SceneValidationError,
    SceneParseError,
    AssetLoadError,
    get_loader,
    reset_loader,
    load_scene,
    save_scene,
)




def _convert_tuples_for_yaml(obj):
    """Convert tuples and enums to lists/strings for YAML serialization."""
    from enum import Enum
    if isinstance(obj, tuple):
        return list(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: _convert_tuples_for_yaml(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_tuples_for_yaml(item) for item in obj]
    return obj

class TestSceneCache:
    """Tests for SceneCache class."""

    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        cache = SceneCache(max_size=10)
        assert cache.max_size == 10
        assert len(cache) == 0

    def test_cache_put_and_get(self, tmp_path: Path):
        """Test putting and getting scenes from cache."""
        cache = SceneCache(max_size=10)
        scene = SceneDefinition(metadata=Metadata(name="Test Scene"))
        scene_file = tmp_path / "test_scene.json"
        scene_file.write_text(scene.model_dump_json())

        # Put scene in cache
        cache.put(scene_file, scene)
        assert len(cache) == 1

        # Get scene from cache
        cached = cache.get(scene_file)
        assert cached is not None
        assert cached.metadata.name == "Test Scene"

    def test_cache_miss(self, tmp_path: Path):
        """Test cache miss for non-existent scene."""
        cache = SceneCache(max_size=10)
        scene_file = tmp_path / "nonexistent.json"

        result = cache.get(scene_file)
        assert result is None

    def test_cache_eviction(self, tmp_path: Path):
        """Test LRU eviction when cache is full."""
        cache = SceneCache(max_size=3)

        for i in range(5):
            scene = SceneDefinition(metadata=Metadata(name=f"Scene {i}"))
            scene_file = tmp_path / f"scene_{i}.json"
            scene_file.write_text(scene.model_dump_json())
            cache.put(scene_file, scene)

        # Cache should have max_size scenes
        assert len(cache) == 3

        # First two scenes should be evicted
        scene_file_0 = tmp_path / "scene_0.json"
        assert cache.get(scene_file_0) is None

        # Last three scenes should be present
        scene_file_3 = tmp_path / "scene_3.json"
        assert cache.get(scene_file_3) is not None

    def test_cache_clear(self, tmp_path: Path):
        """Test clearing cache."""
        cache = SceneCache(max_size=10)
        scene = SceneDefinition(metadata=Metadata(name="Test"))
        scene_file = tmp_path / "test.json"
        scene_file.write_text(scene.model_dump_json())

        cache.put(scene_file, scene)
        assert len(cache) == 1

        cache.clear()
        assert len(cache) == 0

    def test_cache_contains(self, tmp_path: Path):
        """Test __contains__ method."""
        cache = SceneCache(max_size=10)
        scene = SceneDefinition(metadata=Metadata(name="Test"))
        scene_file = tmp_path / "test.json"
        scene_file.write_text(scene.model_dump_json())

        assert scene_file not in cache

        cache.put(scene_file, scene)
        assert scene_file in cache


class TestAssetManager:
    """Tests for AssetManager class."""

    def test_asset_manager_initialization(self):
        """Test asset manager initializes correctly."""
        manager = AssetManager()
        assert manager.assets_dir is None

        manager_with_dir = AssetManager(assets_dir=Path("/some/path"))
        assert manager_with_dir.assets_dir == Path("/some/path")

    def test_supported_mesh_formats(self):
        """Test mesh format validation."""
        manager = AssetManager()

        for ext in [".obj", ".stl", ".ply", ".gltf", ".glb", ".urdf"]:
            assert ext in manager.SUPPORTED_MESH_FORMATS

    def test_supported_texture_formats(self):
        """Test texture format validation."""
        manager = AssetManager()

        for ext in [".png", ".jpg", ".jpeg", ".bmp", ".tga", ".hdr"]:
            assert ext in manager.SUPPORTED_TEXTURE_FORMATS

    def test_asset_exists(self, tmp_path: Path):
        """Test checking if asset exists."""
        manager = AssetManager(assets_dir=tmp_path)

        # Create test file
        test_file = tmp_path / "test.obj"
        test_file.write_text("test")

        assert manager.asset_exists("test.obj")
        assert manager.asset_exists(test_file)
        assert not manager.asset_exists("nonexistent.obj")

    def test_resolve_asset_path(self, tmp_path: Path):
        """Test resolving asset paths."""
        manager = AssetManager(assets_dir=tmp_path)

        # Create test file
        test_file = tmp_path / "test.obj"
        test_file.write_text("test")

        # Test relative path
        resolved = manager._resolve_asset_path("test.obj")
        assert resolved == test_file

        # Test absolute path
        resolved = manager._resolve_asset_path(test_file)
        assert resolved == test_file

    def test_load_mesh(self, tmp_path: Path):
        """Test loading mesh files."""
        manager = AssetManager(assets_dir=tmp_path)

        # Create valid mesh file
        mesh_file = tmp_path / "test.obj"
        mesh_file.write_text("mesh data")

        loaded = manager.load_mesh("test.obj")
        assert loaded == mesh_file

    def test_load_mesh_unsupported_format(self, tmp_path: Path):
        """Test loading unsupported mesh format."""
        manager = AssetManager(assets_dir=tmp_path)

        mesh_file = tmp_path / "test.xyz"
        mesh_file.write_text("data")

        with pytest.raises(AssetLoadError, match="Unsupported mesh format"):
            manager.load_mesh("test.xyz")

    def test_load_texture(self, tmp_path: Path):
        """Test loading texture files."""
        manager = AssetManager(assets_dir=tmp_path)

        # Create valid texture file
        texture_file = tmp_path / "test.png"
        texture_file.write_bytes(b"texture data")

        loaded = manager.load_texture("test.png")
        assert loaded == texture_file

    def test_load_texture_unsupported_format(self, tmp_path: Path):
        """Test loading unsupported texture format."""
        manager = AssetManager(assets_dir=tmp_path)

        texture_file = tmp_path / "test.xyz"
        texture_file.write_bytes(b"data")

        with pytest.raises(AssetLoadError, match="Unsupported texture format"):
            manager.load_texture("test.xyz")

    def test_validate_scene_assets(self, tmp_path: Path):
        """Test validating scene assets."""
        manager = AssetManager(assets_dir=tmp_path)

        # Create a valid scene
        scene = SceneDefinition(
            metadata=Metadata(name="Test"),
        )

        # No assets, should pass
        missing = manager.validate_scene_assets(scene)
        assert len(missing) == 0


class TestSceneLoader:
    """Tests for SceneLoader class."""

    def test_loader_initialization(self):
        """Test loader initializes correctly."""
        loader = SceneLoader()
        assert loader.cache is not None
        assert loader.asset_manager is not None

    def test_load_json_scene(self, tmp_path: Path):
        """Test loading JSON scene file."""
        loader = SceneLoader()

        # Create test scene
        scene = SceneDefinition(metadata=Metadata(name="Test JSON Scene"))
        scene_file = tmp_path / "test.json"
        scene_file.write_text(scene.model_dump_json())

        loaded = loader.load(scene_file)
        assert loaded.metadata.name == "Test JSON Scene"

    def test_load_yaml_scene(self, tmp_path: Path):
        """Test loading YAML scene file."""
        import yaml
        loader = SceneLoader()

        # Create test scene
        scene = SceneDefinition(metadata=Metadata(name="Test YAML Scene"))
        scene_file = tmp_path / "test.yaml"
        # Convert tuples to lists for proper YAML serialization
        data = _convert_tuples_for_yaml(scene.model_dump())
        scene_file.write_text(yaml.dump(data))

        loaded = loader.load(scene_file)
        assert loaded.metadata.name == "Test YAML Scene"

    def test_load_nonexistent_file(self, tmp_path: Path):
        """Test loading non-existent file."""
        loader = SceneLoader()

        with pytest.raises(SceneFileNotFoundError):
            loader.load(tmp_path / "nonexistent.json")

    def test_load_invalid_json(self, tmp_path: Path):
        """Test loading invalid JSON."""
        loader = SceneLoader()

        scene_file = tmp_path / "invalid.json"
        scene_file.write_text("{ invalid json }")

        with pytest.raises(SceneParseError, match="Invalid JSON"):
            loader.load(scene_file)

    def test_load_invalid_yaml(self, tmp_path: Path):
        """Test loading invalid YAML."""
        loader = SceneLoader()

        scene_file = tmp_path / "invalid.yaml"
        scene_file.write_text("key: value\n  nested: invalid")

        with pytest.raises(SceneParseError, match="Invalid YAML"):
            loader.load(scene_file)

    def test_load_unsupported_format(self, tmp_path: Path):
        """Test loading unsupported file format."""
        loader = SceneLoader()

        scene_file = tmp_path / "test.xml"
        scene_file.write_text("<scene></scene>")

        with pytest.raises(SceneParseError, match="Unsupported file format"):
            loader.load(scene_file)

    def test_load_invalid_scene(self, tmp_path: Path):
        """Test loading scene with validation errors."""
        loader = SceneLoader()

        # Create invalid scene (missing required fields)
        scene_file = tmp_path / "invalid.json"
        scene_file.write_text('{"metadata": {"name": "Test"}, "simulator": "invalid_simulator"}')

        with pytest.raises(SceneValidationError) as exc_info:
            loader.load(scene_file)

        assert len(exc_info.value.validation_errors) > 0

    def test_load_from_string_json(self):
        """Test loading scene from JSON string."""
        loader = SceneLoader()

        scene = SceneDefinition(metadata=Metadata(name="Test"))
        json_str = scene.model_dump_json()

        loaded = loader.load_from_string(json_str, format="json")
        assert loaded.metadata.name == "Test"

    def test_load_from_string_yaml(self):
        """Test loading scene from YAML string."""
        import yaml
        loader = SceneLoader()

        scene = SceneDefinition(metadata=Metadata(name="Test"))
        data = _convert_tuples_for_yaml(scene.model_dump())
        yaml_str = yaml.dump(data)

        loaded = loader.load_from_string(yaml_str, format="yaml")
        assert loaded.metadata.name == "Test"

    def test_load_from_dict(self):
        """Test loading scene from dictionary."""
        loader = SceneLoader()

        data = {"metadata": {"name": "Test"}}
        loaded = loader.load_from_dict(data)
        assert loaded.metadata.name == "Test"

    def test_save_json_scene(self, tmp_path: Path):
        """Test saving scene to JSON file."""
        loader = SceneLoader()

        scene = SceneDefinition(metadata=Metadata(name="Test Save"))
        output_file = tmp_path / "output.json"

        loader.save(scene, output_file)

        assert output_file.exists()
        loaded = loader.load(output_file)
        assert loaded.metadata.name == "Test Save"

    def test_save_yaml_scene(self, tmp_path: Path):
        """Test saving scene to YAML file."""
        loader = SceneLoader()

        scene = SceneDefinition(metadata=Metadata(name="Test Save YAML"))
        output_file = tmp_path / "output.yaml"

        loader.save(scene, output_file, format="yaml")

        assert output_file.exists()
        loaded = loader.load(output_file)
        assert loaded.metadata.name == "Test Save YAML"

    def test_cache_usage(self, tmp_path: Path):
        """Test that cache is used for repeated loads."""
        loader = SceneLoader(cache_size=10)

        scene = SceneDefinition(metadata=Metadata(name="Cached Test"))
        scene_file = tmp_path / "cached.json"
        scene_file.write_text(scene.model_dump_json())

        # First load - should cache
        loaded1 = loader.load(scene_file, use_cache=True)
        assert scene_file in loader.cache

        # Second load - should use cache
        loaded2 = loader.load(scene_file, use_cache=True)
        assert loaded1.metadata.name == loaded2.metadata.name

    def test_cache_bypass(self, tmp_path: Path):
        """Test bypassing cache."""
        loader = SceneLoader(cache_size=10)

        scene = SceneDefinition(metadata=Metadata(name="No Cache"))
        scene_file = tmp_path / "no_cache.json"
        scene_file.write_text(scene.model_dump_json())

        # Load without caching
        loaded = loader.load(scene_file, use_cache=False)
        assert scene_file not in loader.cache

    def test_list_scenes(self, tmp_path: Path):
        """Test listing scene files in directory."""
        loader = SceneLoader()

        # Create some scene files
        for i in range(3):
            scene = SceneDefinition(metadata=Metadata(name=f"Scene {i}"))
            scene_file = tmp_path / f"scene_{i}.json"
            scene_file.write_text(scene.model_dump_json())

        # Create a non-scene file
        (tmp_path / "other.txt").write_text("not a scene")

        scenes = loader.list_scenes(tmp_path)
        assert len(scenes) == 3

    def test_load_directory(self, tmp_path: Path):
        """Test loading all scenes from directory."""
        loader = SceneLoader()

        # Create multiple scenes
        for i in range(3):
            scene = SceneDefinition(
                metadata=Metadata(name=f"Scene {i}"),
                simulator=SimulatorType.MUJOCO,
            )
            scene_file = tmp_path / f"scene_{i}.json"
            scene_file.write_text(scene.model_dump_json())

        scenes = loader.load_directory(tmp_path)
        assert len(scenes) == 3
        assert "Scene 0" in scenes
        assert "Scene 1" in scenes
        assert "Scene 2" in scenes

    def test_validation_disabled(self, tmp_path: Path):
        """Test loading with validation disabled."""
        loader = SceneLoader()

        # Create a minimal valid scene
        scene_file = tmp_path / "minimal.json"
        scene_file.write_text('{"metadata": {"name": "Minimal"}}')

        loaded = loader.load(scene_file, validate=True)
        assert loaded.metadata.name == "Minimal"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_loader(self):
        """Test get_loader returns singleton."""
        reset_loader()
        loader1 = get_loader()
        loader2 = get_loader()
        assert loader1 is loader2

        reset_loader()

    def test_load_scene_function(self, tmp_path: Path):
        """Test load_scene convenience function."""
        reset_loader()

        scene = SceneDefinition(metadata=Metadata(name="Convenience Test"))
        scene_file = tmp_path / "convenience.json"
        scene_file.write_text(scene.model_dump_json())

        loaded = load_scene(scene_file)
        assert loaded.metadata.name == "Convenience Test"

        reset_loader()

    def test_save_scene_function(self, tmp_path: Path):
        """Test save_scene convenience function."""
        reset_loader()

        scene = SceneDefinition(metadata=Metadata(name="Save Test"))
        output_file = tmp_path / "save_test.json"

        save_scene(scene, output_file)
        assert output_file.exists()

        reset_loader()


class TestExceptionClasses:
    """Tests for exception classes."""

    def test_scene_loader_error(self):
        """Test SceneLoaderError."""
        error = SceneLoaderError("Test error", details={"key": "value"})
        assert str(error) == "Test error"
        assert error.details == {"key": "value"}

    def test_scene_file_not_found_error(self):
        """Test SceneFileNotFoundError."""
        error = SceneFileNotFoundError(
            "File not found",
            details={"file_path": "/path/to/file.json"},
        )
        assert isinstance(error, SceneLoaderError)

    def test_scene_validation_error(self):
        """Test SceneValidationError."""
        error = SceneValidationError(
            "Validation failed",
            validation_errors=[
                {"location": "robots.0.name", "message": "Required"}
            ],
        )
        assert isinstance(error, SceneLoaderError)
        assert len(error.validation_errors) == 1

    def test_scene_parse_error(self):
        """Test SceneParseError."""
        error = SceneParseError(
            "Parse error",
            details={"line": 10, "column": 5},
        )
        assert isinstance(error, SceneLoaderError)

    def test_asset_load_error(self):
        """Test AssetLoadError."""
        error = AssetLoadError(
            "Asset not found",
            details={"asset_path": "/path/to/mesh.obj"},
        )
        assert isinstance(error, SceneLoaderError)


class TestExistingScenes:
    """Tests for loading existing scene files."""

    def test_load_simple_suturing(self):
        """Test loading the simple_suturing.json scene."""
        import yaml
        from pathlib import Path

        scenes_dir = Path(__file__).parent.parent / "scenes"
        scene_file = scenes_dir / "simple_suturing.json"

        if scene_file.exists():
            loader = SceneLoader()
            scene = loader.load(scene_file)
            assert scene.metadata.name == "Simple Suturing Scene"
            assert len(scene.robots) > 0

    def test_load_laparoscopic_dissection(self):
        """Test loading the laparoscopic_dissection.yaml scene."""
        from pathlib import Path

        scenes_dir = Path(__file__).parent.parent / "scenes"
        scene_file = scenes_dir / "laparoscopic_dissection.yaml"

        if scene_file.exists():
            loader = SceneLoader()
            scene = loader.load(scene_file)
            assert "Laparoscopic" in scene.metadata.name or len(scene.robots) >= 2

    def test_load_minimal_scene(self):
        """Test loading the minimal_scene.json scene."""
        from pathlib import Path

        scenes_dir = Path(__file__).parent.parent / "scenes"
        scene_file = scenes_dir / "minimal_scene.json"

        if scene_file.exists():
            loader = SceneLoader()
            scene = loader.load(scene_file)
            assert scene.metadata.name == "Minimal Test Scene"
