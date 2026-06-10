"""DreamerV3 training orchestration - CLI entry point, checkpoint management, evaluation."""

import json
from pathlib import Path
from typing import Any, Literal

from surg_rl.dreamer.spike import check_spike_status
from surg_rl.dreamer.subprocess import DreamerSubprocess
from surg_rl.dreamer.wrapper import GymToEmbodiedWrapper
from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
from surg_rl.scene_definition.loader import load_scene
from surg_rl.scene_definition.schema import DreamerConfig, SceneDefinition


def _create_scene_for_task(
    task: str, obs_type: str, pixel_resolution: tuple[int, int]
) -> SceneDefinition:
    """Create or load scene for a surgical task."""
    scene_path = Path(f"scenes/{task}.json")
    if scene_path.exists():
        scene = load_scene(str(scene_path))
        # If the loaded scene has a dreamer block, override obs_type and
        # pixel_resolution with the call-site params so the test contract
        # (e.g., scene.dreamer.obs_type == 'pixels' and tuple equality on
        # pixel_resolution) is satisfied.
        if scene.dreamer is not None:
            scene.dreamer.obs_type = obs_type
            scene.dreamer.pixel_resolution = tuple(pixel_resolution)
        return scene

    # Import required schema classes
    from surg_rl.scene_definition.schema import (
        InstrumentConfig,
        InstrumentType,
        MeshAsset,
        Orientation,
        Pose,
        Position,
        PyBulletSoftBodyConfig,
        RewardShaping,
        SceneDefinition,
        SoftBodyPhysics,
        TaskConfig,
        TaskObjective,
        TissueConfig,
        TissueMeshDefinition,
        TissueType,
    )

    # Task-specific instrument
    if task == "suturing":
        instrument_type = InstrumentType.NEEDLE_DRIVER
        instrument_name = "needle_driver"
    elif task == "grasping":
        instrument_type = InstrumentType.FORCEPS
        instrument_name = "forceps"
    elif task == "cutting":
        instrument_type = InstrumentType.SCISSORS
        instrument_name = "scissors"
    elif task == "knot_tying":
        instrument_type = InstrumentType.KNOT_TIER
        instrument_name = "knot_tier"
    elif task == "needle_insertion":
        instrument_type = InstrumentType.NEEDLE
        instrument_name = "needle"
    elif task == "dissection":
        instrument_type = InstrumentType.SCISSORS
        instrument_name = "dissection_scissors"
    else:
        instrument_type = InstrumentType.CUSTOM
        instrument_name = task

    instrument = InstrumentConfig(
        name=instrument_name,
        type=instrument_type,
        urdf_path=f"assets/instruments/{instrument_name}.urdf",
        pose=Pose(
            position=Position(x=0.0, y=0.0, z=0.15),
            orientation=Orientation(w=1.0, x=0.0, y=0.0, z=0.0),
        ),
    )

    # Task-specific tissue
    if task == "suturing":
        tissue_name = "liver"
        tissue_type = TissueType.ORGAN
        mesh_path = "assets/tissues/liver_tet.vtk"
        target_pos = [0.0, 0.02, 0.02]
    elif task == "grasping":
        tissue_name = "skin"
        tissue_type = TissueType.SKIN
        mesh_path = "assets/tissues/skin_patch.vtk"
        target_pos = [0.02, 0.0, 0.02]
    elif task == "knot_tying":
        tissue_name = "suture_pad"
        tissue_type = TissueType.CUSTOM
        mesh_path = "assets/tissues/suture_pad_tet.vtk"
        target_pos = [0.0, 0.02, 0.02]
    elif task == "needle_insertion":
        tissue_name = "organ_tissue"
        tissue_type = TissueType.ORGAN
        mesh_path = "assets/tissues/liver_tet.vtk"
        target_pos = [0.0, 0.0, 0.02]
    elif task == "cutting":
        tissue_name = "tissue"
        tissue_type = TissueType.SKIN
        mesh_path = "assets/tissues/skin_patch.vtk"
        target_pos = [0.02, 0.02, 0.02]
    elif task == "dissection":
        tissue_name = "dissection_tissue"
        tissue_type = TissueType.MUSCLE
        mesh_path = "assets/tissues/dissection_tissue_tet.vtk"
        target_pos = [0.02, 0.02, 0.02]
    else:
        tissue_name = "tissue"
        tissue_type = TissueType.CUSTOM
        mesh_path = f"assets/tissues/{task}_tissue.vtk"
        target_pos = [0.0, 0.0, 0.02]

    tissue = TissueConfig(
        name=tissue_name,
        type=tissue_type,
        geometry=TissueMeshDefinition(mesh=MeshAsset(path=mesh_path, scale=(1.0, 1.0, 1.0))),
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
            position=Position(x=target_pos[0], y=target_pos[1], z=target_pos[2]),
            orientation=Orientation(w=1.0, x=0.0, y=0.0, z=0.0),
        ),
    )

    # Task config
    task_config = TaskConfig(
        name=task,
        description=f"{task.title()} task for DreamerV3 training",
        task_type=task,
        objectives=[
            TaskObjective(
                name=task,
                description=f"Complete {task} task",
                success_criteria=f"{task.title()} completed successfully",
                weight=1.0,
            )
        ],
        reward_shaping=RewardShaping(),
        success_threshold=0.01,
    )

    return SceneDefinition(
        name=f"dreamer_{task}",
        description=f"DreamerV3 training scene: {task} with deformable tissue",
        instruments=[instrument],
        tissues=[tissue],
        task=task_config,
        dreamer=DreamerConfig(
            obs_type=obs_type,
            pixel_resolution=pixel_resolution,
            process_isolation=True,
            memory_fraction=0.4,
        ),
    )


