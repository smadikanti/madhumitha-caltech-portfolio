"""YAML-based configuration loader for the stellar data pipeline.

Reads configuration from a YAML file and returns typed dataclass
instances with sensible defaults and validation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from stellar_pipeline.exceptions import ConfigError


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection parameters."""

    host: str = "localhost"
    port: int = 5432
    name: str = "stellar_pipeline"
    user: str = "pipeline_user"
    password: str = ""

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password}"
        )


@dataclass(frozen=True)
class ApiConfig:
    """NASA Exoplanet Archive TAP API settings."""

    base_url: str = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
    timeout: int = 60
    max_retries: int = 3
    backoff_base: float = 2.0
    backoff_max: float = 60.0


@dataclass(frozen=True)
class PipelineConfig:
    """Pipeline execution settings."""

    batch_size: int = 500
    log_file: str = "pipeline.log"
    log_level: str = "INFO"


@dataclass(frozen=True)
class Config:
    """Top-level configuration aggregating all subsections."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)


def _resolve_env_vars(value: Any) -> Any:
    """Replace ${ENV_VAR} references in string values with environment variables."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        env_val = os.environ.get(env_key)
        if env_val is None:
            raise ConfigError(f"Environment variable {env_key} is not set")
        return env_val
    return value


def _build_section(cls: type, raw: dict[str, Any]) -> Any:
    """Instantiate a config dataclass from a raw dict, resolving env vars."""
    known = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {}
    for key, value in raw.items():
        if key in known:
            filtered[key] = _resolve_env_vars(value)
    return cls(**filtered)


def load_config(path: str | Path) -> Config:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A fully populated Config instance.

    Raises:
        ConfigError: If the file is missing, unreadable, or contains
            invalid structure.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Expected top-level mapping in {config_path}")

    database = _build_section(DatabaseConfig, raw.get("database", {}))
    api = _build_section(ApiConfig, raw.get("api", {}))
    pipeline = _build_section(PipelineConfig, raw.get("pipeline", {}))

    return Config(database=database, api=api, pipeline=pipeline)
