"""YAML configuration loader with sensible defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_DEFAULTS: dict[str, Any] = {
    "thresholds": {
        "cpu": {"warning": 80, "critical": 95},
        "memory": {"warning": 80, "critical": 95},
        "disk": {"warning": 80, "critical": 95},
        "swap": {"warning": 50, "critical": 80},
    },
    "network": {
        "ping_targets": ["8.8.8.8", "1.1.1.1"],
        "dns_targets": ["google.com", "github.com"],
        "port_checks": [],
    },
    "processes": {"critical": ["sshd", "cron"]},
    "docker": {"enabled": True},
    "postgres": {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "dbname": "postgres",
        "max_replication_lag_bytes": 1_048_576,
        "max_connections_warning": 80,
    },
    "webserver": {
        "endpoints": [
            {"url": "http://localhost:8080/health", "expected_status": 200, "timeout": 5}
        ],
    },
    "alerting": {"webhooks": []},
    "reports": {"output_dir": "./reports", "retain_days": 30},
    "cron": {"interval_minutes": 5, "output_dir": "/var/log/health-reports"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into a copy of *base*."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass
class Config:
    """Typed accessor around the raw YAML dict."""

    _data: dict[str, Any] = field(default_factory=lambda: _DEFAULTS.copy())

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Config":
        """Load config from a YAML file, falling back to defaults."""
        data = _DEFAULTS.copy()
        if path is not None:
            p = Path(path)
            if p.exists():
                with p.open() as fh:
                    user_data = yaml.safe_load(fh) or {}
                data = _deep_merge(data, user_data)
        return cls(_data=data)

    def get(self, *keys: str, default: Any = None) -> Any:
        """Dot-path access: ``cfg.get("thresholds", "cpu", "warning")``."""
        node: Any = self._data
        for k in keys:
            if isinstance(node, dict):
                node = node.get(k)
            else:
                return default
            if node is None:
                return default
        return node

    @property
    def thresholds(self) -> dict[str, dict[str, int]]:
        return self._data.get("thresholds", _DEFAULTS["thresholds"])

    @property
    def alerting(self) -> dict[str, Any]:
        return self._data.get("alerting", _DEFAULTS["alerting"])

    @property
    def network(self) -> dict[str, Any]:
        return self._data.get("network", _DEFAULTS["network"])

    @property
    def processes(self) -> dict[str, Any]:
        return self._data.get("processes", _DEFAULTS["processes"])

    @property
    def postgres(self) -> dict[str, Any]:
        return self._data.get("postgres", _DEFAULTS["postgres"])

    @property
    def webserver(self) -> dict[str, Any]:
        return self._data.get("webserver", _DEFAULTS["webserver"])

    @property
    def reports(self) -> dict[str, Any]:
        return self._data.get("reports", _DEFAULTS["reports"])

    @property
    def cron(self) -> dict[str, Any]:
        return self._data.get("cron", _DEFAULTS["cron"])

    def threshold_for(self, check: str) -> int:
        """Return the warning threshold for a named check."""
        return self.thresholds.get(check, {}).get("warning", 80)
