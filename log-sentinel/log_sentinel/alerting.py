"""Threshold-based alert evaluation and multi-channel dispatch."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path
from typing import TextIO

from .config import AlertChannelConfig
from .models import AlertEvent, AlertRule, RollingStats


class AlertEvaluator:
    """Evaluates alert rules against rolling statistics.

    Tracks firing state so alerts are only dispatched on state transitions
    (firing or resolved), not on every evaluation cycle.
    """

    def __init__(self, rules: list[AlertRule]) -> None:
        self._rules = list(rules)
        self._firing: dict[str, AlertEvent] = {}
        self._lock = threading.Lock()

    def evaluate(self, stats: RollingStats) -> list[AlertEvent]:
        """Check all rules against current stats.

        Returns:
            Newly fired or resolved ``AlertEvent`` instances.
        """
        metrics = stats.as_dict()
        events: list[AlertEvent] = []
        now = time.time()

        with self._lock:
            for rule in self._rules:
                value = metrics.get(rule.metric)
                if value is None:
                    continue

                triggered = rule.operator.evaluate(value, rule.threshold)

                if triggered and rule.name not in self._firing:
                    event = AlertEvent(rule=rule, current_value=value, triggered_at=now)
                    self._firing[rule.name] = event
                    events.append(event)
                elif not triggered and rule.name in self._firing:
                    event = AlertEvent(
                        rule=rule, current_value=value, triggered_at=now, resolved=True
                    )
                    del self._firing[rule.name]
                    events.append(event)

        return events

    @property
    def firing_alerts(self) -> list[AlertEvent]:
        with self._lock:
            return list(self._firing.values())


class AlertDispatcher:
    """Sends alert events to configured channels (stdout, file, webhook)."""

    def __init__(self, channels: AlertChannelConfig) -> None:
        self._channels = channels
        self._file_lock = threading.Lock()

    def dispatch(self, event: AlertEvent) -> None:
        if self._channels.stdout:
            self._send_stdout(event)
        if self._channels.file_path:
            self._send_file(event, self._channels.file_path)
        if self._channels.webhook_url:
            self._send_webhook(event, self._channels.webhook_url)

    def _send_stdout(self, event: AlertEvent) -> None:
        print(event.message)

    def _send_file(self, event: AlertEvent, path: str) -> None:
        with self._file_lock:
            with open(path, "a") as f:
                f.write(self._format_json(event) + "\n")

    def _send_webhook(self, event: AlertEvent, url: str) -> None:
        payload = self._format_json(event).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception:
            pass

    @staticmethod
    def _format_json(event: AlertEvent) -> str:
        return json.dumps({
            "alert": event.rule.name,
            "severity": event.rule.severity.value,
            "metric": event.rule.metric,
            "value": event.current_value,
            "threshold": event.rule.threshold,
            "operator": event.rule.operator.value,
            "state": "resolved" if event.resolved else "firing",
            "triggered_at": event.triggered_at,
            "message": event.message,
        })
