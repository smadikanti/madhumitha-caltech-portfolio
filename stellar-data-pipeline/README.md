# stellar-data-pipeline

Data ingestion pipeline that pulls confirmed exoplanet data from the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/) TAP API, validates it, transforms units, and loads into PostgreSQL.

Pipeline stages: **Extract → Validate → Transform → Load**

- Fetches via TAP sync endpoint (ADQL queries, JSON response)
- Validates against physical constraints (positive radius, positive mass, etc.) and detects duplicates
- Transforms units (Earth radii → Jupiter radii), derives habitable zone flag from equilibrium temperature
- Loads with `INSERT ... ON CONFLICT DO UPDATE` (idempotent, safe to re-run)
- Retry with exponential backoff + jitter on API failures
- Structured logging (JSON to file, human-readable to console)

## Usage

```bash
pip install -r requirements.txt && pip install -e .
cp config.yaml.example config.yaml   # edit DB creds

python -m stellar_pipeline ingest
python -m stellar_pipeline ingest --limit 100 --dry-run
python -m stellar_pipeline validate
python -m stellar_pipeline status
```

## Tests

```bash
pytest -v
```

All external calls (API, DB) are mocked. No network or database needed.

## Config

See `config.yaml.example`. Supports `${ENV_VAR}` interpolation for secrets.
