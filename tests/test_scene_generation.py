"""Tests for scene generation module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from surg_rl.scene_generation import (
    BaseParser,
    TextParser,
    VisionParser,
    SceneComposer,
    get_template,
    list_templates,
)
from surg_rl.scene_generation.base_parser import ParserError, ParseValidationError
from surg_rl.scene_generation.base_parser import ParseTimeoutError
from surg_rl.scene_definition import SceneDefinition, Metadata, SimulatorType


class TestTemplates:
    """Tests for scene templates."""

    def test_get_suturing_template(self):
        """Test getting suturing template."""
        scene = get_template("suturing")
        assert isinstance(scene, SceneDefinition)
        assert "suturing" in scene.metadata.name.lower()
        assert len(scene.robots) > 0
        assert len(scene.tissues) > 0

    def test_get_dissection_template(self):
        """Test getting dissection template."""
        scene = get_template("dissection")
        assert isinstance(scene, SceneDefinition)
        assert "dissection" in scene.metadata.name.lower()
        assert len(scene.robots) >= 2  # Two instruments

    def test_get_manipulation_template(self):
        """Test getting manipulation template."""
        scene = get_template("manipulation")
        assert isinstance(scene, SceneDefinition)
        assert "manipulation" in scene.metadata.name.lower()

    def test_get_template_case_insensitive(self):
        """Test template name is case insensitive."""
        scene1 = get_template("SUTURING")
        scene2 = get_template("Suturing")
        scene3 = get_template("suturing")
        assert scene1.metadata.name == scene2.metadata.name == scene3.metadata.name

    def test_get_unknown_template(self):
        """Test error on unknown template."""
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("unknown_template")

    def test_list_templates(self):
        """Test listing available templates."""
        templates = list_templates()
        assert isinstance(templates, dict)
        assert "suturing" in templates
        assert "dissection" in templates
        assert "manipulation" in templates
        assert all(isinstance(desc, str) for desc in templates.values())


class TestBaseParser:
    """Tests for base parser class."""

    def test_resolve_input_string(self):
        """Test resolving string input."""
        text = "This is a test description"
        result = BaseParser._resolve_input(text)
        assert result == text

    def test_resolve_input_path(self, tmp_path: Path):
        """Test resolving file path input."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("File content")

        result = BaseParser._resolve_input(test_file)
        assert result == "File content"

    def test_resolve_input_path_not_found(self):
        """Test error when file not found."""
        with pytest.raises(FileNotFoundError):
            BaseParser._resolve_input(Path("/nonexistent/file.txt"))

    def test_resolve_input_bytes(self):
        """Test resolving bytes input."""
        data = b"binary data"
        result = BaseParser._resolve_input(data)
        assert result == data

    def test_validate_scene(self):
        """Test scene validation."""
        # validate_scene is now a static method
        scene_data = {
            "metadata": {"name": "Test"},
            "simulator": "mujoco"
        }
        scene = BaseParser.validate_scene(scene_data)
        assert isinstance(scene, SceneDefinition)
        assert scene.metadata.name == "Test"


class TestTextParser:
    """Tests for text parser."""

    def test_parser_initialization(self):
        """Test parser initializes correctly."""
        parser = TextParser()
        assert parser.provider is not None
        assert parser.model is not None

    def test_parser_custom_settings(self):
        """Test parser with custom settings."""
        parser = TextParser(
            provider="openai",
            model="gpt-4",
            temperature=0.5,
            max_tokens=2000,
        )
        assert parser.provider == "openai"
        assert parser.model == "gpt-4"
        assert parser.temperature == 0.5
        assert parser.max_tokens == 2000

    def test_parse_json_response_direct(self):
        """Test parsing direct JSON response."""
        parser = TextParser()
        response = '{"name": "Test", "version": "1.0"}'
        result = parser._parse_json_response(response)
        assert result == {"name": "Test", "version": "1.0"}

    def test_parse_json_response_markdown(self):
        """Test parsing JSON from markdown code block."""
        parser = TextParser()
        response = '```json\n{"name": "Test"}\n```'
        result = parser._parse_json_response(response)
        assert result == {"name": "Test"}

    def test_parse_json_response_embedded(self):
        """Test parsing embedded JSON."""
        parser = TextParser()
        response = 'Here is the scene: {"name": "Test"}'
        result = parser._parse_json_response(response)
        assert result == {"name": "Test"}

    def test_parse_json_response_invalid(self):
        """Test error on invalid JSON."""
        parser = TextParser()
        response = "This is not valid JSON"
        with pytest.raises(ParserError, match="Could not extract"):
            parser._parse_json_response(response)

    @pytest.mark.asyncio
    async def test_parse_requires_text(self):
        """Test that parser requires text input."""
        parser = TextParser()
        with pytest.raises(ParserError, match="requires text input"):
            await parser.parse(b"binary data")


