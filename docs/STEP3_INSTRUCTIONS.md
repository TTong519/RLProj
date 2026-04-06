# Step 3: Scene Generation Module - Implementation Instructions

## Overview

Step 3 implements the scene generation module that converts natural language text or images into structured scene definitions using LLMs and VLMs.

## Current Status

- **Step 1:** COMPLETED - Project structure and dependencies
- **Step 2:** COMPLETED - Scene schema and file format
- **Step 3:** READY TO START - Scene Generation Module

## Files to Create

```
src/surg_rl/scene_generation/
├── __init__.py           # Module exports
├── base_parser.py        # Abstract base class for parsers
├── text_parser.py        # LLM-based text parser
├── vision_parser.py      # VLM-based image parser
├── scene_composer.py     # Combines parsed inputs into scenes
├── templates.py          # Scene templates for common tasks
└── prompts/              # LLM prompt templates
    ├── __init__.py
    ├── text_prompts.py   # Prompts for text-to-scene
    └── vision_prompts.py # Prompts for image-to-scene
```

## Implementation Order

### 1. Base Parser Class (`base_parser.py`)

```python
"""Abstract base class for scene parsers."""

from abc import ABC, abstractmethod
from typing import Optional, Union, List
from pathlib import Path

from surg_rl.scene_definition import SceneDefinition


class BaseParser(ABC):
    """Abstract base class for scene generation parsers."""

    @abstractmethod
    async def parse(
        self,
        input_data: Union[str, Path, bytes],
        **kwargs
    ) -> SceneDefinition:
        """Parse input and return a scene definition.
        
        Args:
            input_data: Input to parse (text, image path, or image bytes)
            **kwargs: Additional parser-specific arguments
            
        Returns:
            SceneDefinition object
        """
        pass

    @abstractmethod
    async def parse_with_context(
        self,
        input_data: Union[str, Path, bytes],
        context: Optional[SceneDefinition] = None,
        **kwargs
    ) -> SceneDefinition:
        """Parse input with optional context scene.
        
        Args:
            input_data: Input to parse
            context: Existing scene to modify/extend
            **kwargs: Additional parser-specific arguments
            
        Returns:
            SceneDefinition object (modified or new)
        """
        pass
```

### 2. Text Parser (`text_parser.py`)

```python
"""LLM-based text parser for scene generation."""

from typing import Optional, Union, List
from pathlib import Path
import json

from surg_rl.scene_definition import SceneDefinition
from surg_rl.utils.config import get_settings
from .base_parser import BaseParser


class TextParser(BaseParser):
    """Parse natural language descriptions into scene definitions."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the text parser.
        
        Args:
            provider: LLM provider ('openai' or 'anthropic')
            model: Model name to use
            api_key: API key (uses env var if not provided)
        """
        settings = get_settings()
        self.provider = provider or settings.llm_provider
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.llm_api_key
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

    async def parse(
        self,
        input_data: Union[str, Path],
        **kwargs
    ) -> SceneDefinition:
        """Parse text description into scene definition.
        
        Args:
            input_data: Text description or path to text file
            
        Returns:
            SceneDefinition object
        """
        # Get text from input
        if isinstance(input_data, Path):
            text = input_data.read_text()
        else:
            text = input_data
        
        # Generate scene using LLM
        scene_data = await self._generate_scene(text, **kwargs)
        
        # Validate and return
        return SceneDefinition(**scene_data)

    async def parse_with_context(
        self,
        input_data: Union[str, Path],
        context: Optional[SceneDefinition] = None,
        **kwargs
    ) -> SceneDefinition:
        """Parse text with optional existing scene context."""
        # Implementation with context awareness
        pass

    async def _generate_scene(
        self,
        description: str,
        **kwargs
    ) -> dict:
        """Call LLM to generate scene from description."""
        # Build prompt
        prompt = self._build_prompt(description)
        
        # Call LLM (implement based on provider)
        response = await self._call_llm(prompt)
        
        # Parse JSON response
        return self._parse_response(response)

    def _build_prompt(self, description: str) -> str:
        """Build the LLM prompt for scene generation."""
        return f"""Generate a surgical robotics training scene based on this description:

{description}

Return a JSON object with the following structure:
{{
  "metadata": {{"name": "...", "description": "...", "version": "1.0.0"}},
  "physics": {{"gravity": [0, 0, -9.81], "timestep": 0.002}},
  "robots": [...],
  "tissues": [...],
  "instruments": [...],
  "environment": {{...}},
  "task": {{...}}
}}

Important guidelines:
- Use realistic anatomical positions for surgical scenes
- Include appropriate surgical instruments for the procedure
- Set physics parameters appropriate for soft tissue simulation
- Define clear task objectives and constraints
"""

    async def _call_llm(self, prompt: str) -> str:
        """Make API call to LLM provider."""
        # Implement based on provider selection
        if self.provider == "openai":
            return await self._call_openai(prompt)
        elif self.provider == "anthropic":
            return await self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _parse_response(self, response: str) -> dict:
        """Extract JSON from LLM response."""
        # Find JSON in response
        # Handle markdown code blocks
        # Return parsed dict
        pass
```

