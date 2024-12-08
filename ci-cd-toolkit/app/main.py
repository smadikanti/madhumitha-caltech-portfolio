"""Minimal Flask application demonstrating the CI/CD pipeline."""

from __future__ import annotations

import os
import time
from typing import Any

import redis
from flask import Flask, jsonify

app = Flask(__name__)

_start_time = time.time()


def _get_redis() -> redis.Redis | None:
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        client = redis.from_url(url, socket_connect_timeout=2)
        client.ping()
        return client
    except redis.ConnectionError:
        return None


@app.route("/health")
def health() -> tuple[Any, int]:
    checks: dict[str, str] = {"app": "ok"}

    r = _get_redis()
    checks["redis"] = "ok" if r else "unavailable"

    status = 200 if checks["app"] == "ok" else 503
    return jsonify(
        status="healthy" if status == 200 else "degraded",
        uptime_seconds=round(time.time() - _start_time, 1),
        checks=checks,
        version=os.getenv("APP_VERSION", "dev"),
        environment=os.getenv("APP_ENV", "local"),
    ), status


@app.route("/ready")
def readiness() -> tuple[Any, int]:
    """Kubernetes readiness probe — only ok when all dependencies are reachable."""
    r = _get_redis()
    if r is None and os.getenv("REDIS_URL"):
        return jsonify(ready=False, reason="redis unreachable"), 503
    return jsonify(ready=True), 200


@app.route("/")
def index() -> dict[str, str]:
    return {"service": "ci-cd-toolkit", "docs": "/health"}


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
