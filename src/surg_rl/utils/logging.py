"""Logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from surg_rl.utils.config import get_settings


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    rich_output: bool = True,
) -> logging.Logger:
    """Set up logging with optional rich formatting.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to log to
        rich_output: Whether to use rich formatting

    Returns:
        Configured logger instance
    """
    settings = get_settings()

    # Use provided values or fall back to settings
    log_level = level or settings.log_level
    file_path = log_file or settings.log_file

    # Create logger
    logger = logging.getLogger("surg_rl")
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    if rich_output:
        console = Console(stderr=True)
        handler = RichHandler(
            console=console,
            show_path=True,
            show_time=True,
            rich_tracebacks=True,
        )
    else:
        handler = logging.StreamHandler(sys.stderr)

    handler.setLevel(getattr(logging, log_level))
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # File handler (optional)
    if file_path:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "surg_rl") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
