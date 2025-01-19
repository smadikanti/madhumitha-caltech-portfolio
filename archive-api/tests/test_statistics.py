"""Tests for the /api/v1/statistics endpoint."""

from httpx import AsyncClient


async def test_statistics_total(client: AsyncClient):
    resp = await client.get("/api/v1/statistics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_planets"] == 5


async def test_statistics_by_discovery_method(client: AsyncClient):
    resp = await client.get("/api/v1/statistics")
    body = resp.json()
    methods = {m["method"]: m["count"] for m in body["by_discovery_method"]}
    assert methods["Transit"] == 3
    assert methods["Radial Velocity"] == 1
    assert methods["Direct Imaging"] == 1


async def test_statistics_by_year(client: AsyncClient):
    resp = await client.get("/api/v1/statistics")
    body = resp.json()
    years = {y["year"]: y["count"] for y in body["by_year"]}
    assert years[2020] == 1
    assert years[2015] == 1
    assert years[2010] == 1
    assert years[2022] == 1
    assert years[2018] == 1


async def test_statistics_parameter_distributions(client: AsyncClient):
    resp = await client.get("/api/v1/statistics")
    body = resp.json()
    dist_map = {d["parameter"]: d for d in body["parameter_distributions"]}

    assert "orbital_period" in dist_map
    assert "pl_rade" in dist_map
    assert "pl_bmasse" in dist_map

    op = dist_map["orbital_period"]
    assert op["min_val"] is not None
    assert op["max_val"] is not None
    assert op["mean_val"] is not None
    assert op["min_val"] <= op["mean_val"] <= op["max_val"]
