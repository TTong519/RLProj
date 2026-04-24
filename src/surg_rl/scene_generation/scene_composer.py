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
        inputs: Optional[List[Union[str, Path, bytes]]] = None,
        text_inputs: Optional[List[Union[str, Path]]] = None,
        image_inputs: Optional[List[Union[str, Path, bytes]]] = None,
        base_scene: Optional[SceneDefinition] = None,
        merge_strategy: str = "sequential",
        **kwargs: Any,
    ) -> SceneDefinition:
        """Compose scene from multiple inputs.

        Args:
            inputs: Unified list of text strings and image paths/bytes to
                process in order (sequential mode only).
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
        if inputs is not None:
            total = len(inputs)
        else:
            total = len(text_inputs or []) + len(image_inputs or [])
        logger.info(
            f"Composing scene with {total} inputs"
        )

        if merge_strategy == "sequential":
            return await self._compose_sequential(
                inputs=inputs,
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
        inputs: Optional[List[Union[str, Path, bytes]]] = None,
        text_inputs: Optional[List[Union[str, Path]]] = None,
        image_inputs: Optional[List[Union[str, Path, bytes]]] = None,
        base_scene: Optional[SceneDefinition] = None,
        **kwargs: Any,
    ) -> SceneDefinition:
        """Compose scene sequentially, each input modifying previous.

        Args:
            inputs: Unified list of inputs to process in order.
            text_inputs: Text inputs to process (legacy, used when inputs is None).
            image_inputs: Image inputs to process (legacy, used when inputs is None).
            base_scene: Starting scene.
            **kwargs: Additional arguments.

        Returns:
            Final SceneDefinition.
        """
        scene = base_scene

        if inputs is not None:
            for inp in inputs:
                if isinstance(inp, str):
                    logger.debug("Processing text input")
                    scene = await self.text_parser.parse_with_context(
                        input_data=inp,
                        context=scene,
                        **kwargs,
                    )
                else:
                    logger.debug("Processing image input")
                    scene = await self.vision_parser.parse_with_context(
                        input_data=inp,
                        context=scene,
                        **kwargs,
                    )
        else:
            # Process text inputs sequentially
            if text_inputs:
                for text in text_inputs:
                    logger.debug("Processing text input")
                    scene = await self.text_parser.parse_with_context(
                        input_data=text,
                        context=scene,
                        **kwargs,
                    )

            # Process image inputs sequentially
            if image_inputs:
                for image in image_inputs:
                    logger.debug("Processing image input")
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

            # Separate successes from exceptions
            scenes: list[SceneDefinition] = []
            exceptions: list[BaseException] = []
            for r in results:
                if isinstance(r, SceneDefinition):
                    scenes.append(r)
                elif isinstance(r, BaseException):
                    exceptions.append(r)

            if exceptions:
                if not scenes:
                    # All tasks failed — raise composite error
                    messages = "; ".join(
                        f"{type(e).__name__}: {e}" for e in exceptions
                    )
                    raise ParserError(
                        f"All parallel composition tasks failed ({len(exceptions)}): {messages}",
                        details={
                            "task_count": len(tasks),
                            "failures": [
                                {"type": type(e).__name__, "message": str(e)}
                                for e in exceptions
                            ],
                        },
                    )
                # Partial failure — warn but continue with successful results
                for e in exceptions:
                    logger.warning(
                        "Parallel composition task failed: %s: %s",
                        type(e).__name__,
                        e,
                    )

            if not scenes:
                # Should only reach here if tasks was empty (handled above),
                # but keep as a safety guard.
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
        scene2_data = scene2.model_dump()

        # Merge metadata (scene2 takes precedence)
        merged_data["metadata"] = {
            **merged_data.get("metadata", {}),
            **scene2_data.get("metadata", {}),
        }

        # Merge physics configs safely
        if scene1.physics is not None and scene2.physics is not None:
            merged_physics = merged_data.get("physics", {})
            scene2_physics = scene2_data.get("physics", {})
            merged_data["physics"] = {**merged_physics, **scene2_physics}
            # Concatenate materials lists instead of overwriting
            if merged_physics.get("materials") and scene2_physics.get("materials"):
                merged_data["physics"]["materials"] = (
                    list(merged_physics["materials"]) + list(scene2_physics["materials"])
                )
        elif scene2.physics is not None:
            merged_data["physics"] = scene2_data["physics"]
        elif scene1.physics is not None:
            merged_data["physics"] = merged_data.get("physics")

        # Concatenate lists
        for field in ["robots", "tissues", "instruments"]:
            merged_data[field] = merged_data.get(field, []) + scene2_data.get(field, [])

        # Merge environment (scene2's cameras/lights added)
        if "environment" in scene2_data and scene2_data["environment"] is not None:
            env1 = merged_data.get("environment") or {}
            env2 = scene2_data["environment"]

            # Start with scene1's environment, then overlay scene2's fields
            merged_env = {**env1, **env2}

            # Concatenate cameras and lights lists instead of overwriting
            merged_env["cameras"] = (env1.get("cameras") or []) + (env2.get("cameras") or [])
            merged_env["lights"] = (env1.get("lights") or []) + (env2.get("lights") or [])

            merged_data["environment"] = merged_env

        # Use scene2's task if defined
        if scene2.task is not None:
            merged_data["task"] = scene2_data.get("task")

        # Merge domain randomization (only if scene2 explicitly set it)
        if "domain_randomization" in scene2.model_fields_set:
            merged_data["domain_randomization"] = scene2_data.get(
                "domain_randomization", {}
            )

        # Use scene2's simulator only if explicitly set
        if "simulator" in scene2.model_fields_set:
            merged_data["simulator"] = scene2_data.get("simulator", "mujoco")

        # Merge custom parameters
        merged_data["custom"] = {
            **merged_data.get("custom", {}),
            **scene2_data.get("custom", {}),
        }

        # Remove None-valued keys that have default factories to avoid
        # Pydantic validation errors
        if merged_data.get("physics") is None:
            merged_data.pop("physics", None)
        if merged_data.get("environment") is None:
            merged_data.pop("environment", None)
        if merged_data.get("task") is None:
            merged_data.pop("task", None)

        return SceneDefinition(**merged_data)

    # Synchronous wrapper

    def compose_sync(
        self,
        inputs: Optional[List[Union[str, Path, bytes]]] = None,
        text_inputs: Optional[List[Union[str, Path]]] = None,
        image_inputs: Optional[List[Union[str, Path, bytes]]] = None,
        base_scene: Optional[SceneDefinition] = None,
        merge_strategy: str = "sequential",
        **kwargs: Any,
    ) -> SceneDefinition:
        """Synchronous wrapper for compose.

        Args:
            inputs: Unified list of text strings and image paths/bytes to
                process in order (sequential mode only).
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
                inputs=inputs,
                text_inputs=text_inputs,
                image_inputs=image_inputs,
                base_scene=base_scene,
                merge_strategy=merge_strategy,
                **kwargs,
            )
        )
