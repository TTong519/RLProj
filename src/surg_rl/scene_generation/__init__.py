"""Scene generation module - Convert text/images to scene definitions.

This module provides parsers and generators for creating surgical robotics
training scenes from natural language descriptions and images using LLMs/VLMs.
"""

from .base_parser import BaseParser
from .text_parser import TextParser
from .vision_parser import VisionParser
from .scene_composer import SceneComposer
from .templates import (
    get_template,
    get_suturing_template,
    get_dissection_template,
    get_manipulation_template,
    TEMPLATE_REGISTRY,
)
from .templates import list_templates

__all__ = [
    # Parsers
    "BaseParser",
    "TextParser",
    "VisionParser",
    # Composer
    "SceneComposer",
    # Templates
    "get_template",
    "get_suturing_template",
    "get_dissection_template",
    "get_manipulation_template",
    "TEMPLATE_REGISTRY",
    "list_templates",
]
