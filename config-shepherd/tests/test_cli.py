"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from config_shepherd.__main__ import main


class TestCLIValidate:
    def test_valid_configs(self, tmp_config_dir: Path, sample_schema: Path) -> None:
        rc = main(["validate", str(tmp_config_dir), "--schema", str(sample_schema)])
        assert rc == 0

    def test_invalid_configs(self, tmp_path: Path, sample_schema: Path) -> None:
        (tmp_path / "bad.yaml").write_text(yaml.dump({"app": {"name": ""}}))
        rc = main(["validate", str(tmp_path), "--schema", str(sample_schema)])
        assert rc == 1


class TestCLIDiff:
    def test_diff_two_envs(self, tmp_config_dir: Path) -> None:
        rc = main(["diff", "dev", "prod", "--config-dir", str(tmp_config_dir), "--no-color"])
        assert rc == 0

    def test_diff_same_env(self, tmp_config_dir: Path) -> None:
        rc = main(["diff", "base", "base", "--config-dir", str(tmp_config_dir), "--no-color"])
        assert rc == 0


class TestCLIScan:
    def test_scan_clean_dir(self, tmp_path: Path) -> None:
        (tmp_path / "clean.yaml").write_text("app:\n  name: safe\n")
        rc = main(["scan", str(tmp_path)])
        assert rc == 0

    def test_scan_with_secrets(self, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text("password: secret123\n")
        rc = main(["scan", str(tmp_path)])
        assert rc == 1

    def test_scan_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "f.yaml"
        f.write_text("x: 1\n")
        rc = main(["scan", str(f)])
        assert rc == 0


class TestCLISnapshot:
    def test_snapshot(self, tmp_path: Path) -> None:
        out = tmp_path / "snap.yaml"
        rc = main(["snapshot", "--output", str(out), "--no-env"])
        assert rc == 0
        assert out.exists()


class TestCLIInventory:
    def test_inventory(self, tmp_config_dir: Path) -> None:
        rc = main(["inventory", str(tmp_config_dir)])
        assert rc == 0


class TestCLIMerge:
    def test_merge(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(yaml.dump({"x": 1, "y": 2}))
        (tmp_path / "b.yaml").write_text(yaml.dump({"y": 99, "z": 3}))
        rc = main(["merge", str(tmp_path / "a.yaml"), str(tmp_path / "b.yaml")])
        assert rc == 0


class TestCLIErrors:
    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent"
        rc = main(["validate", str(fake), "--schema", str(fake / "s.json")])
        assert rc == 1
