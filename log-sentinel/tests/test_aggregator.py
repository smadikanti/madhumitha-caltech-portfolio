"""Tests for the log aggregator."""

from __future__ import annotations

import json
import time

from log_sentinel.aggregator import LogAggregator, RollingWindow
from log_sentinel.models import LogEntry


class TestRollingWindow:
    def test_add_and_stats(self):
        w = RollingWindow(window_seconds=300)
        now = time.time()
        w.add(LogEntry(now - 10, "INFO", "test", "msg1"))
        w.add(LogEntry(now - 5, "ERROR", "test", "msg2"))
        w.add(LogEntry(now, "WARNING", "test", "msg3"))

        stats = w.stats()
        assert stats.total_entries == 3
        assert stats.error_count == 1
        assert stats.warning_count == 1

    def test_eviction(self):
        w = RollingWindow(window_seconds=10)
        old = time.time() - 20
        w.add(LogEntry(old, "INFO", "test", "old"))
        w.add(LogEntry(time.time(), "INFO", "test", "new"))

        stats = w.stats()
        assert stats.total_entries == 1

    def test_error_rate(self):
        w = RollingWindow(window_seconds=300)
        now = time.time()
        for i in range(8):
            w.add(LogEntry(now - i, "INFO", "test", f"info {i}"))
        w.add(LogEntry(now, "ERROR", "test", "err"))
        w.add(LogEntry(now, "CRITICAL", "test", "crit"))

        stats = w.stats()
        assert abs(stats.error_rate - 0.2) < 1e-9

    def test_empty_stats(self):
        w = RollingWindow(window_seconds=300)
        stats = w.stats()
        assert stats.total_entries == 0
        assert stats.error_rate == 0.0
        assert stats.throughput == 0.0

    def test_size_property(self):
        w = RollingWindow(window_seconds=300)
        assert w.size == 0
        w.add(LogEntry(time.time(), "INFO", "test", "msg"))
        assert w.size == 1

    def test_counts_all_levels(self):
        w = RollingWindow(window_seconds=300)
        now = time.time()
        w.add(LogEntry(now, "DEBUG", "test", "d"))
        w.add(LogEntry(now, "INFO", "test", "i"))
        w.add(LogEntry(now, "WARNING", "test", "w"))
        w.add(LogEntry(now, "ERROR", "test", "e"))
        w.add(LogEntry(now, "CRITICAL", "test", "c"))

        stats = w.stats()
        assert stats.debug_count == 1
        assert stats.info_count == 1
        assert stats.warning_count == 1
        assert stats.error_count == 1
        assert stats.critical_count == 1


class TestLogAggregator:
    def test_process_existing(self, sample_json_logs):
        agg = LogAggregator(sample_json_logs, window_seconds=3600)
        stats = agg.process_existing()
        assert stats.total_entries == 8
        assert stats.error_count == 2
        assert stats.critical_count == 1

    def test_process_nonexistent_file(self, tmp_path):
        agg = LogAggregator(tmp_path / "nope.log", window_seconds=300)
        stats = agg.process_existing()
        assert stats.total_entries == 0

    def test_watch_new_lines(self, tmp_path):
        log_file = tmp_path / "live.log"
        log_file.write_text("")

        entries_seen: list[LogEntry] = []
        agg = LogAggregator(
            log_file,
            poll_interval=0.1,
            window_seconds=300,
            on_entry=lambda e: entries_seen.append(e),
        )
        agg.start()
        try:
            time.sleep(0.2)
            with open(log_file, "a") as f:
                entry = {"timestamp": time.time(), "level": "INFO", "logger_name": "test", "message": "new line"}
                f.write(json.dumps(entry) + "\n")
                f.flush()
            time.sleep(0.5)
            assert len(entries_seen) >= 1
            assert entries_seen[0].message == "new line"
        finally:
            agg.stop()

    def test_handles_truncation(self, tmp_path):
        log_file = tmp_path / "rotate.log"
        entry1 = {"timestamp": time.time(), "level": "INFO", "logger_name": "test", "message": "before"}
        log_file.write_text(json.dumps(entry1) + "\n")

        agg = LogAggregator(log_file, poll_interval=0.1, window_seconds=300)
        agg.start()
        time.sleep(0.3)

        # Truncate and wait so the poller sees size < position
        log_file.write_text("")
        time.sleep(0.3)

        entry2 = {"timestamp": time.time(), "level": "ERROR", "logger_name": "test", "message": "after"}
        with open(log_file, "a") as f:
            f.write(json.dumps(entry2) + "\n")
            f.flush()
        time.sleep(0.5)

        stats = agg.stats
        agg.stop()
        assert stats.error_count >= 1

    def test_handles_partial_writes(self, tmp_path):
        log_file = tmp_path / "partial.log"
        log_file.write_text("")

        agg = LogAggregator(log_file, poll_interval=0.1, window_seconds=300)
        agg.start()
        try:
            time.sleep(0.2)
            entry = json.dumps(
                {"timestamp": time.time(), "level": "INFO", "logger_name": "t", "message": "complete"}
            )
            with open(log_file, "a") as f:
                f.write(entry[:10])
                f.flush()
            time.sleep(0.3)
            assert agg.stats.total_entries == 0

            with open(log_file, "a") as f:
                f.write(entry[10:] + "\n")
                f.flush()
            time.sleep(0.3)
            assert agg.stats.total_entries == 1
        finally:
            agg.stop()

    def test_multiple_lines_at_once(self, tmp_path):
        log_file = tmp_path / "multi.log"
        log_file.write_text("")

        agg = LogAggregator(log_file, poll_interval=0.1, window_seconds=300)
        agg.start()
        try:
            time.sleep(0.2)
            with open(log_file, "a") as f:
                for i in range(5):
                    entry = {"timestamp": time.time(), "level": "INFO", "logger_name": "t", "message": f"line {i}"}
                    f.write(json.dumps(entry) + "\n")
                f.flush()
            time.sleep(0.5)
            assert agg.stats.total_entries == 5
        finally:
            agg.stop()
