"""Threshold-based alerting with webhook notification support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import requests

from .config import Config
from .models import CheckResult, HealthReport, Status

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """A single alert triggered by a check breaching its threshold."""

    check: str
    status: Status
    value: float
    threshold: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status.value,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class AlertEngine:
    """Evaluate check results against configured thresholds and fire webhooks."""

    config: Config
    alerts: list[Alert] = field(default_factory=list, init=False)

    def evaluate(self, report: HealthReport) -> list[Alert]:
        """Walk every result and produce alerts for WARNING/CRITICAL/ERROR status."""
        self.alerts = []
        for result in report.results:
            if result.status in (Status.WARNING, Status.CRITICAL, Status.ERROR):
                threshold = self._resolve_threshold(result)
                self.alerts.append(
                    Alert(
                        check=result.check,
                        status=result.status,
                        value=result.value,
                        threshold=threshold,
                        message=result.message,
                    )
                )
        return self.alerts

    def _resolve_threshold(self, result: CheckResult) -> float:
        """Use the config threshold if available, otherwise fall back to the check's own."""
        cfg_thresh = self.config.thresholds.get(result.check, {})
        if result.status == Status.CRITICAL:
            return float(cfg_thresh.get("critical", result.threshold))
        return float(cfg_thresh.get("warning", result.threshold))

    def notify(self, alerts: list[Alert] | None = None) -> list[dict[str, Any]]:
        """Send alerts to configured webhook URLs. Returns delivery receipts."""
        alerts = alerts if alerts is not None else self.alerts
        if not alerts:
            return []

        webhooks: list[dict[str, Any]] = self.config.alerting.get("webhooks", [])
        if not webhooks:
            logger.debug("No webhooks configured, skipping notification")
            return []

        receipts: list[dict[str, Any]] = []

        for hook in webhooks:
            url = hook.get("url", "")
            trigger_on = {s.upper() for s in hook.get("on", ["CRITICAL"])}

            matching = [a for a in alerts if a.status.value in trigger_on]
            if not matching:
                continue

            payload = {
                "source": "infra-health-checker",
                "alerts": [a.to_dict() for a in matching],
            }

            receipt = _send_webhook(url, payload)
            receipts.append(receipt)

        return receipts


def _send_webhook(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST a JSON payload to *url* with basic error handling."""
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return {
            "url": url,
            "status_code": resp.status_code,
            "success": 200 <= resp.status_code < 300,
        }
    except requests.RequestException as exc:
        logger.warning("Webhook delivery failed for %s: %s", url, exc)
        return {"url": url, "status_code": 0, "success": False, "error": str(exc)}
