"""Predefined scene templates for common surgical tasks.

This module provides template scene definitions for common surgical
training scenarios, which can be used as starting points or directly
instantiated.
"""

from typing import Callable, Dict

from surg_rl.scene_definition import (
    CameraConfig,
    CameraType,
    DomainRandomizationConfig,
    EndEffectorConfig,
    EnvironmentConfig,
    GroundPlaneConfig,
    InstrumentConfig,
    InstrumentType,
    LightConfig,
    LightType,
    Metadata,
    PhysicsConfig,
    Pose,
    Position,
    RewardShaping,
    RgbColor,
    RobotConfig,
    RobotType,
    SceneDefinition,
    SimulatorType,
    TaskConfig,
    TaskObjective,
    TissueConfig,
    TissueMeshDefinition,
    TissueType,
)


def get_suturing_template() -> SceneDefinition:
    """Return a template scene for suturing practice.

    This template provides a basic suturing scene with:
    - Single robotic arm with needle driver
    - Skin tissue sample
    - Surgical needle
    - Basic suturing task objectives

    Returns:
        SceneDefinition configured for suturing practice.
    """
    return SceneDefinition(
        metadata=Metadata(
            name="Suturing Practice Template",
            description="Basic suturing practice scene with needle driver and tissue",
            version="1.0.0",
            tags=["suturing", "training", "basic", "template"],
        ),
        physics=PhysicsConfig(
            gravity=(0.0, 0.0, -9.81),
            timestep=0.002,
            solver_iterations=50,
        ),
        environment=EnvironmentConfig(
            name="training_environment",
            lights=[
                LightConfig(
                    name="overhead",
                    type=LightType.DIRECTIONAL,
                    direction=(0.0, 0.0, -1.0),
                    intensity=1.0,
                ),
            ],
            cameras=[
                CameraConfig(
                    name="main_camera",
                    type=CameraType.PERSPECTIVE,
                    pose=Pose(
                        position=Position(x=0.5, y=0.0, z=0.6),
                    ),
                    fov=45.0,
                    active=True,
                ),
            ],
            ground_plane=GroundPlaneConfig(enabled=True),
        ),
        robots=[
            RobotConfig(
                name="surgical_arm",
                type=RobotType.ROBOTIC_ARM,
                urdf_path="assets/robots/surgical_arm.urdf",
                base_pose=Pose(),
                control_mode="position",
                end_effectors=[
                    EndEffectorConfig(
                        name="needle_driver",
                        type="needle_driver",
                        max_aperture=0.02,
                        force_limit=10.0,
                    )
                ],
            )
        ],
        tissues=[
            TissueConfig(
                name="skin_pad",
                type=TissueType.SKIN,
                geometry=TissueMeshDefinition(
                    primitive="box",
                    dimensions=(0.1, 0.1, 0.01),
                ),
                pose=Pose(position=Position(x=0.3, y=0.0, z=0.05)),
                color=RgbColor(r=0.95, g=0.85, b=0.8),
            )
        ],
        instruments=[
            InstrumentConfig(
                name="surgical_needle",
                type=InstrumentType.CUSTOM,
                pose=Pose(position=Position(x=0.35, y=0.0, z=0.1)),
            )
        ],
        task=TaskConfig(
            name="suturing_task",
            description="Thread a needle through the tissue to create a suture",
            objectives=[
                TaskObjective(
                    name="needle_pickup",
                    description="Pick up the surgical needle",
                    success_criteria="Needle grasped with correct orientation",
                    weight=1.0,
                ),
                TaskObjective(
                    name="tissue_penetration",
                    description="Penetrate the tissue with the needle",
                    success_criteria="Needle passes through tissue",
                    weight=2.0,
                ),
                TaskObjective(
                    name="suture_completion",
                    description="Complete the suture",
                    success_criteria="Suture correctly placed",
                    weight=3.0,
                ),
            ],
            reward_shaping=RewardShaping(
                success_reward=100.0,
                failure_penalty=-100.0,
                time_penalty=-0.01,
            ),
            max_episode_length=1000,
        ),
        simulator=SimulatorType.MUJOCO,
    )


