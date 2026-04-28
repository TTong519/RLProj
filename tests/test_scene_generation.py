"""Tests for scene generation module."""

import asyncio
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


def test_sequential_composition_preserves_input_order():
    """Sequential composition with inputs must process in given order."""
    import asyncio
    from unittest.mock import MagicMock
    from surg_rl.scene_generation.scene_composer import SceneComposer

    composer = SceneComposer()

    order = []

    async def mock_text_parse(*args, **kwargs):
        inp = kwargs.get("input_data", args[0] if args else None)
        order.append(("text", inp))
        return MagicMock()

    async def mock_image_parse(*args, **kwargs):
        inp = kwargs.get("input_data", args[0] if args else None)
        order.append(("image", str(inp)))
        return MagicMock()

    composer.text_parser.parse_with_context = mock_text_parse
    composer.vision_parser.parse_with_context = mock_image_parse

    asyncio.run(
        composer.compose(
            inputs=["text1", Path("img.png"), "text2"],
            merge_strategy="sequential",
        )
    )

    assert order == [("text", "text1"), ("image", "img.png"), ("text", "text2")]


class TestTextParserMocked:
    """Tests for TextParser with mocked LLM clients."""

    def test_parse_with_context_mocked(self):
        """parse_with_context feeds context scene into prompt."""
        from surg_rl.scene_generation.text_parser import TextParser
        from surg_rl.scene_definition import SceneDefinition, Metadata
        parser = TextParser()
        context = SceneDefinition(metadata=Metadata(name="base"))
        parser._call_llm_async = AsyncMock(return_value='{"metadata": {"name": "modified"}}')
        result = asyncio.run(parser.parse_with_context("modify", context))
        assert "modified" in result.metadata.name

    def test_parse_with_context_sync(self):
        """parse_with_context_sync returns valid dict."""
        from surg_rl.scene_generation.text_parser import TextParser
        from surg_rl.scene_definition import SceneDefinition, Metadata
        parser = TextParser()
        context = SceneDefinition(metadata=Metadata(name="base"))
        parser._call_llm_async = AsyncMock(return_value='{"metadata": {"name": "sync_mod"}}')
        result = parser.parse_with_context_sync("modify", context)
        assert "sync_mod" in result.metadata.name

    @pytest.mark.asyncio
    async def test_parse_bytes_rejected(self):
        """parse with bytes input raises ParserError."""
        from surg_rl.scene_generation.text_parser import TextParser, ParserError
        parser = TextParser()
        with pytest.raises(ParserError):
            await parser.parse(b"some bytes")


class TestVisionParserMocked:
    """Tests for VisionParser with mocked VLM calls."""

    def test_generate_scene_from_image_mocked(self):
        """_generate_scene_from_image parses VLM response."""
        from surg_rl.scene_generation.vision_parser import VisionParser
        parser = VisionParser()
        parser._call_vlm_async = AsyncMock(return_value='{"metadata": {"name": "vision_scene"}}')
        result = asyncio.run(parser._generate_scene_from_image(b"fake_image"))
        assert result["metadata"]["name"] == "vision_scene"