### 3. Vision Parser (`vision_parser.py`)

```python
"""VLM-based vision parser for scene generation."""

from typing import Optional, Union
from pathlib import Path

from surg_rl.scene_definition import SceneDefinition
from surg_rl.utils.config import get_settings
from .base_parser import BaseParser


class VisionParser(BaseParser):
    """Parse images into scene definitions using Vision Language Models."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the vision parser."""
        settings = get_settings()
        self.provider = provider or settings.llm_provider
        self.model = model or settings.vlm_model
        self.api_key = api_key or settings.llm_api_key

    async def parse(
        self,
        input_data: Union[Path, bytes],
        **kwargs
    ) -> SceneDefinition:
        """Parse image into scene definition.
        
        Args:
            input_data: Path to image file or image bytes
            
        Returns:
            SceneDefinition object
        """
        # Get image data
        if isinstance(input_data, Path):
            image_bytes = input_data.read_bytes()
        else:
            image_bytes = input_data
        
        # Analyze image with VLM
        scene_data = await self._analyze_image(image_bytes, **kwargs)
        
        return SceneDefinition(**scene_data)

    async def parse_with_context(
        self,
        input_data: Union[Path, bytes],
        context: Optional[SceneDefinition] = None,
        **kwargs
    ) -> SceneDefinition:
        """Parse image with context."""
        pass

    async def _analyze_image(self, image_bytes: bytes, **kwargs) -> dict:
        """Analyze image with VLM and return scene data."""
        # Encode image (base64)
        # Call VLM API
        # Parse response
        pass
```

### 4. Scene Composer (`scene_composer.py`)

```python
"""Compose scenes from multiple inputs."""

from typing import List, Optional
from pathlib import Path

from surg_rl.scene_definition import SceneDefinition
from .base_parser import BaseParser
from .text_parser import TextParser
from .vision_parser import VisionParser


class SceneComposer:
    """Combine multiple inputs into a complete scene."""

    def __init__(self):
        self.text_parser = TextParser()
        self.vision_parser = VisionParser()

    async def compose(
        self,
        text_inputs: Optional[List[str]] = None,
        image_inputs: Optional[List[Path]] = None,
        base_scene: Optional[SceneDefinition] = None,
        **kwargs
    ) -> SceneDefinition:
        """Compose scene from multiple inputs.
        
        Args:
            text_inputs: List of text descriptions
            image_inputs: List of image paths
            base_scene: Optional starting scene
            
        Returns:
            Complete SceneDefinition
        """
        scene = base_scene or SceneDefinition()
        
        # Process text inputs
        if text_inputs:
            for text in text_inputs:
                scene = await self.text_parser.parse_with_context(
                    text, context=scene
                )
        
        # Process image inputs
        if image_inputs:
            for image in image_inputs:
                scene = await self.vision_parser.parse_with_context(
                    image, context=scene
                )
        
        return scene
```

