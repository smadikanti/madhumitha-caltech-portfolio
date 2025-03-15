"""CLI entry point for log-sentinel.

Usage:
    python -m log_sentinel serve
    python -m log_sentinel watch <logfile>
    python -m log_sentinel check <logfile>
    python -m log_sentinel alert-test
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from typing import Sequence

from .aggregator import LogAggregator
from .alerting import AlertDispatcher, AlertEvaluator
from .config import SentinelConfig, load_config
from .metrics import MetricsRegistry, MetricsServer
from .models import AlertEvent, AlertRule, AlertSeverity, Operator, RollingStats


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="log_sentinel",
        description="Logging and metrics framework for scientific computing infrastructure.",
    )
    parser.add_argument("-c", "--config", default=None, help="Path to config.yaml")

    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start the Prometheus metrics HTTP server")
    serve_p.add_argument("--host", default=None, help="Bind address")
    serve_p.add_argument("--port", type=int, default=None, help="Bind port")

    watch_p = sub.add_parser("watch", help="Watch and aggregate a log file")
    watch_p.add_argument("logfile", help="Path to the log file to watch")

    check_p = sub.add_parser("check", help="One-shot analysis of a log file")
    check_p.add_argument("logfile", help="Path to the log file to analyse")

    sub.add_parser("alert-test", help="Test alert configuration with synthetic data")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    cfg = load_config(args.config)

    dispatch: dict[str, object] = {
        "serve": lambda: _cmd_serve(cfg, args),
        "watch": lambda: _cmd_watch(cfg, args),
        "check": lambda: _cmd_check(cfg, args),
        "alert-test": lambda: _cmd_alert_test(cfg),
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler()  # type: ignore[return-value]


# ── Commands ─────────────────────────────────────────────────────────────────


def _cmd_serve(cfg: SentinelConfig, args: argparse.Namespace) -> int:
    host = args.host or cfg.metrics_server.host
    port = args.port or cfg.metrics_server.port

    registry = MetricsRegistry.get_instance()
    registry.counter("requests_total", "Total HTTP requests")
    registry.counter("errors_total", "Total errors")
    registry.counter("records_processed_total", "Total records processed")
    registry.gauge("active_connections", "Current active connections")
    registry.gauge("queue_depth", "Current queue depth")
    registry.gauge("disk_usage_bytes", "Current disk usage in bytes")
    registry.histogram("request_duration_seconds", "HTTP request duration in seconds")
    registry.histogram("batch_processing_seconds", "Batch processing duration in seconds")

    server = MetricsServer(registry, host=host, port=port, path=cfg.metrics_server.path)
    server.start(daemon=False)
    print(f"Metrics server listening on http://{host}:{port}{cfg.metrics_server.path}")

    def _shutdown(*_: object) -> None:
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    return 0


def _cmd_watch(cfg: SentinelConfig, args: argparse.Namespace) -> int:
    evaluator = AlertEvaluator(cfg.alert_rules)
    dispatcher = AlertDispatcher(cfg.alert_channels)

    aggregator = LogAggregator(
        args.logfile,
        window_seconds=cfg.aggregator.window_seconds,
        poll_interval=cfg.aggregator.poll_interval_seconds,
    )
    aggregator.start()
    print(f"Watching {args.logfile} (window={cfg.aggregator.window_seconds}s)")

    try:
        while True:
            time.sleep(cfg.aggregator.poll_interval_seconds)
            stats = aggregator.stats
            events = evaluator.evaluate(stats)
            for event in events:
                dispatcher.dispatch(event)
            _print_status(stats)
    except KeyboardInterrupt:
        aggregator.stop()
        print("\nStopped.")
    return 0


def _cmd_check(cfg: SentinelConfig, args: argparse.Namespace) -> int:
    aggregator = LogAggregator(
        args.logfile,
        window_seconds=cfg.aggregator.window_seconds,
    )
    stats = aggregator.process_existing()

    evaluator = AlertEvaluator(cfg.alert_rules)
    events = evaluator.evaluate(stats)

    _print_report(stats, events)
    return 1 if events else 0


def _cmd_alert_test(cfg: SentinelConfig) -> int:
    rules = cfg.alert_rules
    if not rules:
        rules = [
            AlertRule(
                name="high_error_rate",
                metric="error_rate",
                operator=Operator.GT,
                threshold=0.05,
                window_seconds=300,
                severity=AlertSeverity.CRITICAL,
                channels=["stdout"],
            ),
        ]

    stats = RollingStats(
        total_entries=100,
        error_count=10,
        critical_count=2,
        warning_count=5,
        info_count=80,
        debug_count=3,
        window_start=time.time() - 300,
        window_end=time.time(),
    )

    print("Testing alert rules with synthetic data:")
    print(f"  error_rate    = {stats.error_rate:.2%}")
    print(f"  throughput    = {stats.throughput:.1f} entries/sec")
    print(f"  total_entries = {stats.total_entries}")
    print()

    evaluator = AlertEvaluator(rules)
    dispatcher = AlertDispatcher(cfg.alert_channels)

    events = evaluator.evaluate(stats)
    if events:
        for event in events:
            dispatcher.dispatch(event)
    else:
        print("No alerts triggered.")
    return 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _print_status(stats: RollingStats) -> None:
    sys.stdout.write(
        f"\r  entries={stats.total_entries} "
        f"err_rate={stats.error_rate:.2%} "
        f"throughput={stats.throughput:.1f}/s"
    )
    sys.stdout.flush()


def _print_report(stats: RollingStats, events: list[AlertEvent]) -> None:
    print("=== Log Analysis Report ===")
    print(f"  Total entries:  {stats.total_entries}")
    print(f"  Errors:         {stats.error_count}")
    print(f"  Critical:       {stats.critical_count}")
    print(f"  Warnings:       {stats.warning_count}")
    print(f"  Error rate:     {stats.error_rate:.2%}")
    print(f"  Throughput:     {stats.throughput:.1f} entries/sec")
    print()
    if events:
        print("Alerts triggered:")
        for event in events:
            print(f"  {event.message}")
    else:
        print("No alerts triggered.")


if __name__ == "__main__":
    sys.exit(main())
