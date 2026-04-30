"""LLM-based text parser for scene generation.

This module provides a text parser that uses Large Language Models (LLMs)
to convert natural language descriptions into structured scene definitions.
Supports OpenAI, Anthropic, and Ollama providers.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from surg_rl.scene_definition import SceneDefinition
from surg_rl.utils.config import get_settings
from surg_rl.utils.logging import get_logger

from .base_parser import BaseParser, ParserError, ParseValidationError
from .prompts.text_prompts import (
    SYSTEM_PROMPT,
    get_scene_generation_prompt,
    get_scene_modification_prompt,
)

logger = get_logger(__name__)

# Pre-compiled regex patterns for JSON extraction (hot path during parsing)
_JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_JSON_OBJ_RE = re.compile(r"\{[\s\S]*?\}")


class TextParser(BaseParser):
    """Parse natural language descriptions into scene definitions using LLMs.

    This parser uses OpenAI, Anthropic, or Ollama LLMs to convert text descriptions
    into structured SceneDefinition objects.

    Attributes:
        provider: LLM provider ('openai', 'anthropic', or 'ollama').
        model: Model name to use.
        temperature: Sampling temperature for generation.
        max_tokens: Maximum tokens in response.
        ollama_base_url: Base URL for Ollama API (if using Ollama).
        ollama_timeout: Timeout for Ollama API calls.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        ollama_base_url: str | None = None,
        ollama_timeout: int | None = None,
    ):
        """Initialize the text parser.

        Args:
            provider: LLM provider ('openai', 'anthropic', or 'ollama').
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
            settings.ollama_model if self.provider == "ollama" else settings.llm_model
        )
        self.api_key = api_key or settings.llm_api_key
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.ollama_timeout = ollama_timeout or settings.ollama_timeout

        # Client will be initialized lazily when needed
        self._client = None
        self._async_client = None

        super().__init__(provider=self.provider, model=self.model, api_key=self.api_key)

    def _get_client(self):
        """Get or create the LLM client.

        Returns:
            LLM client instance.

        Raises:
            ImportError: If required package is not installed.
            ValueError: If provider is not supported.
        """
        if self._client is None:
            if self.provider == "openai":
                try:
                    import openai

                    self._client = openai.OpenAI(api_key=self.api_key)
                except ImportError:
                    raise ImportError(
                        "OpenAI package not installed. Install with: pip install openai"
                    ) from None
            elif self.provider == "anthropic":
                try:
                    import anthropic

                    self._client = anthropic.Anthropic(api_key=self.api_key)
                except ImportError:
                    raise ImportError(
                        "Anthropic package not installed. Install with: pip install anthropic"
                    ) from None
            elif self.provider == "ollama":
                # Ollama uses HTTP requests, no special client needed
                self._client = self._create_ollama_client()
            else:
                raise ValueError(
                    f"Unsupported provider: {self.provider}. "
                    "Supported: 'openai', 'anthropic', 'ollama'"
                )

        return self._client

    def _create_ollama_client(self):
        """Create an Ollama client wrapper.

        Returns:
            Ollama client wrapper with generate method.
        """
        import httpx

        class OllamaClient:
            """Simple Ollama API client wrapper."""

            def __init__(self, base_url: str, timeout: int):
                self.base_url = base_url.rstrip("/")
                self.timeout = timeout
                self._client = httpx.Client(timeout=timeout)

            def generate(
                self,
                model: str,
                prompt: str,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 4096,
            ) -> str:
                """Generate completion using Ollama API.

                Args:
                    model: Model name.
                    prompt: User prompt.
                    system: System prompt.
                    temperature: Sampling temperature.
                    max_tokens: Maximum tokens.

                Returns:
                    Generated text.
                """
                # Build the full prompt with system message
                full_prompt = f"{system}\n\n{prompt}" if system else prompt

                response = self._client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

            def close(self):
                """Close the HTTP client."""
                self._client.close()

        return OllamaClient(self.ollama_base_url, self.ollama_timeout)

    def _get_async_client(self):
        """Get or create the async LLM client.

        Returns:
            Async LLM client instance.
        """
        if self._async_client is None:
            if self.provider == "openai":
                import openai

                self._async_client = openai.AsyncOpenAI(api_key=self.api_key)
            elif self.provider == "anthropic":
                import anthropic

                self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            elif self.provider == "ollama":
                self._async_client = self._create_async_ollama_client()
            else:
                raise ValueError(
                    f"Unsupported provider: {self.provider}. "
                    "Supported: 'openai', 'anthropic', 'ollama'"
                )

        return self._async_client

    def _create_async_ollama_client(self):
        """Create an async Ollama client wrapper.

        Returns:
            Async Ollama client wrapper.
        """
        import httpx

        class AsyncOllamaClient:
            """Async Ollama API client wrapper."""

            def __init__(self, base_url: str, timeout: int):
                self.base_url = base_url.rstrip("/")
                self.timeout = timeout
                self._client = httpx.AsyncClient(timeout=timeout)

            async def generate(
                self,
                model: str,
                prompt: str,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 4096,
            ) -> str:
                """Generate completion using Ollama API asynchronously.

                Args:
                    model: Model name.
                    prompt: User prompt.
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

        return AsyncOllamaClient(self.ollama_base_url, self.ollama_timeout)

    async def parse(
        self,
        input_data: str | Path,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Parse text description into scene definition.

        Args:
            input_data: Text description or path to text file.
            **kwargs: Additional arguments:
                - temperature: Override default temperature.
                - schema_example: Custom schema example for prompt.

        Returns:
            SceneDefinition object.

        Raises:
            ParserError: If parsing fails.
            ParseValidationError: If generated scene is invalid.
        """
        # Resolve input to text
        text = self._resolve_input(input_data)
        if isinstance(text, bytes):
            raise ParserError("TextParser requires text input, not bytes")

        # Override settings with kwargs
        temperature = kwargs.get("temperature", self.temperature)
        schema_example = kwargs.get("schema_example")

        logger.info(f"Parsing text with {self.provider}/{self.model}")

        # Generate scene
        scene_data = await self._generate_scene_async(
            description=text,
            temperature=temperature,
            schema_example=schema_example,
        )

        # Validate and return
        try:
            scene = self.validate_scene(scene_data)
            logger.info(f"Successfully parsed scene: {scene.metadata.name}")
            return scene
        except ValidationError as e:
            details: dict[str, Any] = {
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
        input_data: str | Path | bytes,
        context: SceneDefinition | None = None,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Parse text with optional existing scene context.

        Args:
            input_data: Text description or path to text file.
            context: Existing scene to modify/extend.
            **kwargs: Additional arguments.

        Returns:
            Modified SceneDefinition object.
        """
        # Resolve input to text
        text = self._resolve_input(input_data)
        if isinstance(text, bytes):
            raise ParserError("TextParser requires text input, not bytes")

        # Get context JSON if provided
        context_json = self._get_context_json(context)

        # Generate modified scene
        scene_data = await self._modify_scene_async(
            current_scene=context_json,
            instructions=text,
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
            ) from e

    async def _generate_scene_async(
        self,
        description: str,
        temperature: float | None = None,
        schema_example: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call LLM to generate scene from description.

        Args:
            description: Scene description text.
            temperature: Sampling temperature.
            schema_example: Custom schema example.

        Returns:
            Dictionary containing scene data.
        """
        prompt = get_scene_generation_prompt(description, schema_example)

        response = await self._call_llm_async(
            prompt=prompt,
            temperature=temperature or self.temperature,
        )

        return self._parse_json_response(response)

    async def _modify_scene_async(
        self,
        current_scene: str,
        instructions: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Call LLM to modify existing scene.

        Args:
            current_scene: Current scene JSON string.
            instructions: Modification instructions.
            temperature: Sampling temperature.

        Returns:
            Dictionary containing modified scene data.
        """
        import json

        # Parse current_scene to dict if it's a string
        if isinstance(current_scene, str):
            current_scene_dict = json.loads(current_scene)
        else:
            current_scene_dict = current_scene

        prompt = get_scene_modification_prompt(current_scene_dict, instructions)

        response = await self._call_llm_async(
            prompt=prompt,
            temperature=temperature or self.temperature,
        )

        return self._parse_json_response(response)

    async def _call_llm_async(
        self,
        prompt: str,
        temperature: float | None = None,
    ) -> str:
        """Make async API call to LLM provider.

        Args:
            prompt: The prompt to send.
            temperature: Sampling temperature.

        Returns:
            LLM response text.

        Raises:
            ParserError: If API call fails.
        """
        client = self._get_async_client()
        temp = temperature if temperature is not None else self.temperature

        try:
            if self.provider == "openai":
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temp,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content

            elif self.provider == "anthropic":
                response = await client.messages.create(
                    model=self.model,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temp,
                    max_tokens=self.max_tokens,
                )
                return response.content[0].text

            elif self.provider == "ollama":
                response = await client.generate(
                    model=self.model,
                    prompt=prompt,
                    system=SYSTEM_PROMPT,
                    temperature=temp,
                    max_tokens=self.max_tokens,
                )
                return response

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise ParserError(
                f"LLM API call failed: {e}",
                details={"provider": self.provider, "model": self.model, "error": str(e)},
            ) from e

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM response.

        Args:
            response: Raw LLM response text.

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
            "Could not extract valid JSON from LLM response",
            details={"response": response[:1000]},  # Include first 1000 chars
        )

    # Synchronous wrappers for convenience

    def parse_sync(
        self,
        input_data: str | Path,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Synchronous wrapper for parse.

        Args:
            input_data: Text description or path to text file.
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
        input_data: str | Path | bytes,
        context: SceneDefinition | None = None,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Synchronous wrapper for parse_with_context.

        Args:
            input_data: Text description or path to text file.
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
