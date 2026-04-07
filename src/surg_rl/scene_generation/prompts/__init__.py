"""Prompt templates for LLM/VLM scene generation."""

from .text_prompts import (
    SCENE_GENERATION_PROMPT,
    SCENE_MODIFICATION_PROMPT,
    SYSTEM_PROMPT,
    get_scene_generation_prompt,
    get_scene_modification_prompt,
)
from .vision_prompts import (
    IMAGE_ANALYSIS_PROMPT,
    IMAGE_TO_SCENE_PROMPT,
    get_image_analysis_prompt,
    get_image_to_scene_prompt,
)

__all__ = [
    # Text prompts
    "SCENE_GENERATION_PROMPT",
    "SCENE_MODIFICATION_PROMPT",
    "SYSTEM_PROMPT",
    "get_scene_generation_prompt",
    "get_scene_modification_prompt",
    # Vision prompts
    "IMAGE_ANALYSIS_PROMPT",
    "IMAGE_TO_SCENE_PROMPT",
    "get_image_analysis_prompt",
    "get_image_to_scene_prompt",
]
