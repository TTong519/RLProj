"""Scene composer for combining multiple inputs.

This module provides functionality to compose scenes from multiple
text and image inputs, allowing incremental scene building.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from surg_rl.scene_definition import SceneDefinition
from surg_rl.utils.logging import get_logger

from .base_parser import ParserError
from .text_parser import TextParser
from .vision_parser import VisionParser

logger = get_logger(__name__)


class SceneComposer:
    """Compose scenes from multiple inputs.

    This class combines text and image inputs to create complete
    scene definitions. It supports incremental building and merging
    of multiple sources.

    Attributes:
        text_parser: TextParser instance for text inputs.
        vision_parser: VisionParser instance for image inputs.
    """

    def __init__(
        self,
        text_parser: Optional[TextParser] = None,
        vision_parser: Optional[VisionParser] = None,
    ):
        """Initialize the scene composer.

        Args:
            text_parser: Optional TextParser instance.
                Created with defaults if not provided.
            vision_parser: Optional VisionParser instance.
                Created with defaults if not provided.
        """
        self.text_parser = text_parser or TextParser()
        self.vision_parser = vision_parser or VisionParser()

    async def compose(
        self,
        text_inputs: Optional[List[Union[str, Path]]] = None,
        image_inputs: Optional[List[Union[str, Path, bytes]]] = None,
        base_scene: Optional[SceneDefinition] = None,
        merge_strategy: str = "sequential",
        **kwargs: Any,
    ) -> SceneDefinition:
        """Compose scene from multiple inputs.

        Args:
            text_inputs: List of text descriptions or text file paths.
            image_inputs: List of image paths or image bytes.
            base_scene: Optional starting scene to build upon.
            merge_strategy: Strategy for merging inputs:
                - 'sequential': Process inputs in order, each modifying previous
                - 'parallel': Process all inputs independently, then merge
            **kwargs: Additional arguments passed to parsers.

        Returns:
            Complete SceneDefinition.

        Raises:
            ParserError: If any parsing fails.
        """
        logger.info(
            f"Composing scene with {len(text_inputs or [])} text inputs, "
            f"{len(image_inputs or [])} image inputs"
        )

        if merge_strategy == "sequential":
            return await self._compose_sequential(
                text_inputs=text_inputs,
                image_inputs=image_inputs,
                base_scene=base_scene,
                **kwargs,
            )
        elif merge_strategy == "parallel":
            return await self._compose_parallel(
                text_inputs=text_inputs,
                image_inputs=image_inputs,
                base_scene=base_scene,
                **kwargs,
            )
        else:
            raise ValueError(
                f"Unknown merge strategy: {merge_strategy}. "
                "Supported: 'sequential', 'parallel'"
            )

    async def _compose_sequential(
        self,
        text_inputs: Optional[List[Union[str, Path]]],
        image_inputs: Optional[List[Union[str, Path, bytes]]],
        base_scene: Optional[SceneDefinition],
        **kwargs: Any,
    ) -> SceneDefinition:
        """Compose scene sequentially, each input modifying previous.

        Args:
            text_inputs: Text inputs to process.
            image_inputs: Image inputs to process.
            base_scene: Starting scene.
            **kwargs: Additional arguments.

        Returns:
            Final SceneDefinition.
        """
        scene = base_scene

        # Process text inputs sequentially
        if text_inputs:
            for text in text_inputs:
                logger.debug(f"Processing text input")
                scene = await self.text_parser.parse_with_context(
                    input_data=text,
                    context=scene,
                    **kwargs,
                )

        # Process image inputs sequentially
        if image_inputs:
            for image in image_inputs:
                logger.debug(f"Processing image input")
                scene = await self.vision_parser.parse_with_context(
                    input_data=image,
                    context=scene,
                    **kwargs,
                )

        # If no inputs, return empty or base scene
        if scene is None:
            scene = SceneDefinition()

        logger.info(f"Composition complete: {scene.metadata.name}")
        return scene

    async def _compose_parallel(
        self,
        text_inputs: Optional[List[Union[str, Path]]],
        image_inputs: Optional[List[Union[str, Path, bytes]]],
        base_scene: Optional[SceneDefinition],
        **kwargs: Any,
    ) -> SceneDefinition:
        """Compose scene in parallel, merging all results.

        Args:
            text_inputs: Text inputs to process.
            image_inputs: Image inputs to process.
            base_scene: Starting scene.
            **kwargs: Additional arguments.

        Returns:
            Merged SceneDefinition.
        """
        tasks = []

        # Create tasks for text inputs
        if text_inputs:
            for text in text_inputs:
                tasks.append(self.text_parser.parse(text, **kwargs))

        # Create tasks for image inputs
        if image_inputs:
            for image in image_inputs:
                tasks.append(self.vision_parser.parse(image, **kwargs))

        # Process base scene as initial context
        if base_scene and not tasks:
            return base_scene

        # Run all tasks in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions
            scenes = [r for r in results if isinstance(r, SceneDefinition)]

            if not scenes:
                # All failed, return base or empty
                return base_scene or SceneDefinition()

            # Merge all scenes
            return self._merge_scenes(scenes, base_scene)

        return base_scene or SceneDefinition()

    def _merge_scenes(
        self,
        scenes: List[SceneDefinition],
        base_scene: Optional[SceneDefinition] = None,
    ) -> SceneDefinition:
        """Merge multiple scene definitions.

        Args:
            scenes: List of scenes to merge.
            base_scene: Optional base scene to merge into.

        Returns:
            Merged SceneDefinition.
        """
        if not scenes:
            return base_scene or SceneDefinition()

        if len(scenes) == 1:
            if base_scene:
                return self._merge_two_scenes(base_scene, scenes[0])
            return scenes[0]

        # Start with base scene or first scene
        merged = base_scene or scenes[0]

        # Merge remaining scenes
        for scene in scenes if base_scene else scenes[1:]:
            merged = self._merge_two_scenes(merged, scene)

        return merged

    def _merge_two_scenes(
        self,
        scene1: SceneDefinition,
        scene2: SceneDefinition,
    ) -> SceneDefinition:
        """Merge two scene definitions.

        Scene2's values take precedence for single-value fields.
        Lists are concatenated.

        Args:
            scene1: First scene.
            scene2: Second scene.

        Returns:
            Merged scene.
        """
        merged_data = scene1.model_dump()

        # Merge metadata (scene2 takes precedence)
        merged_data["metadata"] = {
            **merged_data.get("metadata", {}),
            **scene2.model_dump().get("metadata", {}),
        }

        # Use scene2's physics if different
        scene2_data = scene2.model_dump()
        if scene2.physics.timestep != scene1.physics.timestep:
            merged_data["physics"] = scene2_data["physics"]

        # Concatenate lists
        for field in ["robots", "tissues", "instruments"]:
            merged_data[field] = merged_data.get(field, []) + scene2_data.get(field, [])

        # Merge environment (scene2's cameras/lights added)
        if "environment" in scene2_data:
            env1 = merged_data.get("environment", {})
            env2 = scene2_data["environment"]

            # Merge cameras and lights
            merged_env = {
                **env1,
                "cameras": env1.get("cameras", []) + env2.get("cameras", []),
                "lights": env1.get("lights", []) + env2.get("lights", []),
            }

            # Use scene2's other environment settings
            for key in ["name", "background_color", "ground_plane", "surgical_table"]:
                if key in env2:
                    merged_env[key] = env2[key]

            merged_data["environment"] = merged_env

        # Use scene2's task if defined
        if scene2.task:
            merged_data["task"] = scene2_data.get("task")

        # Merge domain randomization
        if scene2.domain_randomization:
            merged_data["domain_randomization"] = scene2_data.get(
                "domain_randomization", {}
            )

        # Use scene2's simulator
        merged_data["simulator"] = scene2_data.get("simulator", "mujoco")

        # Merge custom parameters
        merged_data["custom"] = {
            **merged_data.get("custom", {}),
            **scene2_data.get("custom", {}),
        }

        return SceneDefinition(**merged_data)

    # Synchronous wrapper

    def compose_sync(
        self,
        text_inputs: Optional[List[Union[str, Path]]] = None,
        image_inputs: Optional[List[Union[str, Path, bytes]]] = None,
        base_scene: Optional[SceneDefinition] = None,
        merge_strategy: str = "sequential",
        **kwargs: Any,
    ) -> SceneDefinition:
        """Synchronous wrapper for compose.

        Args:
            text_inputs: List of text descriptions or text file paths.
            image_inputs: List of image paths or image bytes.
            base_scene: Optional starting scene to build upon.
            merge_strategy: Strategy for merging inputs.
            **kwargs: Additional arguments passed to parsers.

        Returns:
            Complete SceneDefinition.
        """
        return asyncio.run(
            self.compose(
                text_inputs=text_inputs,
                image_inputs=image_inputs,
                base_scene=base_scene,
                merge_strategy=merge_strategy,
                **kwargs,
            )
        )
