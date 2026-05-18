"""Command-line interface for Surg-RL."""

import asyncio
import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from surg_rl import __version__
from surg_rl.assets.download import (
    ALL_INSTRUMENT_NAMES,
    ALL_ORGAN_NAMES,
    download_meshes,
    list_local_meshes,
)
from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.scene_generation import TextParser, VisionParser, get_template
from surg_rl.utils.config import get_settings
from surg_rl.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _yaml_serialize(scene):
    """Serialize a scene to YAML-safe dict."""
    return scene.model_dump(mode="json")


app = typer.Typer(
    name="surg-rl",
    help="Surgical Robotics RL Training System",
    add_completion=False,
)

assets_app = typer.Typer(help="Manage surgical mesh assets")
app.add_typer(assets_app, name="assets")


@assets_app.command("download")
def assets_download(
    instruments: str = typer.Option(
        "", "--instruments", "-i",
        help="Comma-separated instrument names to download",
    ),
    organs: str = typer.Option(
        "", "--organs", "-o",
        help="Comma-separated organ names to download",
    ),
    all_meshes: bool = typer.Option(
        False, "--all", "-a",
        help="Download all available meshes",
    ),
    output_dir: str = typer.Option(
        "assets/meshes", "--output", help="Output directory for OBJ files",
    ),
):
    """Download real surgical mesh OBJ files from public datasets."""
    names: list[str] = []
    if instruments:
        names.extend(n.strip() for n in instruments.split(",") if n.strip())
    if organs:
        names.extend(n.strip() for n in organs.split(",") if n.strip())
    if all_meshes:
        names = list(set(ALL_INSTRUMENT_NAMES + ALL_ORGAN_NAMES))
    if not names:
        typer.echo(
            "Specify meshes to download: --instruments forceps,scalpel "
            "or --organs liver,kidney or --all"
        )
        typer.echo(f"Available instruments: {', '.join(ALL_INSTRUMENT_NAMES)}")
        typer.echo(f"Available organs: {', '.join(ALL_ORGAN_NAMES)}")
        raise typer.Exit(1)

    typer.echo(f"Downloading {len(names)} mesh(es)...")
    try:
        downloaded = download_meshes(names, output_dir=output_dir)
    except ImportError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    if downloaded:
        typer.echo(f"Downloaded {len(downloaded)}/{len(names)} file(s):")
        for f in downloaded:
            typer.echo(f"  ✓ {f}")
    else:
        typer.echo("No files downloaded. Check internet connection and URLs.")


@assets_app.command("info")
def assets_info(
    meshes_dir: str = typer.Option(
        "assets/meshes", "--dir", help="Meshes directory",
    ),
):
    """Show available and downloaded surgical meshes."""
    status = list_local_meshes(meshes_dir)
    present = [k for k, v in status.items() if v]
    missing = [k for k, v in status.items() if not v]

    typer.echo(f"Local meshes in {meshes_dir}/")
    typer.echo(f"  Present: {len(present)}/{len(status)}")
    for name in present:
        typer.echo(f"    ✓ {name}.obj")
    typer.echo(f"  Available for download:")
    for name in missing:
        typer.echo(f"    ○ {name}.obj")
    if missing:
        typer.echo(
            f"\nRun 'surg-rl assets download --all' to download all "
            f"{len(missing)} missing mesh(es)."
        )

console = Console()


@app.callback()
def main():
    """CLI entry point."""
    setup_logging()


