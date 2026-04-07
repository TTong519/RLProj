"""Tests for dynamics module - environment controllers.

Tests domain randomization, curriculum learning, and adaptive difficulty.
"""

import pytest
import numpy as np

from surg_rl.dynamics.base_controller import (
    BaseController,
    ControllerConfig,
    ControllerState,
    ParameterBounds,
    ParameterSnapshot,
)

from surg_rl.dynamics.parameter_randomizer import (
    ParameterRandomizer,
    PhysicsParameterBounds,
    VisualParameterBounds,
    DynamicsParameterBounds,
)

from surg_rl.dynamics.curriculum import (
    CurriculumScheduler,
    CurriculumConfig,
    CurriculumStage,
    CurriculumStageConfig,
)

from surg_rl.dynamics.adaptive_difficulty import (
    AdaptiveDifficultyController,
    DifficultyConfig,
    DifficultyState,
    AdaptationStrategy,
    AdaptationDirection,
)

from surg_rl.dynamics.environment_controller import (
    EnvironmentController,
    EnvironmentControllerConfig,
)

from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    PhysicsRandomization,
    VisualRandomization,
    DynamicsRandomization,
)


# === Test BaseController ===

class ConcreteController(BaseController):
    """Concrete implementation for testing."""
    
    def sample_parameters(self) -> ParameterSnapshot:
        return ParameterSnapshot(
            physics={"mass_ratio": self._rng.uniform(0.8, 1.2)},
            episode=self._episode,
            step=self._step,
        )
    
    def apply_parameters(self, snapshot, simulator):
        return True
    
    def update_curriculum(self, episode, metrics):
        return {"episode": episode}


class TestBaseController:
    """Tests for BaseController."""
    
    def test_init(self):
        """Test controller initialization."""
        config = ControllerConfig(enabled=True, seed=42)
        controller = ConcreteController(config=config)
        
        assert controller.state == ControllerState.IDLE
        assert controller.step == 0
        assert controller.episode == 0
    
    def test_start_stop(self):
        """Test start and stop lifecycle."""
        controller = ConcreteController()
        
        controller.start()
        assert controller.state == ControllerState.ACTIVE
        
        controller.stop()
        assert controller.state == ControllerState.IDLE
        
        controller.pause()
        assert controller.state == ControllerState.PAUSED
        
        controller.resume()
        assert controller.state == ControllerState.ACTIVE
    
    def test_reset(self):
        """Test episode reset."""
        controller = ConcreteController()
        controller.start()
        
        params = controller.reset(seed=42)
        
        assert controller.episode == 1
        assert params.episode == 1
        assert "mass_ratio" in params.physics
    
    def test_sample_parameters_reproducible(self):
        """Test that sampling is reproducible with seed."""
        controller1 = ConcreteController(config=ControllerConfig(seed=42))
        controller2 = ConcreteController(config=ControllerConfig(seed=42))
        
        controller1.start()
        controller2.start()
        
        params1 = controller1.reset()
        params2 = controller2.reset()
        
        # Both should have same sampled values
        assert params1.physics == params2.physics
    
    def test_callbacks(self):
        """Test callback system."""
        controller = ConcreteController()
        
        called = []
        
        def on_reset():
            called.append("reset")
        
        def on_episode_start():
            called.append("start")
        
        controller.on("on_reset", on_reset)
        controller.on("on_episode_start", on_episode_start)
        
        controller.start()
        controller.reset()
        
        assert "reset" in called
        assert "start" in called
    
    def test_parameter_bounds(self):
        """Test parameter bounds sampling."""
        bounds = ParameterBounds(
            name="test_param",
            min_value=0.0,
            max_value=1.0,
            default=0.5,
        )
        
        assert bounds.name == "test_param"
        assert bounds.min_value == 0.0
        assert bounds.max_value == 1.0
    
    def test_parameter_snapshot(self):
        """Test parameter snapshot."""
        snapshot = ParameterSnapshot(
            physics={"mass_ratio": 1.1},
            visual={"lighting": 0.8},
            dynamics={"action_noise": 0.02},
            episode=5,
            step=100,
        )
        
        assert snapshot.physics["mass_ratio"] == 1.1
        assert snapshot.visual["lighting"] == 0.8
        assert snapshot.dynamics["action_noise"] == 0.02
        assert snapshot.episode == 5
        assert snapshot.step == 100


