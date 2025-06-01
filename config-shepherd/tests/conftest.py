"""Shared fixtures for config-shepherd tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a base → dev → prod inheritance chain."""
    base = {
        "app": {"name": "test-app", "version": "1.0.0", "debug": False, "log_level": "INFO"},
        "database": {"host": "localhost", "port": 5432, "name": "testdb", "pool_size": 5},
        "cache": {"backend": "local", "ttl_seconds": 300},
        "software": {
            "os_version": "Ubuntu 22.04",
            "python_version": "3.11.7",
            "packages": {"fastapi": "0.109.0", "numpy": "1.26.3"},
            "system_packages": {"postgresql": "15.5"},
        },
        "features": {"search": True, "export": True},
    }
    dev = {
        "inherits": "base",
        "app": {"debug": True, "log_level": "DEBUG"},
        "database": {"pool_size": 2},
    }
    prod = {
        "inherits": "dev",
        "app": {"log_level": "WARNING"},
        "database": {"host": "prod-db.internal", "pool_size": 20, "ssl": True},
        "software": {
            "packages": {"fastapi": "0.109.2", "numpy": "1.26.4"},
        },
    }

    for name, data in [("base", base), ("dev", dev), ("prod", prod)]:
        (tmp_path / f"{name}.yaml").write_text(yaml.dump(data, default_flow_style=False))

    return tmp_path


@pytest.fixture
def sample_schema(tmp_path: Path) -> Path:
    """Write a minimal JSON Schema and return its path."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "app": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                    "debug": {"type": "boolean"},
                    "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]},
                },
                "required": ["name", "version"],
            },
            "database": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "name": {"type": "string"},
                    "pool_size": {"type": "integer", "minimum": 1},
                },
                "required": ["host", "port", "name"],
            },
        },
        "required": ["app"],
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))
    return schema_path
