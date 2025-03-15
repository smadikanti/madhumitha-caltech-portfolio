"""Log line parsers for JSON, syslog, and auto-detection."""

from __future__ import annotations

import json
import re
import time
from typing import Callable

from .models import LogEntry

_SYSLOG_RE = re.compile(
    r"^(?:<\d+>)?"
    r"(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<app>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
    r"(?P<message>.*)$"
)

_LEVEL_KEYWORDS: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "WARN": "WARNING",
    "ERROR": "ERROR",
    "ERR": "ERROR",
    "CRITICAL": "CRITICAL",
    "FATAL": "CRITICAL",
    "CRIT": "CRITICAL",
}


def parse_json_line(line: str) -> LogEntry | None:
    """Parse a JSON-structured log line into a LogEntry."""
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    ts_raw = data.get("timestamp") or data.get("ts") or data.get("time")
    timestamp = _parse_timestamp(ts_raw) if ts_raw else time.time()

    level = str(data.get("level", data.get("severity", "INFO"))).upper()
    level = _LEVEL_KEYWORDS.get(level, level)

    logger_name = str(data.get("logger_name", data.get("logger", data.get("name", ""))))
    message = str(data.get("message", data.get("msg", "")))

    context = data.get("context", {})
    if not isinstance(context, dict):
        context = {}

    return LogEntry(
        timestamp=timestamp,
        level=level,
        logger_name=logger_name,
        message=message,
        context=context,
    )


def parse_syslog_line(line: str) -> LogEntry | None:
    """Parse a syslog-formatted line (RFC 3164) into a LogEntry."""
    line = line.strip()
    if not line:
        return None

    match = _SYSLOG_RE.match(line)
    if not match:
        return None

    ts_str = match.group("timestamp")
    try:
        ts_struct = time.strptime(ts_str, "%b %d %H:%M:%S")
        now = time.localtime()
        timestamp = time.mktime(ts_struct[:5] + (now.tm_year,) + ts_struct[6:])
    except ValueError:
        timestamp = time.time()

    message = match.group("message")
    level = _infer_level(message)
    logger_name = match.group("app") or ""

    context: dict[str, object] = {}
    hostname = match.group("hostname")
    if hostname:
        context["hostname"] = hostname
    pid = match.group("pid")
    if pid:
        context["pid"] = int(pid)

    return LogEntry(
        timestamp=timestamp,
        level=level,
        logger_name=logger_name,
        message=message,
        context=context,
    )


def parse_auto(line: str) -> LogEntry | None:
    """Try JSON first, then syslog, then fall back to a plain-text entry."""
    entry = parse_json_line(line)
    if entry is not None:
        return entry

    entry = parse_syslog_line(line)
    if entry is not None:
        return entry

    return _parse_plain(line)


def _parse_plain(line: str) -> LogEntry | None:
    line = line.strip()
    if not line:
        return None
    level = _infer_level(line)
    return LogEntry(
        timestamp=time.time(),
        level=level,
        logger_name="",
        message=line,
    )


def _infer_level(text: str) -> str:
    upper = text.upper()
    for keyword, level in _LEVEL_KEYWORDS.items():
        if keyword in upper:
            return level
    return "INFO"


def _parse_timestamp(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return time.mktime(time.strptime(value, fmt))
        except ValueError:
            continue
    return time.time()


ParserFunc = Callable[[str], LogEntry | None]
