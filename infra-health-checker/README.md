# infra-health-checker

Bash scripts for system health checks + Python runner for aggregation, reporting, and alerting. Works on Linux and macOS.

## Quick start

```bash
pip install -r requirements.txt && pip install -e .
chmod +x checks/*.sh

python -m health_checker run                           # all checks
python -m health_checker run --check cpu,memory,disk   # specific checks
python -m health_checker report --format html -o report.html
python -m health_checker report --format json
python -m health_checker cron-setup --interval 5       # cron every 5 min
```

## Checks

Each script in `checks/` outputs structured JSON and accepts `--threshold`:

| Script | What it checks |
|--------|---------------|
| `cpu.sh` | CPU usage, load average |
| `memory.sh` | RAM total/used/available, swap |
| `disk.sh` | Disk usage per mount point |
| `network.sh` | Ping, DNS, port connectivity |
| `processes.sh` | Critical processes, zombie count |
| `docker.sh` | Daemon status, container health |
| `postgres.sh` | Connection test, connection count |
| `webserver.sh` | HTTP response time and status |

All scripts detect the OS (`uname`) and use the right commands for Linux vs macOS.

## Adding a check

Drop a `.sh` file in `checks/`. Follow the JSON contract:

```json
{"check":"name","status":"OK","value":45.2,"threshold":80,"message":"...","timestamp":"..."}
```

The runner auto-discovers it.

## Tests

```bash
pytest -v   # 38 tests
```
