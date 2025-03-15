"""Tests for the structured JSON logger."""

from __future__ import annotations

import io
import json
import logging
import sys

from log_sentinel.structured_logger import ContextLogger, StructuredFormatter, get_logger


class TestStructuredFormatter:
    def test_format_produces_valid_json(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed

    def test_format_includes_default_context(self):
        formatter = StructuredFormatter(default_context={"service": "myapp"})
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["context"]["service"] == "myapp"

    def test_format_includes_exception(self):
        formatter = StructuredFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="failed", args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["exception"]["type"] == "ValueError"
        assert "boom" in parsed["exception"]["message"]

    def test_timestamp_format(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="ts", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        ts = parsed["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts

    def test_record_context_merges_with_default(self):
        formatter = StructuredFormatter(default_context={"env": "prod"})
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        record.context = {"request_id": "abc"}  # type: ignore[attr-defined]
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["context"]["env"] == "prod"
        assert parsed["context"]["request_id"] == "abc"


class TestContextLogger:
    def test_creates_logger_with_context(self):
        logger = get_logger("test.ctx1", service_name="svc", run_id="abc123")
        assert logger._context["service_name"] == "svc"
        assert logger._context["run_id"] == "abc123"
        assert "hostname" in logger._context

    def test_writes_json_to_stream(self):
        buf = io.StringIO()
        logger = get_logger("test.stream1", stream=buf, service_name="demo")
        logger.info("hello")
        output = buf.getvalue()
        parsed = json.loads(output.strip())
        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"

    def test_writes_to_file(self, tmp_path):
        log_file = tmp_path / "out.log"
        logger = get_logger("test.file1", file_path=str(log_file), service_name="demo")
        logger.warning("disk full")
        content = log_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["level"] == "WARNING"
        assert parsed["message"] == "disk full"

    def test_bind_adds_context(self):
        buf = io.StringIO()
        logger = get_logger("test.bind1", stream=buf, run_id="x")
        child = logger.bind(request_id="r123")
        child.info("handled")
        parsed = json.loads(buf.getvalue().strip())
        assert parsed["context"]["request_id"] == "r123"
        assert parsed["context"]["run_id"] == "x"

    def test_error_with_exc_info(self):
        buf = io.StringIO()
        logger = get_logger("test.exc1", stream=buf)
        try:
            raise RuntimeError("test error")
        except RuntimeError:
            logger.error("caught", exc_info=sys.exc_info())
        parsed = json.loads(buf.getvalue().strip())
        assert parsed["exception"]["type"] == "RuntimeError"

    def test_all_levels(self):
        buf = io.StringIO()
        logger = get_logger("test.levels1", stream=buf, level=logging.DEBUG)
        logger.debug("d")
        logger.info("i")
        logger.warning("w")
        logger.error("e")
        logger.critical("c")
        lines = [json.loads(line) for line in buf.getvalue().strip().split("\n")]
        levels = [l["level"] for l in lines]
        assert levels == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_auto_run_id(self):
        buf = io.StringIO()
        logger = get_logger("test.autorun1", stream=buf)
        assert "run_id" in logger._context
        assert len(logger._context["run_id"]) == 12

    def test_name_property(self):
        logger = get_logger("test.name1")
        assert logger.name == "test.name1"
