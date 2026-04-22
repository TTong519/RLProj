"""Scene file loader with validation, caching, and asset management.

This module provides functionality to load scene definitions from JSON/YAML files,
validate them against the schema, cache loaded scenes, and manage referenced assets.
"""

import json
import hashlib
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

import yaml
from pydantic import ValidationError

from surg_rl.utils.logging import get_logger

from .schema import SceneDefinition

logger = get_logger(__name__)

T = TypeVar("T", bound=SceneDefinition)


class SceneLoaderError(Exception):
    """Base exception for scene loader errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SceneFileNotFoundError(SceneLoaderError):
    """Exception raised when scene file is not found."""

    pass


class SceneValidationError(SceneLoaderError):
    """Exception raised when scene validation fails."""

    def __init__(
        self,
        message: str,
        validation_errors: List[Dict[str, Any]],
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.validation_errors = validation_errors


class SceneParseError(SceneLoaderError):
    """Exception raised when scene file parsing fails."""

    pass


class AssetLoadError(SceneLoaderError):
    """Exception raised when asset loading fails."""

    pass


class SceneCache:
    """Thread-safe cache for loaded scenes.

    Provides in-memory caching of loaded scene definitions to avoid
    repeated file I/O and parsing for frequently used scenes.

    Attributes:
        max_size: Maximum number of scenes to cache.
        cache: Internal cache dictionary.
        lock: Thread lock for safe concurrent access.
    """

    def __init__(self, max_size: int = 100):
        """Initialize the scene cache.

        Args:
            max_size: Maximum number of scenes to cache. LRU eviction
                is used when the cache is full.
        """
        self.max_size = max_size
        self._cache: Dict[str, SceneDefinition] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()

    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key from file path and modification time.

        Args:
            file_path: Path to the scene file.

        Returns:
            Cache key string.
        """
        file_path = Path(file_path)
        mtime = file_path.stat().st_mtime if file_path.exists() else 0
        return f"{file_path}:{mtime}"

    def get(self, file_path: Union[str, Path]) -> Optional[SceneDefinition]:
        """Get a scene from the cache.

        Args:
            file_path: Path to the scene file.

        Returns:
            Cached SceneDefinition or None if not in cache.
        """
        file_path = Path(file_path)
        cache_key = self._get_cache_key(file_path)

        with self._lock:
            if cache_key in self._cache:
                # Move to end of access order (most recently used)
                self._access_order.remove(cache_key)
                self._access_order.append(cache_key)
                logger.debug(f"Cache hit for scene: {file_path}")
                return self._cache[cache_key]

        return None

    def put(self, file_path: Union[str, Path], scene: SceneDefinition) -> None:
        """Add a scene to the cache.

        Args:
            file_path: Path to the scene file.
            scene: SceneDefinition to cache.
        """
        file_path = Path(file_path)
        cache_key = self._get_cache_key(file_path)

        with self._lock:
            # Evict oldest if cache is full
            while len(self._cache) >= self.max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                self._cache.pop(oldest_key, None)
                logger.debug(f"Evicted scene from cache: {oldest_key}")

            self._cache[cache_key] = scene
            if cache_key not in self._access_order:
                self._access_order.append(cache_key)
            logger.debug(f"Cached scene: {file_path}")

    def clear(self) -> None:
        """Clear all cached scenes."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            logger.debug("Cache cleared")

    def __contains__(self, file_path: Union[str, Path]) -> bool:
        """Check if a scene is in the cache.

        Args:
            file_path: Path to the scene file.

        Returns:
            True if scene is cached, False otherwise.
        """
        return self.get(file_path) is not None

    def __len__(self) -> int:
        """Get the number of cached scenes."""
        return len(self._cache)


class AssetManager:
    """Manager for loading and caching scene assets.

    Handles loading of mesh files, textures, URDFs, and other assets
    referenced in scene definitions.

    Attributes:
        assets_dir: Base directory for asset files.
        cache: Asset cache dictionary.
    """

    SUPPORTED_MESH_FORMATS = {".obj", ".stl", ".ply", ".gltf", ".glb", ".urdf"}
    SUPPORTED_TEXTURE_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".hdr"}

    def __init__(self, assets_dir: Optional[Path] = None):
        """Initialize the asset manager.

        Args:
            assets_dir: Base directory for assets. If None, assets must
                be specified with absolute paths.
        """
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self._cache: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def _resolve_asset_path(self, asset_path: Union[str, Path]) -> Path:
        """Resolve an asset path to an absolute path.

        Args:
            asset_path: Asset path (relative or absolute).

        Returns:
            Resolved absolute path.

        Raises:
            AssetLoadError: If asset path cannot be resolved.
        """
        path = Path(asset_path)

        if path.is_absolute():
            return path

        if self.assets_dir:
            resolved = self.assets_dir / path
            if resolved.exists():
                return resolved

        # Try current directory
        if path.exists():
            return path.resolve()

        raise AssetLoadError(
            f"Asset not found: {asset_path}",
            details={"asset_path": str(asset_path), "assets_dir": str(self.assets_dir)},
        )

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of a file for cache key.

        Args:
            file_path: Path to the file.

        Returns:
            MD5 hash string.
        """
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def asset_exists(self, asset_path: Union[str, Path]) -> bool:
        """Check if an asset file exists.

        Args:
            asset_path: Path to the asset.

        Returns:
            True if asset exists, False otherwise.
        """
        try:
            resolved = self._resolve_asset_path(asset_path)
            return resolved.exists()
        except AssetLoadError:
            return False

    def load_asset(
        self,
        asset_path: Union[str, Path],
        loader: Optional[Callable[[Path], Any]] = None,
    ) -> Any:
        """Load an asset file with caching.

        Args:
            asset_path: Path to the asset file.
            loader: Optional custom loader function. If None, returns file path.

        Returns:
            Loaded asset (or file path if no loader).

        Raises:
            AssetLoadError: If asset cannot be loaded.
        """
        resolved_path = self._resolve_asset_path(asset_path)
        cache_key = f"{resolved_path}:{resolved_path.stat().st_mtime}"

        with self._lock:
            if cache_key in self._cache:
                logger.debug(f"Asset cache hit: {asset_path}")
                return self._cache[cache_key]

        # Load the asset
        if loader:
            try:
                asset = loader(resolved_path)
            except Exception as e:
                raise AssetLoadError(
                    f"Failed to load asset: {asset_path}",
                    details={"asset_path": str(asset_path), "error": str(e)},
                )
        else:
            asset = resolved_path

        with self._lock:
            self._cache[cache_key] = asset
            logger.debug(f"Cached asset: {asset_path}")

        return asset

    def load_mesh(self, mesh_path: Union[str, Path]) -> Path:
        """Load a mesh file.

        Args:
            mesh_path: Path to the mesh file.

        Returns:
            Resolved path to the mesh file.

        Raises:
            AssetLoadError: If mesh format is unsupported or file not found.
        """
        path = Path(mesh_path)
        if path.suffix.lower() not in self.SUPPORTED_MESH_FORMATS:
            raise AssetLoadError(
                f"Unsupported mesh format: {path.suffix}",
                details={
                    "mesh_path": str(mesh_path),
                    "supported_formats": list(self.SUPPORTED_MESH_FORMATS),
                },
            )

        return self.load_asset(mesh_path)

    def load_texture(self, texture_path: Union[str, Path]) -> Path:
        """Load a texture file.

        Args:
            texture_path: Path to the texture file.

        Returns:
            Resolved path to the texture file.

        Raises:
            AssetLoadError: If texture format is unsupported or file not found.
        """
        path = Path(texture_path)
        if path.suffix.lower() not in self.SUPPORTED_TEXTURE_FORMATS:
            raise AssetLoadError(
                f"Unsupported texture format: {path.suffix}",
                details={
                    "texture_path": str(texture_path),
                    "supported_formats": list(self.SUPPORTED_TEXTURE_FORMATS),
                },
            )

        return self.load_asset(texture_path)

    def validate_scene_assets(self, scene: SceneDefinition) -> List[str]:
        """Validate that all assets referenced in a scene exist.

        Args:
            scene: SceneDefinition to validate.

        Returns:
            List of missing asset paths (empty if all assets exist).
        """
        missing_assets = []

        # Check robot URDF paths
        for robot in scene.robots:
            if robot.urdf_path:
                if not self.asset_exists(robot.urdf_path):
                    missing_assets.append(f"Robot URDF: {robot.urdf_path}")

        # Check tissue mesh paths
        for tissue in scene.tissues:
            if tissue.geometry.mesh and tissue.geometry.mesh.path:
                if not self.asset_exists(tissue.geometry.mesh.path):
                    missing_assets.append(f"Tissue mesh: {tissue.geometry.mesh.path}")

        # Check instrument mesh paths
        for instrument in scene.instruments:
            if instrument.mesh and instrument.mesh.path:
                if not self.asset_exists(instrument.mesh.path):
                    missing_assets.append(f"Instrument mesh: {instrument.mesh.path}")

        # Check additional assets
        for name, asset in scene.assets.items():
            if asset.path:
                if not self.asset_exists(asset.path):
                    missing_assets.append(f"Asset '{name}': {asset.path}")

        return missing_assets

    def clear_cache(self) -> None:
        """Clear the asset cache."""
        with self._lock:
            self._cache.clear()
            logger.debug("Asset cache cleared")