def _create_env(scene: SceneDefinition) -> SurgicalEnv:
    """Create SurgicalEnv with the scene."""
    config = SurgicalEnvConfig(
        scene=scene,
        simulator_type="mujoco",
        render_mode="rgb_array",
        max_episode_steps=200,
    )
    return SurgicalEnv(config=config, render_mode="rgb_array")


def _find_latest_checkpoint(task: str, obs_type: str) -> str | None:
    """Find latest checkpoint for task/obs_type."""
    checkpoint_dir = Path(f"models/dreamerv3/{task}_{obs_type}")
    if not checkpoint_dir.exists():
        return None
    checkpoints = list(checkpoint_dir.glob("checkpoint_*.pt"))
    if not checkpoints:
        # Also check for final.pt
        final = checkpoint_dir / "final.pt"
        if final.exists():
            return str(final)
        return None
    latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
    return str(latest)


def run_dreamer_training(
    task: str = "suturing",
    obs_type: Literal["pixels", "state"] = "state",
    total_steps: int = 100000,
    eval_episodes: int = 10,
    eval_every: int = 10000,
    resume: bool = False,
    checkpoint_dir: str | None = None,
    eval_only: bool = False,
    config_overrides: dict[str, Any] | None = None,
    pixel_resolution: tuple[int, int] = (64, 64),
) -> dict[str, Any]:
    """Main DreamerV3 training entry point.

    Args:
        task: Surgical task type
        obs_type: "pixels" or "state" observation mode
        total_steps: Total training steps
        eval_episodes: Episodes per evaluation
        eval_every: Evaluation interval
        resume: Resume from latest checkpoint
        checkpoint_dir: Custom checkpoint directory
        eval_only: Run evaluation only (no training)
        config_overrides: DreamerConfig overrides
        pixel_resolution: Image resolution for pixels mode

    Returns:
        Dictionary with training results and metrics
    """
    # Check spike status
    spike_report = check_spike_status()
    if spike_report and spike_report.get("status") == "failed":
        raise RuntimeError("DreamerV3 integration deferred to v0.5.0 (spike failed)")

    # Determine checkpoint directory
    if checkpoint_dir is None:
        checkpoint_dir = f"models/dreamerv3/{task}_{obs_type}"
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)

    # Create scene and environment
    scene = _create_scene_for_task(task, obs_type, pixel_resolution)
    env = _create_env(scene)

    # Create wrapper
    wrapper = GymToEmbodiedWrapper(env, obs_type=obs_type, pixel_resolution=pixel_resolution)

    # Create subprocess
    dreamer_config = {
        "process_isolation": True,
        "memory_fraction": 0.4,
        "obs_type": obs_type,
        "pixel_resolution": list(pixel_resolution),
        "total_steps": total_steps,
        **(config_overrides or {}),
    }
    subprocess = DreamerSubprocess(dreamer_config)
    subprocess.spawn()
    subprocess.send_config(dreamer_config)

    metrics_log = {
        "task": task,
        "obs_type": obs_type,
        "total_steps": total_steps,
        "eval_episodes": eval_episodes,
        "training_curves": {
            "reconstruction_loss": [],
            "reward_loss": [],
            "total_loss": [],
        },
        "eval_results": [],
    }

    try:
        if eval_only:
            # Evaluation only mode
            latest_checkpoint = _find_latest_checkpoint(task, obs_type)
            if not latest_checkpoint:
                raise RuntimeError(f"No checkpoint found for {task}_{obs_type}")
            print(f"[Training] Evaluating checkpoint: {latest_checkpoint}")
            eval_metrics = subprocess.evaluate(latest_checkpoint, eval_episodes)
            metrics_log["eval_results"].append(
                {
                    "checkpoint": latest_checkpoint,
                    "metrics": eval_metrics,
                }
            )
            print(f"[Training] Evaluation complete: {eval_metrics}")
            return metrics_log

        # Check for resume
        resume_checkpoint = None
        if resume:
            latest = _find_latest_checkpoint(task, obs_type)
            if latest:
                resume_checkpoint = latest
                print(f"[Training] Resuming from checkpoint: {resume_checkpoint}")
                subprocess.load_checkpoint(resume_checkpoint)

        # Training loop
        print(f"[Training] Starting training for {total_steps} steps...")
        step = 0
        for metrics in subprocess.train(total_steps, eval_every):
            step = metrics.get("step", 0)
            recon_loss = metrics.get("reconstruction_loss", 0.0)
            reward_loss = metrics.get("reward_loss", 0.0)
            total_loss = metrics.get("total_loss", 0.0)

            metrics_log["training_curves"]["reconstruction_loss"].append(recon_loss)
            metrics_log["training_curves"]["reward_loss"].append(reward_loss)
            metrics_log["training_curves"]["total_loss"].append(total_loss)

            if step % 20000 == 0:
                print(
                    f"[Training] Step {step}: recon={recon_loss:.4f}, reward={reward_loss:.4f}, total={total_loss:.4f}"
                )

            # Periodic evaluation
            if step > 0 and step % eval_every == 0:
                checkpoint_file = checkpoint_path / f"checkpoint_{step}.pt"
                subprocess.save_checkpoint(str(checkpoint_file))
                eval_metrics = subprocess.evaluate(str(checkpoint_file), eval_episodes)
                metrics_log["eval_results"].append(
                    {
                        "step": step,
                        "checkpoint": str(checkpoint_file),
                        "metrics": eval_metrics,
                    }
                )
                print(f"[Training] Eval at step {step}: {eval_metrics}")

                # Save metrics alongside checkpoint
                metrics_file = checkpoint_path / f"metrics_{step}.json"
                with open(metrics_file, "w") as f:
                    json.dump(metrics_log, f, indent=2)

        # Final checkpoint
        final_checkpoint = checkpoint_path / "final.pt"
        subprocess.save_checkpoint(str(final_checkpoint))
        final_eval = subprocess.evaluate(str(final_checkpoint), eval_episodes)
        metrics_log["eval_results"].append(
            {
                "step": step,
                "checkpoint": str(final_checkpoint),
                "metrics": final_eval,
            }
        )

        # Save final metrics
        with open(checkpoint_path / "training_metrics.json", "w") as f:
            json.dump(metrics_log, f, indent=2)

        print(f"[Training] Training complete. Final checkpoint: {final_checkpoint}")

    except KeyboardInterrupt:
        print("[Training] Interrupted - saving checkpoint...")
        interrupt_checkpoint = checkpoint_path / f"checkpoint_interrupt_{step}.pt"
        subprocess.save_checkpoint(str(interrupt_checkpoint))
        raise
    finally:
        subprocess.shutdown()
        env.close()

    return metrics_log


