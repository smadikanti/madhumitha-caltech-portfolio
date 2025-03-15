"""Tests for the Prometheus metrics registry and exposition."""

from __future__ import annotations

import threading
import time
import urllib.request

from log_sentinel.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    MetricsServer,
)


class TestCounter:
    def test_increment(self):
        c = Counter("test_total", "A test counter")
        c.inc()
        c.inc(5)
        assert c.get() == 6.0

    def test_negative_increment_raises(self):
        c = Counter("neg_total", "A test counter")
        try:
            c.inc(-1)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_labels(self):
        c = Counter("http_requests_total", "HTTP requests", label_names=["method"])
        c.inc(labels={"method": "GET"})
        c.inc(labels={"method": "POST"})
        c.inc(labels={"method": "GET"})
        assert c.get(labels={"method": "GET"}) == 2.0
        assert c.get(labels={"method": "POST"}) == 1.0

    def test_expose_format(self):
        c = Counter("errors_total", "Total errors")
        c.inc(3)
        output = c.expose()
        assert "# HELP errors_total Total errors" in output
        assert "# TYPE errors_total counter" in output
        assert "errors_total 3" in output

    def test_expose_with_labels(self):
        c = Counter("reqs_total", "Requests", label_names=["code"])
        c.inc(10, labels={"code": "200"})
        c.inc(2, labels={"code": "500"})
        output = c.expose()
        assert 'reqs_total{code="200"} 10' in output
        assert 'reqs_total{code="500"} 2' in output

    def test_thread_safety(self):
        c = Counter("concurrent_total", "Concurrency test")

        def inc_many():
            for _ in range(1000):
                c.inc()

        threads = [threading.Thread(target=inc_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert c.get() == 10000.0


class TestGauge:
    def test_set_and_get(self):
        g = Gauge("temperature", "Current temp")
        g.set(72.5)
        assert g.get() == 72.5

    def test_inc_dec(self):
        g = Gauge("connections", "Active connections")
        g.inc()
        g.inc()
        g.dec()
        assert g.get() == 1.0

    def test_expose_format(self):
        g = Gauge("queue_depth", "Queue depth")
        g.set(42)
        output = g.expose()
        assert "# TYPE queue_depth gauge" in output
        assert "queue_depth 42" in output

    def test_labels(self):
        g = Gauge("pool_size", "Pool size", label_names=["pool"])
        g.set(5, labels={"pool": "read"})
        g.set(10, labels={"pool": "write"})
        assert g.get(labels={"pool": "read"}) == 5
        assert g.get(labels={"pool": "write"}) == 10


class TestHistogram:
    def test_observe_and_expose(self):
        h = Histogram("duration_seconds", "Duration", buckets=[0.1, 0.5, 1.0])
        h.observe(0.05)
        h.observe(0.3)
        h.observe(0.8)
        h.observe(2.0)
        output = h.expose()
        assert "# TYPE duration_seconds histogram" in output
        assert 'duration_seconds_bucket{le="0.1"} 1' in output
        assert 'duration_seconds_bucket{le="0.5"} 2' in output
        assert 'duration_seconds_bucket{le="1.0"} 3' in output
        assert 'duration_seconds_bucket{le="+Inf"} 4' in output
        assert "duration_seconds_count 4" in output

    def test_sum_accuracy(self):
        h = Histogram("test_hist", "test", buckets=[1.0])
        h.observe(0.5)
        h.observe(1.5)
        output = h.expose()
        assert "test_hist_sum 2.0" in output

    def test_empty_histogram(self):
        h = Histogram("empty_hist", "empty", buckets=[1.0])
        output = h.expose()
        assert "# HELP empty_hist empty" in output
        assert "# TYPE empty_hist histogram" in output

    def test_inf_bucket_always_present(self):
        h = Histogram("custom_hist", "custom", buckets=[0.5])
        h.observe(100)
        output = h.expose()
        assert 'le="+Inf"' in output


class TestMetricsRegistry:
    def test_register_and_expose(self):
        reg = MetricsRegistry()
        c = reg.counter("reqs_total", "Total requests")
        g = reg.gauge("active", "Active items")
        c.inc(10)
        g.set(5)
        output = reg.expose()
        assert "reqs_total 10" in output
        assert "active 5" in output

    def test_duplicate_registration_returns_same(self):
        reg = MetricsRegistry()
        c1 = reg.counter("dup_total", "First")
        c2 = reg.counter("dup_total", "First")
        assert c1 is c2

    def test_type_mismatch_raises(self):
        reg = MetricsRegistry()
        reg.counter("conflict", "A counter")
        try:
            reg.gauge("conflict", "A gauge")
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_singleton(self):
        a = MetricsRegistry.get_instance()
        b = MetricsRegistry.get_instance()
        assert a is b

    def test_reset_clears_singleton(self):
        a = MetricsRegistry.get_instance()
        MetricsRegistry.reset()
        b = MetricsRegistry.get_instance()
        assert a is not b


class TestMetricsServer:
    def test_serves_metrics(self):
        reg = MetricsRegistry()
        c = reg.counter("server_test_total", "Test counter")
        c.inc(42)
        server = MetricsServer(reg, host="127.0.0.1", port=0, path="/metrics")
        server.start(daemon=True)
        try:
            time.sleep(0.15)
            port = server.port
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics")
            body = resp.read().decode()
            assert "server_test_total 42" in body
            assert "# HELP server_test_total" in body
        finally:
            server.stop()

    def test_404_on_wrong_path(self):
        reg = MetricsRegistry()
        server = MetricsServer(reg, host="127.0.0.1", port=0, path="/metrics")
        server.start(daemon=True)
        try:
            time.sleep(0.15)
            port = server.port
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/wrong")
                assert False, "Should have raised"
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            server.stop()

    def test_url_property(self):
        server = MetricsServer(host="0.0.0.0", port=9999, path="/metrics")
        assert server.url == "http://0.0.0.0:9999/metrics"
