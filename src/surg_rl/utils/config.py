"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Project paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent,
        description="Root directory of the project",
    )

    @field_validator("project_root", mode="before")
    @classmethod
    def resolve_project_root(cls, v: str | Path) -> Path:
        if isinstance(v, str):
            return Path(v).resolve()
        return v.resolve() if isinstance(v, Path) else Path.cwd()

    # Asset directories
    assets_dir: Path = Field(
        default_factory=lambda: Path("assets"),
        description="Directory for assets (meshes, textures, materials)",
    )

    scenes_dir: Path = Field(
        default_factory=lambda: Path("scenes"),
        description="Directory for scene files",
    )

    configs_dir: Path = Field(
        default_factory=lambda: Path("configs"),
        description="Directory for configuration files",
    )

    @property
    def meshes_dir(self) -> Path:
        """Get meshes directory."""
        return self.assets_dir / "meshes"

    @property
    def textures_dir(self) -> Path:
        """Get textures directory."""
        return self.assets_dir / "textures"

    @property
    def materials_dir(self) -> Path:
        """Get materials directory."""
        return self.assets_dir / "materials"

    # LLM Configuration for scene generation
    llm_provider: Literal["openai", "anthropic", "ollama"] = Field(
        default="openai",
        description="LLM provider for scene generation",
    )

    llm_model: str = Field(
        default="gpt-4-turbo-preview",
        description="Model name for LLM",
    )

    llm_api_key: Optional[str] = Field(
        default=None,
        description="API key for LLM provider",
    )

    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )

    ollama_model: str = Field(
        default="llama3.2",
        description="Default Ollama model for text generation",
    )

    ollama_vision_model: str = Field(
        default="llava",
        description="Default Ollama model for vision tasks",
    )

    ollama_timeout: int = Field(
        default=300,
        ge=1,
        description="Timeout in seconds for Ollama API calls",
    )

    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM responses",
    )

    llm_max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum tokens for LLM responses",
    )

    # VLM Configuration for visual scene generation
    vlm_model: str = Field(
        default="gpt-4-vision-preview",
        description="Model name for VLM",
    )

    # Simulator settings
    default_simulator: Literal["mujoco", "pybullet"] = Field(
        default="mujoco",
        description="Default simulator backend",
    )

    mujoco_timestep: float = Field(
        default=0.002,
        ge=0.0001,
        le=0.1,
        description="MuJoCo simulation timestep",
    )

    pybullet_timestep: float = Field(
        default=1.0 / 240.0,
        ge=0.0001,
        le=0.1,
        description="PyBullet simulation timestep",
    )

    # Rendering settings
    render_width: int = Field(
        default=640,
        ge=64,
        description="Render width in pixels",
    )

    render_height: int = Field(
        default=480,
        ge=64,
        description="Render height in pixels",
    )

    render_fps: int = Field(
        default=60,
        ge=1,
        description="Frames per second for rendering",
    )

    # RL Training settings
    rl_device: str = Field(
        default="auto",
        description="Device for RL training (auto, cpu, cuda, mps)",
    )

    rl_seed: int = Field(
        default=42,
        description="Random seed for reproducibility",
    )

    rl_tensorboard_log: Optional[Path] = Field(
        default=None,
        description="TensorBoard log directory",
    )

    # Domain randomization settings
    randomization_enabled: bool = Field(
        default=False,
        description="Enable domain randomization",
    )

    physics_randomization: bool = Field(
        default=True,
        description="Randomize physics parameters",
    )

    visual_randomization: bool = Field(
        default=True,
        description="Randomize visual parameters",
    )

    dynamics_randomization: bool = Field(
        default=True,
        description="Randomize dynamics parameters",
    )

    # Logging settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    log_file: Optional[Path] = Field(
        default=None,
        description="Optional log file path",
    )

    def get_full_path(self, relative_path: Path | str) -> Path:
        """Convert a relative path to absolute path based on project root.

        Args:
            relative_path: Path relative to project root

        Returns:
            Absolute path
        """
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return self.project_root / path

    def ensure_directories(self) -> None:
        """Create all necessary directories if they don't exist."""
        dirs_to_create = [
            self.assets_dir,
            self.scenes_dir,
            self.configs_dir,
            self.meshes_dir,
            self.textures_dir,
            self.materials_dir,
        ]

        for directory in dirs_to_create:
            full_path = self.get_full_path(directory)
            full_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance.

    Useful for testing or when settings need to be reloaded.
    """
    global _settings
    _settings = None