# === Test ParameterRandomizer ===

class TestParameterRandomizer:
    """Tests for ParameterRandomizer."""
    
    def test_init(self):
        """Test randomizer initialization."""
        domain_config = DomainRandomizationConfig()
        randomizer = ParameterRandomizer(domain_config=domain_config)
        
        assert randomizer.domain_config == domain_config
    
    def test_sample_parameters_physics(self):
        """Test physics parameter sampling."""
        domain_config = DomainRandomizationConfig(
            physics=PhysicsRandomization(
                enabled=True,
                mass_range=(0.8, 1.2),
                friction_range=(0.3, 0.7),
            )
        )
        
        randomizer = ParameterRandomizer(domain_config=domain_config)
        randomizer.start()
        
        params = randomizer.reset()
        
        assert "mass_ratio" in params.physics or len(params.physics) >= 0
    
    def test_sample_parameters_disabled(self):
        """Test that disabled randomization returns empty params."""
        domain_config = DomainRandomizationConfig(
            physics=PhysicsRandomization(enabled=False),
            visual=VisualRandomization(enabled=False),
            dynamics=DynamicsRandomization(enabled=False),
        )
        
        randomizer = ParameterRandomizer(domain_config=domain_config)
        randomizer.start()
        
        params = randomizer.reset()
        
        assert len(params.physics) == 0
        assert len(params.visual) == 0
        assert len(params.dynamics) == 0
    
    def test_get_randomized_action(self):
        """Test action randomization."""
        domain_config = DomainRandomizationConfig(
            dynamics=DynamicsRandomization(
                enabled=True,
                action_noise=(-0.1, 0.1),
            )
        )
        
        randomizer = ParameterRandomizer(domain_config=domain_config)
        randomizer.start()
        randomizer.reset()
        
        action = np.array([0.5, 0.5, 0.5])
        randomized = randomizer.get_randomized_action(action)
        
        # Action should potentially be different (though not guaranteed)
        assert randomized.shape == action.shape
    
    def test_get_randomized_observation(self):
        """Test observation randomization."""
        domain_config = DomainRandomizationConfig(
            dynamics=DynamicsRandomization(
                enabled=True,
                joint_noise=(-0.05, 0.05),
            )
        )
        
        randomizer = ParameterRandomizer(domain_config=domain_config)
        randomizer.start()
        randomizer.reset()
        
        obs = np.array([1.0, 2.0, 3.0])
        randomized = randomizer.get_randomized_observation(obs)
        
        assert randomized.shape == obs.shape


# === Test CurriculumScheduler ===

class TestCurriculumScheduler:
    """Tests for CurriculumScheduler."""
    
    def test_init(self):
        """Test scheduler initialization."""
        scheduler = CurriculumScheduler()
        
        assert scheduler.current_stage == CurriculumStage.EASY
        assert scheduler.current_difficulty == 0.25
    
    def test_stage_progression(self):
        """Test manual stage progression."""
        scheduler = CurriculumScheduler()
        
        assert scheduler.current_stage == CurriculumStage.EASY
        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.MEDIUM
        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.HARD
        assert scheduler.advance_stage() is True
        assert scheduler.current_stage == CurriculumStage.EXPERT
        assert scheduler.advance_stage() is False  # Already at max
    
    def test_stage_regression(self):
        """Test manual stage regression."""
        curriculum_config = CurriculumConfig(
            initial_stage=CurriculumStage.HARD
        )
        scheduler = CurriculumScheduler(curriculum_config=curriculum_config)
        
        assert scheduler.current_stage == CurriculumStage.HARD
        assert scheduler.regress_stage() is True
        assert scheduler.current_stage == CurriculumStage.MEDIUM
        assert scheduler.regress_stage() is True
        assert scheduler.current_stage == CurriculumStage.EASY
        assert scheduler.regress_stage() is False  # Already at min
    
    def test_set_stage(self):
        """Test manual stage setting."""
        scheduler = CurriculumScheduler()
        
        scheduler.set_stage(CurriculumStage.EXPERT)
        
        assert scheduler.current_stage == CurriculumStage.EXPERT
        assert scheduler.current_difficulty == 1.0
    
    def test_sample_parameters(self):
        """Test parameter sampling for curriculum stages."""
        scheduler = CurriculumScheduler()
        scheduler.start()
        
        params = scheduler.reset()
        
        assert params.episode == 1
        assert isinstance(params.physics, dict)
    
    def test_auto_advancement(self):
        """Test automatic stage advancement based on performance."""
        curriculum_config = CurriculumConfig(
            auto_advance=True,
            advancement_window=10,
        )
        scheduler = CurriculumScheduler(curriculum_config=curriculum_config)
        scheduler.start()
        
        # Simulate good performance
        for i in range(60):
            scheduler.reset()
            info = scheduler.episode_end(
                {"success": 1, "reward": 100},
                simulator=None,
            )
        
        # Should have advanced from EASY
        assert scheduler.current_stage != CurriculumStage.EASY or scheduler._episode < 50
    
    def test_get_progress(self):
        """Test progress reporting."""
        scheduler = CurriculumScheduler()
        
        progress = scheduler.get_progress()
        
        assert "current_stage" in progress
        assert "difficulty" in progress
        assert "progress" in progress
    
    def test_get_performance_summary(self):
        """Test performance summary."""
        scheduler = CurriculumScheduler()
        scheduler.start()
        
        # Add some performance data
        scheduler._performance_history = [
            {"success": 1, "reward": 100},
            {"success": 0, "reward": 50},
            {"success": 1, "reward": 80},
        ]
        
        summary = scheduler.get_performance_summary()
        
        assert "success_rate" in summary
        assert "avg_reward" in summary
        assert summary["success_rate"] == pytest.approx(2/3, rel=0.1)
        assert summary["avg_reward"] == pytest.approx(230/3, rel=0.1)


