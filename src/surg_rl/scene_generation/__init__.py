"""Scene generation module - Convert text/images to scene definitions.

This module provides parsers and generators for creating surgical robotics
training scenes from natural language descriptions and images using LLMs/VLMs.
"""

from .base_parser import BaseParser
from .scene_composer import SceneComposer
from .templates import (
    TEMPLATE_REGISTRY,
    get_dissection_template,
    get_manipulation_template,
    get_suturing_template,
    get_template,
    list_templates,
)
from .text_parser import TextParser
from .vision_parser import VisionParser

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
