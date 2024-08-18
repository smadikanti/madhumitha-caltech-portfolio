# personal projects

Tools and utilities I've built while working on data pipelines, DevOps, and infrastructure monitoring.

| Project | What it does | Stack |
|---------|-------------|-------|
| [stellar-data-pipeline](./stellar-data-pipeline/) | Ingests exoplanet data from NASA's TAP API into PostgreSQL | Python, PostgreSQL |
| [fits-image-processor](./fits-image-processor/) | FITS image processing — stacking, CCD calibration, thumbnails | Python, astropy |
| [ci-cd-toolkit](./ci-cd-toolkit/) | Reusable CI/CD framework with GitHub Actions + Docker + K8s | Bash, YAML, Docker |
| [archive-api](./archive-api/) | REST API + dashboard for querying scientific datasets | Python, FastAPI, Dash |
| [log-sentinel](./log-sentinel/) | Structured logging + Prometheus metrics + alerting | Python |
| [config-shepherd](./config-shepherd/) | Config management with inheritance, validation, secret scanning | Python, YAML |
| [infra-health-checker](./infra-health-checker/) | System health checks (bash) + Python reporting engine | Bash, Python |

Each project has its own README. Generally:

```bash
cd <project>
pip install -r requirements.txt && pip install -e .
pytest
```
