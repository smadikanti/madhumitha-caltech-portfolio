# log-sentinel

Structured logging + Prometheus metrics + threshold alerting for Python services.

## Usage

```python
from log_sentinel import get_logger, MetricsRegistry

# structured JSON logging
log = get_logger("my_pipeline", service_name="data-ingest")
log.info("Pipeline started", records=15000)

# prometheus metrics
registry = MetricsRegistry.get_instance()
counter = registry.counter("records_total", "Records processed")
counter.inc()
```

## CLI

```bash
pip install -r requirements.txt && pip install -e .

python -m log_sentinel serve --port 9090          # metrics HTTP server
python -m log_sentinel watch /var/log/app.log     # real-time aggregation + alerting
python -m log_sentinel check /var/log/app.log     # one-shot analysis
python -m log_sentinel alert-test                  # test alert rules
```

## Alerting

Configure in `config.yaml` (see `config.yaml.example`):

```yaml
alert_rules:
  - name: high_error_rate
    metric: error_rate
    operator: ">"
    threshold: 0.05
    window_seconds: 300
    severity: critical
```

Channels: stdout, file (JSONL), webhook.

## Tests

```bash
pytest -v   # 61 tests
```
