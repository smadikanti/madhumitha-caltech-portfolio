"""Tests for the /api/v1/export endpoint."""

import csv
import io
import json

from httpx import AsyncClient


async def test_export_csv(client: AsyncClient):
    resp = await client.get("/api/v1/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 5
    assert "pl_name" in reader.fieldnames
    assert "hostname" in reader.fieldnames


async def test_export_json(client: AsyncClient):
    resp = await client.get("/api/v1/export", params={"format": "json"})
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]

    data = json.loads(resp.text)
    assert isinstance(data, list)
    assert len(data) == 5
    assert data[0]["pl_name"] is not None


async def test_export_votable(client: AsyncClient):
    resp = await client.get("/api/v1/export", params={"format": "votable"})
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    assert "<VOTABLE" in resp.text
    assert "<FIELD" in resp.text
    assert "<TABLEDATA>" in resp.text
    assert resp.text.count("<TR>") == 5


async def test_export_csv_content_disposition(client: AsyncClient):
    resp = await client.get("/api/v1/export", params={"format": "csv"})
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "exoplanets.csv" in resp.headers.get("content-disposition", "")


async def test_export_default_format_is_csv(client: AsyncClient):
    resp = await client.get("/api/v1/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


async def test_export_invalid_format(client: AsyncClient):
    resp = await client.get("/api/v1/export", params={"format": "parquet"})
    assert resp.status_code == 422
