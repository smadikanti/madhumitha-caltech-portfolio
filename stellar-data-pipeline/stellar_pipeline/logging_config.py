"""Structured logging configuration for the stellar data pipeline.

Provides a human-readable console handler and a JSON-structured file
handler, with support for injecting pipeline run metadata into log records.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
        }
        if hasattr(record, "run_id"):
            entry["run_id"] = str(record.run_id)
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


CONSOLE_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
CONSOLE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_file: Optional[str] = None,
    log_level: str = "INFO",
) -> None:
    """Configure root logger with console and optional file handlers.

    Args:
        log_file: Path to the log file. If None, only console output is used.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        root.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATE_FORMAT)
    )
    root.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)


class PipelineLogger(logging.LoggerAdapter):
    """Logger adapter that injects run_id into every log record."""

    def __init__(self, logger: logging.Logger, run_id: str) -> None:
        super().__init__(logger, {"run_id": run_id})

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        extra["run_id"] = self.extra["run_id"]
        kwargs["extra"] = extra
        return msg, kwargs
