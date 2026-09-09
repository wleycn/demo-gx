"""Structured logging utilities for the pipeline.

Provides a JSON-formatted logger that outputs one JSON object per log line,
facilitating log aggregation and auditing.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Logging formatter that emits each record as a single-line JSON object.

    Each log line contains ``timestamp``, ``level``, ``logger`` name, and
    ``message`` fields.  When exception info is attached, it is included
    under the ``exc_info`` key.  This structured format simplifies collection
    and auditing.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into a JSON string.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: A single-line JSON representation of the log record.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Configure and return the ``pipeline`` logger.

    The logger writes to stdout and, optionally, appends to a file.  The
    function is idempotent: calling it multiple times will not duplicate
    handlers.

    Args:
        level (str): Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
            Defaults to ``"INFO"``.
        log_file (str | None): Optional path to a log file.  Parent
            directories are created automatically.  If ``None``, only stdout
            logging is enabled.

    Returns:
        logging.Logger: The configured ``pipeline`` logger.
    """
    logger = logging.getLogger("pipeline")
    logger.setLevel(level.upper())
    # Idempotent: skip if handlers already exist, avoiding duplicate output
    if not logger.handlers:
        formatter = JsonFormatter()
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        logger.propagate = False
    return logger


def get_logger(name: str = "pipeline") -> logging.Logger:
    """Return the pipeline logger for reuse across modules.

    ``setup_logging`` must be called before the first use of this function
    so that handlers are configured.

    Args:
        name (str): Logger name.  Defaults to ``"pipeline"``.

    Returns:
        logging.Logger: The logger instance.
    """
    return logging.getLogger(name)
