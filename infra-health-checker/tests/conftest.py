"""Shared fixtures for health checker tests."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from health_checker.config import Config
from health_checker.models import CheckResult, HealthReport, Status


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(textwrap.dedent("""\
        thresholds:
          cpu:
            warning: 80
            critical: 95
          memory:
            warning: 75
            critical: 90
        alerting:
          webhooks:
            - url: https://hooks.test.local/alert
              on:
                - CRITICAL
            - url: https://hooks.test.local/warn
              on:
                - WARNING
                - CRITICAL
    """))
    return Config.load(config_file)


@pytest.fixture
def ok_result() -> CheckResult:
    return CheckResult(
        check="cpu",
        status=Status.OK,
        value=42.5,
        threshold=80,
        message="CPU usage at 42.5%",
        timestamp="2026-02-27T12:00:00Z",
        details={"load_average": "1.2", "num_cpus": 4},
        duration_ms=150.0,
    )


@pytest.fixture
def warning_result() -> CheckResult:
    return CheckResult(
        check="memory",
        status=Status.WARNING,
        value=82.3,
        threshold=75,
        message="Memory usage at 82.3%",
        timestamp="2026-02-27T12:00:00Z",
        details={"total_mb": 16384, "used_mb": 13500},
        duration_ms=50.0,
    )


@pytest.fixture
def critical_result() -> CheckResult:
    return CheckResult(
        check="disk",
        status=Status.CRITICAL,
        value=97.1,
        threshold=80,
        message="Worst disk usage at 97.1% on /",
        timestamp="2026-02-27T12:00:00Z",
        details={"mounts": [{"mount": "/", "usage_pct": 97}]},
        duration_ms=200.0,
    )


@pytest.fixture
def sample_report(ok_result, warning_result, critical_result) -> HealthReport:
    return HealthReport(
        results=[ok_result, warning_result, critical_result],
        hostname="test-host",
        generated_at="2026-02-27T12:00:05Z",
    )


@pytest.fixture
def fake_check_script(tmp_path: Path) -> Path:
    """Create a minimal check script that outputs valid JSON."""
    checks_dir = tmp_path / "checks"
    checks_dir.mkdir()
    script = checks_dir / "fake.sh"
    script.write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        set -euo pipefail
        THRESHOLD=80
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --threshold) THRESHOLD="$2"; shift 2 ;;
                *) shift ;;
            esac
        done
        cat <<EOF
        {"check":"fake","status":"OK","value":25.0,"threshold":${THRESHOLD},"message":"Fake check OK","timestamp":"2026-02-27T12:00:00Z","details":{}}
        EOF
    """))
    script.chmod(0o755)
    return checks_dir