class TestVisionParser:
    """Tests for vision parser."""

    def test_parser_initialization(self):
        """Test parser initializes correctly."""
        parser = VisionParser()
        assert parser.provider is not None
        assert parser.model is not None

    def test_validate_image_format(self, tmp_path: Path):
        """Test image format validation."""
        parser = VisionParser()

        # Valid format
        valid_image = tmp_path / "test.jpg"
        valid_image.touch()
        parser._validate_image(valid_image)  # Should not raise

        # Invalid format
        invalid_image = tmp_path / "test.xyz"
        invalid_image.touch()
        with pytest.raises(ValueError, match="Unsupported image format"):
            parser._validate_image(invalid_image)

    def test_validate_image_not_found(self):
        """Test error when image not found."""
        parser = VisionParser()
        with pytest.raises(FileNotFoundError):
            parser._validate_image(Path("/nonexistent/image.jpg"))

    def test_get_image_format(self):
        """Test image format detection."""
        parser = VisionParser()

        assert parser._get_image_format(Path("test.jpg")) == "image/jpeg"
        assert parser._get_image_format(Path("test.png")) == "image/png"
        assert parser._get_image_format(Path("test.gif")) == "image/gif"
        assert parser._get_image_format(Path("test.webp")) == "image/webp"
        assert parser._get_image_format() == "image/jpeg"  # Default

    def test_encode_image_bytes(self):
        """Test encoding image bytes."""
        parser = VisionParser()
        test_data = b"fake image data"
        result = parser._encode_image(test_data)
        assert isinstance(result, str)
        # Verify it's base64
        import base64
        decoded = base64.b64decode(result)
        assert decoded == test_data


