"""Data models for config-shepherd."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiffOp(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class ValidationError:
    """A single validation finding against a config file."""

    path: str
    message: str
    severity: Severity = Severity.ERROR
    schema_path: str = ""

    def __str__(self) -> str:
        prefix = f"[{self.severity.value.upper()}]"
        location = f" at $.{self.path}" if self.path else ""
        return f"{prefix}{location}: {self.message}"


@dataclass(frozen=True)
class SecretFinding:
    """A potential secret detected in a file."""

    file: Path
    line_number: int
    pattern_name: str
    matched_text: str
    severity: Severity = Severity.ERROR

    def __str__(self) -> str:
        return (
            f"[{self.severity.value.upper()}] {self.file}:{self.line_number} "
            f"— {self.pattern_name}: {self.redacted_text}"
        )

    @property
    def redacted_text(self) -> str:
        if len(self.matched_text) <= 8:
            return "***"
        return self.matched_text[:4] + "***" + self.matched_text[-4:]


@dataclass(frozen=True)
class DiffEntry:
    """One difference between two configuration trees."""

    key_path: str
    operation: DiffOp
    old_value: Any = None
    new_value: Any = None

    def __str__(self) -> str:
        if self.operation == DiffOp.ADDED:
            return f"+ {self.key_path}: {self.new_value!r}"
        if self.operation == DiffOp.REMOVED:
            return f"- {self.key_path}: {self.old_value!r}"
        return f"~ {self.key_path}: {self.old_value!r} → {self.new_value!r}"


@dataclass
class PackageInfo:
    """A single installed package."""

    name: str
    version: str
    source: str = "pip"


@dataclass
class EnvironmentSnapshot:
    """Point-in-time capture of an environment's state."""

    hostname: str = ""
    os_name: str = ""
    os_version: str = ""
    python_version: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    packages: list[PackageInfo] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "os": {"name": self.os_name, "version": self.os_version},
            "python_version": self.python_version,
            "timestamp": self.timestamp,
            "packages": [
                {"name": p.name, "version": p.version, "source": p.source}
                for p in self.packages
            ],
            "env_vars": self.env_vars,
        }


@dataclass
class SoftwareInventory:
    """Software versions declared in an environment config."""

    environment: str
    packages: dict[str, str] = field(default_factory=dict)
    system_packages: dict[str, str] = field(default_factory=dict)
    os_version: str = ""
    python_version: str = ""
