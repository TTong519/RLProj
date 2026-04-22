"""Parameter randomization for domain randomization.

This module provides randomization utilities for physics, visual, and
dynamics parameters in surgical robotics simulations.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    PhysicsRandomization,
    VisualRandomization,
    DynamicsRandomization,
)
from .base_controller import (
    BaseController,
    ControllerConfig,
    ParameterBounds,
    ParameterSnapshot,
)


@dataclass
class PhysicsParameterBounds:
    """Default bounds for physics parameters."""
    mass_ratio: Tuple[float, float] = (0.8, 1.2)
    friction: Tuple[float, float] = (0.3, 0.8)
    damping: Tuple[float, float] = (0.05, 0.3)
    stiffness: Tuple[float, float] = (500.0, 2000.0)
    gravity_x: Tuple[float, float] = (-0.5, 0.5)
    gravity_y: Tuple[float, float] = (-0.5, 0.5)
    gravity_z: Tuple[float, float] = (-10.0, -9.0)


@dataclass
class VisualParameterBounds:
    """Default bounds for visual parameters."""
    color_variation: Tuple[float, float] = (-0.1, 0.1)
    lighting_intensity: Tuple[float, float] = (0.5, 1.5)
    camera_position_noise: Tuple[float, float] = (-0.01, 0.01)
    camera_orientation_noise: Tuple[float, float] = (-0.01, 0.01)


@dataclass
class DynamicsParameterBounds:
    """Default bounds for dynamics parameters."""
    joint_noise: Tuple[float, float] = (-0.01, 0.01)
    action_noise: Tuple[float, float] = (-0.05, 0.05)
    delay_range: Tuple[float, float] = (0.0, 0.05)


class ParameterRandomizer(BaseController):
    """Domain randomization controller for physics, visual, and dynamics parameters.
    
    This controller randomizes environment parameters at the start of each episode
    or during simulation steps, supporting domain randomization for RL training.
    
    The randomization is configured via DomainRandomizationConfig from the
    scene definition, allowing per-scene customization.
    """

    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        domain_config: Optional[DomainRandomizationConfig] = None,
        physics_bounds: Optional[PhysicsParameterBounds] = None,
        visual_bounds: Optional[VisualParameterBounds] = None,
        dynamics_bounds: Optional[DynamicsParameterBounds] = None,
    ):
        """Initialize the parameter randomizer.
        
        Args:
            config: Controller configuration.
            domain_config: Domain randomization config from scene.
            physics_bounds: Bounds for physics parameters.
            visual_bounds: Bounds for visual parameters.
            dynamics_bounds: Bounds for dynamics parameters.
        """
        super().__init__(config=config)
        self.domain_config = domain_config or DomainRandomizationConfig()
        self.physics_bounds = physics_bounds or PhysicsParameterBounds()
        self.visual_bounds = visual_bounds or VisualParameterBounds()
        self.dynamics_bounds = dynamics_bounds or DynamicsParameterBounds()
        
        # Override seed from domain config if set
        if self.domain_config.seed is not None:
            self._rng = np.random.default_rng(self.domain_config.seed)
        
        # Build parameter bounds for sampling
        self._build_parameter_bounds()

    def _build_parameter_bounds(self) -> None:
        """Build parameter bounds from configuration."""
        self.parameter_bounds = {}
        
        # Physics parameters
        phys = self.domain_config.physics
        if phys.enabled:
            if phys.mass_range is not None:
                self.parameter_bounds["mass_ratio"] = ParameterBounds(
                    name="mass_ratio",
                    min_value=phys.mass_range[0],
                    max_value=phys.mass_range[1],
                    default=1.0,
                )
            if phys.friction_range is not None:
                self.parameter_bounds["friction"] = ParameterBounds(
                    name="friction",
                    min_value=phys.friction_range[0],
                    max_value=phys.friction_range[1],
                    default=0.5,
                )
            if phys.damping_range is not None:
                self.parameter_bounds["damping"] = ParameterBounds(
                    name="damping",
                    min_value=phys.damping_range[0],
                    max_value=phys.damping_range[1],
                    default=0.1,
                )
            if phys.stiffness_range is not None:
                self.parameter_bounds["stiffness"] = ParameterBounds(
                    name="stiffness",
                    min_value=phys.stiffness_range[0],
                    max_value=phys.stiffness_range[1],
                    default=1000.0,
                    distribution="log_uniform",
                )
        
        # Visual parameters
        vis = self.domain_config.visual
        if vis.enabled:
            if vis.color_range is not None:
                self.parameter_bounds["color_variation"] = ParameterBounds(
                    name="color_variation",
                    min_value=vis.color_range[0],
                    max_value=vis.color_range[1],
                    default=0.0,
                )
            if vis.lighting_variation is not None:
                self.parameter_bounds["lighting_intensity"] = ParameterBounds(
                    name="lighting_intensity",
                    min_value=vis.lighting_variation[0],
                    max_value=vis.lighting_variation[1],
                    default=1.0,
                )
        
        # Dynamics parameters
        dyn = self.domain_config.dynamics
        if dyn.enabled:
            if dyn.joint_noise is not None:
                self.parameter_bounds["joint_noise"] = ParameterBounds(
                    name="joint_noise",
                    min_value=dyn.joint_noise[0],
                    max_value=dyn.joint_noise[1],
                    default=0.0,
                )
            if dyn.action_noise is not None:
                self.parameter_bounds["action_noise"] = ParameterBounds(
                    name="action_noise",
                    min_value=dyn.action_noise[0],
                    max_value=dyn.action_noise[1],
                    default=0.0,
                )
            if dyn.delay_range is not None:
                self.parameter_bounds["delay"] = ParameterBounds(
                    name="delay",
                    min_value=dyn.delay_range[0],
                    max_value=dyn.delay_range[1],
                    default=0.0,
                )

    def sample_parameters(self) -> ParameterSnapshot:
        """Sample randomized parameters.
        
        Returns:
            Snapshot of randomized parameters.
        """
        physics_params = {}
        visual_params = {}
        dynamics_params = {}
        
        # Sample physics parameters
        phys = self.domain_config.physics
        if phys.enabled:
            if "mass_ratio" in self.parameter_bounds:
                physics_params["mass_ratio"] = self._sample_value(
                    self.parameter_bounds["mass_ratio"]
                )
            if "friction" in self.parameter_bounds:
                physics_params["friction"] = self._sample_value(
                    self.parameter_bounds["friction"]
                )
            if "damping" in self.parameter_bounds:
                physics_params["damping"] = self._sample_value(
                    self.parameter_bounds["damping"]
                )
            if "stiffness" in self.parameter_bounds:
                physics_params["stiffness"] = self._sample_value(
                    self.parameter_bounds["stiffness"]
                )
            
            # Handle gravity randomization
            if phys.gravity_range:
                physics_params["gravity_x"] = self._rng.uniform(
                    phys.gravity_range[0][0],
                    phys.gravity_range[0][1],
                )
                physics_params["gravity_y"] = self._rng.uniform(
                    phys.gravity_range[1][0],
                    phys.gravity_range[1][1],
                )
                physics_params["gravity_z"] = self._rng.uniform(
                    phys.gravity_range[2][0],
                    phys.gravity_range[2][1],
                )
        
        # Sample visual parameters
        vis = self.domain_config.visual
        if vis.enabled:
            if "color_variation" in self.parameter_bounds:
                visual_params["color_r_offset"] = self._rng.uniform(
                    vis.color_range[0], vis.color_range[1]
                )
                visual_params["color_g_offset"] = self._rng.uniform(
                    vis.color_range[0], vis.color_range[1]
                )
                visual_params["color_b_offset"] = self._rng.uniform(
                    vis.color_range[0], vis.color_range[1]
                )
            
            if "lighting_intensity" in self.parameter_bounds:
                visual_params["lighting_intensity"] = self._sample_value(
                    self.parameter_bounds["lighting_intensity"]
                )
            
            if vis.camera_pose_noise:
                visual_params["camera_pos_noise"] = self._rng.uniform(
                    -vis.camera_pose_noise[0], vis.camera_pose_noise[0]
                )
                visual_params["camera_rot_noise"] = self._rng.uniform(
                    -vis.camera_pose_noise[1], vis.camera_pose_noise[1]
                )
        
        # Sample dynamics parameters
        dyn = self.domain_config.dynamics
        if dyn.enabled:
            if "joint_noise" in self.parameter_bounds:
                dynamics_params["joint_noise"] = self._sample_value(
                    self.parameter_bounds["joint_noise"]
                )
            if "action_noise" in self.parameter_bounds:
                dynamics_params["action_noise"] = self._sample_value(
                    self.parameter_bounds["action_noise"]
                )
            if "delay" in self.parameter_bounds:
                dynamics_params["delay"] = self._sample_value(
                    self.parameter_bounds["delay"]
                )
        
        return ParameterSnapshot(
            physics=physics_params,
            visual=visual_params,
            dynamics=dynamics_params,
            episode=self._episode,
            step=self._step,
        )

    def apply_parameters(
        self,
        snapshot: ParameterSnapshot,
        simulator: Any,
    ) -> bool:
        """Apply randomized parameters to the simulator.

        This method applies physics, visual, and dynamics parameters to the simulator.

        Args:
            snapshot: Parameters to apply.
            simulator: Simulator instance (MuJoCo or PyBullet).

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Apply physics parameters based on simulator type
            sim_type = type(simulator).__name__

            # Apply gravity changes
            if any(k.startswith("gravity_") for k in snapshot.physics):
                gravity = [
                    snapshot.physics.get("gravity_x", 0.0),
                    snapshot.physics.get("gravity_y", 0.0),
                    snapshot.physics.get("gravity_z", -9.81),
                ]
                self._apply_gravity(simulator, gravity)

            # Apply mass scaling
            if "mass_ratio" in snapshot.physics:
                self._apply_mass_scaling(
                    simulator, snapshot.physics["mass_ratio"]
                )

            # Apply friction
            if "friction" in snapshot.physics:
                self._apply_friction(
                    simulator, snapshot.physics["friction"]
                )

            # Apply damping
            if "damping" in snapshot.physics:
                self._apply_damping(
                    simulator, snapshot.physics["damping"]
                )

            # Apply stiffness (soft body parameters)
            if "stiffness" in snapshot.physics:
                self._apply_stiffness(
                    simulator, snapshot.physics["stiffness"]
                )

            # Apply visual parameters
            if snapshot.visual:
                self._apply_visual_parameters(simulator, snapshot.visual)

            return True

        except Exception as e:
            # Log error and return False
            import warnings
            warnings.warn(f"Failed to apply parameters: {e}")
            return False

    def _apply_gravity(self, simulator: Any, gravity: List[float]) -> None:
        """Apply gravity vector to simulator.
        
        Args:
            simulator: Simulator instance.
            gravity: Gravity vector [x, y, z].
        """
        try:
            # MuJoCo
            if hasattr(simulator, "_model") and simulator._model is not None and hasattr(simulator._model, "opt"):
                simulator._model.opt.gravity[:] = gravity
            # PyBullet
            elif hasattr(simulator, "_physics_client"):
                import pybullet as p
                p.setGravity(gravity[0], gravity[1], gravity[2], 
                            physicsClientId=simulator._physics_client)
        except Exception:
            pass

    def _apply_mass_scaling(self, simulator: Any, ratio: float) -> None:
        """Apply mass scaling to bodies.

        Args:
            simulator: Simulator instance.
            ratio: Mass ratio multiplier.
        """
        try:
            # MuJoCo
            if hasattr(simulator, "_model") and simulator._model is not None:
                model = simulator._model
                if hasattr(model, "body_mass") and model.body_mass is not None:
                    model.body_mass[:] = model.body_mass * ratio
            # PyBullet
            elif hasattr(simulator, "_physics_client") and hasattr(simulator, "_body_ids"):
                import pybullet as p
                for body_id in simulator._body_ids.values():
                    dynamics = p.getDynamicsInfo(body_id, -1, physicsClientId=simulator._physics_client)
                    new_mass = dynamics[0] * ratio
                    p.changeDynamics(
                        body_id, -1, mass=new_mass,
                        physicsClientId=simulator._physics_client,
                    )
        except Exception:
            pass

    def _apply_friction(self, simulator: Any, friction: float) -> None:
        """Apply friction coefficient.

        Args:
            simulator: Simulator instance.
            friction: Friction coefficient.
        """
        try:
            # MuJoCo
            if hasattr(simulator, "_model") and simulator._model is not None:
                model = simulator._model
                if hasattr(model, "geom_friction") and model.geom_friction is not None:
                    # Set sliding friction (first column)
                    model.geom_friction[:, 0] = friction
            # PyBullet
            elif hasattr(simulator, "_physics_client") and hasattr(simulator, "_body_ids"):
                import pybullet as p
                for body_id in simulator._body_ids.values():
                    p.changeDynamics(
                        body_id, -1, lateralFriction=friction,
                        physicsClientId=simulator._physics_client,
                    )
        except Exception:
            pass

    def _apply_damping(self, simulator: Any, damping: float) -> None:
        """Apply damping coefficient.

        Args:
            simulator: Simulator instance.
            damping: Damping coefficient.
        """
        try:
            # MuJoCo
            if hasattr(simulator, "_model") and simulator._model is not None:
                model = simulator._model
                if hasattr(model, "dof_damping") and model.dof_damping is not None:
                    model.dof_damping[:] = damping
            # PyBullet
            elif hasattr(simulator, "_physics_client") and hasattr(simulator, "_body_ids"):
                import pybullet as p
                for body_id in simulator._body_ids.values():
                    p.changeDynamics(
                        body_id, -1,
                        linearDamping=damping,
                        angularDamping=damping,
                        physicsClientId=simulator._physics_client,
                    )
        except Exception:
            pass

    def _apply_stiffness(self, simulator: Any, stiffness: float) -> None:
        """Apply stiffness for soft bodies.

        Args:
            simulator: Simulator instance.
            stiffness: Stiffness value.
        """
        try:
            # MuJoCo: modify tendon stiffness or actuator gains if present
            if hasattr(simulator, "_model") and simulator._model is not None:
                model = simulator._model
                if hasattr(model, "tendon_stiffness") and model.tendon_stiffness is not None:
                    model.tendon_stiffness[:] = stiffness
                if hasattr(model, "actuator_gainprm") and model.actuator_gainprm is not None:
                    model.actuator_gainprm[:, 0] = stiffness
            # PyBullet: no direct soft body stiffness control at runtime
        except Exception:
            pass

    def _apply_visual_parameters(
        self, simulator: Any, params: Dict[str, float]
    ) -> None:
        """Apply visual randomization parameters to simulator.

        Args:
            simulator: Simulator instance.
            params: Visual parameter dictionary.
        """
        try:
            r_offset = params.get("color_r_offset", 0.0)
            g_offset = params.get("color_g_offset", 0.0)
            b_offset = params.get("color_b_offset", 0.0)
            lighting = params.get("lighting_intensity")

            # MuJoCo
            if hasattr(simulator, "_model") and simulator._model is not None:
                model = simulator._model
                if hasattr(model, "geom_rgba") and model.geom_rgba is not None:
                    model.geom_rgba[:, 0] = np.clip(
                        model.geom_rgba[:, 0] + r_offset, 0.0, 1.0
                    )
                    model.geom_rgba[:, 1] = np.clip(
                        model.geom_rgba[:, 1] + g_offset, 0.0, 1.0
                    )
                    model.geom_rgba[:, 2] = np.clip(
                        model.geom_rgba[:, 2] + b_offset, 0.0, 1.0
                    )
                if lighting is not None and hasattr(model, "vis"):
                    # Scale headlight intensity
                    if hasattr(model.vis, "headlight"):
                        model.vis.headlight[:] = [
                            0.1 * lighting, 0.15 * lighting, 0.3 * lighting
                        ]

            # PyBullet
            elif hasattr(simulator, "_physics_client") and hasattr(simulator, "_body_ids"):
                import pybullet as p
                for body_id in simulator._body_ids.values():
                    # Get current color and apply offset
                    # PyBullet doesn't provide a getVisualShapeData that easily
                    # gives rgba, so we use a default base and apply offsets
                    p.changeVisualShape(
                        body_id, -1,
                        rgbaColor=[
                            np.clip(0.5 + r_offset, 0.0, 1.0),
                            np.clip(0.5 + g_offset, 0.0, 1.0),
                            np.clip(0.5 + b_offset, 0.0, 1.0),
                            1.0,
                        ],
                        physicsClientId=simulator._physics_client,
                    )
                if lighting is not None:
                    p.configureDebugVisualizer(
                        p.COV_ENABLE_SHADOWS, 1 if lighting > 0.8 else 0,
                        lightPosition=[1.0 * lighting, 1.0 * lighting, 5.0 * lighting],
                        physicsClientId=simulator._physics_client,
                    )
        except Exception:
            pass

    def update_curriculum(
        self,
        episode: int,
        metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """Update curriculum (no-op for basic randomizer).
        
        The parameter randomizer does not modify curriculum - it only
        randomizes parameters. Curriculum learning is handled by a
        separate controller.
        
        Args:
            episode: Episode number.
            metrics: Episode metrics.
            
        Returns:
            Empty dictionary (no curriculum updates).
        """
        return {}

    def get_randomized_action(
        self,
        action: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply action noise to an action.
        
        Args:
            action: Original action array.
            noise_scale: Optional override for noise scale.
            
        Returns:
            Action with noise applied.
        """
        if not self.domain_config.dynamics.enabled:
            return action
        
        if "action_noise" not in self._current_params.dynamics:
            return action
        
        scale = noise_scale if noise_scale is not None else abs(self._current_params.dynamics["action_noise"])
        noise = self._rng.uniform(-scale, scale, size=action.shape)
        return action + noise

    def get_randomized_observation(
        self,
        observation: np.ndarray,
        noise_scale: Optional[float] = None,
    ) -> np.ndarray:
        """Apply observation noise.
        
        Args:
            observation: Original observation array.
            noise_scale: Optional override for noise scale.
            
        Returns:
            Observation with noise applied.
        """
        if not self.domain_config.dynamics.enabled:
            return observation
        
        if "joint_noise" not in self._current_params.dynamics:
            return observation
        
        scale = noise_scale if noise_scale is not None else abs(self._current_params.dynamics["joint_noise"])
        noise = self._rng.uniform(-scale, scale, size=observation.shape)
        return observation + noise