@app.command()
def version(verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed system info including GPU availability")) -> None:
    """Show version information."""
    from surg_rl.scene_definition.schema import HardwareBackend
    from surg_rl.utils.gpu import (
        detect_backends,
        get_cuda_version,
        get_rocm_version,
        select_backend,
    )
    console.print(f"[bold blue]Surg-RL[/bold blue] version: [green]{__version__}[/green]")
    if verbose:
        backends = detect_backends()
        table = Table(title="GPU Availability")
        table.add_column("Backend", style="cyan")
        table.add_column("Available", style="green")
        table.add_column("Version / Info", style="yellow")
        for backend in [HardwareBackend.cuda, HardwareBackend.rocm, HardwareBackend.metal, HardwareBackend.intel, HardwareBackend.cpu]:
            available = backend in backends
            version_info = "N/A"
            if backend == HardwareBackend.cuda and available:
                version_info = get_cuda_version() or "N/A"
            elif backend == HardwareBackend.rocm and available:
                version_info = get_rocm_version() or "N/A"
            elif backend == HardwareBackend.metal and available:
                version_info = "Apple Silicon" if "arm" in os.uname().machine.lower() else "Intel Mac"
            elif backend == HardwareBackend.intel and available:
                version_info = "oneAPI / XPU"
            elif backend == HardwareBackend.cpu:
                version_info = "Always available"
            table.add_row(backend.value, "Yes" if available else "No", version_info)
        console.print(table)
        default_backend = select_backend(HardwareBackend.auto)
        console.print(f"Default backend: {default_backend.value}")


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    config_items = [
        ("Version", __version__),
        ("Project Root", str(settings.project_root)),
        ("Default Simulator", settings.default_simulator),
        ("", ""),
        ("LLM Provider", settings.llm_provider),
        ("LLM Model", settings.llm_model),
        ("VLM Model", settings.vlm_model),
        ("", ""),
        ("Ollama Base URL", settings.ollama_base_url),
        ("Ollama Model", settings.ollama_model),
        ("Ollama Vision Model", settings.ollama_vision_model),
        ("Ollama Timeout", f"{settings.ollama_timeout}s"),
        ("", ""),
        ("Render Width", str(settings.render_width)),
        ("Render Height", str(settings.render_height)),
        ("RL Seed", str(settings.rl_seed)),
        ("Log Level", settings.log_level),
    ]

    for key, value in config_items:
        if key == "":
            table.add_row("", "")
        else:
            table.add_row(key, value)

    console.print(table)


@app.command()
def setup() -> None:
    """Set up project directories."""
    settings = get_settings()
    settings.ensure_directories()

    console.print("[bold green]✓[/bold green] Project directories created:")
    console.print(f"  • Assets: {settings.assets_dir}")
    console.print(f"  • Scenes: {settings.scenes_dir}")
    console.print(f"  • Configs: {settings.configs_dir}")


@app.command()
def generate(
    text: str = typer.Option(None, "--text", "-t", help="Text description of scene"),
    image: str = typer.Option(None, "--image", "-i", help="Path to image file"),
    template: str = typer.Option(None, "--template", "-T", help="Use a predefined template"),
    output: str = typer.Option("scene.json", "--output", "-o", help="Output file path"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json or yaml)"),
    provider: str = typer.Option(
        None, "--provider", "-p", help="LLM provider (openai, anthropic, ollama)"
    ),
    model: str = typer.Option(None, "--model", "-m", help="Model name to use"),
    ollama_url: str = typer.Option(
        None, "--ollama-url", help="Ollama API base URL (for ollama provider)"
    ),
) -> None:
    """Generate a scene from text, image, or template input."""
    try:
        if template:
            console.print(f"[bold blue]Loading template:[/bold blue] {template}")
            try:
                scene = get_template(template)
            except ValueError as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                console.print("[dim]Available templates: suturing, dissection, manipulation[/dim]")
                raise typer.Exit(1) from e

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml

                content = yaml.dump(
                    _yaml_serialize(scene), default_flow_style=False, sort_keys=False
                )
            else:
                content = json.dumps(scene.model_dump(mode="json"), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        if text:
            console.print("[bold blue]Generating scene from text...[/bold blue]")
            console.print(f"[dim]Provider: {provider or 'default'}[/dim]")
            console.print(f"[dim]Description: {text[:100]}{'...' if len(text) > 100 else ''}[/dim]")

            try:
                parser = TextParser(
                    provider=provider,
                    model=model,
                    ollama_base_url=ollama_url,
                )
                scene = asyncio.run(parser.parse(text))
            except ImportError as e:
                console.print(f"[bold red]Import Error:[/bold red] {e}")
                console.print(
                    "[dim]The required LLM package may not be installed. "
                    "Try using --provider ollama to use a local model instead.[/dim]"
                )
                raise typer.Exit(1) from e

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml

                content = yaml.dump(
                    _yaml_serialize(scene), default_flow_style=False, sort_keys=False
                )
            else:
                content = json.dumps(scene.model_dump(mode="json"), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        if image:
            console.print("[bold blue]Generating scene from image...[/bold blue]")
            console.print(f"[dim]Provider: {provider or 'default'}[/dim]")
            console.print(f"[dim]Image: {image}[/dim]")

            try:
                parser = VisionParser(
                    provider=provider,
                    model=model,
                    ollama_base_url=ollama_url,
                )
                scene = asyncio.run(parser.parse(image))
            except ImportError as e:
                console.print(f"[bold red]Import Error:[/bold red] {e}")
                console.print(
                    "[dim]The required LLM package may not be installed. "
                    "Try using --provider ollama to use a local model instead.[/dim]"
                )
                raise typer.Exit(1) from e

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml

                content = yaml.dump(
                    _yaml_serialize(scene), default_flow_style=False, sort_keys=False
                )
            else:
                content = json.dumps(scene.model_dump(mode="json"), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        console.print("[bold red]Error:[/bold red] No input provided.")
        console.print("[dim]Use --text, --image, or --template to specify input.[/dim]")
        raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Scene generation failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def train(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    algorithm: str = typer.Option(
        "PPO", "--algorithm", "-a", help="RL algorithm (PPO, SAC, TD3, DDPG, A2C)"
    ),
    timesteps: int = typer.Option(100000, "--timesteps", "-t", help="Total training timesteps"),
    n_envs: int = typer.Option(1, "--n-envs", "-n", help="Number of parallel environments"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    learning_rate: float = typer.Option(3e-4, "--lr", help="Learning rate"),
    batch_size: int = typer.Option(64, "--batch-size", help="Batch size"),
    device: str = typer.Option("auto", "--device", help="Device (auto, cpu, cuda, mps)"),
    log_dir: str = typer.Option("logs/training", "--log-dir", help="Log directory"),
    save_freq: int = typer.Option(50000, "--save-freq", help="Checkpoint save frequency"),
    eval_freq: int = typer.Option(10000, "--eval-freq", help="Evaluation frequency"),
    curriculum: bool = typer.Option(False, "--curriculum", help="Enable curriculum learning"),
    adaptive: bool = typer.Option(False, "--adaptive", help="Enable adaptive difficulty"),
    simulator: str = typer.Option(
        "mujoco", "--simulator", help="Simulator backend (mujoco, pybullet)"
    ),
    max_episode_steps: int = typer.Option(1000, "--max-steps", help="Max steps per episode"),
    verbose: int = typer.Option(1, "--verbose", "-v", help="Verbosity level (0, 1, 2)"),
    wandb: bool = typer.Option(False, "--wandb", help="Enable Weights \u0026 Biases logging"),
    mlflow: bool = typer.Option(False, "--mlflow", help="Enable MLflow logging"),
    experiment_name: str | None = typer.Option(None, "--experiment-name", "-e", help="Experiment name for tracking"),
    wandb_project: str | None = typer.Option(None, "--wandb-project", help="W\u0026B project name (default: surg-rl)"),
    backend: str = typer.Option(
        "auto", "--backend", help="Hardware backend: auto, cuda, rocm, metal, intel, cpu"
    ),
    render_human: bool = typer.Option(
        False, "--render-human",
        help="Open a live 3D viewer during training (requires display)"
    ),
    render_fps: float = typer.Option(
        30.0, "--render-fps",
        help="Target FPS for the live viewer (default: 30)"
    ),
) -> None:
    """Train an RL agent on a surgical scene.

    Supports PPO, SAC, TD3, DDPG, and A2C algorithms via Stable-Baselines3.

    Examples:
        surg-rl train --scene scenes/suturing.json --algorithm PPO --timesteps 100000
        surg-rl train --scene scenes/suturing.json --algorithm SAC --lr 1e-4 --curriculum
        surg-rl train --scene scenes/suturing.json --algorithm PPO --n-envs 4 --device cuda
    """
    from surg_rl.rl.training import AlgorithmConfig, TrainingConfig, TrainingManager

    console.print("[bold blue]Starting RL Training[/bold blue]")
    console.print(f"  • Scene: {scene}")
    console.print(f"  • Algorithm: {algorithm}")
    console.print(f"  • Timesteps: {timesteps:,}")
    console.print(f"  • Seed: {seed}")

    try:
        algo_config = AlgorithmConfig(
            name=algorithm.upper(),
            learning_rate=learning_rate,
            batch_size=batch_size,
        )

        backend_enum = HardwareBackend(backend)

        config = TrainingConfig(
            scene_path=scene,
            algorithm=algo_config,
            total_timesteps=timesteps,
            n_envs=n_envs,
            seed=seed,
            device=device,
            log_dir=log_dir,
            save_freq=save_freq,
            eval_freq=eval_freq,
            simulator=simulator,
            max_episode_steps=max_episode_steps,
            use_curriculum=curriculum,
            use_adaptive_difficulty=adaptive,
            verbose=verbose,
            use_wandb=wandb,
            use_mlflow=mlflow,
            experiment_name=experiment_name,
            wandb_project=wandb_project,
            backend=backend_enum,
            render_mode="human" if render_human else None,
            render_fps=render_fps,
        )

        manager = TrainingManager(config)
        manager.train()

        console.print("[bold green]✓ Training complete![/bold green]")
        console.print(f"  • Model saved to: {log_dir}/final_model")

    except ImportError as e:
        console.print(f"[bold red]Import Error:[/bold red] {e}")
        console.print(
            "[dim]Make sure stable-baselines3 is installed: pip install stable-baselines3[/dim]"
        )
        console.print(
            "[dim]stable-baselines3 is listed in pyproject.toml dependencies. "
            'If the import still fails, reinstall with: pip install -e ".[dev]"[/dim]'
        )
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"Training failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def evaluate(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    model: str = typer.Option(..., "--model", "-m", help="Path to trained model"),
    episodes: int = typer.Option(10, "--episodes", "-e", help="Number of evaluation episodes"),
    render: bool = typer.Option(False, "--render", "-r", help="Render during evaluation"),
    simulator: str = typer.Option("mujoco", "--simulator", help="Simulator backend"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    verbose: int = typer.Option(1, "--verbose", "-v", help="Verbosity level"),
) -> None:
    """Evaluate a trained RL agent.

    Runs evaluation episodes and reports performance metrics.

    Examples:
        surg-rl evaluate --scene scenes/suturing.json --model logs/training/final_model
        surg-rl evaluate --scene scenes/suturing.json --model model.zip --episodes 20 --render
    """
    from surg_rl.rl.training import TrainingConfig, TrainingManager

    console.print("[bold blue]Starting Evaluation[/bold blue]")
    console.print(f"  • Scene: {scene}")
    console.print(f"  • Model: {model}")
    console.print(f"  • Episodes: {episodes}")

    try:
        config = TrainingConfig(
            scene_path=scene,
            seed=seed,
            simulator=simulator,
            verbose=verbose,
        )

        manager = TrainingManager(config)
        results = manager.evaluate(
            model_path=model,
            n_episodes=episodes,
            render=render,
        )

        # Display results
        table = Table(title="Evaluation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Episodes", str(results["n_episodes"]))
        table.add_row("Mean Reward", f"{results['mean_reward']:.2f}")
        table.add_row("Std Reward", f"{results['std_reward']:.2f}")
        table.add_row("Max Reward", f"{results['max_reward']:.2f}")
        table.add_row("Min Reward", f"{results['min_reward']:.2f}")
        table.add_row("Mean Length", f"{results['mean_episode_length']:.1f}")
        table.add_row("Success Rate", f"{results['success_rate']:.1%}")

        console.print(table)

    except ImportError as e:
        console.print(f"[bold red]Import Error:[/bold red] {e}")
        console.print(
            "[dim]Make sure stable-baselines3 is installed: pip install stable-baselines3[/dim]"
        )
        console.print(
            "[dim]stable-baselines3 is listed in pyproject.toml dependencies. "
            'If the import still fails, reinstall with: pip install -e ".[dev]"[/dim]'
        )
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command(name="marl-train")
def marl_train(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to dual-arm scene JSON/YAML"),
    algorithm: str = typer.Option("PPO", "--algorithm", "-a", help="SB3 algorithm (PPO, SAC)"),
    policy: str = typer.Option("shared", "--policy", "-p", help="Policy mode: shared or independent"),
    timesteps: int = typer.Option(100000, "--timesteps", "-t", help="Total training timesteps"),
    model_dir: str = typer.Option("models/", "--model-dir", "-m", help="Model output directory"),
    simulator: str = typer.Option("mujoco", "--simulator", help="Simulator backend (mujoco or pybullet)"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run without GUI"),
) -> None:
    """Train dual-arm multi-agent RL policies.

    Supports shared policy (one model for both arms) and independent
    policy (per-arm models trained in parallel threads).

    Examples:
        surg-rl marl-train --scene scenes/dual_arm.json --policy shared
        surg-rl marl-train --scene scenes/dual_arm.json --policy independent --algorithm SAC
    """
    from surg_rl.marl.multi_agent_env import MultiAgentSurgicalEnv
    from surg_rl.marl.training import MultiAgentTrainingManager
    from surg_rl.rl.environment import SurgicalEnvConfig

    if policy not in ("shared", "independent"):
        console.print(f"[bold red]Error:[/bold red] --policy must be 'shared' or 'independent', got '{policy}'")
        raise typer.Exit(code=1)

    render_mode = None if headless else "rgb_array"
    try:
        config = SurgicalEnvConfig(
            scene_path=scene,
            simulator_type=simulator,
            render_mode=render_mode,
        )
        env = MultiAgentSurgicalEnv(config, render_mode=render_mode)

        trainer = MultiAgentTrainingManager(
            env=env,
            algorithm=algorithm,
            shared_policy=(policy == "shared"),
            total_timesteps=timesteps,
            model_dir=model_dir,
        )
        result = trainer.train()
        console.print(f"[bold green]Training complete.[/bold green] Models: {result}")
    except ImportError as e:
        console.print(f"[bold red]Import Error:[/bold red] {e}")
        console.print("[dim]Install: pip install surg-rl[marl][/dim]")
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"MARL training failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command(name="train-rllib")
def cli_train_rllib(
    scene: str = typer.Option("scenes/simple_suturing.json", "--scene", "-s", help="Scene definition JSON"),
    algorithm: str = typer.Option("PPO", "--algorithm", "-a", help="RL algorithm"),
    timesteps: int = typer.Option(100_000, "--timesteps", "-t", help="Total training timesteps"),
    n_envs: int = typer.Option(1, "--n-envs", "-n", help="Number of parallel environments"),
    lr: float = typer.Option(3e-4, "--lr", help="Learning rate"),
    gamma: float = typer.Option(0.99, "--gamma", help="Discount factor"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    log_dir: str = typer.Option("logs/rllib", "--log-dir", help="Directory for RLlib results/checkpoints"),
    checkpoint_freq: int = typer.Option(50_000, "--checkpoint-freq", help="Save checkpoint every N timesteps"),
    local_mode: bool = typer.Option(False, "--local-mode", help="Run Ray in local mode"),
    verbose: bool = typer.Option(True, "--verbose", help="Verbose logging"),
) -> None:
    """Train a policy with Ray RLlib.

    Examples::

        surg-rl train-rllib --scene scenes/suturing.json --timesteps 200000
        surg-rl train-rllib --algorithm SAC --n-envs 4 --lr 1e-4
    """
    try:
        from surg_rl.rl.rllib.config import RllibConfig
        from surg_rl.rl.rllib.train import train_rllib

        config = RllibConfig(
            env_name="surg-rl",
            env_config={"scene_path": scene, "simulator_type": "mujoco"},
            algorithm=algorithm,
            total_timesteps=timesteps,
            num_env_runners=max(0, n_envs - 1),
            lr=lr,
            gamma=gamma,
            seed=seed,
            save_dir=log_dir,
            checkpoint_freq=checkpoint_freq,
        )

        console.print("[bold blue]Starting RLlib Training[/bold blue]")
        console.print(f"  • Scene: {scene}")
        console.print(f"  • Algorithm: {algorithm}")
        console.print(f"  • Timesteps: {timesteps:,}")
        console.print(f"  • Environments: {n_envs}")

        final_ckpt = train_rllib(config, local_mode=local_mode)
        console.print(f"[bold green]Training complete![/bold green] Final checkpoint: {final_ckpt}")

    except ImportError as exc:
        console.print(f"[bold red]Import Error:[/bold red] {exc}")
        console.print(
            '[dim]Make sure ray[rllib] is installed: pip install "surg-rl[distributed]"[/dim]'
        )
        raise typer.Exit(1) from exc


@app.command(name="tune")
def cli_tune(
    scene: str = typer.Option("scenes/simple_suturing.json", "--scene", "-s", help="Scene definition JSON"),
    algorithm: str = typer.Option("PPO", "--algorithm", "-a", help="RL algorithm"),
    timesteps: int = typer.Option(50_000, "--timesteps", "-t", help="Total training timesteps per trial"),
    num_samples: int = typer.Option(3, "--num-samples", "-n", help="Number of Tune trials"),
    max_iters: int = typer.Option(10, "--max-iters", help="Max iterations per trial"),
    lr_min: float = typer.Option(1e-5, "--lr-min", help="Learning rate search lower bound"),
    lr_max: float = typer.Option(1e-3, "--lr-max", help="Learning rate search upper bound"),
    gamma_min: float = typer.Option(0.95, "--gamma-min", help="Gamma search lower bound"),
    gamma_max: float = typer.Option(0.999, "--gamma-max", help="Gamma search upper bound"),
    log_dir: str = typer.Option("logs/tune", "--log-dir", help="Directory for Tune results"),
    scheduler: str = typer.Option("asha", "--scheduler", help="ASHA or PBT"),
    local_mode: bool = typer.Option(True, "--local-mode", help="Run Ray in local mode"),
) -> None:
    """Run Ray Tune hyperparameter search.

    Examples::

        surg-rl tune --scene scenes/suturing.json --num-samples 5
        surg-rl tune --algorithm SAC --scheduler pbt
    """
    try:
        from ray import tune
        from surg_rl.rl.rllib.config import RllibConfig
        from surg_rl.rl.rllib.tune_integration import build_tune_search_space, run_tune_experiment

        base_config = RllibConfig(
            env_config={"scene_path": scene, "simulator_type": "mujoco"},
            algorithm=algorithm,
            total_timesteps=timesteps,
            save_dir=log_dir,
        )

        param_space = build_tune_search_space(
            base_config,
            lr_range=(lr_min, lr_max),
            gamma_range=(gamma_min, gamma_max),
        )

        console.print("[bold blue]Starting Ray Tune Experiment[/bold blue]")
        console.print(f"  • Scene: {scene}")
        console.print(f"  • Algorithm: {algorithm}")
        console.print(f"  • Trials: {num_samples}")
        console.print(f"  • Max iterations: {max_iters}")
        console.print(f"  • Scheduler: {scheduler}")

        results = run_tune_experiment(
            base_config,
            param_space=param_space,
            num_samples=num_samples,
            max_training_iterations=max_iters,
            scheduler=scheduler,
            local_mode=local_mode,
        )

        best = results.get_best_result()
        if best and hasattr(best, "metrics"):
            reward = best.metrics.get("env_runners/episode_return_mean", float("nan"))
            console.print(f"[bold green]Best reward: {reward:.2f}[/bold green]")
        console.print(f"Results saved to: {log_dir}/best_config.json")

    except ImportError as exc:
        console.print(f"[bold red]Import Error:[/bold red] {exc}")
        console.print(
            '[dim]Make sure ray[rllib] is installed: pip install "surg-rl[distributed]"[/dim]'
        )
        raise typer.Exit(1) from exc


@app.command(name="checkpoint-inspect")
def cli_checkpoint_inspect(
    path: str = typer.Argument(..., help="Path to checkpoint (RLlib dir or SB3 zip)"),
    compare_with: str | None = typer.Option(None, "--compare-with", help="Path to second checkpoint for comparison"),
) -> None:
    """Inspect checkpoint meta-data and compare RLlib vs SB3 formats.

    Examples::

        surg-rl checkpoint-inspect logs/rllib/checkpoint_50000
        surg-rl checkpoint-inspect models/ppo_model.zip --compare-with logs/rllib/final
    """
    try:
        from surg_rl.rl.rllib.checkpoint_utils import inspect_rllib_checkpoint, inspect_sb3_checkpoint, compare_checkpoints

        path_obj = Path(path)
        if not path_obj.exists():
            console.print(f"[bold red]Path not found:[/bold red] {path}")
            raise typer.Exit(1)

        # Sniff format
        if path_obj.is_dir():
            info = inspect_rllib_checkpoint(path)
        else:
            info = inspect_sb3_checkpoint(path)

        console.print(f"[bold cyan]Checkpoint: {path}[/bold cyan]")
        console.print(f"  Format: {info['format'].upper()}")
        console.print(f"  Algorithm: {info.get('algorithm', 'unknown')}")
        if info.get('layer_shapes'):
            console.print(f"  Layers: {len(info['layer_shapes'])}")
            for name, shape in list(info['layer_shapes'].items())[:5]:
                console.print(f"    {name}: {shape}")
            if len(info['layer_shapes']) > 5:
                console.print(f"    ... and {len(info['layer_shapes']) - 5} more")

        if compare_with:
            other_obj = Path(compare_with)
            if not other_obj.exists():
                console.print(f"[bold red]Path not found:[/bold red] {compare_with}")
                raise typer.Exit(1)

            if other_obj.is_dir():
                other_info = inspect_rllib_checkpoint(compare_with)
            else:
                other_info = inspect_sb3_checkpoint(compare_with)

            comparison = compare_checkpoints(
                info if info['format'] == 'rllib' else other_info,
                info if info['format'] == 'sb3' else other_info,
            )
            console.print(f"\n[bold cyan]Comparison:[/bold cyan]")
            console.print(f"  Input dim match: {comparison.get('input_dim_match')}")
            console.print(f"  Output dim match: {comparison.get('output_dim_match')}")
            console.print(f"\n[bold yellow]Notes:[/bold yellow]")
            console.print(comparison["notes"])

    except ImportError as exc:
        console.print(f"[bold red]Import Error:[/bold red] {exc}")
        console.print(
            '[dim]Make sure required dependencies are installed.'
        )
        raise typer.Exit(1) from exc


@app.command()
def ros2_bridge(
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to ros2_bridge.yaml config file",
    ),
    scene: str = typer.Option(
        None,
        "--scene",
        "-s",
        help="Path to scene JSON file",
    ),
    simulator: str = typer.Option(
        "mujoco",
        "--simulator",
        help="Simulator backend: mujoco or pybullet",
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Run without GUI rendering",
    ),
) -> None:
    """Start ROS2 bridge publisher and subscriber nodes."""
    from surg_rl.ros2 import HAS_ROS2
    from surg_rl.ros2.config import Ros2BridgeConfig

    # macOS guard per D-15
    import platform
    if platform.system() == "Darwin":
        typer.echo(
            "ROS2 bridge is not supported on macOS.\n"
            "Use a Docker Linux container:\n"
            "  docker run -v $(pwd):/workspace ros:humble \\\n"
            "    surg-rl ros2-bridge --config /workspace/ros2_bridge.yaml"
        )
        raise typer.Exit(0)

    if not HAS_ROS2:
        typer.echo(
            "ROS2 not installed. Install via apt:\n"
            "  sudo apt install ros-humble-rclpy ros-humble-sensor-msgs "
            "ros-humble-geometry-msgs ros-humble-std-msgs"
        )
        raise typer.Exit(1)

    # Load config per D-21: user-specified --config path
    if config is None:
        typer.echo("Error: --config is required.", err=True)
        typer.echo("  surg-rl ros2-bridge --config ros2_bridge.yaml")
        raise typer.Exit(1)

    bridge_config = Ros2BridgeConfig.from_yaml(config)
    logger.info("Loaded bridge config: %s", config)

    # Load scene if provided
    if scene is None:
        typer.echo("Error: --scene is required.", err=True)
        raise typer.Exit(1)

    from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
    env_config = SurgicalEnvConfig(
        scene_path=scene,
        simulator_type=simulator,
        render_mode=None if headless else "human",
        ros2_bridge_config=bridge_config,
    )
    env = SurgicalEnv(env_config)

    typer.echo(
        f"ROS2 bridge started:\n"
        f"  Publishing: {bridge_config.state_topic}\n"
        f"  Subscribing: {bridge_config.command_topic}\n"
    )

    # Run env interactively until interrupted
    try:
        import time
        obs, _ = env.reset()
        while True:
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                obs, _ = env.reset()
    except KeyboardInterrupt:
        typer.echo("Shutting down bridge...")
    finally:
        env.close()
        typer.echo("Bridge terminated.")


@app.command()
def ros2_replay(
    checkpoint: str = typer.Option(
        ...,
        "--checkpoint",
        help="Path to SB3 model checkpoint (zip file)",
    ),
    scene: str = typer.Option(
        ...,
        "--scene",
        help="Path to scene JSON file",
    ),
    command_topic: str = typer.Option(
        "/surg_rl/commands",
        "--command-topic",
        help="ROS2 topic to publish actions to",
    ),
    speed: float = typer.Option(
        0.1,
        "--speed",
        min=0.01,
        max=1.0,
        help="Replay speed multiplier (0.01=1%, 0.1=10%, 1.0=full)",
    ),
    simulator: str = typer.Option(
        "mujoco",
        "--simulator",
        help="Simulator backend: mujoco or pybullet",
    ),
    max_steps: int = typer.Option(
        10000,
        "--max-steps",
        help="Maximum replay steps",
    ),
) -> None:
    """Replay a trained SB3 checkpoint at reduced speed through ROS2 bridge."""
    import platform
    if platform.system() == "Darwin":
        typer.echo(
            "ROS2 is not supported on macOS.\n"
            "Use a Docker Linux container:\n"
            "  docker run -v $(pwd):/workspace ros:humble \\\n"
            "    surg-rl ros2-replay --checkpoint /workspace/model.zip "
            "--scene /workspace/scene.json"
        )
        raise typer.Exit(0)

    from surg_rl.ros2.replay import TrajectoryReplay

    try:
        replay = TrajectoryReplay(
            model_path=checkpoint,
            scene_path=scene,
            command_topic=command_topic,
            speed=speed,
            simulator_type=simulator,
        )
    except RuntimeError as exc:
        typer.echo(
            f"ROS2 not installed. Install via apt:\n"
            f"  sudo apt install ros-humble-rclpy ros-humble-std-msgs\n"
            f"\nDetails: {exc}"
        )
        raise typer.Exit(1)

    typer.echo(f"Replaying {checkpoint} at {speed:.0%} speed on {command_topic}")

    try:
        result = replay.run_replay(max_steps=max_steps)
        typer.echo(
            f"Replay complete: {result['steps_executed']} steps "
            f"in {result['total_wall_time']:.1f}s "
            f"(avg {result['avg_step_time']*1000:.1f}ms/step)"
        )
    except KeyboardInterrupt:
        typer.echo("Replay interrupted.")
    finally:
        replay.terminate()


@app.command(name="ros2-control")
def ros2_control(
    scene: str = typer.Argument(..., help="Path to scene definition JSON/YAML"),
    controller_yaml: str = typer.Option(
        "configs/ros2_control.yaml",
        "--controller-yaml",
        help="ros2_control controller configuration YAML",
    ),
    launch_file: str | None = typer.Option(
        None,
        "--launch",
        help="Optional .launch.py file to use instead of direct start",
    ),
):
    """Start bridge with ros2_control hardware interface."""
    from surg_rl.ros2 import HAS_ROS2

    if not HAS_ROS2:
        console.print(
            "[yellow]ROS2 not available on this platform. "
            "Use a Docker Linux container.[/yellow]"
        )
        raise typer.Exit(0)

    if launch_file:
        import subprocess

        subprocess.run(
            ["ros2", "launch", "surg_rl", launch_file], check=True
        )
    else:
        from surg_rl.ros2.hardware_bridge import ControllerBridge
        from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

        config = SurgicalEnvConfig(
            scene_path=scene,
            use_ros2_control=True,
            controller_yaml=controller_yaml,
        )
        env = SurgicalEnv(config)
        try:
            env.reset()
            console.print(
                "[green]ros2_control bridge active. Press Ctrl+C to stop.[/green]"
            )
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            env.close()


if __name__ == "__main__":
    app()
