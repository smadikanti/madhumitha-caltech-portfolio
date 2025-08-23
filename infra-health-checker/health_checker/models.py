"""Data models for health check results."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Status(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"

    @property
    def severity(self) -> int:
        return {
            Status.OK: 0,
            Status.WARNING: 1,
            Status.CRITICAL: 2,
            Status.ERROR: 3,
        }[self]

    def __lt__(self, other: "Status") -> bool:
        return self.severity < other.severity

    def __le__(self, other: "Status") -> bool:
        return self.severity <= other.severity


@dataclass
class CheckResult:
    """Result from a single health check script."""

    check: str
    status: Status
    value: float
    threshold: float
    message: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @classmethod
    def from_json(cls, data: dict[str, Any], duration_ms: float = 0.0) -> "CheckResult":
        """Parse a check result from the JSON output of a check script."""
        return cls(
            check=data.get("check", "unknown"),
            status=Status(data.get("status", "ERROR")),
            value=float(data.get("value", 0)),
            threshold=float(data.get("threshold", 0)),
            message=data.get("message", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            details=data.get("details", {}),
            duration_ms=duration_ms,
        )

    @classmethod
    def error(cls, check_name: str, error_msg: str) -> "CheckResult":
        """Create an error result for a check that failed to execute."""
        return cls(
            check=check_name,
            status=Status.ERROR,
            value=0,
            threshold=0,
            message=error_msg,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            details={"error": error_msg},
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass
class HealthReport:
    """Aggregated health report from all checks."""

    results: list[CheckResult]
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    hostname: str = ""

    @property
    def overall_status(self) -> Status:
        if not self.results:
            return Status.OK
        return max(self.results, key=lambda r: r.status.severity).status

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.OK)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.WARNING)

    @property
    def critical_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.ERROR)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "hostname": self.hostname,
            "overall_status": self.overall_status.value,
            "summary": {
                "total": len(self.results),
                "ok": self.ok_count,
                "warning": self.warning_count,
                "critical": self.critical_count,
                "error": self.error_count,
            },
            "checks": [r.to_dict() for r in self.results],
        }
