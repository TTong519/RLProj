"""VLM-based vision parser for scene generation.

This module provides a vision parser that uses Vision Language Models (VLMs)
to analyze images and generate structured scene definitions.
Supports OpenAI GPT-4 Vision, Anthropic Claude, and Ollama vision models.
"""

import asyncio
import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from surg_rl.scene_definition import SceneDefinition
from surg_rl.utils.config import get_settings
from surg_rl.utils.logging import get_logger

from pydantic import ValidationError

from .base_parser import BaseParser, ParserError, ParseValidationError
from .prompts.text_prompts import SYSTEM_PROMPT
from .prompts.vision_prompts import (
    get_image_analysis_prompt,
    get_image_to_scene_prompt,
    get_specialized_prompt,
)

logger = get_logger(__name__)

# Pre-compiled regex patterns for JSON extraction (hot path during parsing)
_JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_JSON_OBJ_RE = re.compile(r"\{[\s\S]*?\}")

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


class VisionParser(BaseParser):
    """Parse images into scene definitions using Vision Language Models.

    This parser uses OpenAI GPT-4 Vision, Anthropic Claude with vision,
    or Ollama vision models to analyze images and generate scene definitions.

    Attributes:
        provider: VLM provider ('openai', 'anthropic', or 'ollama').
        model: Model name to use.
        temperature: Sampling temperature for generation.
        max_tokens: Maximum tokens in response.
        ollama_base_url: Base URL for Ollama API.
        ollama_timeout: Timeout for Ollama API calls.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        ollama_base_url: Optional[str] = None,
        ollama_timeout: Optional[int] = None,
    ):
        """Initialize the vision parser.

        Args:
            provider: VLM provider ('openai', 'anthropic', or 'ollama').
                Uses config default if not provided.
            model: Model name to use.
                Uses config default if not provided.
            api_key: API key for authentication (not needed for Ollama).
                Uses environment variable if not provided.
            temperature: Sampling temperature (0.0-2.0).
                Uses config default if not provided.
            max_tokens: Maximum tokens in response.
                Uses config default if not provided.
            ollama_base_url: Base URL for Ollama API.
                Uses config default if not provided.
            ollama_timeout: Timeout for Ollama API calls.
                Uses config default if not provided.
        """
        settings = get_settings()

        self.provider = provider or settings.llm_provider
        self.model = model or (
            settings.ollama_vision_model if self.provider == "ollama" else settings.vlm_model
        )
        self.api_key = api_key or settings.llm_api_key
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.ollama_timeout = ollama_timeout or settings.ollama_timeout

        # Client will be initialized lazily when needed
        self._async_client = None

        super().__init__(provider=self.provider, model=self.model, api_key=self.api_key)

    def _get_async_client(self):
        """Get or create the async VLM client.

        Returns:
            Async VLM client instance.

        Raises:
            ImportError: If required package is not installed.
            ValueError: If provider is not supported.
        """
        if self._async_client is None:
            if self.provider == "openai":
                try:
                    import openai

                    self._async_client = openai.AsyncOpenAI(api_key=self.api_key)
                except ImportError:
                    raise ImportError(
                        "OpenAI package not installed. Install with: pip install openai"
                    )
            elif self.provider == "anthropic":
                try:
                    import anthropic

                    self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
                except ImportError:
                    raise ImportError(
                        "Anthropic package not installed. Install with: pip install anthropic"
                    )
            elif self.provider == "ollama":
                self._async_client = self._create_async_ollama_client()
            else:
                raise ValueError(
                    f"Unsupported provider: {self.provider}. "
                    "Supported: 'openai', 'anthropic', 'ollama'"
                )

        return self._async_client

    def _create_async_ollama_client(self):
        """Create an async Ollama client wrapper for vision.

        Returns:
            Async Ollama client wrapper with vision support.
        """
        import httpx

        class AsyncOllamaVisionClient:
            """Async Ollama API client wrapper with vision support."""

            def __init__(self, base_url: str, timeout: int):
                self.base_url = base_url.rstrip("/")
                self.timeout = timeout
                self._client = httpx.AsyncClient(timeout=timeout)

            async def generate_with_image(
                self,
                model: str,
                prompt: str,
                image_data: str,
                image_format: str = "image/jpeg",
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 4096,
            ) -> str:
                """Generate completion with image using Ollama API.

                Args:
                    model: Model name (e.g., 'llava', 'bakllava').
                    prompt: User prompt.
                    image_data: Base64 encoded image data.
                    image_format: Image MIME type.
                    system: System prompt.
                    temperature: Sampling temperature.
                    max_tokens: Maximum tokens.

                Returns:
                    Generated text.
                """
                # Build the full prompt with system message
                full_prompt = f"{system}\n\n{prompt}" if system else prompt

                response = await self._client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": full_prompt,
                        "stream": False,
                        "images": [image_data],  # Ollama expects base64 images
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

            async def close(self):
                """Close the HTTP client."""
                await self._client.aclose()

        return AsyncOllamaVisionClient(self.ollama_base_url, self.ollama_timeout)

    def _validate_image(self, image_path: Path) -> None:
        """Validate image file.

        Args:
            image_path: Path to image file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If format is not supported.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        suffix = image_path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(
                f"Unsupported image format: {suffix}. "
                f"Supported formats: {SUPPORTED_IMAGE_FORMATS}"
            )

    def _encode_image(self, image_data: Union[Path, bytes]) -> str:
        """Encode image to base64 string.

        Args:
            image_data: Path to image file or image bytes.

        Returns:
            Base64 encoded image string.
        """
        if isinstance(image_data, Path):
            with open(image_data, "rb") as f:
                image_bytes = f.read()
        else:
            image_bytes = image_data

        return base64.b64encode(image_bytes).decode("utf-8")

    def _get_image_format(self, image_path: Optional[Path] = None) -> str:
        """Get image format for API.

        Args:
            image_path: Optional path to determine format.

        Returns:
            Image format string (e.g., 'image/jpeg').
        """
        if image_path:
            suffix = image_path.suffix.lower()
            format_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }
            return format_map.get(suffix, "image/jpeg")
        return "image/jpeg"

    async def parse(
        self,
        input_data: Union[str, Path, bytes],
        **kwargs: Any,
    ) -> SceneDefinition:
        """Parse image into scene definition.

        Args:
            input_data: Path to image file or image bytes.
            **kwargs: Additional arguments:
                - temperature: Override default temperature.
                - scenario_type: Type of surgical scenario.
                - additional_instructions: Extra instructions for generation.

        Returns:
            SceneDefinition object.

        Raises:
            ParserError: If parsing fails.
            ParseValidationError: If generated scene is invalid.
        """
        # Resolve image input
        if isinstance(input_data, str):
            input_data = Path(input_data)

        if isinstance(input_data, Path):
            self._validate_image(input_data)
            image_bytes = input_data.read_bytes()
            image_path = input_data
        else:
            image_bytes = input_data
            image_path = None

        logger.info(f"Parsing image with {self.provider}/{self.model}")

        # Generate scene
        scene_data = await self._generate_scene_from_image(
            image_data=image_bytes,
            image_path=image_path,
            temperature=kwargs.get("temperature", self.temperature),
            scenario_type=kwargs.get("scenario_type"),
            additional_instructions=kwargs.get("additional_instructions"),
        )

        # Validate and return
        try:
            scene = self.validate_scene(scene_data)
            logger.info(f"Successfully parsed scene: {scene.metadata.name}")
            return scene
        except ValidationError as e:
            details: Dict[str, Any] = {
                "raw_response": scene_data,
                "errors": [
                    {"loc": list(err.get("loc", [])), "msg": err.get("msg", "")}
                    for err in e.errors()
                ],
            }
            raise ParseValidationError(
                f"Scene validation failed: {e}",
                details=details,
            ) from e
        except Exception as e:
            raise ParseValidationError(
                f"Scene validation failed: {e}",
                details={"raw_response": scene_data, "error": str(e)},
            ) from e

    async def parse_with_context(
        self,
        input_data: Union[str, Path, bytes],
        context: Optional[SceneDefinition] = None,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Parse image with optional existing scene context.

        Args:
            input_data: Path to image file or image bytes.
            context: Existing scene to modify/extend.
            **kwargs: Additional arguments.

        Returns:
            Modified SceneDefinition object.
        """
        # Resolve image input
        if isinstance(input_data, str):
            input_data = Path(input_data)

        if isinstance(input_data, Path):
            self._validate_image(input_data)
            image_bytes = input_data.read_bytes()
            image_path = input_data
        else:
            image_bytes = input_data
            image_path = None

        # Get context JSON if provided
        context_json = self._get_context_json(context)

        # Generate modified scene
        scene_data = await self._modify_scene_from_image(
            image_data=image_bytes,
            image_path=image_path,
            context_json=context_json,
            temperature=kwargs.get("temperature", self.temperature),
        )

        try:
            scene = self.validate_scene(scene_data)
            logger.info(f"Successfully modified scene: {scene.metadata.name}")
            return scene
        except Exception as e:
            raise ParseValidationError(
                f"Modified scene validation failed: {e}",
                details={"raw_response": scene_data, "error": str(e)},
            )

    async def analyze_image(
        self,
        input_data: Union[str, Path, bytes],
        **kwargs: Any,
    ) -> str:
        """Analyze image and return text description (no scene generation).

        Args:
            input_data: Path to image file or image bytes.
            **kwargs: Additional arguments.

        Returns:
            Text description of the image.
        """
        # Resolve image input
        if isinstance(input_data, str):
            input_data = Path(input_data)

        if isinstance(input_data, Path):
            self._validate_image(input_data)
            image_bytes = input_data.read_bytes()
            image_path = input_data
        else:
            image_bytes = input_data
            image_path = None

        prompt = get_image_analysis_prompt()

        return await self._call_vlm_async(
            prompt=prompt,
            image_data=image_bytes,
            image_path=image_path,
            temperature=kwargs.get("temperature", self.temperature),
        )

    async def _generate_scene_from_image(
        self,
        image_data: bytes,
        image_path: Optional[Path] = None,
        temperature: Optional[float] = None,
        scenario_type: Optional[str] = None,
        additional_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze image with VLM and return scene data.

        Args:
            image_data: Image bytes.
            image_path: Optional path for format detection.
            temperature: Sampling temperature.
            scenario_type: Type of surgical scenario.
            additional_instructions: Extra instructions for generation.

        Returns:
            Dictionary containing scene data.
        """
        # Build prompt based on scenario type
        if scenario_type:
            specialized = get_specialized_prompt(scenario_type)
            if additional_instructions:
                additional_instructions = f"{specialized}\n\nAdditional instructions: {additional_instructions}"
            else:
                additional_instructions = specialized

        prompt = get_image_to_scene_prompt(
            additional_instructions=additional_instructions,
        )

        response = await self._call_vlm_async(
            prompt=prompt,
            image_data=image_data,
            image_path=image_path,
            temperature=temperature or self.temperature,
        )

        return self._parse_json_response(response)

    async def _modify_scene_from_image(
        self,
        image_data: bytes,
        context_json: Optional[str],
        image_path: Optional[Path] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Modify existing scene based on image.

        Args:
            image_data: Image bytes.
            context_json: Current scene JSON.
            image_path: Optional path for format detection.
            temperature: Sampling temperature.

        Returns:
            Dictionary containing modified scene data.
        """
        import json

        context_str = context_json or "{}"
        prompt = f"""Analyze this image and modify the following scene definition accordingly.

Current scene:
{context_str}

Generate a complete modified scene definition in JSON format.
Respond ONLY with the JSON object, no additional text."""

        response = await self._call_vlm_async(
            prompt=prompt,
            image_data=image_data,
            image_path=image_path,
            temperature=temperature or self.temperature,
        )

        return self._parse_json_response(response)

    async def _call_vlm_async(
        self,
        prompt: str,
        image_data: Union[Path, bytes],
        image_path: Optional[Path] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Make async API call to VLM provider.

        Args:
            prompt: The prompt to send.
            image_data: Image path or bytes.
            image_path: Optional path for format detection.
            temperature: Sampling temperature.

        Returns:
            VLM response text.

        Raises:
            ParserError: If API call fails.
        """
        client = self._get_async_client()
        temp = temperature if temperature is not None else self.temperature
        image_format = self._get_image_format(image_path)
        base64_image = self._encode_image(image_data)

        try:
            if self.provider == "openai":
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{image_format};base64,{base64_image}",
                                    },
                                },
                            ],
                        }
                    ],
                    temperature=temp,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content

            elif self.provider == "anthropic":
                response = await client.messages.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": image_format,
                                        "data": base64_image,
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                    temperature=temp,
                    max_tokens=self.max_tokens,
                )
                return response.content[0].text

            elif self.provider == "ollama":
                response = await client.generate_with_image(
                    model=self.model,
                    prompt=prompt,
                    image_data=base64_image,
                    image_format=image_format,
                    system=SYSTEM_PROMPT,
                    temperature=temp,
                    max_tokens=self.max_tokens,
                )
                return response

        except Exception as e:
            logger.error(f"VLM API call failed: {e}")
            raise ParserError(
                f"VLM API call failed: {e}",
                details={"provider": self.provider, "model": self.model, "error": str(e)},
            )

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Extract and parse JSON from VLM response.

        Args:
            response: Raw VLM response text.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ParserError: If JSON cannot be extracted or parsed.
        """
        # Try direct parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        matches = _JSON_CODE_BLOCK_RE.findall(response)

        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # Try to find JSON object in text
        matches = _JSON_OBJ_RE.findall(response)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        raise ParserError(
            "Could not extract valid JSON from VLM response",
            details={"response": response[:1000]},  # Include first 1000 chars
        )

    # Synchronous wrappers for convenience

    def parse_sync(
        self,
        input_data: Union[str, Path, bytes],
        **kwargs: Any,
    ) -> SceneDefinition:
        """Synchronous wrapper for parse.

        Args:
            input_data: Path to image file or image bytes.
            **kwargs: Additional arguments.

        Returns:
            SceneDefinition object.

        Raises:
            RuntimeError: If called inside a running event loop.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.parse(input_data, **kwargs))
        raise RuntimeError(
            "parse_sync cannot be called from within a running event loop. "
            "Use parse() (async) instead."
        )

    def parse_with_context_sync(
        self,
        input_data: Union[str, Path, bytes],
        context: Optional[SceneDefinition] = None,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Synchronous wrapper for parse_with_context.

        Args:
            input_data: Path to image file or image bytes.
            context: Existing scene to modify/extend.
            **kwargs: Additional arguments.

        Returns:
            Modified SceneDefinition object.

        Raises:
            RuntimeError: If called inside a running event loop.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.parse_with_context(input_data, context, **kwargs))
        raise RuntimeError(
            "parse_with_context_sync cannot be called from within a running event loop. "
            "Use parse_with_context() (async) instead."
        )

    def analyze_image_sync(
        self,
        input_data: Union[str, Path, bytes],
        **kwargs: Any,
    ) -> str:
        """Synchronous wrapper for analyze_image.

        Args:
            input_data: Path to image file or image bytes.
            **kwargs: Additional arguments.

        Returns:
            Text description of the image.

        Raises:
            RuntimeError: If called inside a running event loop.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.analyze_image(input_data, **kwargs))
        raise RuntimeError(
            "analyze_image_sync cannot be called from within a running event loop. "
            "Use analyze_image() (async) instead."
        )