class TestSceneComposerMerge:
    """Tests for SceneComposer scene merging logic."""

    def test_merge_scenes_empty_list(self):
        """Empty scenes list returns a new SceneDefinition."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import SceneDefinition
        composer = SceneComposer()
        result = composer._merge_scenes([])
        assert isinstance(result, SceneDefinition)

    def test_merge_scenes_single_scene_with_base(self):
        """Single scene with base_scene merges correctly."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import SceneDefinition, Metadata
        composer = SceneComposer()
        base = SceneDefinition(metadata=Metadata(name="base"))
        scene = SceneDefinition(metadata=Metadata(name="child"))
        result = composer._merge_scenes([scene], base_scene=base)
        # Child metadata should override base in a real merge; here just verify no crash
        assert isinstance(result, SceneDefinition)

    def test_compose_parallel_all_fail(self):
        """Parallel composition where all tasks fail raises ParserError."""
        from surg_rl.scene_generation.scene_composer import SceneComposer, ParserError
        composer = SceneComposer()
        composer.text_parser.parse = AsyncMock(side_effect=Exception("fail"))
        with pytest.raises(ParserError):
            asyncio.run(composer._compose_parallel(text_inputs=["text"], image_inputs=None, base_scene=None))

    def test_merge_two_scenes_metadata_override(self):
        """Second scene metadata overrides first."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import SceneDefinition, Metadata
        composer = SceneComposer()
        a = SceneDefinition(metadata=Metadata(name="a"))
        b = SceneDefinition(metadata=Metadata(name="b"))
        result = composer._merge_two_scenes(a, b)
        assert result.metadata.name == "b"

    def test_merge_two_scenes_combines_robots(self):
        """Merging combines robots from both scenes."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import SceneDefinition, Metadata, RobotConfig
        composer = SceneComposer()
        a = SceneDefinition(metadata=Metadata(name="a"))
        a.robots.append(RobotConfig(name="r1", urdf_path="robot1.urdf"))
        b = SceneDefinition(metadata=Metadata(name="b"))
        b.robots.append(RobotConfig(name="r2", urdf_path="robot2.urdf"))
        result = composer._merge_two_scenes(a, b)
        names = {r.name for r in result.robots}
        assert names == {"r1", "r2"}

    def test_merge_duplicate_name_same_type_raises(self):
        """Two robots with the same name raises ValueError."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import SceneDefinition, Metadata, RobotConfig
        composer = SceneComposer()
        a = SceneDefinition(
            metadata=Metadata(name="a"),
            robots=[RobotConfig(name="arm", urdf_path="a.urdf")],
        )
        b = SceneDefinition(
            metadata=Metadata(name="b"),
            robots=[RobotConfig(name="arm", urdf_path="b.urdf")],
        )
        with pytest.raises(ValueError, match="Duplicate entity name 'arm' during scene merge"):
            composer._merge_two_scenes(a, b)

    def test_merge_duplicate_name_different_type_ok(self):
        """A robot and a tissue with the same name does NOT raise."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import (
            SceneDefinition, Metadata, RobotConfig, TissueConfig, TissueMeshDefinition,
        )
        composer = SceneComposer()
        a = SceneDefinition(
            metadata=Metadata(name="a"),
            robots=[RobotConfig(name="arm", urdf_path="a.urdf")],
        )
        b = SceneDefinition(
            metadata=Metadata(name="b"),
            tissues=[TissueConfig(name="arm", geometry=TissueMeshDefinition(primitive="box", dimensions=(1.0, 1.0, 1.0)))],
        )
        result = composer._merge_two_scenes(a, b)
        assert len(result.robots) == 1
        assert len(result.tissues) == 1

    def test_merge_domain_randomization_preserves_scene1_defaults(self):
        """scene1 has explicit physics.enabled=True; scene2 has default DR; merged keeps it."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import (
            SceneDefinition, Metadata, DomainRandomizationConfig,
        )
        composer = SceneComposer()
        dr1 = DomainRandomizationConfig(physics={"enabled": True})
        a = SceneDefinition(metadata=Metadata(name="a"), domain_randomization=dr1)
        b = SceneDefinition(metadata=Metadata(name="b"))
        result = composer._merge_two_scenes(a, b)
        assert result.domain_randomization.physics.enabled is True

    def test_merge_environment_not_clobbered_by_defaults(self):
        """scene1 has fog_enabled=True and background_color set; scene2 has no explicit env."""
        from surg_rl.scene_generation.scene_composer import SceneComposer
        from surg_rl.scene_definition import SceneDefinition, Metadata, EnvironmentConfig, RgbColor
        composer = SceneComposer()
        env1 = EnvironmentConfig(fog_enabled=True, background_color=RgbColor(r=0.2, g=0.3, b=0.4, a=1.0))
        a = SceneDefinition(metadata=Metadata(name="a"), environment=env1)
        b = SceneDefinition(metadata=Metadata(name="b"))
        result = composer._merge_two_scenes(a, b)
        assert result.environment.fog_enabled is True
        assert result.environment.background_color.r == pytest.approx(0.2)

