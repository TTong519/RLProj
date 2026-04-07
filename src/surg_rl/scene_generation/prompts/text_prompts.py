"""Text prompt templates for LLM-based scene generation.

This module contains prompt templates for generating surgical robotics
training scenes from natural language descriptions.
"""

import json
from typing import Any, Dict, Optional


SYSTEM_PROMPT = """You are an expert surgical robotics simulation designer. Your task is to create detailed scene definitions for surgical training simulations in JSON format.

You must respond with valid JSON that conforms to the scene schema. Include all required fields and ensure physical realism.

Key guidelines:
1. Use realistic anatomical positions and dimensions
2. Include appropriate surgical instruments for the procedure
3. Set physics parameters appropriate for soft tissue simulation
4. Define clear task objectives and constraints
5. Ensure robot configurations are physically achievable
6. Use correct SI units (meters for distance, seconds for time)"""


SCENE_GENERATION_PROMPT = """Generate a surgical robotics training scene based on the following description:

{description}

Return a valid JSON object with this structure:
{schema}

Important requirements:
- All positions are in meters (m)
- All rotations use quaternions (w, x, y, z)
- Physics timestep should be 0.001-0.01 seconds
- Gravity is typically [0, 0, -9.81] m/s²
- Tissue stiffness should be 1000-50000 Pa for realistic behavior
- Include clear task objectives with measurable success criteria
- Define appropriate constraints (force limits, workspace bounds)

Respond ONLY with the JSON object, no additional text."""


SCENE_MODIFICATION_PROMPT = """Modify the existing surgical training scene based on the following instructions:

Current scene:
{current_scene}

Modification instructions:
{instructions}

Return the complete modified scene as a valid JSON object. Preserve all unchanged elements exactly as they are.

Respond ONLY with the JSON object, no additional text."""


def get_scene_generation_prompt(
    description: str,
    schema_example: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a prompt for scene generation.

    Args:
        description: Natural language description of the scene.
        schema_example: Optional schema example to include in prompt.

    Returns:
        Formatted prompt string.
    """
    if schema_example is None:
        schema_example = _get_minimal_schema_example()

    return SCENE_GENERATION_PROMPT.format(
        description=description,
        schema=json.dumps(schema_example, indent=2),
    )


def get_scene_modification_prompt(
    current_scene: Dict[str, Any],
    instructions: str,
) -> str:
    """Generate a prompt for scene modification.

    Args:
        current_scene: Current scene definition.
        instructions: Modification instructions.

    Returns:
        Formatted prompt string.
    """
    return SCENE_MODIFICATION_PROMPT.format(
        current_scene=json.dumps(current_scene, indent=2),
        instructions=instructions,
    )


def _get_minimal_schema_example() -> Dict[str, Any]:
    """Get a minimal schema example for prompts.

    Returns:
        Minimal scene definition example.
    """
    return {
        "metadata": {
            "name": "Scene name",
            "description": "Scene description",
            "version": "1.0.0",
        },
        "physics": {
            "gravity": [0.0, 0.0, -9.81],
            "timestep": 0.002,
        },
        "environment": {
            "name": "environment_name",
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
        "robots": [
            {
                "name": "robot_name",
                "type": "robotic_arm",
                "urdf_path": "path/to/robot.urdf",
                "base_pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "orientation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
                },
            }
        ],
        "tissues": [
            {
                "name": "tissue_name",
                "type": "skin",
                "geometry": {
                    "primitive": "box",
                    "dimensions": [0.1, 0.1, 0.01],
                },
                "physics": {
                    "stiffness": 5000.0,
                    "damping": 0.1,
                    "density": 1000.0,
                },
                "pose": {
                    "position": {"x": 0.3, "y": 0.0, "z": 0.05},
                    "orientation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
                },
            }
        ],
        "instruments": [],
        "task": {
            "name": "task_name",
            "description": "Task description",
            "objectives": [
                {
                    "name": "objective_name",
                    "description": "Objective description",
                    "success_criteria": "Success criteria description",
                    "weight": 1.0,
                }
            ],
        },
        "simulator": "mujoco",
    }
