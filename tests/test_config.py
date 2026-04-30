"""Tests for configuration module."""

import pytest
from pydantic import ValidationError
from pathlib import Path

from surg_rl.utils.config import Settings, get_settings, reset_settings


def test_settings_creation():
    """Test that settings can be created."""
    settings = Settings()
    assert settings is not None
    assert settings.default_simulator == "mujoco"
    assert settings.llm_provider == "openai"


def test_get_settings():
    """Test that get_settings returns a Settings instance."""
    reset_settings()
    settings = get_settings()
    assert isinstance(settings, Settings)

    # Call again to test singleton
    settings2 = get_settings()
    assert settings is settings2


def test_settings_paths():
    """Test path resolution in settings."""
    settings = Settings()

    # Test mesh directory
    assert settings.meshes_dir == settings.assets_dir / "meshes"

    # Test textures directory
    assert settings.textures_dir == settings.assets_dir / "textures"

    # Test materials directory
    assert settings.materials_dir == settings.assets_dir / "materials"


def test_ensure_directories(tmp_path):
    """Test directory creation."""
    settings = Settings(
        project_root=tmp_path,
        assets_dir=Path("assets"),
        scenes_dir=Path("scenes"),
        configs_dir=Path("configs"),
    )

    settings.ensure_directories()

    assert (tmp_path / "assets").exists()
    assert (tmp_path / "assets" / "meshes").exists()
    assert (tmp_path / "assets" / "textures").exists()
    assert (tmp_path / "assets" / "materials").exists()
    assert (tmp_path / "scenes").exists()
    assert (tmp_path / "configs").exists()


def test_cli_calls_setup_logging():
    """CLI commands must initialize logging."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from surg_rl.cli import app

    with patch("surg_rl.cli.setup_logging") as mock_setup:
        runner = CliRunner()
        runner.invoke(app, ["version"])
        mock_setup.assert_called_once()


class TestSettingsValidation:
    def test_settings_rejects_placeholder_api_key(self):
        """Known placeholder API keys must be rejected."""
        with pytest.raises(ValidationError, match="placeholder"):
            Settings(llm_api_key="your_api_key_here")

    def test_settings_allows_real_api_key(self):
        """Non-placeholder API keys must be accepted."""
        settings = Settings(llm_api_key="sk-realkey123456")
        assert settings.llm_api_key == "sk-realkey123456"