class SceneLoader:
    """Load and validate scene definitions from files.

    Provides methods to load scenes from JSON/YAML files with validation,
    caching, and asset management.

    Attributes:
        cache: Scene cache for loaded definitions.
        asset_manager: Asset manager for referenced assets.
    """

    def __init__(
        self,
        assets_dir: Optional[Union[str, Path]] = None,
        cache_size: int = 100,
        validate_assets: bool = True,
    ):
        """Initialize the scene loader.

        Args:
            assets_dir: Directory containing asset files.
            cache_size: Maximum number of scenes to cache.
            validate_assets: Whether to validate asset existence.
        """
        self.cache = SceneCache(max_size=cache_size)
        self.asset_manager = AssetManager(assets_dir=assets_dir if assets_dir else None)
        self.validate_assets = validate_assets

    def _read_file(self, file_path: Path) -> str:
        """Read a file's contents.

        Args:
            file_path: Path to the file.

        Returns:
            File contents as string.

        Raises:
            SceneFileNotFoundError: If file doesn't exist.
            SceneParseError: If file can't be read.
        """
        if not file_path.exists():
            raise SceneFileNotFoundError(
                f"Scene file not found: {file_path}",
                details={"file_path": str(file_path)},
            )

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise SceneParseError(
                f"Failed to read file: {file_path}",
                details={"file_path": str(file_path), "error": str(e)},
            )

    def _parse_json(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Parse JSON content.

        Args:
            content: JSON string.
            file_path: Path for error messages.

        Returns:
            Parsed dictionary.

        Raises:
            SceneParseError: If JSON is invalid.
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise SceneParseError(
                f"Invalid JSON in file: {file_path}",
                details={"file_path": str(file_path), "line": e.lineno, "column": e.colno, "error": str(e)},
            )

    def _parse_yaml(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Parse YAML content.

        Args:
            content: YAML string.
            file_path: Path for error messages.

        Returns:
            Parsed dictionary.

        Raises:
            SceneParseError: If YAML is invalid.
        """
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise SceneParseError(
                f"Invalid YAML in file: {file_path}",
                details={"file_path": str(file_path), "error": str(e)},
            )

    def _format_validation_errors(self, error: ValidationError) -> List[Dict[str, Any]]:
        """Format Pydantic validation errors for user-friendly display.

        Args:
            error: Pydantic ValidationError.

        Returns:
            List of formatted error dictionaries.
        """
        errors = []
        for err in error.errors():
            location = ".".join(str(loc) for loc in err["loc"])
            errors.append({
                "location": location,
                "message": err["msg"],
                "type": err["type"],
                "input": str(err.get("input", ""))[:100],  # Truncate for display
            })
        return errors

    def _get_file_format(self, file_path: Path) -> str:
        """Determine file format from extension.

        Args:
            file_path: Path to the file.

        Returns:
            Format string ('json' or 'yaml').

        Raises:
            SceneParseError: If format is unsupported.
        """
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            return "json"
        elif suffix in {".yaml", ".yml"}:
            return "yaml"
        else:
            raise SceneParseError(
                f"Unsupported file format: {suffix}",
                details={"file_path": str(file_path), "supported_formats": [".json", ".yaml", ".yml"]},
            )

    def load(
        self,
        file_path: Union[str, Path],
        use_cache: bool = True,
        validate: bool = True,
    ) -> SceneDefinition:
        """Load a scene from a file.

        Args:
            file_path: Path to the scene file (JSON or YAML).
            use_cache: Whether to use cached result if available.
            validate: Whether to validate against schema.

        Returns:
            Loaded SceneDefinition.

        Raises:
            SceneFileNotFoundError: If file doesn't exist.
            SceneParseError: If file can't be parsed.
            SceneValidationError: If validation fails.
        """
        file_path = Path(file_path)

        # Check cache first
        if use_cache:
            cached = self.cache.get(file_path)
            if cached is not None:
                return cached.model_copy(deep=True)

        logger.info(f"Loading scene from: {file_path}")

        # Determine format and parse
        content = self._read_file(file_path)
        file_format = self._get_file_format(file_path)

        if file_format == "json":
            data = self._parse_json(content, file_path)
        else:
            data = self._parse_yaml(content, file_path)

        # Validate and create scene
        try:
            scene = SceneDefinition(**data) if validate else SceneDefinition.model_construct(**data)
        except ValidationError as e:
            formatted_errors = self._format_validation_errors(e)
            raise SceneValidationError(
                f"Scene validation failed: {file_path}",
                validation_errors=formatted_errors,
                details={"file_path": str(file_path)},
            )

        # Validate assets if enabled
        if self.validate_assets:
            missing = self.asset_manager.validate_scene_assets(scene)
            if missing:
                logger.warning(f"Missing assets for scene {file_path}: {missing}")

        # Cache the result
        if use_cache:
            self.cache.put(file_path, scene)

        scene_name = getattr(scene.metadata, "name", None) or (
            scene.metadata.get("name", "unknown") if isinstance(scene.metadata, dict) else "unknown"
        )
        logger.info(f"Loaded scene: {scene_name}")
        return scene.model_copy(deep=True)

    def load_from_string(
        self,
        content: str,
        format: str = "json",
        validate: bool = True,
    ) -> SceneDefinition:
        """Load a scene from a string.

        Args:
            content: Scene content string (JSON or YAML).
            format: Content format ('json' or 'yaml').
            validate: Whether to validate against schema.

        Returns:
            Loaded SceneDefinition.

        Raises:
            SceneParseError: If content can't be parsed.
            SceneValidationError: If validation fails.
        """
        if format == "json":
            data = self._parse_json(content, Path("<string>"))
        elif format in {"yaml", "yml"}:
            data = self._parse_yaml(content, Path("<string>"))
        else:
            raise SceneParseError(
                f"Unsupported format: {format}",
                details={"supported_formats": ["json", "yaml"]},
            )

        try:
            scene = SceneDefinition(**data) if validate else SceneDefinition.model_construct(**data)
        except ValidationError as e:
            formatted_errors = self._format_validation_errors(e)
            raise SceneValidationError(
                "Scene validation failed",
                validation_errors=formatted_errors,
            )

        return scene

    def load_from_dict(
        self,
        data: Dict[str, Any],
        validate: bool = True,
    ) -> SceneDefinition:
        """Load a scene from a dictionary.

        Args:
            data: Scene data dictionary.
            validate: Whether to validate against schema.

        Returns:
            Loaded SceneDefinition.

        Raises:
            SceneValidationError: If validation fails.
        """
        try:
            scene = SceneDefinition(**data) if validate else SceneDefinition.model_construct(**data)
        except ValidationError as e:
            formatted_errors = self._format_validation_errors(e)
            raise SceneValidationError(
                "Scene validation failed",
                validation_errors=formatted_errors,
            )

        return scene

    def save(
        self,
        scene: SceneDefinition,
        file_path: Union[str, Path],
        format: Optional[str] = None,
    ) -> None:
        """Save a scene to a file.

        Args:
            scene: SceneDefinition to save.
            file_path: Output file path.
            format: Output format ('json' or 'yaml'). If None, inferred from extension.
        """
        file_path = Path(file_path)

        # Determine format
        if format is None:
            format = self._get_file_format(file_path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize
        data = scene.model_dump(mode="python")

        if format == "json":
            content = json.dumps(data, indent=2, default=str)
        else:
            # Convert tuples to lists for YAML serialization
            def convert_tuples(obj):
                from enum import Enum
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, tuple):
                    return list(obj)
                elif isinstance(obj, dict):
                    return {k: convert_tuples(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_tuples(item) for item in obj]
                return obj

            yaml_data = convert_tuples(data)
            content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved scene to: {file_path}")

    def clear_cache(self) -> None:
        """Clear both scene cache and asset cache."""
        self.cache.clear()
        self.asset_manager.clear_cache()

    def list_scenes(self, directory: Union[str, Path]) -> List[Path]:
        """List all scene files in a directory.

        Args:
            directory: Directory to search.

        Returns:
            List of scene file paths.
        """
        directory = Path(directory)
        if not directory.exists():
            return []

        scene_files = []
        for ext in [".json", ".yaml", ".yml"]:
            scene_files.extend(directory.glob(f"*{ext}"))

        return sorted(scene_files)

    def load_directory(
        self,
        directory: Union[str, Path],
        pattern: str = "*",
    ) -> Dict[str, SceneDefinition]:
        """Load all scenes from a directory.

        Args:
            directory: Directory containing scene files.
            pattern: Glob pattern to filter files.

        Returns:
            Dictionary mapping scene names to definitions.

        Raises:
            SceneLoaderError: If any scene fails to load.
        """
        directory = Path(directory)
        scenes = {}

        for ext in [".json", ".yaml", ".yml"]:
            for file_path in directory.glob(f"{pattern}{ext}"):
                try:
                    scene = self.load(file_path)
                    scenes[scene.metadata.name] = scene
                except SceneLoaderError as e:
                    logger.error(f"Failed to load {file_path}: {e}")
                    # Continue loading other scenes

        return scenes


# Global loader instance
_loader: Optional[SceneLoader] = None


def get_loader(
    assets_dir: Optional[Union[str, Path]] = None,
    cache_size: int = 100,
    validate_assets: bool = True,
) -> SceneLoader:
    """Get or create the global scene loader instance.

    Args:
        assets_dir: Directory containing asset files.
        cache_size: Maximum number of scenes to cache.
        validate_assets: Whether to validate asset existence.

    Returns:
        SceneLoader instance.
    """
    global _loader
    if _loader is None:
        _loader = SceneLoader(
            assets_dir=assets_dir,
            cache_size=cache_size,
            validate_assets=validate_assets,
        )
    return _loader


def reset_loader() -> None:
    """Reset the global loader instance."""
    global _loader
    _loader = None


# Convenience functions

def load_scene(
    file_path: Union[str, Path],
    use_cache: bool = True,
    validate: bool = True,
) -> SceneDefinition:
    """Load a scene from a file using the global loader.

    Args:
        file_path: Path to the scene file.
        use_cache: Whether to use cached result.
        validate: Whether to validate.

    Returns:
        Loaded SceneDefinition.
    """
    return get_loader().load(file_path, use_cache=use_cache, validate=validate)


def save_scene(
    scene: SceneDefinition,
    file_path: Union[str, Path],
    format: Optional[str] = None,
) -> None:
    """Save a scene to a file using the global loader.

    Args:
        scene: SceneDefinition to save.
        file_path: Output file path.
        format: Output format.
    """
    get_loader().save(scene, file_path, format=format)


# Convenience function for validation
def validate_scene(scene: SceneDefinition) -> bool:
    """Validate a scene definition.
    
    Args:
        scene: Scene definition to validate
        
    Returns:
        True if scene is valid
        
    Raises:
        SceneValidationError: If scene is invalid
    """
    try:
        # Pydantic models are validated on construction
        # This function exists for API consistency
        if not isinstance(scene, SceneDefinition):
            raise SceneValidationError(f"Expected SceneDefinition, got {type(scene)}")
        
        # Check required fields
        if not scene.metadata:
            raise SceneValidationError("Scene must have metadata")
        
        if not scene.physics:
            raise SceneValidationError("Scene must have physics configuration")
        
        # Validate using Pydantic's built-in validation
        # (already done during construction, but explicit check)
        _ = scene.model_dump()
        
        return True
        
    except Exception as e:
        raise SceneValidationError(f"Scene validation failed: {str(e)}") from e
