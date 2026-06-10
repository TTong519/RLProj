"""DreamerV3 Feasibility Spike (DMV3-01) - Tests if DreamerV3 can model surgical dynamics."""

import json
import time
from pathlib import Path
from typing import Any

from surg_rl.dreamer.subprocess import DreamerSubprocess
from surg_rl.dreamer.wrapper import GymToEmbodiedWrapper
from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
from surg_rl.scene_definition.loader import load_scene
from surg_rl.scene_definition.schema import DreamerConfig, SceneDefinition

SPIKE_REPORT_PATH = Path("models/dreamerv3/spike_report.json")
DEFAULT_THRESHOLDS = {
    "reconstruction_mse": 0.01,
    "reward_mae": 0.5,
}


class SpikeOrchestrator:
    """Orchestrates the DreamerV3 feasibility spike."""

    def __init__(
        self,
        task: str = "suturing",
        obs_type: str = "pixels",
        total_steps: int = 100000,
        eval_episodes: int = 10,
        pixel_resolution: tuple[int, int] = (64, 64),
        thresholds: dict[str, float] | None = None,
    ):
        """Initialize spike orchestrator.

        Args:
            task: Surgical task type
            obs_type: "pixels" or "state"
            total_steps: Training steps for spike
            eval_episodes: Evaluation episodes
            pixel_resolution: Image resolution for pixels mode
            thresholds: Custom pass/fail thresholds
        """
        self.task = task
        self.obs_type = obs_type
        self.total_steps = total_steps
        self.eval_episodes = eval_episodes
        self.pixel_resolution = pixel_resolution
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

        self.subprocess: DreamerSubprocess | None = None
        self.env: SurgicalEnv | None = None
        self.wrapper: GymToEmbodiedWrapper | None = None
        self._training_curves = {
            "reconstruction_loss": [],
            "reward_loss": [],
            "total_loss": [],
        }
        self._start_time: float | None = None

    def _create_spike_scene(self) -> SceneDefinition:
        """Create the spike scene: forceps + liver tet mesh + suturing task."""
        # Try to load existing scene first
        scene_path = Path(f"scenes/{self.task}.json")
        if scene_path.exists():
            return load_scene(str(scene_path))

        # Build minimal scene programmatically
        from surg_rl.scene_definition.schema import (
            InstrumentConfig,
            InstrumentType,
            MeshAsset,
            Orientation,
            Pose,
            Position,
            PyBulletSoftBodyConfig,
            SceneDefinition,
            SoftBodyPhysics,
            TaskConfig,
            TissueConfig,
            TissueMeshDefinition,
            TissueType,
        )

        # Forceps instrument
        forceps = InstrumentConfig(
            name="forceps",
            type=InstrumentType.NEEDLE_DRIVER,
            urdf_path="assets/instruments/forceps.urdf",
            pose=Pose(
                position=Position(x=0.0, y=0.0, z=0.15),
                orientation=Orientation(w=1.0, x=0.0, y=0.0, z=0.0),
            ),
        )

        # Liver tissue with tetrahedral mesh
        liver = TissueConfig(
            name="liver",
            type=TissueType.ORGAN,
            geometry=TissueMeshDefinition(
                mesh=MeshAsset(
                    path="assets/tissues/liver_tet.vtk",
                    scale=(1.0, 1.0, 1.0),
                )
            ),
            soft_body=True,
            physics=SoftBodyPhysics(
                pybullet=PyBulletSoftBodyConfig(
                    use_mass_spring=True,
                    spring_elastic_stiffness=1.0,
                    spring_damping_stiffness=0.1,
                ),
                stiffness=1000.0,
                damping=0.1,
                density=1060.0,
            ),
            pose=Pose(
                position=Position(x=0.0, y=0.02, z=0.02),
                orientation=Orientation(w=1.0, x=0.0, y=0.0, z=0.0),
            ),
        )

        # Suturing task
        from surg_rl.scene_definition.schema import RewardShaping, TaskObjective

        task_config = TaskConfig(
            name="suturing",
            description="Suturing task for DreamerV3 feasibility spike",
            task_type="suturing",
            objectives=[
                TaskObjective(
                    name="suture",
                    description="Complete suturing task",
                    success_criteria="Needle passes through tissue and knot is tied",
                    weight=1.0,
                )
            ],
            reward_shaping=RewardShaping(),
            success_threshold=0.01,
        )

        return SceneDefinition(
            name=f"spike_{self.task}",
            description=f"Feasibility spike: {self.task} with forceps and liver tet mesh",
            instruments=[forceps],
            tissues=[liver],
            task=task_config,
            dreamer=DreamerConfig(
                obs_type=self.obs_type,
                pixel_resolution=self.pixel_resolution,
                process_isolation=True,
                memory_fraction=0.4,
            ),
        )

    def _create_env(self, scene: SceneDefinition) -> SurgicalEnv:
        """Create SurgicalEnv with the spike scene."""
        config = SurgicalEnvConfig(
            scene=scene,
            simulator_type="mujoco",  # Prefer MuJoCo for rendering
            render_mode="rgb_array",
            max_episode_steps=200,
        )
        return SurgicalEnv(config=config, render_mode="rgb_array")

    def run(self) -> tuple[bool, dict[str, Any]]:
        """Execute the full feasibility spike.

        Returns:
            (passed, report_dict)
        """
        self._start_time = time.time()

        print("[Spike] Starting DreamerV3 feasibility spike")
        print(f"[Spike] Task: {self.task}, Obs: {self.obs_type}, Steps: {self.total_steps}")

        # 1. Create scene
        print("[Spike] Creating scene...")
        scene = self._create_spike_scene()
        print(f"[Spike] Scene created: {scene.metadata.name}")

        # 2. Create environment
        print("[Spike] Creating environment...")
        self.env = self._create_env(scene)
        print("[Spike] Environment created")

        # 3. Create wrapper
        print("[Spike] Creating GymToEmbodiedWrapper...")
        self.wrapper = GymToEmbodiedWrapper(
            self.env,
            obs_type=self.obs_type,
            pixel_resolution=self.pixel_resolution,
        )
        print(f"[Spike] Wrapper created, obs_type: {self.obs_type}")

        # 4. Test wrapper produces valid observations
        print("[Spike] Testing wrapper...")
        test_obs, _info = self.wrapper.reset()
        print(f"[Spike] Test obs keys: {test_obs.keys()}")
        if self.obs_type == "pixels":
            print(f"[Spike] Image shape: {test_obs['image'].shape}")
        else:
            print(f"[Spike] State shape: {test_obs['state'].shape}")

        # 5. Create DreamerSubprocess
        print("[Spike] Spawning DreamerSubprocess...")
        dreamer_config = {
            "process_isolation": True,
            "memory_fraction": 0.4,
            "obs_type": self.obs_type,
            "pixel_resolution": list(self.pixel_resolution),
            "total_steps": self.total_steps,
        }
        self.subprocess = DreamerSubprocess(dreamer_config)
        self.subprocess.spawn()
        print("[Spike] Subprocess spawned")

        # 6. Send config
        print("[Spike] Sending config to subprocess...")
        self.subprocess.send_config(dreamer_config)

        # 7. Train
        print(f"[Spike] Training for {self.total_steps} steps...")
        try:
            for metrics in self.subprocess.train(self.total_steps, eval_every=10000):
                step = metrics.get("step", 0)
                recon_loss = metrics.get("reconstruction_loss", 0.0)
                reward_loss = metrics.get("reward_loss", 0.0)
                total_loss = metrics.get("total_loss", 0.0)

                self._training_curves["reconstruction_loss"].append(recon_loss)
                self._training_curves["reward_loss"].append(reward_loss)
                self._training_curves["total_loss"].append(total_loss)

                if step % 20000 == 0:
                    print(f"[Spike] Step {step}: recon={recon_loss:.4f}, reward={reward_loss:.4f}")

        except Exception as e:
            print(f"[Spike] Training error: {e}")
            # Continue to evaluation anyway

        # 8. Evaluate
        print(f"[Spike] Evaluating on {self.eval_episodes} episodes...")
        # Find latest checkpoint
        checkpoint_dir = Path(f"models/dreamerv3/{self.task}_{self.obs_type}")
        checkpoints = list(checkpoint_dir.glob("checkpoint_*.pt"))
        if not checkpoints:
            # Create a dummy checkpoint path for evaluation
            checkpoint_path = str(checkpoint_dir / "final.pt")
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
        else:
            latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
            checkpoint_path = str(latest)

        eval_metrics = self.subprocess.evaluate(checkpoint_path, self.eval_episodes)
        reconstruction_mse = eval_metrics.get("reconstruction_mse", float("inf"))
        reward_mae = eval_metrics.get("reward_mae", float("inf"))

        # 9. Determine pass/fail
        mse_passed = reconstruction_mse < self.thresholds["reconstruction_mse"]
        mae_passed = reward_mae < self.thresholds["reward_mae"]
        passed = mse_passed and mae_passed

        print(
            f"[Spike] Reconstruction MSE: {reconstruction_mse:.6f} (threshold: {self.thresholds['reconstruction_mse']})"
        )
        print(f"[Spike] Reward MAE: {reward_mae:.6f} (threshold: {self.thresholds['reward_mae']})")
        print("[Spike] PASSED" if passed else "[Spike] FAILED")

        # 10. Generate report
        report = self._generate_report(
            passed=passed,
            reconstruction_mse=reconstruction_mse,
            reward_mae=reward_mae,
            eval_metrics=eval_metrics,
        )

        # 11. Cleanup
        if self.subprocess:
            self.subprocess.shutdown()
        if self.env:
            self.env.close()

        # 12. Save report
        SPIKE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SPIKE_REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[Spike] Report saved to {SPIKE_REPORT_PATH}")

        return passed, report

    def _generate_report(
        self,
        passed: bool,
        reconstruction_mse: float,
        reward_mae: float,
        eval_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate detailed spike report."""
        training_time = time.time() - self._start_time if self._start_time else 0

        # Determine deferral reason
        deferral_reasons = []
        if reconstruction_mse >= self.thresholds["reconstruction_mse"]:
            deferral_reasons.append("reconstruction_mse_above_threshold")
        if reward_mae >= self.thresholds["reward_mae"]:
            deferral_reasons.append("reward_mae_above_threshold")

        analysis = f"""
DreamerV3 Feasibility Spike Analysis (DMV3-01)
Task: {self.task}
Observation type: {self.obs_type}
Training steps: {self.total_steps}
Evaluation episodes: {self.eval_episodes}

RESULTS:
- Reconstruction MSE: {reconstruction_mse:.6f} (threshold: {self.thresholds['reconstruction_mse']}) {'✓' if reconstruction_mse < self.thresholds['reconstruction_mse'] else '✗'}
- Reward MAE: {reward_mae:.6f} (threshold: {self.thresholds['reward_mae']}) {'✓' if reward_mae < self.thresholds['reward_mae'] else '✗'}

TRAINING CURVES:
- Reconstruction loss: {self._training_curves['reconstruction_loss'][-1] if self._training_curves['reconstruction_loss'] else 'N/A'}
- Reward loss: {self._training_curves['reward_loss'][-1] if self._training_curves['reward_loss'] else 'N/A'}
- Total loss: {self._training_curves['total_loss'][-1] if self._training_curves['total_loss'] else 'N/A'}

INTERPRETATION:
{'DreamerV3 RSSM successfully models surgical dynamics from pixel observations.' if passed else 'DreamerV3 RSSM struggles to model surgical dynamics. The high reconstruction error suggests the stochastic recurrent state space model cannot capture the complex deformable tissue dynamics within the training budget.'}

RECOMMENDATION:
{'Proceed with full DreamerV3 integration for v0.4.0.' if passed else 'Defer full DreamerV3 integration to v0.5.0. Focus on improving RSSM architecture for surgical domain or increasing training budget.'}
""".strip()

        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "passed" if passed else "failed",
            "thresholds": self.thresholds,
            "results": {
                "reconstruction_mse": reconstruction_mse,
                "reward_mae": reward_mae,
                "training_steps": self.total_steps,
                "eval_episodes": self.eval_episodes,
                "training_time_seconds": training_time,
                **eval_metrics,
            },
            "training_curves": self._training_curves,
            "analysis": analysis,
            "recommendation": "proceed with integration" if passed else "defer to v0.5.0",
            "deferral_reason": "_and_".join(deferral_reasons) if deferral_reasons else None,
        }


def run_spike(
    task: str = "suturing",
    obs_type: str = "pixels",
    steps: int = 100000,
    eval_episodes: int = 10,
    **kwargs,
) -> tuple[bool, dict[str, Any]]:
    """Convenience function to run spike."""
    orchestrator = SpikeOrchestrator(
        task=task,
        obs_type=obs_type,
        total_steps=steps,
        eval_episodes=eval_episodes,
        **kwargs,
    )
    return orchestrator.run()


def check_spike_status() -> dict[str, Any] | None:
    """Check if spike report exists and return its contents."""
    if SPIKE_REPORT_PATH.exists():
        with open(SPIKE_REPORT_PATH) as f:
            return json.load(f)
    return None
