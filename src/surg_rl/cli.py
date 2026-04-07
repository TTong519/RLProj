"""Command-line interface for Surg-RL."""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from surg_rl import __version__
from surg_rl.utils.config import get_settings
from surg_rl.utils.logging import get_logger
from surg_rl.scene_generation import TextParser, VisionParser, SceneComposer, get_template

logger = get_logger(__name__)

app = typer.Typer(
    name="surg-rl",
    help="Surgical Robotics RL Training System",
    add_completion=False,
)

console = Console()


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"[bold blue]Surg-RL[/bold blue] version: [green]{__version__}[/green]")


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Display key settings
    config_items = [
        ("Version", __version__),
        ("Project Root", str(settings.project_root)),
        ("Default Simulator", settings.default_simulator),
        ("", ""),  # Separator
        ("LLM Provider", settings.llm_provider),
        ("LLM Model", settings.llm_model),
        ("VLM Model", settings.vlm_model),
        ("", ""),  # Separator
        ("Ollama Base URL", settings.ollama_base_url),
        ("Ollama Model", settings.ollama_model),
        ("Ollama Vision Model", settings.ollama_vision_model),
        ("Ollama Timeout", f"{settings.ollama_timeout}s"),
        ("", ""),  # Separator
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
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider (openai, anthropic, ollama)"),
    model: str = typer.Option(None, "--model", "-m", help="Model name to use"),
    ollama_url: str = typer.Option(None, "--ollama-url", help="Ollama API base URL (for ollama provider)"),
) -> None:
    """Generate a scene from text, image, or template input.

    Uses LLM/VLM to convert natural language descriptions or images into
    structured scene definitions for surgical robotics simulation.

    Supports multiple providers:
    - openai: OpenAI GPT models (requires OPENAI_API_KEY)
    - anthropic: Anthropic Claude models (requires ANTHROPIC_API_KEY)
    - ollama: Local models via Ollama (requires Ollama server running)

    Examples:
        surg-rl generate --text "Create a suturing scene with two robotic arms"
        surg-rl generate --image surgical_scene.jpg --output scene.json
        surg-rl generate --template suturing --output my_suturing.json
        surg-rl generate --text "Simple scene" --provider ollama --model llama3.2
        surg-rl generate --text "Scene description" --provider ollama --ollama-url http://localhost:11434
    """
    try:
        # Handle template generation (no LLM needed)
        if template:
            console.print(f"[bold blue]Loading template:[/bold blue] {template}")
            try:
                scene = get_template(template)
            except ValueError as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                console.print("[dim]Available templates: suturing, dissection, manipulation[/dim]")
                raise typer.Exit(1)

            # Save the scene
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml
                content = yaml.dump(scene.model_dump(), default_flow_style=False)
            else:
                content = json.dumps(scene.model_dump(), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        # Handle text generation
        if text:
            console.print(f"[bold blue]Generating scene from text...[/bold blue]")
            console.print(f"[dim]Provider: {provider or 'default'}[/dim]")
            console.print(f"[dim]Description: {text[:100]}{'...' if len(text) > 100 else ''}[/dim]")

            # Create parser with specified provider
            parser = TextParser(
                provider=provider,
                model=model,
                ollama_base_url=ollama_url,
            )

            # Run async parse
            scene = asyncio.run(parser.parse(text))

            # Save the scene
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml
                content = yaml.dump(scene.model_dump(), default_flow_style=False)
            else:
                content = json.dumps(scene.model_dump(), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        # Handle image generation
        if image:
            console.print("[bold blue]Generating scene from image...[/bold blue]")
            console.print(f"[dim]Provider: {provider or 'default'}[/dim]")
            console.print(f"[dim]Image: {image}[/dim]")

            # Create parser with specified provider
            parser = VisionParser(
                provider=provider,
                model=model,
                ollama_base_url=ollama_url,
            )

            # Run async parse
            scene = asyncio.run(parser.parse(image))

            # Save the scene
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml
                content = yaml.dump(scene.model_dump(), default_flow_style=False)
            else:
                content = json.dumps(scene.model_dump(), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        # No input provided
        console.print("[bold red]Error:[/bold red] No input provided.")
        console.print("[dim]Use --text, --image, or --template to specify input.[/dim]")
        console.print("")
        console.print("[bold]Examples:[/bold]")
        console.print("  surg-rl generate --template suturing --output scene.json")
        console.print("  surg-rl generate --text 'Create a suturing scene' --provider ollama")
        console.print("  surg-rl generate --image scene.jpg --provider openai")
        raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Scene generation failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def train(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    algorithm: str = typer.Option("PPO", "--algorithm", "-a", help="RL algorithm"),
    timesteps: int = typer.Option(100000, "--timesteps", "-t", help="Training timesteps"),
) -> None:
    """Train an RL agent on a scene.

    This command will be implemented in Step 7 (RL Training Pipeline).
    """
    console.print("[yellow]Training not yet implemented.[/yellow]")
    console.print("[yellow]This feature will be available after Step 7.[/yellow]")
    console.print(f"[dim]Scene: {scene}[/dim]")
    console.print(f"[dim]Algorithm: {algorithm}[/dim]")
    console.print(f"[dim]Timesteps: {timesteps}[/dim]")


@app.command()
def evaluate(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    model: str = typer.Option(..., "--model", "-m", help="Path to trained model"),
    episodes: int = typer.Option(10, "--episodes", "-e", help="Number of episodes"),
) -> None:
    """Evaluate a trained agent.

    This command will be implemented in Step 7 (RL Training Pipeline).
    """
    console.print("[yellow]Evaluation not yet implemented.[/yellow]")
    console.print("[yellow]This feature will be available after Step 7.[/yellow]")
    console.print(f"[dim]Scene: {scene}[/dim]")
    console.print(f"[dim]Model: {model}[/dim]")
    console.print(f"[dim]Episodes: {episodes}[/dim]")


if __name__ == "__main__":
    app()