### 5. Scene Templates (`templates.py`)

```python
"""Predefined scene templates for common surgical tasks."""

from surg_rl.scene_definition import (
    SceneDefinition, Metadata, PhysicsConfig,
    RobotConfig, TissueConfig, InstrumentConfig,
    EnvironmentConfig, TaskConfig, SimulatorType,
    TissueMeshDefinition, TissueType, RobotType
)


def get_suturing_template() -> SceneDefinition:
    """Return a template scene for suturing practice."""
    return SceneDefinition(
        metadata=Metadata(
            name="Suturing Practice Template",
            description="Basic suturing practice scene",
            tags=["suturing", "training", "basic"]
        ),
        physics=PhysicsConfig(timestep=0.002),
        robots=[
            RobotConfig(
                name="surgical_arm",
                type=RobotType.ROBOTIC_ARM,
                urdf_path="assets/robots/surgical_arm.urdf",
            )
        ],
        tissues=[
            TissueConfig(
                name="practice_pad",
                type=TissueType.SKIN,
                geometry=TissueMeshDefinition(
                    primitive="box",
                    dimensions=(0.1, 0.1, 0.01)
                ),
            )
        ],
        simulator=SimulatorType.MUJOCO,
    )


def get_dissection_template() -> SceneDefinition:
    """Return a template scene for dissection practice."""
    # Implementation
    pass


TEMPLATE_REGISTRY = {
    "suturing": get_suturing_template,
    "dissection": get_dissection_template,
    # Add more templates as needed
}


def get_template(name: str) -> SceneDefinition:
    """Get a scene template by name."""
    if name not in TEMPLATE_REGISTRY:
        raise ValueError(f"Unknown template: {name}")
    return TEMPLATE_REGISTRY[name]()
```

## Testing Strategy

### Unit Tests

Create `tests/test_scene_generation.py`:

```python
"""Tests for scene generation module."""

import pytest
from unittest.mock import AsyncMock, patch

from surg_rl.scene_generation import TextParser, VisionParser, SceneComposer
from surg_rl.scene_definition import SceneDefinition, Metadata


class TestTextParser:
    """Tests for text parser."""

    @pytest.mark.asyncio
    async def test_parse_text_description(self):
        """Test parsing text into scene."""
        parser = TextParser()
        # Mock LLM call
        # Test parsing logic
        pass

    @pytest.mark.asyncio
    async def test_parse_with_context(self):
        """Test parsing with existing scene context."""
        pass


class TestVisionParser:
    """Tests for vision parser."""

    @pytest.mark.asyncio
    async def test_parse_image(self):
        """Test parsing image into scene."""
        pass


class TestSceneComposer:
    """Tests for scene composer."""

    @pytest.mark.asyncio
    async def test_compose_multiple_inputs(self):
        """Test composing scene from multiple inputs."""
        pass
```

### Integration Tests

Test with real API calls (optional, requires API keys):

```python
@pytest.mark.integration
async def test_real_llm_call():
    """Test with actual LLM API call."""
    parser = TextParser()
    scene = await parser.parse("Create a simple suturing scene")
    assert isinstance(scene, SceneDefinition)
    assert len(scene.robots) > 0
```

## Completion Criteria

Step 3 is complete when:

- [ ] `base_parser.py` with abstract base class
- [ ] `text_parser.py` with LLM integration (OpenAI/Anthropic)
- [ ] `vision_parser.py` with VLM integration
- [ ] `scene_composer.py` for combining inputs
- [ ] `templates.py` with at least 3 templates
- [ ] Unit tests with mocked API calls
- [ ] Integration tests (optional, requires API keys)
- [ ] CLI `generate` command works with text input
- [ ] Documentation in `__init__.py`

## After Completion

Update `docs/STATUS.md`:
- Mark Step 3 as COMPLETED
- Add completion notes
- Update project structure

Update `docs/IMPLEMENTATION_PLAN.md`:
- Change status to COMPLETED
- Update current work location to Step 4

Then proceed to **Step 4: Scene Loader and Parser**.
