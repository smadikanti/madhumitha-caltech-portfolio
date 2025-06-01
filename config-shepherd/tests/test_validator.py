"""Tests for JSON Schema-based config validation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from config_shepherd.models import Severity
from config_shepherd.validator import validate_config, validate_directory


class TestValidateConfig:
    def test_valid_config(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {
            "app": {"name": "my-app", "version": "1.0.0", "debug": False},
            "database": {"host": "localhost", "port": 5432, "name": "mydb"},
        }
        errors = validate_config(config, schema)
        assert errors == []

    def test_missing_required_field(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {"app": {"name": "my-app"}}  # missing version
        errors = validate_config(config, schema)
        assert len(errors) >= 1
        assert any("version" in e.message for e in errors)

    def test_type_mismatch(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {
            "app": {"name": "my-app", "version": "1.0.0", "debug": "yes"},
        }
        errors = validate_config(config, schema)
        assert len(errors) >= 1
        assert any("debug" in e.path for e in errors)

    def test_invalid_enum_value(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {
            "app": {"name": "my-app", "version": "1.0.0", "log_level": "TRACE"},
        }
        errors = validate_config(config, schema)
        assert len(errors) >= 1

    def test_invalid_port(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {
            "app": {"name": "my-app", "version": "1.0.0"},
            "database": {"host": "localhost", "port": 99999, "name": "db"},
        }
        errors = validate_config(config, schema)
        assert len(errors) >= 1

    def test_missing_app_section(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {"database": {"host": "h", "port": 1, "name": "d"}}
        errors = validate_config(config, schema)
        assert len(errors) >= 1
        assert any("app" in e.message for e in errors)

    def test_errors_have_severity(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {}  # missing required 'app'
        errors = validate_config(config, schema)
        assert all(e.severity == Severity.ERROR for e in errors)

    def test_version_pattern_mismatch(self, sample_schema: Path) -> None:
        schema = json.loads(sample_schema.read_text())
        config = {"app": {"name": "x", "version": "not-a-semver"}}
        errors = validate_config(config, schema)
        assert len(errors) >= 1


class TestValidateDirectory:
    def test_all_envs_validated(self, tmp_config_dir: Path, sample_schema: Path) -> None:
        results = validate_directory(tmp_config_dir, sample_schema)
        assert "base" in results
        assert "dev" in results
        assert "prod" in results

    def test_valid_configs_pass(self, tmp_config_dir: Path, sample_schema: Path) -> None:
        results = validate_directory(tmp_config_dir, sample_schema)
        for env_name, errors in results.items():
            assert errors == [], f"{env_name} had unexpected errors: {errors}"

    def test_invalid_config_detected(self, tmp_path: Path, sample_schema: Path) -> None:
        bad = {"app": {"name": ""}}  # empty name fails minLength, missing version
        (tmp_path / "bad.yaml").write_text(yaml.dump(bad))
        results = validate_directory(tmp_path, sample_schema)
        assert len(results["bad"]) > 0