def evaluate_checkpoint(
    checkpoint_path: str,
    task: str,
    obs_type: Literal["pixels", "state"],
    n_episodes: int = 10,
    pixel_resolution: tuple[int, int] = (64, 64),
) -> dict[str, Any]:
    """Evaluate a DreamerV3 checkpoint.

    Args:
        checkpoint_path: Path to checkpoint file
        task: Surgical task type
        obs_type: Observation mode
        n_episodes: Number of evaluation episodes
        pixel_resolution: Image resolution for pixels mode

    Returns:
        Metrics dictionary compatible with benchmark Aggregator
    """
    # Create scene and environment
    scene = _create_scene_for_task(task, obs_type, pixel_resolution)
    env = _create_env(scene)
    wrapper = GymToEmbodiedWrapper(env, obs_type=obs_type, pixel_resolution=pixel_resolution)

    # Create subprocess
    dreamer_config = {
        "process_isolation": True,
        "memory_fraction": 0.4,
        "obs_type": obs_type,
        "pixel_resolution": list(pixel_resolution),
    }
    subprocess = DreamerSubprocess(dreamer_config)
    subprocess.spawn()
    subprocess.send_config(dreamer_config)

    try:
        # Load checkpoint
        subprocess.load_checkpoint(checkpoint_path)

        # Run evaluation
        metrics = subprocess.evaluate(checkpoint_path, n_episodes)

        # Convert to benchmark-compatible format
        return {
            "success_rate": metrics.get("success_rate", 0.0),
            "mean_reward": metrics.get("mean_reward", 0.0),
            "mean_episode_length": metrics.get("mean_episode_length", 0.0),
            "wall_clock_time": metrics.get("wall_clock_time", 0.0),
            "sample_efficiency": metrics.get("sample_efficiency", 0.0),
            "reconstruction_mse": metrics.get("reconstruction_mse", 0.0),
            "reward_mae": metrics.get("reward_mae", 0.0),
            "obs_type": obs_type,
            "checkpoint": checkpoint_path,
        }
    finally:
        subprocess.shutdown()
        env.close()
