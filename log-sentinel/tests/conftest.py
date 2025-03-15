"""Shared test fixtures for log-sentinel."""

from __future__ import annotations

import json
import logging
import time

import pytest

from log_sentinel.metrics import MetricsRegistry


@pytest.fixture
def sample_json_logs(tmp_path):
    """Create a temporary log file with JSON-structured entries."""
    log_file = tmp_path / "test.log"
    entries = [
        {"timestamp": time.time() - 60, "level": "INFO", "logger_name": "app", "message": "Starting up", "context": {"service_name": "test"}},
        {"timestamp": time.time() - 50, "level": "INFO", "logger_name": "app.db", "message": "Connected to database", "context": {}},
        {"timestamp": time.time() - 40, "level": "WARNING", "logger_name": "app.cache", "message": "Cache miss rate high", "context": {}},
        {"timestamp": time.time() - 30, "level": "ERROR", "logger_name": "app.api", "message": "Request failed: timeout", "context": {"endpoint": "/data"}},
        {"timestamp": time.time() - 20, "level": "ERROR", "logger_name": "app.api", "message": "Request failed: 503", "context": {"endpoint": "/query"}},
        {"timestamp": time.time() - 10, "level": "INFO", "logger_name": "app", "message": "Health check OK", "context": {}},
        {"timestamp": time.time() - 5, "level": "CRITICAL", "logger_name": "app.db", "message": "Connection pool exhausted", "context": {}},
        {"timestamp": time.time(), "level": "INFO", "logger_name": "app", "message": "Processing batch", "context": {"batch_size": 500}},
    ]
    lines = [json.dumps(e) for e in entries]
    log_file.write_text("\n".join(lines) + "\n")
    return log_file


@pytest.fixture(autouse=True)
def _reset_metrics_registry():
    """Ensure each test gets a fresh MetricsRegistry."""
    MetricsRegistry.reset()
    yield
    MetricsRegistry.reset()


@pytest.fixture(autouse=True)
def _clean_loggers():
    """Remove handlers added during tests to avoid cross-test leaks."""
    yield
    for name in list(logging.Logger.manager.loggerDict):
        logger = logging.getLogger(name)
        logger.handlers.clear()
