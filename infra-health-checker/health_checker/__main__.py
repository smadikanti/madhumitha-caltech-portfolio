"""CLI entry point: python -m health_checker"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from .alerting import AlertEngine
from .config import Config
from .models import Status
from .reporter import write_report
from .runner import run_checks

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CHECKS_DIR = _PROJECT_ROOT / "checks"

_STATUS_COLORS = {
    Status.OK: "\033[32m",
    Status.WARNING: "\033[33m",
    Status.CRITICAL: "\033[31m",
    Status.ERROR: "\033[35m",
}
_RESET = "\033[0m"


def _colored(text: str, status: Status) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{_STATUS_COLORS.get(status, '')}{text}{_RESET}"


def _find_config() -> Path | None:
    candidates = [
        Path("config.yaml"),
        _PROJECT_ROOT / "config.yaml",
        Path.home() / ".config" / "health-checker" / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def cmd_run(args: argparse.Namespace) -> int:
    """Run health checks and display results."""
    config = Config.load(args.config or _find_config())
    selected = [s.strip() for s in args.check.split(",")] if args.check else None

    report = run_checks(
        checks_dir=Path(args.checks_dir),
        config=config,
        selected=selected,
        max_workers=args.parallel,
        timeout=args.timeout,
    )

    print(f"\n{'='*60}")
    print(f"  Health Report — {report.hostname}")
    print(f"  {report.generated_at}")
    print(f"{'='*60}\n")

    for r in report.results:
        tag = _colored(f"[{r.status.value:>8}]", r.status)
        duration = f" ({r.duration_ms:.0f}ms)" if r.duration_ms else ""
        print(f"  {tag}  {r.check:<14} {r.message}{duration}")

    overall = report.overall_status
    print(f"\n  Overall: {_colored(overall.value, overall)}")
    print(
        f"  {report.ok_count} OK · {report.warning_count} Warning · "
        f"{report.critical_count} Critical · {report.error_count} Error\n"
    )

    if not args.no_alert:
        engine = AlertEngine(config)
        alerts = engine.evaluate(report)
        if alerts:
            receipts = engine.notify(alerts)
            for receipt in receipts:
                status = "sent" if receipt["success"] else "FAILED"
                print(f"  Webhook {receipt['url']}: {status}")

    return 2 if overall == Status.CRITICAL else (1 if overall == Status.WARNING else 0)


def cmd_report(args: argparse.Namespace) -> int:
    """Run checks and generate a report file."""
    config = Config.load(args.config or _find_config())
    selected = [s.strip() for s in args.check.split(",")] if args.check else None

    report = run_checks(
        checks_dir=Path(args.checks_dir),
        config=config,
        selected=selected,
        max_workers=args.parallel,
        timeout=args.timeout,
    )

    output_path = Path(args.output) if args.output else None
    content = write_report(report, args.format, output_path)

    if output_path:
        print(f"Report written to {output_path}")
    else:
        print(content)

    return 0


def cmd_cron_setup(args: argparse.Namespace) -> int:
    """Install or remove a cron job for periodic health checks."""
    marker = "# infra-health-checker"
    python = sys.executable
    module_cmd = f"{python} -m health_checker report --format json"

    if args.output_dir:
        output_dir = Path(args.output_dir)
        module_cmd += f' --output "{output_dir}/health-$(date +%Y%m%d-%H%M%S).json"'

    cron_line = f"*/{args.interval} * * * * {module_cmd} {marker}"

    try:
        existing = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        ).stdout
    except FileNotFoundError:
        print("crontab command not found", file=sys.stderr)
        return 1

    filtered = "\n".join(
        line for line in existing.splitlines() if marker not in line
    )

    if args.remove:
        new_crontab = filtered.rstrip() + "\n" if filtered.strip() else ""
        action = "Removed"
    else:
        new_crontab = (filtered.rstrip() + "\n" + cron_line + "\n") if filtered.strip() else cron_line + "\n"
        action = "Installed"

    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        print(f"Failed to update crontab: {proc.stderr}", file=sys.stderr)
        return 1

    print(f"{action} cron job (every {args.interval} min)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="health_checker",
        description="Infrastructure health monitoring toolkit",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml (auto-detected if omitted)",
    )
    parser.add_argument(
        "--checks-dir",
        default=str(_CHECKS_DIR),
        help="Directory containing check scripts",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run health checks")
    run_parser.add_argument("--check", help="Comma-separated list of checks to run")
    run_parser.add_argument("--parallel", type=int, default=8, help="Max parallel checks")
    run_parser.add_argument("--timeout", type=int, default=30, help="Per-check timeout in seconds")
    run_parser.add_argument("--no-alert", action="store_true", help="Skip alerting")

    report_parser = subparsers.add_parser("report", help="Generate a health report")
    report_parser.add_argument(
        "--format", "-f",
        choices=["html", "json", "markdown"],
        default="json",
    )
    report_parser.add_argument("--output", "-o", help="Output file path")
    report_parser.add_argument("--check", help="Comma-separated list of checks to run")
    report_parser.add_argument("--parallel", type=int, default=8)
    report_parser.add_argument("--timeout", type=int, default=30)

    cron_parser = subparsers.add_parser("cron-setup", help="Install/remove cron job")
    cron_parser.add_argument("--interval", type=int, default=5, help="Run every N minutes")
    cron_parser.add_argument("--output-dir", help="Directory for report output")
    cron_parser.add_argument("--remove", action="store_true", help="Remove the cron entry")

    args = parser.parse_args(argv)

    handlers = {
        "run": cmd_run,
        "report": cmd_report,
        "cron-setup": cmd_cron_setup,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