def get_dissection_template() -> SceneDefinition:
    """Return a template scene for tissue dissection practice.

    This template provides a dissection scene with:
    - Two laparoscopic instruments (grasper and scissors)
    - Organ tissue sample
    - Dissection task objectives

    Returns:
        SceneDefinition configured for dissection practice.
    """
    return SceneDefinition(
        metadata=Metadata(
            name="Dissection Practice Template",
            description="Tissue dissection practice with laparoscopic instruments",
            version="1.0.0",
            tags=["dissection", "laparoscopic", "training", "template"],
        ),
        physics=PhysicsConfig(
            gravity=(0.0, 0.0, -9.81),
            timestep=0.002,
        ),
        environment=EnvironmentConfig(
            name="laparoscopic_environment",
            lights=[
                LightConfig(
                    name="scope_light",
                    type=LightType.POINT,
                    position=Position(x=0.0, y=0.0, z=0.5),
                    intensity=0.8,
                ),
            ],
            cameras=[
                CameraConfig(
                    name="laparoscope",
                    type=CameraType.PERSPECTIVE,
                    pose=Pose(position=Position(x=0.0, y=0.0, z=0.3)),
                    fov=60.0,
                    active=True,
                ),
            ],
            ground_plane=GroundPlaneConfig(enabled=True),
        ),
        robots=[
            RobotConfig(
                name="left_instrument",
                type=RobotType.LAPAROSCOPIC,
                urdf_path="assets/robots/laparoscopic_instrument.urdf",
                base_pose=Pose(position=Position(x=-0.1, y=0.15, z=0.2)),
                end_effectors=[
                    EndEffectorConfig(
                        name="grasper",
                        type="grasper",
                        max_aperture=0.015,
                        force_limit=8.0,
                    )
                ],
            ),
            RobotConfig(
                name="right_instrument",
                type=RobotType.LAPAROSCOPIC,
                urdf_path="assets/robots/laparoscopic_instrument.urdf",
                base_pose=Pose(position=Position(x=0.1, y=0.15, z=0.2)),
                end_effectors=[
                    EndEffectorConfig(
                        name="scissors",
                        type="scissors",
                        max_aperture=0.01,
                        force_limit=5.0,
                    )
                ],
            ),
        ],
        tissues=[
            TissueConfig(
                name="target_tissue",
                type=TissueType.ORGAN,
                geometry=TissueMeshDefinition(
                    primitive="box",
                    dimensions=(0.08, 0.06, 0.02),
                ),
                pose=Pose(position=Position(x=0.0, y=0.0, z=0.05)),
                color=RgbColor(r=0.85, g=0.65, b=0.55),
            )
        ],
        instruments=[],
        task=TaskConfig(
            name="dissection_task",
            description="Dissect tissue layer using laparoscopic instruments",
            objectives=[
                TaskObjective(
                    name="tissue_identification",
                    description="Identify correct tissue plane",
                    success_criteria="Instrument contacts target tissue",
                    weight=1.0,
                ),
                TaskObjective(
                    name="dissection_start",
                    description="Begin dissection",
                    success_criteria="Tissue layer separated",
                    weight=2.0,
                ),
                TaskObjective(
                    name="complete_dissection",
                    description="Complete the dissection",
                    success_criteria="Target tissue fully dissected",
                    weight=3.0,
                ),
            ],
            reward_shaping=RewardShaping(
                success_reward=100.0,
                tissue_damage_penalty=-50.0,
            ),
            max_episode_length=2000,
        ),
        simulator=SimulatorType.MUJOCO,
    )


def get_manipulation_template() -> SceneDefinition:
    """Return a template scene for object manipulation practice.

    This template provides a manipulation scene with:
    - Single robotic arm with gripper
    - Various objects to manipulate
    - Pick-and-place task objectives

    Returns:
        SceneDefinition configured for manipulation practice.
    """
    return SceneDefinition(
        metadata=Metadata(
            name="Manipulation Practice Template",
            description="Object manipulation practice with robotic arm",
            version="1.0.0",
            tags=["manipulation", "pick-place", "training", "template"],
        ),
        physics=PhysicsConfig(
            gravity=(0.0, 0.0, -9.81),
            timestep=0.002,
        ),
        environment=EnvironmentConfig(
            name="manipulation_environment",
            lights=[
                LightConfig(
                    name="overhead",
                    type=LightType.DIRECTIONAL,
                    direction=(0.0, 0.0, -1.0),
                    intensity=1.0,
                ),
            ],
            cameras=[
                CameraConfig(
                    name="side_camera",
                    type=CameraType.PERSPECTIVE,
                    pose=Pose(position=Position(x=0.6, y=0.3, z=0.4)),
                    fov=50.0,
                    active=True,
                ),
            ],
            ground_plane=GroundPlaneConfig(
                enabled=True,
                size=(1.0, 1.0),
            ),
        ),
        robots=[
            RobotConfig(
                name="manipulator_arm",
                type=RobotType.ROBOTIC_ARM,
                urdf_path="assets/robots/robot_arm.urdf",
                base_pose=Pose(position=Position(x=0.0, y=0.3, z=0.0)),
                end_effectors=[
                    EndEffectorConfig(
                        name="gripper",
                        type="gripper",
                        max_aperture=0.1,
                        force_limit=50.0,
                    )
                ],
            )
        ],
        tissues=[],
        instruments=[],
        task=TaskConfig(
            name="pick_and_place_task",
            description="Pick up objects and place them in target locations",
            objectives=[
                TaskObjective(
                    name="approach",
                    description="Approach the object",
                    success_criteria="Gripper positioned above object",
                    weight=1.0,
                ),
                TaskObjective(
                    name="grasp",
                    description="Grasp the object",
                    success_criteria="Object successfully grasped",
                    weight=2.0,
                ),
                TaskObjective(
                    name="transport",
                    description="Transport object to target",
                    success_criteria="Object moved to target location",
                    weight=2.0,
                ),
                TaskObjective(
                    name="place",
                    description="Place object correctly",
                    success_criteria="Object placed in target zone",
                    weight=3.0,
                ),
            ],
            reward_shaping=RewardShaping(
                success_reward=100.0,
                distance_reward_scale=1.0,
            ),
            max_episode_length=500,
        ),
        simulator=SimulatorType.MUJOCO,
    )


# Template registry
TEMPLATE_REGISTRY: Dict[str, Callable[[], SceneDefinition]] = {
    "suturing": get_suturing_template,
    "dissection": get_dissection_template,
    "manipulation": get_manipulation_template,
}


def get_template(name: str) -> SceneDefinition:
    """Get a scene template by name.

    Args:
        name: Template name ('suturing', 'dissection', 'manipulation').

    Returns:
        SceneDefinition from the template.

    Raises:
        ValueError: If template name is unknown.
    """
    name_lower = name.lower()

    if name_lower not in TEMPLATE_REGISTRY:
        available = list(TEMPLATE_REGISTRY.keys())
        raise ValueError(
            f"Unknown template: '{name}'. Available templates: {available}"
        )

    # Return a copy to prevent modification of template
    template_func = TEMPLATE_REGISTRY[name_lower]
    return template_func()


def list_templates() -> Dict[str, str]:
    """List all available templates with their descriptions.

    Returns:
        Dictionary mapping template names to descriptions.
    """
    return {
        name: func().metadata.description
        for name, func in TEMPLATE_REGISTRY.items()
    }
