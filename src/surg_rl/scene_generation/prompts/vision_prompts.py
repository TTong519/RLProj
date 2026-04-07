"""Vision prompt templates for VLM-based scene generation.

This module contains prompt templates for analyzing surgical images
and generating scene definitions from visual input.
"""

from typing import Any, Dict, Optional


IMAGE_ANALYSIS_PROMPT = """Analyze this surgical image and describe the scene in detail.

Focus on:
1. Surgical instruments visible (type, position, orientation)
2. Anatomical structures (tissues, organs, vessels)
3. Robot or endoscope position
4. Lighting and camera setup
5. Any visible pathology or anatomical features

Provide a structured description that can be used to recreate this scene in simulation."""


IMAGE_TO_SCENE_PROMPT = """Analyze this surgical/medical image and generate a scene definition for simulation.

Based on the image, identify:
1. Surgical instruments and their configurations
2. Tissue/organ types and positions
3. Lighting conditions
4. Camera viewpoint
5. Any visible task objectives

{additional_instructions}

Return a valid JSON scene definition with this structure:
{schema}

Important requirements:
- Estimate realistic dimensions based on typical surgical scales
- Use appropriate tissue types (skin, muscle, organ, vessel)
- Include relevant surgical instruments
- Set up appropriate lighting and camera
- Define clear task objectives

Respond ONLY with the JSON object, no additional text."""


def get_image_analysis_prompt() -> str:
    """Get the prompt for basic image analysis.

    Returns:
        Image analysis prompt string.
    """
    return IMAGE_ANALYSIS_PROMPT


def get_image_to_scene_prompt(
    additional_instructions: Optional[str] = None,
    schema_example: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a prompt for converting image to scene.

    Args:
        additional_instructions: Optional additional instructions.
        schema_example: Optional schema example to include.

    Returns:
        Formatted prompt string.
    """
    if schema_example is None:
        schema_example = _get_visual_schema_example()

    if additional_instructions is None:
        additional_instructions = "Create a scene that accurately represents the visual content."

    return IMAGE_TO_SCENE_PROMPT.format(
        additional_instructions=additional_instructions,
        schema=schema_example,
    )


def _get_visual_schema_example() -> Dict[str, Any]:
    """Get a schema example optimized for visual analysis.

    Returns:
        Scene definition example for visual input.
    """
    return {
        "metadata": {
            "name": "Generated from image",
            "description": "Scene generated from visual analysis",
            "version": "1.0.0",
            "tags": ["vision-generated"],
        },
        "physics": {
            "gravity": [0.0, 0.0, -9.81],
            "timestep": 0.002,
        },
        "environment": {
            "name": "surgical_environment",
            "lights": [
                {
                    "name": "main_light",
                    "type": "directional",
                    "direction": [0.0, 0.0, -1.0],
                    "intensity": 1.0,
                }
            ],
            "cameras": [
                {
                    "name": "main_camera",
                    "type": "perspective",
                    "pose": {
                        "position": {"x": 0.5, "y": 0.0, "z": 0.8},
                        "orientation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "fov": 45.0,
                    "active": True,
                }
            ],
        },
        "robots": [],
        "tissues": [],
        "instruments": [],
        "task": {
            "name": "visual_task",
            "description": "Task derived from visual analysis",
            "objectives": [],
        },
        "simulator": "mujoco",
    }


# Specialized prompts for different surgical scenarios

LAPAROSCOPIC_PROMPT = """Analyze this laparoscopic surgery image.

Identify:
1. Laparoscopic instruments (graspers, scissors, needle drivers)
2. Trocar positions and angles
3. Abdominal cavity contents visible
4. Target tissue or organ
5. Current surgical task being performed

Generate a scene definition suitable for laparoscopic surgery simulation."""

ROBOTIC_SURGERY_PROMPT = """Analyze this robotic surgery image.

Identify:
1. Robot arms and end effectors visible
2. Surgical instruments attached
3. Target anatomical structure
4. Camera position (often endoscope)
5. Assistant instruments if present

Generate a scene definition for robotic surgical training."""

OPEN_SURGERY_PROMPT = """Analyze this open surgery image.

Identify:
1. Surgical instruments visible (retractors, forceps, etc.)
2. Anatomical exposure and retraction
3. Wound or incision characteristics
4. Surrounding anatomy
5. Surgical field lighting

Generate a scene definition for open surgery simulation."""


def get_specialized_prompt(scenario_type: str) -> str:
    """Get a specialized prompt for a specific surgical scenario.

    Args:
        scenario_type: Type of surgical scenario
            ('laparoscopic', 'robotic', 'open').

    Returns:
        Specialized prompt string.

    Raises:
        ValueError: If scenario type is unknown.
    """
    prompts = {
        "laparoscopic": LAPAROSCOPIC_PROMPT,
        "robotic": ROBOTIC_SURGERY_PROMPT,
        "open": OPEN_SURGERY_PROMPT,
    }

    if scenario_type not in prompts:
        raise ValueError(
            f"Unknown scenario type: {scenario_type}. "
            f"Available: {list(prompts.keys())}"
        )

    return prompts[scenario_type]
