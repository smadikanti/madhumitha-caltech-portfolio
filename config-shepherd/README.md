# config-shepherd

Config management tool for multi-environment deployments. YAML inheritance, JSON Schema validation, secret scanning, and version drift detection.

## Usage

```bash
pip install -r requirements.txt && pip install -e .

python -m config_shepherd validate examples/            # validate against schema
python -m config_shepherd diff dev prod                 # colored config diff
python -m config_shepherd scan examples/                # find leaked secrets
python -m config_shepherd snapshot -o snapshot.yaml     # capture env state
python -m config_shepherd inventory examples/           # software version matrix
python -m config_shepherd merge base.yaml dev.yaml      # merge with deep override
```

## How inheritance works

```yaml
# dev.yaml
inherits: base
app:
  debug: true
database:
  pool_size: 2
```

Everything from `base.yaml` is preserved unless overridden. Nested dicts are deep-merged.

## Secret patterns detected

AWS keys, API keys, passwords, private keys, connection strings, GitHub/Slack tokens. Configurable via regex. Binary files skipped.

## Tests

```bash
pytest -v   # 92 tests
```
