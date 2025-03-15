"""Tests for the alert evaluator and dispatcher."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from log_sentinel.alerting import AlertDispatcher, AlertEvaluator
from log_sentinel.config import AlertChannelConfig
from log_sentinel.models import AlertEvent, AlertRule, AlertSeverity, Operator, RollingStats


def _make_stats(error_rate: float = 0.0, total: int = 100) -> RollingStats:
    errors = int(total * error_rate)
    return RollingStats(
        total_entries=total,
        error_count=errors,
        warning_count=0,
        info_count=total - errors,
        window_start=time.time() - 300,
        window_end=time.time(),
    )


class TestAlertEvaluator:
    def test_fires_on_threshold_breach(self):
        rule = AlertRule(
            name="high_errors", metric="error_rate",
            operator=Operator.GT, threshold=0.05,
        )
        evaluator = AlertEvaluator([rule])
        events = evaluator.evaluate(_make_stats(error_rate=0.1))
        assert len(events) == 1
        assert not events[0].resolved
        assert "high_errors" in events[0].message

    def test_no_fire_below_threshold(self):
        rule = AlertRule(
            name="high_errors", metric="error_rate",
            operator=Operator.GT, threshold=0.05,
        )
        evaluator = AlertEvaluator([rule])
        events = evaluator.evaluate(_make_stats(error_rate=0.01))
        assert len(events) == 0

    def test_resolves_on_recovery(self):
        rule = AlertRule(
            name="high_errors", metric="error_rate",
            operator=Operator.GT, threshold=0.05,
        )
        evaluator = AlertEvaluator([rule])
        evaluator.evaluate(_make_stats(error_rate=0.1))

        events = evaluator.evaluate(_make_stats(error_rate=0.01))
        assert len(events) == 1
        assert events[0].resolved

    def test_no_duplicate_fire(self):
        rule = AlertRule(
            name="high_errors", metric="error_rate",
            operator=Operator.GT, threshold=0.05,
        )
        evaluator = AlertEvaluator([rule])
        evaluator.evaluate(_make_stats(error_rate=0.1))

        events = evaluator.evaluate(_make_stats(error_rate=0.2))
        assert len(events) == 0

    def test_multiple_rules(self):
        rules = [
            AlertRule(name="err", metric="error_rate", operator=Operator.GT, threshold=0.05),
            AlertRule(name="low_throughput", metric="throughput", operator=Operator.LT, threshold=1.0),
        ]
        evaluator = AlertEvaluator(rules)
        stats = _make_stats(error_rate=0.1)
        events = evaluator.evaluate(stats)
        triggered_names = {e.rule.name for e in events}
        assert "err" in triggered_names

    def test_firing_alerts_property(self):
        rule = AlertRule(
            name="test_prop", metric="error_rate",
            operator=Operator.GT, threshold=0.01,
        )
        evaluator = AlertEvaluator([rule])
        evaluator.evaluate(_make_stats(error_rate=0.1))
        assert len(evaluator.firing_alerts) == 1

    def test_all_operators(self):
        for op, value, threshold, should_fire in [
            (Operator.GT, 10.0, 5.0, True),
            (Operator.GT, 3.0, 5.0, False),
            (Operator.LT, 3.0, 5.0, True),
            (Operator.LT, 10.0, 5.0, False),
            (Operator.GTE, 5.0, 5.0, True),
            (Operator.LTE, 5.0, 5.0, True),
            (Operator.EQ, 5.0, 5.0, True),
            (Operator.EQ, 5.1, 5.0, False),
        ]:
            assert op.evaluate(value, threshold) == should_fire, f"{op} {value} {threshold}"

    def test_unknown_metric_ignored(self):
        rule = AlertRule(
            name="missing", metric="nonexistent_metric",
            operator=Operator.GT, threshold=0.0,
        )
        evaluator = AlertEvaluator([rule])
        events = evaluator.evaluate(_make_stats())
        assert len(events) == 0


class TestAlertDispatcher:
    def test_stdout_dispatch(self, capsys):
        channels = AlertChannelConfig(stdout=True)
        dispatcher = AlertDispatcher(channels)
        rule = AlertRule(name="test_stdout", metric="error_rate", operator=Operator.GT, threshold=0.05)
        event = AlertEvent(rule=rule, current_value=0.1)
        dispatcher.dispatch(event)

        captured = capsys.readouterr()
        assert "test_stdout" in captured.out
        assert "FIRING" in captured.out

    def test_file_dispatch(self, tmp_path):
        alert_file = tmp_path / "alerts.jsonl"
        channels = AlertChannelConfig(stdout=False, file_path=str(alert_file))
        dispatcher = AlertDispatcher(channels)
        rule = AlertRule(name="file_test", metric="error_rate", operator=Operator.GT, threshold=0.05)
        event = AlertEvent(rule=rule, current_value=0.15)
        dispatcher.dispatch(event)

        content = alert_file.read_text()
        data = json.loads(content.strip())
        assert data["alert"] == "file_test"
        assert data["state"] == "firing"

    def test_webhook_dispatch(self):
        channels = AlertChannelConfig(stdout=False, webhook_url="http://example.com/hook")
        dispatcher = AlertDispatcher(channels)
        rule = AlertRule(name="hook_test", metric="error_rate", operator=Operator.GT, threshold=0.05)
        event = AlertEvent(rule=rule, current_value=0.2)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock()
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            dispatcher.dispatch(event)
            mock_urlopen.assert_called_once()

    def test_resolved_event_format(self, tmp_path):
        alert_file = tmp_path / "resolved.jsonl"
        channels = AlertChannelConfig(stdout=False, file_path=str(alert_file))
        dispatcher = AlertDispatcher(channels)
        rule = AlertRule(name="res_test", metric="error_rate", operator=Operator.GT, threshold=0.05)
        event = AlertEvent(rule=rule, current_value=0.01, resolved=True)
        dispatcher.dispatch(event)

        data = json.loads(alert_file.read_text().strip())
        assert data["state"] == "resolved"


class TestAlertEvent:
    def test_message_firing(self):
        rule = AlertRule(
            name="test_msg", metric="error_rate",
            operator=Operator.GT, threshold=0.05,
            severity=AlertSeverity.CRITICAL,
        )
        event = AlertEvent(rule=rule, current_value=0.12)
        assert "[FIRING]" in event.message
        assert "CRITICAL" in event.message
        assert "test_msg" in event.message

    def test_message_resolved(self):
        rule = AlertRule(
            name="test_msg", metric="error_rate",
            operator=Operator.GT, threshold=0.05,
        )
        event = AlertEvent(rule=rule, current_value=0.02, resolved=True)
        assert "[RESOLVED]" in event.message
