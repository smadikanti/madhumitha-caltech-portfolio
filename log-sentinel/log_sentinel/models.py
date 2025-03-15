"""Data models for log-sentinel."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Operator(str, Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="

    def evaluate(self, value: float, threshold: float) -> bool:
        ops = {
            Operator.GT: value > threshold,
            Operator.LT: value < threshold,
            Operator.GTE: value >= threshold,
            Operator.LTE: value <= threshold,
            Operator.EQ: abs(value - threshold) < 1e-9,
        }
        return ops[self]


@dataclass(frozen=True)
class LogEntry:
    timestamp: float
    level: str
    logger_name: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.level in (LogLevel.ERROR.value, LogLevel.CRITICAL.value)

    @property
    def is_warning(self) -> bool:
        return self.level == LogLevel.WARNING.value


@dataclass
class AlertRule:
    name: str
    metric: str
    operator: Operator
    threshold: float
    window_seconds: int = 300
    severity: AlertSeverity = AlertSeverity.WARNING
    channels: list[str] = field(default_factory=lambda: ["stdout"])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertRule:
        return cls(
            name=data["name"],
            metric=data["metric"],
            operator=Operator(data["operator"]),
            threshold=float(data["threshold"]),
            window_seconds=int(data.get("window_seconds", 300)),
            severity=AlertSeverity(data.get("severity", "warning")),
            channels=data.get("channels", ["stdout"]),
        )


@dataclass
class AlertEvent:
    rule: AlertRule
    current_value: float
    triggered_at: float = field(default_factory=time.time)
    resolved: bool = False

    @property
    def message(self) -> str:
        state = "RESOLVED" if self.resolved else "FIRING"
        return (
            f"[{state}] {self.rule.severity.value.upper()}: "
            f"{self.rule.name} \u2014 {self.rule.metric} is {self.current_value:.4f} "
            f"(threshold: {self.rule.operator.value} {self.rule.threshold})"
        )


@dataclass
class RollingStats:
    total_entries: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    debug_count: int = 0
    critical_count: int = 0
    window_start: float = 0.0
    window_end: float = 0.0

    @property
    def error_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return (self.error_count + self.critical_count) / self.total_entries

    @property
    def throughput(self) -> float:
        duration = self.window_end - self.window_start
        if duration <= 0:
            return 0.0
        return self.total_entries / duration

    def as_dict(self) -> dict[str, float]:
        return {
            "total_entries": float(self.total_entries),
            "error_count": float(self.error_count),
            "warning_count": float(self.warning_count),
            "error_rate": self.error_rate,
            "throughput": self.throughput,
        }
