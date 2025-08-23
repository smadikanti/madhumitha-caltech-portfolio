"""Tests for the check runner and discovery engine."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from health_checker.config import Config
from health_checker.models import Status
from health_checker.runner import discover_checks, run_check, run_checks


class TestDiscoverChecks:
    def test_discovers_sh_files(self, fake_check_script: Path) -> None:
        scripts = discover_checks(fake_check_script)
        assert len(scripts) == 1
        assert scripts[0].name == "fake.sh"

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        scripts = discover_checks(tmp_path / "nonexistent")
        assert scripts == []

    def test_ignores_non_sh_files(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        (checks_dir / "notes.txt").write_text("not a script")
        (checks_dir / "helper.py").write_text("print('hi')")
        (checks_dir / "real.sh").write_text("#!/bin/bash\necho ok")
        (checks_dir / "real.sh").chmod(0o755)
        scripts = discover_checks(checks_dir)
        assert len(scripts) == 1
        assert scripts[0].name == "real.sh"


class TestRunCheck:
    def test_runs_valid_script(self, fake_check_script: Path, sample_config: Config) -> None:
        script = list(fake_check_script.glob("*.sh"))[0]
        result = run_check(script, sample_config)
        assert result.check == "fake"
        assert result.status == Status.OK
        assert result.value == 25.0

    def test_handles_timeout(self, tmp_path: Path, sample_config: Config) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        script = checks_dir / "slow.sh"
        script.write_text("#!/usr/bin/env bash\nset -euo pipefail\nsleep 60\n")
        script.chmod(0o755)
        result = run_check(script, sample_config, timeout=1)
        assert result.status == Status.ERROR
        assert "timed out" in result.message.lower()

    def test_handles_invalid_json(self, tmp_path: Path, sample_config: Config) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        script = checks_dir / "bad.sh"
        script.write_text('#!/usr/bin/env bash\nset -euo pipefail\necho "not json"\n')
        script.chmod(0o755)
        result = run_check(script, sample_config)
        assert result.status == Status.ERROR
        assert "json" in result.message.lower()

    def test_handles_script_error(self, tmp_path: Path, sample_config: Config) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        script = checks_dir / "fail.sh"
        script.write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n")
        script.chmod(0o755)
        result = run_check(script, sample_config)
        assert result.status == Status.ERROR


class TestRunChecks:
    def test_runs_all_discovered(self, fake_check_script: Path, sample_config: Config) -> None:
        report = run_checks(fake_check_script, sample_config)
        assert len(report.results) == 1
        assert report.results[0].check == "fake"
        assert report.hostname

    def test_filters_by_selection(self, tmp_path: Path, sample_config: Config) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        for name in ("alpha", "beta", "gamma"):
            script = checks_dir / f"{name}.sh"
            script.write_text(textwrap.dedent(f"""\
                #!/usr/bin/env bash
                set -euo pipefail
                echo '{{"check":"{name}","status":"OK","value":0,"threshold":80,"message":"ok","timestamp":"2026-02-27T12:00:00Z","details":{{}}}}'
            """))
            script.chmod(0o755)

        report = run_checks(checks_dir, sample_config, selected=["alpha", "gamma"])
        names = {r.check for r in report.results}
        assert names == {"alpha", "gamma"}

    def test_empty_dir_returns_empty_report(self, tmp_path: Path, sample_config: Config) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        report = run_checks(checks_dir, sample_config)
        assert len(report.results) == 0
        assert report.overall_status == Status.OK
