# archive-api

FastAPI REST service for querying exoplanet datasets + interactive Plotly Dash dashboard. Inspired by the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/exoplanets` | List with filtering, sorting, pagination |
| `GET` | `/api/v1/exoplanets/{name}` | Single planet detail |
| `GET` | `/api/v1/exoplanets/search?q=` | Full-text search |
| `GET` | `/api/v1/statistics` | Counts by method/year, parameter distributions |
| `GET` | `/api/v1/export?format=csv\|json\|votable` | Bulk export (VOTable = IVOA standard) |
| `GET` | `/dashboard/` | Interactive Plotly Dash dashboard |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

Filter params: `discovery_method`, `hostname`, `year_min/max`, `mass_min/max`, `radius_min/max`, `sort_by`, `sort_order`, `offset`, `limit`.

## Dashboard

Four tabs: overview (KPIs + charts), mass-radius diagram (log-log scatter with Earth/Jupiter reference lines), sky map (RA/Dec), and filterable data table. Can also run standalone on port 8050.

## Quick start

```bash
# with docker
docker compose up --build
# API at :8000, dashboard at :8000/dashboard/

# or locally
pip install -r requirements.txt && pip install -e .
alembic upgrade head
python -m archive_api.seed
uvicorn archive_api.main:app --reload
```

## Tests

```bash
pytest -v   # 42 tests, uses in-memory SQLite
```

Column names (`pl_name`, `pl_rade`, `pl_bmasse`, `st_teff`, etc.) mirror the NASA Exoplanet Archive PS table. Seeded with 30 real exoplanets.