class TestSceneComposer:
    """Tests for scene composer."""

    def test_composer_initialization(self):
        """Test composer initializes correctly."""
        composer = SceneComposer()
        assert composer.text_parser is not None
        assert composer.vision_parser is not None

    def test_composer_custom_parsers(self):
        """Test composer with custom parsers."""
        text_parser = TextParser(provider="anthropic")
        vision_parser = VisionParser(provider="anthropic")

        composer = SceneComposer(
            text_parser=text_parser,
            vision_parser=vision_parser,
        )
        assert composer.text_parser.provider == "anthropic"
        assert composer.vision_parser.provider == "anthropic"

    def test_merge_two_scenes(self):
        """Test merging two scenes."""
        composer = SceneComposer()

        scene1 = SceneDefinition(
            metadata=Metadata(name="Scene1"),
            simulator=SimulatorType.MUJOCO,
        )
        scene2 = SceneDefinition(
            metadata=Metadata(name="Scene2"),
            simulator=SimulatorType.PYBULLET,
        )

        merged = composer._merge_two_scenes(scene1, scene2)
        assert merged.metadata.name == "Scene2"  # Scene2 takes precedence
        assert merged.simulator == SimulatorType.PYBULLET

    def test_merge_scenes_with_lists(self):
        """Test merging scenes with entity lists."""
        composer = SceneComposer()

        from surg_rl.scene_definition import RobotConfig

        scene1 = SceneDefinition(
            metadata=Metadata(name="Scene1"),
            robots=[RobotConfig(name="robot1", urdf_path="robot1.urdf")],
        )
        scene2 = SceneDefinition(
            metadata=Metadata(name="Scene2"),
            robots=[RobotConfig(name="robot2", urdf_path="robot2.urdf")],
        )

        merged = composer._merge_two_scenes(scene1, scene2)
        assert len(merged.robots) == 2

    def test_merge_strategy_invalid(self):
        """Test error on invalid merge strategy."""
        composer = SceneComposer()

        with pytest.raises(ValueError, match="Unknown merge strategy"):
            composer.compose_sync(
                text_inputs=["test"],
                merge_strategy="invalid",
            )

    def test_merge_scenes_null_physics(self):
        """Test merging scenes where one has no physics config."""
        composer = SceneComposer()

        scene1 = SceneDefinition(
            metadata=Metadata(name="Scene1"),
        )
        scene2 = SceneDefinition(
            metadata=Metadata(name="Scene2"),
            simulator=SimulatorType.PYBULLET,
        )
        # Force physics to None by using model_construct
        from surg_rl.scene_definition import SceneDefinition as SD
        scene1_none_physics = SD.model_construct(
            metadata=Metadata(name="Scene1"),
            physics=None,
        )

        merged = composer._merge_two_scenes(scene1_none_physics, scene2)
        assert merged.metadata.name == "Scene2"
        assert merged.simulator == SimulatorType.PYBULLET

    def test_merge_scenes_both_null_physics(self):
        """Test merging scenes where both have no physics config."""
        composer = SceneComposer()

        from surg_rl.scene_definition import SceneDefinition as SD
        scene1 = SD.model_construct(
            metadata=Metadata(name="Scene1"),
            physics=None,
        )
        scene2 = SD.model_construct(
            metadata=Metadata(name="Scene2"),
            physics=None,
        )

        merged = composer._merge_two_scenes(scene1, scene2)
        assert merged.metadata.name == "Scene2"

    def test_merge_scenes_null_environment(self):
        """Test merging scenes where one has no environment config."""
        composer = SceneComposer()

        from surg_rl.scene_definition import SceneDefinition as SD
        scene1 = SD.model_construct(
            metadata=Metadata(name="Scene1"),
            environment=None,
        )
        scene2 = SceneDefinition(
            metadata=Metadata(name="Scene2"),
        )

        merged = composer._merge_two_scenes(scene1, scene2)
        assert merged.metadata.name == "Scene2"

    def test_merge_scenes_physics_averaging(self):
        """Test that differing physics timesteps use scene2's physics."""
        composer = SceneComposer()

        from surg_rl.scene_definition import PhysicsConfig

        scene1 = SceneDefinition(
            metadata=Metadata(name="Scene1"),
            physics=PhysicsConfig(timestep=0.002),
        )
        scene2 = SceneDefinition(
            metadata=Metadata(name="Scene2"),
            physics=PhysicsConfig(timestep=0.001),
        )

        merged = composer._merge_two_scenes(scene1, scene2)
        assert merged.physics.timestep == pytest.approx(0.001)


class TestParserErrors:
    """Tests for parser error classes."""

    def test_parser_error(self):
        """Test ParserError."""
        error = ParserError("Test error", details={"key": "value"})
        assert str(error) == "Test error"
        assert error.details == {"key": "value"}

    def test_parse_timeout_error(self):
        """Test ParseTimeoutError."""
        error = ParseTimeoutError("Timeout")
        assert isinstance(error, ParserError)

    def test_parse_validation_error(self):
        """Test ParseValidationError."""
        error = ParseValidationError("Validation failed")
        assert isinstance(error, ParserError)


class TestPromptTemplates:
    """Tests for prompt templates."""

    def test_text_prompts_import(self):
        """Test importing text prompts."""
        from surg_rl.scene_generation.prompts.text_prompts import (
            SYSTEM_PROMPT,
            SCENE_GENERATION_PROMPT,
            SCENE_MODIFICATION_PROMPT,
            get_scene_generation_prompt,
            get_scene_modification_prompt,
        )

        assert len(SYSTEM_PROMPT) > 0
        assert "{description}" in SCENE_GENERATION_PROMPT
        assert "{current_scene}" in SCENE_MODIFICATION_PROMPT

        prompt = get_scene_generation_prompt("Test description")
        assert "Test description" in prompt

    def test_vision_prompts_import(self):
        """Test importing vision prompts."""
        from surg_rl.scene_generation.prompts.vision_prompts import (
            IMAGE_ANALYSIS_PROMPT,
            IMAGE_TO_SCENE_PROMPT,
            get_image_analysis_prompt,
            get_image_to_scene_prompt,
            get_specialized_prompt,
        )

        assert len(IMAGE_ANALYSIS_PROMPT) > 0
        assert "{additional_instructions}" in IMAGE_TO_SCENE_PROMPT

        prompt = get_image_analysis_prompt()
        assert len(prompt) > 0

        lap_prompt = get_specialized_prompt("laparoscopic")
        assert "laparoscopic" in lap_prompt.lower()

        with pytest.raises(ValueError, match="Unknown scenario type"):
            get_specialized_prompt("invalid")

    def test_vision_prompt_contains_valid_json(self):
        """The vision prompt schema example must use double-quoted JSON, not Python repr."""
        from surg_rl.scene_generation.prompts.vision_prompts import get_image_to_scene_prompt

        prompt = get_image_to_scene_prompt()
        assert "metadata" in prompt
        # Must not contain single-quoted dict repr
        assert "'metadata'" not in prompt, "Prompt contains Python repr instead of JSON"


