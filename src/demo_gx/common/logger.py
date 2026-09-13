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


LOGGER_NAME = "demo_gx"


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Configure and return the ``demo_gx`` logger.

    Writes to stdout and, optionally, appends to a file.  Idempotent per
    handler TYPE: calling again with a ``log_file`` after an earlier
    no-file call still adds the missing file handler (dev-review: a bare
    ``not logger.handlers`` guard would silently skip it).

    Args:
        level (str): Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
            Defaults to ``"INFO"``.
        log_file (str | None): Optional path to a log file.  Parent
            directories are created automatically.  If ``None``, only stdout
            logging is enabled.

    Returns:
        logging.Logger: The configured ``demo_gx`` logger.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    formatter = JsonFormatter()
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    if log_file and not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.propagate = False
    return logger


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return the ``demo_gx`` logger for reuse across modules.

    ``setup_logging`` must be called before the first use of this function
    so that handlers are configured.

    Args:
        name (str): Logger name.  Defaults to ``demo_gx``.

    Returns:
        logging.Logger: The logger instance.
    """
    return logging.getLogger(name)