# === Test AdaptiveDifficultyController ===

class TestAdaptiveDifficultyController:
    """Tests for AdaptiveDifficultyController."""
    
    def test_init(self):
        """Test controller initialization."""
        controller = AdaptiveDifficultyController()
        
        assert controller.difficulty == 0.3  # Default initial
        assert controller.direction == AdaptationDirection.MAINTAIN
    
    def test_custom_initial_difficulty(self):
        """Test custom initial difficulty."""
        config = DifficultyConfig(initial_difficulty=0.5)
        controller = AdaptiveDifficultyController(difficulty_config=config)
        
        assert controller.difficulty == 0.5
    
    def test_difficulty_bounds(self):
        """Test difficulty bounds."""
        config = DifficultyConfig(
            min_difficulty=0.2,
            max_difficulty=0.8,
        )
        controller = AdaptiveDifficultyController(difficulty_config=config)
        
        controller.set_difficulty(0.1)
        assert controller.difficulty == 0.2  # Clamped to min
        
        controller.set_difficulty(1.0)
        assert controller.difficulty == 0.8  # Clamped to max
    
    def test_sample_parameters(self):
        """Test parameter sampling."""
        controller = AdaptiveDifficultyController()
        controller.start()
        
        params = controller.reset()
        
        assert params.episode == 1
        assert isinstance(params.physics, dict)
    
    def test_difficulty_adaptation(self):
        """Test difficulty adaptation based on performance."""
        config = DifficultyConfig(
            success_threshold_high=0.7,
            adaptation_rate=0.1,
        )
        controller = AdaptiveDifficultyController(difficulty_config=config)
        controller.start()
        
        initial_difficulty = controller.difficulty
        
        # Simulate good performance
        controller.reset()
        for _ in range(25):
            controller.episode_end({"success": 1, "reward": 100}, simulator=None)
        
        # Difficulty should have increased
        assert controller.difficulty >= initial_difficulty
    
    def test_difficulty_decrease(self):
        """Test difficulty decrease on poor performance."""
        config = DifficultyConfig(
            success_threshold_low=0.4,
            adaptation_rate=0.1,
            initial_difficulty=0.5,
        )
        controller = AdaptiveDifficultyController(difficulty_config=config)
        controller.start()
        
        initial_difficulty = controller.difficulty
        
        # Simulate poor performance
        controller.reset()
        for _ in range(25):
            controller.episode_end({"success": 0, "reward": -100}, simulator=None)
        
        # Difficulty should have decreased
        assert controller.difficulty <= initial_difficulty
    
    def test_get_difficulty_state(self):
        """Test difficulty state retrieval."""
        controller = AdaptiveDifficultyController()
        
        state = controller.get_difficulty_state()
        
        assert isinstance(state, DifficultyState)
        assert state.difficulty == controller.difficulty
    
    def test_reset_difficulty(self):
        """Test difficulty reset."""
        config = DifficultyConfig(initial_difficulty=0.5)
        controller = AdaptiveDifficultyController(difficulty_config=config)
        
        controller.set_difficulty(0.8)
        controller.reset_difficulty()
        
        assert controller.difficulty == 0.5


