"""Tests for report generation in JSON, Markdown, and HTML formats."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from health_checker.models import HealthReport, Status
from health_checker.reporter import (
    generate_html,
    generate_json,
    generate_markdown,
    write_report,
)


class TestGenerateJson:
    def test_valid_json(self, sample_report: HealthReport) -> None:
        output = generate_json(sample_report)
        data = json.loads(output)
        assert data["overall_status"] == "CRITICAL"
        assert data["summary"]["total"] == 3
        assert data["summary"]["ok"] == 1

    def test_all_fields_present(self, sample_report: HealthReport) -> None:
        data = json.loads(generate_json(sample_report))
        assert "generated_at" in data
        assert "hostname" in data
        assert "checks" in data
        for check in data["checks"]:
            assert "check" in check
            assert "status" in check
            assert "value" in check

    def test_empty_report(self) -> None:
        report = HealthReport(results=[], hostname="empty")
        data = json.loads(generate_json(report))
        assert data["overall_status"] == "OK"
        assert data["summary"]["total"] == 0


class TestGenerateMarkdown:
    def test_contains_table(self, sample_report: HealthReport) -> None:
        md = generate_markdown(sample_report)
        assert "| Check |" in md
        assert "| cpu |" in md
        assert "| memory |" in md
        assert "| disk |" in md

    def test_contains_header(self, sample_report: HealthReport) -> None:
        md = generate_markdown(sample_report)
        assert "# Health Report" in md
        assert "test-host" in md

    def test_contains_details(self, sample_report: HealthReport) -> None:
        md = generate_markdown(sample_report)
        assert "### cpu" in md
        assert "```json" in md


class TestGenerateHtml:
    def test_contains_html_structure(self, sample_report: HealthReport) -> None:
        html = generate_html(sample_report)
        assert "<!DOCTYPE html>" in html
        assert "<table" in html
        assert "test-host" in html

    def test_contains_status_badges(self, sample_report: HealthReport) -> None:
        html = generate_html(sample_report)
        assert "status-OK" in html
        assert "status-WARNING" in html
        assert "status-CRITICAL" in html

    def test_contains_javascript(self, sample_report: HealthReport) -> None:
        html = generate_html(sample_report)
        assert "toggleDetails" in html


class TestWriteReport:
    def test_write_to_file(self, sample_report: HealthReport, tmp_path: Path) -> None:
        out = tmp_path / "report.json"
        write_report(sample_report, "json", out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["hostname"] == "test-host"

    def test_write_html_to_file(self, sample_report: HealthReport, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        write_report(sample_report, "html", out)
        assert out.exists()
        assert "<html" in out.read_text()

    def test_write_markdown_to_file(self, sample_report: HealthReport, tmp_path: Path) -> None:
        out = tmp_path / "report.md"
        write_report(sample_report, "markdown", out)
        assert out.exists()
        assert "# Health Report" in out.read_text()

    def test_returns_content_without_output(self, sample_report: HealthReport) -> None:
        content = write_report(sample_report, "json")
        assert json.loads(content)["hostname"] == "test-host"

    def test_unknown_format_raises(self, sample_report: HealthReport) -> None:
        with pytest.raises(ValueError, match="Unknown format"):
            write_report(sample_report, "xml")

    def test_creates_parent_dirs(self, sample_report: HealthReport, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "deep" / "report.json"
        write_report(sample_report, "json", out)
        assert out.exists()
