#!/usr/bin/env python3
"""Basic usage example for Surg-RL.

This example demonstrates:
1. Loading configuration
2. Setting up directories
3. Basic CLI usage
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from surg_rl import __version__, get_settings
from surg_rl.utils.logging import setup_logging


def main():
    """Run basic example."""
    # Set up logging
    logger = setup_logging(level="INFO")
    logger.info(f"Surg-RL version: {__version__}")
    
    # Get settings
    settings = get_settings()
    
    # Ensure directories exist
    settings.ensure_directories()
    logger.info("Project directories created")
    
    # Print configuration
    logger.info("Configuration:")
    logger.info(f"  Project Root: {settings.project_root}")
    logger.info(f"  Default Simulator: {settings.default_simulator}")
    logger.info(f"  LLM Provider: {settings.llm_provider}")
    logger.info(f"  LLM Model: {settings.llm_model}")
    logger.info(f"  Assets Dir: {settings.assets_dir}")
    logger.info(f"  Scenes Dir: {settings.scenes_dir}")
    
    # Example: List available configuration options
    logger.info("\nAvailable configuration options:")
    for field_name, field_info in settings.model_fields.items():
        logger.info(f"  {field_name}: {field_info.default}")
    
    print("\n✓ Setup complete!")
    print("✓ Next steps:")
    print("  1. Copy .env.example to .env and configure API keys")
    print("  2. Run: surg-rl config")
    print("  3. Run: surg-rl setup")


if __name__ == "__main__":
    main()
