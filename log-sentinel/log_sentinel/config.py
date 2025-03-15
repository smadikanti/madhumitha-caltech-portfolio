"""YAML configuration loader for log-sentinel."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import AlertRule


@dataclass
class MetricsServerConfig:
    host: str = "0.0.0.0"
    port: int = 9090
    path: str = "/metrics"


@dataclass
class AlertChannelConfig:
    stdout: bool = True
    file_path: str | None = None
    webhook_url: str | None = None


@dataclass
class AggregatorConfig:
    poll_interval_seconds: float = 1.0
    window_seconds: int = 300
    max_line_length: int = 65536


@dataclass
class SentinelConfig:
    metrics_server: MetricsServerConfig = field(default_factory=MetricsServerConfig)
    alert_channels: AlertChannelConfig = field(default_factory=AlertChannelConfig)
    aggregator: AggregatorConfig = field(default_factory=AggregatorConfig)
    alert_rules: list[AlertRule] = field(default_factory=list)
    log_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SentinelConfig:
        metrics_data = data.get("metrics_server", {})
        channels_data = data.get("alert_channels", {})
        agg_data = data.get("aggregator", {})
        rules_data = data.get("alert_rules", [])

        return cls(
            metrics_server=MetricsServerConfig(
                host=metrics_data.get("host", "0.0.0.0"),
                port=int(metrics_data.get("port", 9090)),
                path=metrics_data.get("path", "/metrics"),
            ),
            alert_channels=AlertChannelConfig(
                stdout=channels_data.get("stdout", True),
                file_path=channels_data.get("file_path"),
                webhook_url=channels_data.get("webhook_url"),
            ),
            aggregator=AggregatorConfig(
                poll_interval_seconds=float(agg_data.get("poll_interval_seconds", 1.0)),
                window_seconds=int(agg_data.get("window_seconds", 300)),
                max_line_length=int(agg_data.get("max_line_length", 65536)),
            ),
            alert_rules=[AlertRule.from_dict(r) for r in rules_data],
            log_paths=data.get("log_paths", []),
        )


def load_config(path: str | Path | None = None) -> SentinelConfig:
    """Load configuration from a YAML file.

    Falls back to defaults if no path is given or the file doesn't exist.
    The environment variable LOG_SENTINEL_CONFIG overrides the path argument.
    """
    env_path = os.environ.get("LOG_SENTINEL_CONFIG")
    if env_path:
        path = env_path

    if path is None:
        return SentinelConfig()

    config_path = Path(path)
    if not config_path.exists():
        return SentinelConfig()

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    return SentinelConfig.from_dict(data)
