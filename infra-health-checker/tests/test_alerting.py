"""Tests for the alerting engine and webhook notifications."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from health_checker.alerting import Alert, AlertEngine, _send_webhook
from health_checker.config import Config
from health_checker.models import CheckResult, HealthReport, Status


class TestAlertEvaluation:
    def test_no_alerts_for_ok(self, sample_config: Config, ok_result: CheckResult) -> None:
        report = HealthReport(results=[ok_result], hostname="test")
        engine = AlertEngine(sample_config)
        alerts = engine.evaluate(report)
        assert alerts == []

    def test_alert_on_warning(self, sample_config: Config, warning_result: CheckResult) -> None:
        report = HealthReport(results=[warning_result], hostname="test")
        engine = AlertEngine(sample_config)
        alerts = engine.evaluate(report)
        assert len(alerts) == 1
        assert alerts[0].status == Status.WARNING
        assert alerts[0].check == "memory"

    def test_alert_on_critical(self, sample_config: Config, critical_result: CheckResult) -> None:
        report = HealthReport(results=[critical_result], hostname="test")
        engine = AlertEngine(sample_config)
        alerts = engine.evaluate(report)
        assert len(alerts) == 1
        assert alerts[0].status == Status.CRITICAL

    def test_multiple_alerts(self, sample_config: Config, sample_report: HealthReport) -> None:
        engine = AlertEngine(sample_config)
        alerts = engine.evaluate(sample_report)
        assert len(alerts) == 2
        statuses = {a.status for a in alerts}
        assert Status.WARNING in statuses
        assert Status.CRITICAL in statuses

    def test_alert_uses_config_thresholds(
        self, sample_config: Config, warning_result: CheckResult
    ) -> None:
        report = HealthReport(results=[warning_result], hostname="test")
        engine = AlertEngine(sample_config)
        alerts = engine.evaluate(report)
        assert alerts[0].threshold == 75.0

    def test_error_status_triggers_alert(self, sample_config: Config) -> None:
        err = CheckResult.error("broken", "something went wrong")
        report = HealthReport(results=[err], hostname="test")
        engine = AlertEngine(sample_config)
        alerts = engine.evaluate(report)
        assert len(alerts) == 1
        assert alerts[0].status == Status.ERROR


class TestAlertToDict:
    def test_serialization(self) -> None:
        alert = Alert(
            check="cpu", status=Status.CRITICAL, value=96.0, threshold=95, message="hot"
        )
        d = alert.to_dict()
        assert d["check"] == "cpu"
        assert d["status"] == "CRITICAL"
        assert d["value"] == 96.0


class TestWebhookNotification:
    @patch("health_checker.alerting._send_webhook")
    def test_sends_to_matching_webhooks(
        self,
        mock_send: MagicMock,
        sample_config: Config,
        sample_report: HealthReport,
    ) -> None:
        mock_send.return_value = {"url": "test", "status_code": 200, "success": True}
        engine = AlertEngine(sample_config)
        engine.evaluate(sample_report)
        receipts = engine.notify()
        assert mock_send.call_count >= 1
        assert all(r["success"] for r in receipts)

    @patch("health_checker.alerting._send_webhook")
    def test_skips_webhooks_not_matching_severity(
        self,
        mock_send: MagicMock,
        sample_config: Config,
        ok_result: CheckResult,
    ) -> None:
        report = HealthReport(results=[ok_result], hostname="test")
        engine = AlertEngine(sample_config)
        engine.evaluate(report)
        receipts = engine.notify()
        assert receipts == []
        mock_send.assert_not_called()

    @patch("health_checker.alerting._send_webhook")
    def test_critical_only_webhook_ignores_warnings(
        self,
        mock_send: MagicMock,
        sample_config: Config,
        warning_result: CheckResult,
    ) -> None:
        mock_send.return_value = {"url": "test", "status_code": 200, "success": True}
        report = HealthReport(results=[warning_result], hostname="test")
        engine = AlertEngine(sample_config)
        engine.evaluate(report)
        engine.notify()
        for call_args in mock_send.call_args_list:
            url = call_args[0][0]
            assert "warn" in url

    def test_no_webhooks_configured(self) -> None:
        config = Config.load(None)
        engine = AlertEngine(config)
        engine.alerts = [
            Alert(check="cpu", status=Status.CRITICAL, value=99, threshold=95, message="hot")
        ]
        receipts = engine.notify()
        assert receipts == []


class TestSendWebhook:
    @patch("health_checker.alerting.requests.post")
    def test_successful_post(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = _send_webhook("https://example.com/hook", {"test": True})
        assert result["success"] is True
        assert result["status_code"] == 200
        mock_post.assert_called_once()

    @patch("health_checker.alerting.requests.post")
    def test_handles_connection_error(self, mock_post: MagicMock) -> None:
        import requests
        mock_post.side_effect = requests.ConnectionError("unreachable")

        result = _send_webhook("https://bad.host/hook", {"test": True})
        assert result["success"] is False
        assert "error" in result
