"""Logging configuration."""

import logging
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from surg_rl.utils.config import get_settings


class SensitiveDataFilter(logging.Filter):
    """Masks API keys in log records."""

    # Pattern matches OpenAI sk-... and Anthropic sk-ant-... keys
    _PATTERN = re.compile(
        r"(sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9-]{20,})"
    )

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in the log record.

        Always returns True so the record is not dropped.
        """
        if isinstance(record.msg, str):
            record.msg = self._mask(record.msg)
        if record.args:
            record.args = tuple(
                self._mask(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    @classmethod
    def _mask(cls, text: str) -> str:
        """Replace API keys with **** + last 4 characters."""

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            if len(key) <= 4:
                return "****"
            return f"****{key[-4:]}"

        return cls._PATTERN.sub(replacer, text)


def setup_logging(
    level: str | None = None,
    log_file: Path | None = None,
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

    # Validate log level
    log_level_upper = (log_level or "INFO").upper()
    level_value = getattr(logging, log_level_upper, None)
    if level_value is None or not isinstance(level_value, int):
        raise ValueError(
            f"Invalid log level: {log_level!r}. "
            f"Use one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        )

    # Create logger
    logger = logging.getLogger("surg_rl")
    logger.setLevel(level_value)

    # Remove and close existing handlers to prevent file descriptor leaks
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

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

    handler.setLevel(level_value)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)

    # File handler (optional)
    if file_path:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(level_value)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
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
