"""Prometheus-compatible metrics registry and HTTP exposition server."""

from __future__ import annotations

import math
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Sequence

from .models import MetricType

DEFAULT_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75,
    1.0, 2.5, 5.0, 7.5, 10.0, float("inf"),
)


def _labels_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _format_labels(key: tuple[tuple[str, str], ...]) -> str:
    if not key:
        return ""
    pairs = ",".join(f'{k}="{v}"' for k, v in key)
    return "{" + pairs + "}"


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self.metric_type = MetricType.COUNTER
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        if amount < 0:
            raise ValueError("Counter increment must be non-negative")
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def get(self, labels: dict[str, str] | None = None) -> float:
        key = _labels_key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def expose(self) -> str:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            for key, value in sorted(self._values.items()):
                lines.append(f"{self.name}{_format_labels(key)} {value}")
        return "\n".join(lines)


class Gauge:
    """Value that can arbitrarily go up and down."""

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self.metric_type = MetricType.GAUGE
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

    def get(self, labels: dict[str, str] | None = None) -> float:
        key = _labels_key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def expose(self) -> str:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
        ]
        with self._lock:
            for key, value in sorted(self._values.items()):
                lines.append(f"{self.name}{_format_labels(key)} {value}")
        return "\n".join(lines)


class _HistogramData:
    """Per-label-set accumulator for histogram observations."""

    __slots__ = ("bucket_counts", "total_sum", "count", "_upper_bounds")

    def __init__(self, upper_bounds: tuple[float, ...]) -> None:
        self._upper_bounds = upper_bounds
        self.bucket_counts: dict[float, int] = {b: 0 for b in upper_bounds}
        self.total_sum: float = 0.0
        self.count: int = 0

    def observe(self, value: float) -> None:
        self.total_sum += value
        self.count += 1
        for bound in self._upper_bounds:
            if value <= bound:
                self.bucket_counts[bound] += 1


class Histogram:
    """Tracks the distribution of observed values across configurable buckets."""

    def __init__(
        self,
        name: str,
        help_text: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self.metric_type = MetricType.HISTOGRAM
        self._upper_bounds = tuple(sorted(set(buckets) | {float("inf")}))
        self._data: dict[tuple[tuple[str, str], ...], _HistogramData] = {}
        self._lock = threading.Lock()

    def _get_data(self, key: tuple[tuple[str, str], ...]) -> _HistogramData:
        if key not in self._data:
            self._data[key] = _HistogramData(self._upper_bounds)
        return self._data[key]

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        with self._lock:
            self._get_data(key).observe(value)

    def expose(self) -> str:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            for key in sorted(self._data):
                data = self._data[key]
                base_labels = dict(key)
                for bound in self._upper_bounds:
                    le = "+Inf" if math.isinf(bound) else str(bound)
                    merged = {**base_labels, "le": le}
                    lbl = _format_labels(_labels_key(merged))
                    lines.append(f"{self.name}_bucket{lbl} {data.bucket_counts[bound]}")
                lbl = _format_labels(key)
                lines.append(f"{self.name}_sum{lbl} {data.total_sum}")
                lines.append(f"{self.name}_count{lbl} {data.count}")
        return "\n".join(lines)


class MetricsRegistry:
    """Central registry for all application metrics.

    Thread-safe singleton that holds metric collectors and produces the
    combined Prometheus exposition output.
    """

    _instance: MetricsRegistry | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> MetricsRegistry:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (primarily for testing)."""
        with cls._instance_lock:
            cls._instance = None

    def counter(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> Counter:
        with self._lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if not isinstance(existing, Counter):
                    raise TypeError(f"Metric {name} already registered as {type(existing).__name__}")
                return existing
            c = Counter(name, help_text, label_names)
            self._metrics[name] = c
            return c

    def gauge(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> Gauge:
        with self._lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if not isinstance(existing, Gauge):
                    raise TypeError(f"Metric {name} already registered as {type(existing).__name__}")
                return existing
            g = Gauge(name, help_text, label_names)
            self._metrics[name] = g
            return g

    def histogram(
        self,
        name: str,
        help_text: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> Histogram:
        with self._lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if not isinstance(existing, Histogram):
                    raise TypeError(f"Metric {name} already registered as {type(existing).__name__}")
                return existing
            h = Histogram(name, help_text, label_names, buckets)
            self._metrics[name] = h
            return h

    def expose(self) -> str:
        """Produce the full Prometheus exposition format output."""
        with self._lock:
            metrics = list(self._metrics.values())
        blocks = [m.expose() for m in metrics]
        return "\n\n".join(blocks) + "\n"


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server: _MetricsHTTPServer = self.server  # type: ignore[assignment]
        if self.path.rstrip("/") == server.metrics_path.rstrip("/"):
            body = server.registry.expose().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        pass


class _MetricsHTTPServer(HTTPServer):
    """HTTPServer subclass that carries registry and path config."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        registry: MetricsRegistry,
        metrics_path: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.registry = registry
        self.metrics_path = metrics_path


class MetricsServer:
    """HTTP server that exposes a ``/metrics`` endpoint for Prometheus scraping."""

    def __init__(
        self,
        registry: MetricsRegistry | None = None,
        host: str = "0.0.0.0",
        port: int = 9090,
        path: str = "/metrics",
    ) -> None:
        self._registry = registry or MetricsRegistry.get_instance()
        self._host = host
        self._port = port
        self._path = path
        self._server: _MetricsHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        """Actual bound port (useful when constructed with port 0)."""
        if self._server:
            return self._server.server_address[1]
        return self._port

    def start(self, *, daemon: bool = True) -> None:
        """Start the metrics server in a background thread."""
        self._server = _MetricsHTTPServer(
            (self._host, self._port),
            _MetricsHandler,
            self._registry,
            self._path,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=daemon)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self.port}{self._path}"
