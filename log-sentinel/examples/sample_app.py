"""Demo application showing log-sentinel integration.

Generates structured logs and exposes Prometheus metrics at
http://127.0.0.1:9090/metrics.  Run with:

    python -m examples.sample_app

or:

    python examples/sample_app.py
"""

from __future__ import annotations

import random
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from log_sentinel import MetricsRegistry, MetricsServer, get_logger


def main() -> None:
    logger = get_logger(
        "sample_app",
        service_name="data-processor",
        file_path="sample_app.log",
    )

    registry = MetricsRegistry.get_instance()
    requests_total = registry.counter("requests_total", "Total requests processed")
    errors_total = registry.counter("errors_total", "Total errors encountered")
    records_processed = registry.counter("records_processed_total", "Records processed")
    active_connections = registry.gauge("active_connections", "Active DB connections")
    request_duration = registry.histogram("request_duration_seconds", "Request duration")

    server = MetricsServer(registry, host="127.0.0.1", port=9090)
    server.start()
    logger.info("Metrics server started", port=9090)

    try:
        batch = 0
        while True:
            batch += 1
            batch_logger = logger.bind(batch_id=batch)
            active_connections.set(random.randint(1, 10))

            batch_size = random.randint(10, 100)
            batch_logger.info("Processing batch", size=batch_size)

            start = time.monotonic()
            time.sleep(random.uniform(0.01, 0.2))
            duration = time.monotonic() - start

            requests_total.inc()
            request_duration.observe(duration)

            if random.random() < 0.1:
                errors_total.inc()
                batch_logger.error("Batch processing failed", duration=f"{duration:.3f}s")
            else:
                records_processed.inc(batch_size)
                batch_logger.info("Batch complete", records=batch_size, duration=f"{duration:.3f}s")

            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.stop()


if __name__ == "__main__":
    main()
