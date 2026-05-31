"""
Yapper Logging Infrastructure
=============================
Centralized logging setup for file and console output.

© 2026 Cloudelipute
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Module-level logger cache
_loggers: dict = {}
_initialized: bool = False

# Log directory (relative to app folder)
_LOG_DIR: Optional[Path] = None


def setup_logging(
    log_dir: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    log_format: Optional[str] = None
) -> Path:
    """
    Initialize logging infrastructure.

    Args:
        log_dir: Directory for log files. Defaults to 'logs/' next to app folder.
        console_level: Logging level for console output.
        file_level: Logging level for file output.
        log_format: Custom log format string.

    Returns:
        Path to the log directory.
    """
    global _LOG_DIR, _initialized

    if _initialized:
        return _LOG_DIR

    # Determine log directory
    if log_dir is None:
        # Default: logs/ directory in the project root
        app_dir = Path(__file__).parent.parent.resolve()
        log_dir = app_dir.parent / "logs"

    _LOG_DIR = log_dir
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create log file with date stamp
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = _LOG_DIR / f"yapper_{date_str}.log"

    # Default format
    if log_format is None:
        log_format = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"

    # Configure root logger
    root_logger = logging.getLogger("yapper")
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(log_format, datefmt="%H:%M:%S"))
    root_logger.addHandler(console_handler)

    # File handler
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(file_handler)
    except (IOError, OSError) as e:
        root_logger.warning(f"Could not create log file: {e}")

    _initialized = True
    root_logger.info(f"Logging initialized. Log file: {log_file}")

    return _LOG_DIR


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically module name like 'audio', 'transcriber').

    Returns:
        Configured logger instance.
    """
    global _loggers

    full_name = f"yapper.{name}" if not name.startswith("yapper.") else name

    if full_name not in _loggers:
        _loggers[full_name] = logging.getLogger(full_name)

    return _loggers[full_name]


def set_console_level(level: int) -> None:
    """
    Change console logging level at runtime.

    Args:
        level: New logging level (e.g., logging.DEBUG, logging.WARNING).
    """
    root_logger = logging.getLogger("yapper")
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.setLevel(level)
            break


def disable_console_logging() -> None:
    """Disable console output (useful for GUI mode)."""
    set_console_level(logging.CRITICAL + 1)


def enable_console_logging(level: int = logging.INFO) -> None:
    """Re-enable console output."""
    set_console_level(level)
