"""Abstract base class for scene parsers.

This module defines the interface that all scene parsers must implement,
providing a consistent API for parsing various input types into scene definitions.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Union

from surg_rl.scene_definition import SceneDefinition


class BaseParser(ABC):
    """Abstract base class for scene generation parsers.

    All scene parsers (text, vision, etc.) must inherit from this class
    and implement the abstract methods.

    Attributes:
        provider: LLM/VLM provider name.
        model: Model identifier.
        api_key: API key for authentication.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the base parser.

        Args:
            provider: LLM/VLM provider ('openai' or 'anthropic').
            model: Model name/identifier.
            api_key: API key (uses environment variable if not provided).
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key

    @abstractmethod
    async def parse(
        self,
        input_data: Union[str, Path, bytes],
        **kwargs: Any,
    ) -> SceneDefinition:
        """Parse input and return a scene definition.

        Args:
            input_data: Input to parse (text, image path, or image bytes).
            **kwargs: Additional parser-specific arguments.

        Returns:
            SceneDefinition object.

        Raises:
            ValidationError: If the generated scene is invalid.
            ParserError: If parsing fails.
        """
        pass

    @abstractmethod
    async def parse_with_context(
        self,
        input_data: Union[str, Path, bytes],
        context: Optional[SceneDefinition] = None,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Parse input with optional context scene.

        This method allows incremental scene building by providing an
        existing scene as context for modifications or extensions.

        Args:
            input_data: Input to parse.
            context: Existing scene to modify/extend.
            **kwargs: Additional parser-specific arguments.

        Returns:
            SceneDefinition object (modified or new).
        """
        pass

    def validate_scene(self, scene_data: Dict[str, Any]) -> SceneDefinition:
        """Validate and create a SceneDefinition from dictionary data.

        Args:
            scene_data: Dictionary containing scene definition.

        Returns:
            Validated SceneDefinition object.

        Raises:
            ValidationError: If validation fails.
        """
        return SceneDefinition(**scene_data)

    @staticmethod
    def _resolve_input(
        input_data: Union[str, Path, bytes],
    ) -> Union[str, bytes]:
        """Resolve input data to either string (text) or bytes (image).

        Args:
            input_data: Input to resolve.

        Returns:
            String for text input, bytes for image input.

        Raises:
            FileNotFoundError: If file path doesn't exist.
            ValueError: If input type is invalid.
        """
        if isinstance(input_data, bytes):
            return input_data
        elif isinstance(input_data, Path):
            if not input_data.exists():
                raise FileNotFoundError(f"File not found: {input_data}")
            return input_data.read_text()
        elif isinstance(input_data, str):
            # Check if it's a file path
            path = Path(input_data)
            if path.exists() and path.is_file():
                return path.read_text()
            return input_data  # It's text content
        else:
            raise ValueError(f"Invalid input type: {type(input_data)}")

    def _get_context_json(
        self,
        context: Optional[SceneDefinition] = None,
    ) -> Optional[str]:
        """Convert context scene to JSON string for LLM prompts.

        Args:
            context: Optional scene context.

        Returns:
            JSON string of context or None.
        """
        if context is None:
            return None
        return context.model_dump_json(indent=2)


class ParserError(Exception):
    """Exception raised when scene parsing fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize parser error.

        Args:
            message: Error message.
            details: Additional error details.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ParseTimeoutError(ParserError):
    """Exception raised when parsing times out."""

    pass


class ParseValidationError(ParserError):
    """Exception raised when scene validation fails."""

    pass
