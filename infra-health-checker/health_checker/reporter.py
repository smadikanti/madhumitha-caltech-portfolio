"""Report generation in HTML, JSON, and Markdown formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import HealthReport, Status


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _status_color(status: str) -> str:
    return {
        "OK": "#22c55e",
        "WARNING": "#eab308",
        "CRITICAL": "#ef4444",
        "ERROR": "#a855f7",
    }.get(status, "#6b7280")


def _status_emoji(status: str) -> str:
    return {
        "OK": "✅",
        "WARNING": "⚠️",
        "CRITICAL": "🔴",
        "ERROR": "❌",
    }.get(status, "❓")


def generate_json(report: HealthReport) -> str:
    """Serialize a health report to pretty-printed JSON."""
    return json.dumps(report.to_dict(), indent=2, default=str)


def generate_markdown(report: HealthReport) -> str:
    """Render a health report as Markdown text."""
    lines: list[str] = []
    overall = report.overall_status.value
    lines.append(f"# Health Report — {overall}")
    lines.append("")
    lines.append(f"**Host:** {report.hostname}  ")
    lines.append(f"**Generated:** {report.generated_at}  ")
    lines.append(
        f"**Summary:** {report.ok_count} OK · {report.warning_count} Warning · "
        f"{report.critical_count} Critical · {report.error_count} Error"
    )
    lines.append("")
    lines.append("| Check | Status | Value | Threshold | Message | Duration |")
    lines.append("|-------|--------|-------|-----------|---------|----------|")

    for r in report.results:
        emoji = _status_emoji(r.status.value)
        duration = f"{r.duration_ms:.0f}ms" if r.duration_ms else "—"
        lines.append(
            f"| {r.check} | {emoji} {r.status.value} | {r.value} | {r.threshold} "
            f"| {r.message} | {duration} |"
        )

    lines.append("")

    for r in report.results:
        if r.details:
            lines.append(f"### {r.check} — details")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(r.details, indent=2, default=str))
            lines.append("```")
            lines.append("")

    return "\n".join(lines)


def generate_html(report: HealthReport, template_dir: Path | None = None) -> str:
    """Render a health report as an HTML page via Jinja2."""
    tpl_dir = template_dir or _TEMPLATE_DIR
    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["status_color"] = _status_color
    env.filters["status_emoji"] = _status_emoji
    env.globals["json_dumps"] = lambda obj: json.dumps(obj, indent=2, default=str)

    template = env.get_template("report.html")
    return template.render(report=report)


def write_report(
    report: HealthReport,
    fmt: str,
    output: Path | TextIO | None = None,
) -> str:
    """Generate a report in the requested format and optionally write to a file or stream."""
    generators = {
        "json": generate_json,
        "markdown": generate_markdown,
        "html": generate_html,
    }

    generator = generators.get(fmt)
    if generator is None:
        raise ValueError(f"Unknown format {fmt!r}. Choose from: {', '.join(generators)}")

    content = generator(report)

    if output is None:
        return content

    if isinstance(output, Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    else:
        output.write(content)

    return content
