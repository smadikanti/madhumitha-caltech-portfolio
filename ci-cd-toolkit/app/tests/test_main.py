"""Tests for the Flask health-check application."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.main import app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["service"] == "ci-cd-toolkit"


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert data["checks"]["app"] == "ok"


def test_health_redis_unavailable(client):
    with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
        with patch("app.main._get_redis", return_value=None):
            resp = client.get("/health")
            data = json.loads(resp.data)
            assert data["checks"]["redis"] == "unavailable"


def test_readiness_no_redis_required(client):
    with patch.dict("os.environ", {}, clear=True):
        resp = client.get("/ready")
        assert resp.status_code == 200


def test_readiness_redis_down(client):
    with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
        with patch("app.main._get_redis", return_value=None):
            resp = client.get("/ready")
            assert resp.status_code == 503