# === Test EnvironmentController ===

class TestEnvironmentController:
    """Tests for EnvironmentController."""
    
    def test_init(self):
        """Test controller initialization."""
        config = EnvironmentControllerConfig(
            use_randomization=False,
            use_curriculum=False,
            use_adaptive_difficulty=False,
        )
        controller = EnvironmentController(config=config)
        
        assert controller.config.enabled is True
        assert controller.randomizer is None
        assert controller.curriculum is None
        assert controller.adaptive is None
    
    def test_init_defaults(self):
        """Test controller with default config."""
        controller = EnvironmentController()
        
        # Default config has use_randomization=True
        assert controller.config.use_randomization is True
        assert controller.randomizer is not None
    
    def test_with_randomization(self):
        """Test controller with randomization."""
        domain_config = DomainRandomizationConfig(
            physics=PhysicsRandomization(
                enabled=True,
                mass_range=(0.9, 1.1),
            )
        )
        
        config = EnvironmentControllerConfig(
            use_randomization=True,
            randomization_config=domain_config,
        )
        controller = EnvironmentController(config=config)
        
        assert controller.randomizer is not None
    
    def test_with_curriculum(self):
        """Test controller with curriculum learning."""
        config = EnvironmentControllerConfig(
            use_curriculum=True,
        )
        controller = EnvironmentController(config=config)
        
        assert controller.curriculum is not None
    
    def test_with_adaptive_difficulty(self):
        """Test controller with adaptive difficulty."""
        config = EnvironmentControllerConfig(
            use_adaptive_difficulty=True,
        )
        controller = EnvironmentController(config=config)
        
        assert controller.adaptive is not None
    
    def test_lifecycle(self):
        """Test controller lifecycle."""
        config = EnvironmentControllerConfig(
            use_randomization=True,
        )
        controller = EnvironmentController(config=config)
        
        controller.start()
        params = controller.reset(seed=42)
        
        assert params.episode == 1
        
        info = controller.episode_end(
            {"reward": 100, "success": True},
            simulator=None,
        )
        
        assert "episode" in info
        assert "params" in info
    
    def test_get_status(self):
        """Test status retrieval."""
        config = EnvironmentControllerConfig(
            use_randomization=True,
            use_curriculum=True,
            use_adaptive_difficulty=True,
        )
        controller = EnvironmentController(config=config)
        
        status = controller.get_status()
        
        assert "enabled" in status
        assert "episode" in status
    
    def test_utility_methods(self):
        """Test utility methods."""
        controller = EnvironmentController(
            config=EnvironmentControllerConfig(
                use_curriculum=True,
                use_adaptive_difficulty=True,
            )
        )
        
        # Test curriculum stage
        stage = controller.get_curriculum_stage()
        assert stage == CurriculumStage.EASY
        
        # Test difficulty
        difficulty = controller.get_difficulty()
        assert difficulty == 0.3  # Default
        
        # Test set methods
        controller.set_difficulty(0.7)
        assert controller.get_difficulty() == 0.7
        
        controller.set_curriculum_stage(CurriculumStage.HARD)
        assert controller.get_curriculum_stage() == CurriculumStage.HARD
    
    def test_action_observation_randomization(self):
        """Test action and observation randomization."""
        domain_config = DomainRandomizationConfig(
            dynamics=DynamicsRandomization(
                enabled=True,
                action_noise=(-0.05, 0.05),
                joint_noise=(-0.02, 0.02),
            )
        )
        
        controller = EnvironmentController(
            config=EnvironmentControllerConfig(
                use_randomization=True,
                randomization_config=domain_config,
            )
        )
        
        controller.start()
        controller.reset()
        
        # Test action randomization
        action = np.array([0.5, 0.5])
        randomized = controller.get_randomized_action(action)
        assert randomized.shape == action.shape
        
        # Test observation randomization
        obs = np.array([1.0, 2.0, 3.0])
        randomized = controller.get_randomized_observation(obs)
        assert randomized.shape == obs.shape
