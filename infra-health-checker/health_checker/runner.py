"""Check discovery and parallel execution engine."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from .config import Config
from .models import CheckResult, HealthReport, Status


def discover_checks(checks_dir: Path) -> list[Path]:
    """Find all executable .sh scripts in the checks directory."""
    if not checks_dir.is_dir():
        return []
    scripts = sorted(checks_dir.glob("*.sh"))
    return [s for s in scripts if s.is_file()]


def _build_env(config: Config, check_name: str) -> dict[str, str]:
    """Build environment variables to pass configuration into a check script."""
    env = os.environ.copy()

    if check_name == "network":
        net = config.network
        env["PING_TARGETS"] = ",".join(net.get("ping_targets", []))
        env["DNS_TARGETS"] = ",".join(net.get("dns_targets", []))
        port_checks = net.get("port_checks", [])
        env["PORT_CHECKS"] = ",".join(
            f"{p['host']}:{p['port']}" for p in port_checks if isinstance(p, dict)
        )

    elif check_name == "processes":
        procs = config.processes
        env["CRITICAL_PROCESSES"] = ",".join(procs.get("critical", []))

    elif check_name == "postgres":
        pg = config.postgres
        env["PG_HOST"] = str(pg.get("host", "localhost"))
        env["PG_PORT"] = str(pg.get("port", 5432))
        env["PG_USER"] = str(pg.get("user", "postgres"))
        env["PG_DBNAME"] = str(pg.get("dbname", "postgres"))
        env["MAX_REPLICATION_LAG"] = str(pg.get("max_replication_lag_bytes", 1_048_576))

    elif check_name == "webserver":
        ws = config.webserver
        endpoints = ws.get("endpoints", [])
        env["ENDPOINTS"] = ",".join(e["url"] for e in endpoints if isinstance(e, dict))
        if endpoints and isinstance(endpoints[0], dict):
            env["CONNECT_TIMEOUT"] = str(endpoints[0].get("timeout", 5))

    return env


def run_check(
    script: Path,
    config: Config,
    timeout: int = 30,
) -> CheckResult:
    """Execute a single check script and parse its JSON output."""
    check_name = script.stem
    threshold = config.threshold_for(check_name)
    env = _build_env(config, check_name)

    start = time.monotonic()
    try:
        result = subprocess.run(
            ["bash", str(script), "--threshold", str(threshold)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        duration_ms = (time.monotonic() - start) * 1000

        if result.returncode != 0 and not result.stdout.strip():
            return CheckResult.error(
                check_name,
                f"Script exited with code {result.returncode}: {result.stderr.strip()[:200]}",
            )

        output = result.stdout.strip()
        if not output:
            return CheckResult.error(check_name, "Script produced no output")

        data = json.loads(output)
        return CheckResult.from_json(data, duration_ms=duration_ms)

    except subprocess.TimeoutExpired:
        return CheckResult.error(check_name, f"Check timed out after {timeout}s")
    except json.JSONDecodeError as exc:
        return CheckResult.error(check_name, f"Invalid JSON output: {exc}")
    except Exception as exc:
        return CheckResult.error(check_name, f"Unexpected error: {exc}")


def run_checks(
    checks_dir: Path,
    config: Config,
    selected: Sequence[str] | None = None,
    max_workers: int = 8,
    timeout: int = 30,
) -> HealthReport:
    """Discover and run checks in parallel, returning an aggregated report."""
    scripts = discover_checks(checks_dir)

    if selected:
        names = {s.strip().lower() for s in selected}
        scripts = [s for s in scripts if s.stem.lower() in names]

    results: list[CheckResult] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(run_check, script, config, timeout): script
            for script in scripts
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r.check)

    hostname = socket.gethostname()
    return HealthReport(results=results, hostname=hostname)
