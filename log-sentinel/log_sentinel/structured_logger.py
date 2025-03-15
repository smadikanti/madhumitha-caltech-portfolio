"""Structured JSON logging — drop-in enhancement for Python's logging module."""

from __future__ import annotations

import json
import logging
import socket
import sys
import time
import traceback
import uuid
from typing import Any, TextIO


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Each line contains: timestamp, level, logger_name, message, and an
    optional context dict carrying structured metadata like run_id,
    service_name, and hostname.
    """

    def __init__(self, default_context: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._default_context = default_context or {}

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": self._iso_timestamp(record.created),
            "level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
        }

        context = {**self._default_context}
        record_ctx = getattr(record, "context", None)
        if isinstance(record_ctx, dict):
            context.update(record_ctx)
        if context:
            entry["context"] = context

        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        if record.stack_info:
            entry["stack_info"] = record.stack_info

        return json.dumps(entry, default=str)

    @staticmethod
    def _iso_timestamp(epoch: float) -> str:
        millis = int(epoch * 1000) % 1000
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch)) + f".{millis:03d}Z"


class ContextLogger:
    """Wraps a stdlib logger to inject structured context into every record."""

    def __init__(self, logger: logging.Logger, context: dict[str, Any]) -> None:
        self._logger = logger
        self._context = dict(context)

    @property
    def name(self) -> str:
        return self._logger.name

    def _log(self, level: int, msg: str, exc_info: Any = None, **extra_context: Any) -> None:
        if not self._logger.isEnabledFor(level):
            return
        merged = {**self._context, **extra_context}
        self._logger.log(level, msg, exc_info=exc_info, extra={"context": merged})

    def debug(self, msg: str, **ctx: Any) -> None:
        self._log(logging.DEBUG, msg, **ctx)

    def info(self, msg: str, **ctx: Any) -> None:
        self._log(logging.INFO, msg, **ctx)

    def warning(self, msg: str, **ctx: Any) -> None:
        self._log(logging.WARNING, msg, **ctx)

    def error(self, msg: str, exc_info: Any = None, **ctx: Any) -> None:
        self._log(logging.ERROR, msg, exc_info=exc_info, **ctx)

    def critical(self, msg: str, exc_info: Any = None, **ctx: Any) -> None:
        self._log(logging.CRITICAL, msg, exc_info=exc_info, **ctx)

    def bind(self, **extra_context: Any) -> ContextLogger:
        """Return a new ContextLogger with additional context fields merged in."""
        merged = {**self._context, **extra_context}
        return ContextLogger(self._logger, merged)


def get_logger(
    name: str,
    *,
    level: int = logging.INFO,
    stream: TextIO | None = None,
    file_path: str | None = None,
    run_id: str | None = None,
    service_name: str | None = None,
    **extra_context: Any,
) -> ContextLogger:
    """Create a structured JSON logger.

    Args:
        name: Logger name (typically ``__name__``).
        level: Minimum log level.
        stream: Output stream. Defaults to ``sys.stderr`` when no *file_path*
            is given.
        file_path: Optional path to a file for log output.
        run_id: Unique run identifier. Auto-generated if omitted.
        service_name: Service or application name.
        **extra_context: Additional fields attached to every log record.

    Returns:
        A ``ContextLogger`` that emits structured JSON.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    context: dict[str, Any] = {
        "hostname": socket.gethostname(),
    }
    if run_id or "run_id" not in extra_context:
        context["run_id"] = run_id or uuid.uuid4().hex[:12]
    if service_name:
        context["service_name"] = service_name
    context.update(extra_context)

    formatter = StructuredFormatter(default_context=context)

    if not logger.handlers:
        if stream is not None or file_path is None:
            sh = logging.StreamHandler(stream or sys.stderr)
            sh.setFormatter(formatter)
            logger.addHandler(sh)

        if file_path:
            fh = logging.FileHandler(file_path)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    return ContextLogger(logger, context)
