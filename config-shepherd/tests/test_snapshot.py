"""Tests for environment snapshot capture."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from config_shepherd.models import EnvironmentSnapshot, PackageInfo
from config_shepherd.snapshot import (
    capture_snapshot,
    load_snapshot,
    save_snapshot,
    _safe_env_vars,
)


class TestCaptureSnapshot:
    def test_captures_basic_info(self) -> None:
        snap = capture_snapshot(include_env=False)
        assert snap.hostname
        assert snap.os_name
        assert snap.python_version
        assert snap.timestamp

    def test_includes_packages(self) -> None:
        snap = capture_snapshot(include_env=False)
        assert isinstance(snap.packages, list)

    def test_env_vars_excluded(self) -> None:
        snap = capture_snapshot(include_env=False)
        assert snap.env_vars == {}

    def test_env_vars_included(self) -> None:
        snap = capture_snapshot(include_env=True)
        assert isinstance(snap.env_vars, dict)


class TestSaveAndLoad:
    def test_roundtrip(self, tmp_path: Path) -> None:
        snap = EnvironmentSnapshot(
            hostname="testhost",
            os_name="Linux",
            os_version="6.1.0",
            python_version="3.11.7",
            packages=[
                PackageInfo(name="fastapi", version="0.109.0"),
                PackageInfo(name="numpy", version="1.26.3"),
            ],
            env_vars={"HOME": "/home/test"},
        )
        dest = tmp_path / "snap.yaml"
        save_snapshot(snap, dest)
        assert dest.exists()

        loaded = load_snapshot(dest)
        assert loaded["hostname"] == "testhost"
        assert loaded["os"]["name"] == "Linux"
        assert loaded["python_version"] == "3.11.7"
        assert len(loaded["packages"]) == 2
        assert loaded["packages"][0]["name"] == "fastapi"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        dest = tmp_path / "deep" / "nested" / "snap.yaml"
        snap = EnvironmentSnapshot(hostname="h")
        save_snapshot(snap, dest)
        assert dest.exists()

    def test_to_dict(self) -> None:
        snap = EnvironmentSnapshot(
            hostname="h",
            os_name="Linux",
            os_version="6.1",
            python_version="3.11",
            packages=[PackageInfo(name="p", version="1.0")],
            env_vars={"K": "V"},
        )
        d = snap.to_dict()
        assert d["hostname"] == "h"
        assert d["os"]["name"] == "Linux"
        assert d["packages"][0]["name"] == "p"


class TestSafeEnvVars:
    def test_filters_safe_prefixes(self) -> None:
        env = {"HOME": "/home", "PATH": "/usr/bin", "SECRET_KEY": "abc", "SHELL": "/bin/zsh"}
        with patch.dict("os.environ", env, clear=True):
            result = _safe_env_vars()
            assert "HOME" in result
            assert "PATH" in result
            assert "SHELL" in result
            assert "SECRET_KEY" not in result