# Mark tests that require API access
@pytest.mark.integration
class TestTextParserIntegration:
    """Integration tests for text parser (requires API key)."""

    @pytest.mark.skip(reason="Requires API key")
    async def test_real_parse(self):
        """Test real LLM parsing."""
        parser = TextParser()
        scene = await parser.parse("Create a simple suturing scene")
        assert isinstance(scene, SceneDefinition)


@pytest.mark.integration
class TestVisionParserIntegration:
    """Integration tests for vision parser (requires API key)."""

    @pytest.mark.skip(reason="Requires API key")
    async def test_real_parse(self):
        """Test real VLM parsing."""
        parser = VisionParser()
        # Would need actual image
        # scene = await parser.parse("path/to/image.jpg")
        pass


class TestOllamaIntegration:
    """Tests for Ollama provider integration."""

    def test_text_parser_ollama_initialization(self):
        """Test TextParser initializes with Ollama provider."""
        parser = TextParser(provider="ollama")
        assert parser.provider == "ollama"
        assert parser.ollama_base_url is not None
        assert parser.ollama_timeout > 0

    def test_text_parser_ollama_custom_settings(self):
        """Test TextParser with custom Ollama settings."""
        parser = TextParser(
            provider="ollama",
            model="llama3.2",
            ollama_base_url="http://localhost:11434",
            ollama_timeout=120,
        )
        assert parser.provider == "ollama"
        assert parser.model == "llama3.2"
        assert parser.ollama_base_url == "http://localhost:11434"
        assert parser.ollama_timeout == 120

    def test_vision_parser_ollama_initialization(self):
        """Test VisionParser initializes with Ollama provider."""
        parser = VisionParser(provider="ollama")
        assert parser.provider == "ollama"
        assert parser.ollama_base_url is not None

    def test_vision_parser_ollama_custom_settings(self):
        """Test VisionParser with custom Ollama settings."""
        parser = VisionParser(
            provider="ollama",
            model="llava",
            ollama_base_url="http://192.168.1.100:11434",
            ollama_timeout=180,
        )
        assert parser.provider == "ollama"
        assert parser.model == "llava"
        assert parser.ollama_base_url == "http://192.168.1.100:11434"
        assert parser.ollama_timeout == 180

    @patch('httpx.Client')
    def test_ollama_client_creation(self, mock_httpx):
        """Test Ollama client is created correctly."""
        parser = TextParser(provider="ollama")
        client = parser._get_client()
        assert client is not None
        assert hasattr(client, 'generate')

    @patch('httpx.AsyncClient')
    def test_ollama_async_client_creation(self, mock_async_client):
        """Test async Ollama client is created correctly."""
        parser = TextParser(provider="ollama")
        client = parser._get_async_client()
        assert client is not None
        assert hasattr(client, 'generate')

    def test_config_ollama_defaults(self):
        """Test configuration has default Ollama settings."""
        from surg_rl.utils.config import get_settings
        settings = get_settings()
        
        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "llama3.2"
        assert settings.ollama_vision_model == "llava"
        assert settings.ollama_timeout == 300

    def test_config_allows_ollama_provider(self):
        """Test configuration allows 'ollama' as a provider."""
        from surg_rl.utils.config import Settings
        settings = Settings(llm_provider="ollama")
        assert settings.llm_provider == "ollama"


def test_parse_sync_inside_event_loop_raises():
    """parse_sync must raise RuntimeError when called inside a running event loop."""
    import asyncio
    from surg_rl.scene_generation.text_parser import TextParser
    from surg_rl.scene_generation.vision_parser import VisionParser

    async def inner():
        text_parser = TextParser(provider="openai")
        with pytest.raises(RuntimeError, match="running event loop"):
            text_parser.parse_sync("test")

        vision_parser = VisionParser(provider="openai")
        with pytest.raises(RuntimeError, match="running event loop"):
            vision_parser.parse_sync("test.jpg")

    asyncio.run(inner())
