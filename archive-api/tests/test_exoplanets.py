"""Tests for the /api/v1/exoplanets endpoints."""

import pytest
from httpx import AsyncClient


async def test_list_all(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 5
    assert len(body["results"]) == 5
    assert "offset" in body
    assert "limit" in body


async def test_list_pagination(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["total_count"] == 5

    resp2 = await client.get("/api/v1/exoplanets", params={"limit": 2, "offset": 2})
    body2 = resp2.json()
    assert len(body2["results"]) == 2
    names_page1 = {r["pl_name"] for r in body["results"]}
    names_page2 = {r["pl_name"] for r in body2["results"]}
    assert names_page1.isdisjoint(names_page2)


async def test_filter_by_discovery_method(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"discovery_method": "Radial Velocity"}
    )
    body = resp.json()
    assert body["total_count"] == 1
    assert body["results"][0]["pl_name"] == "Test-2 c"


async def test_filter_by_year_range(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"year_min": 2018, "year_max": 2022}
    )
    body = resp.json()
    assert body["total_count"] == 3
    years = {r["disc_year"] for r in body["results"]}
    assert all(2018 <= y <= 2022 for y in years)


async def test_filter_by_mass_range(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"mass_min": 100, "mass_max": 500}
    )
    body = resp.json()
    assert body["total_count"] == 1
    assert body["results"][0]["pl_name"] == "Test-2 c"


async def test_filter_by_radius_range(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"radius_min": 10}
    )
    body = resp.json()
    assert body["total_count"] == 2
    names = {r["pl_name"] for r in body["results"]}
    assert names == {"Test-2 c", "Test-3 d"}


async def test_filter_by_hostname(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"hostname": "Test-1"}
    )
    body = resp.json()
    assert body["total_count"] == 1
    assert body["results"][0]["hostname"] == "Test-1"


async def test_sort_by_disc_year_desc(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"sort_by": "disc_year", "sort_order": "desc"}
    )
    body = resp.json()
    years = [r["disc_year"] for r in body["results"]]
    assert years == sorted(years, reverse=True)


async def test_invalid_sort_column(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets", params={"sort_by": "nonexistent"}
    )
    assert resp.status_code == 400


async def test_get_single_planet(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/Test-1 b")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pl_name"] == "Test-1 b"
    assert body["hostname"] == "Test-1"
    assert body["discovery_method"] == "Transit"
    assert body["disc_year"] == 2020


async def test_get_planet_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/Nonexistent-1 z")
    assert resp.status_code == 404


async def test_search_by_planet_name(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/search", params={"q": "Kepler"})
    body = resp.json()
    assert body["total_count"] == 1
    assert body["results"][0]["pl_name"] == "Kepler-999 b"


async def test_search_by_hostname(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/search", params={"q": "Alpha"})
    body = resp.json()
    assert body["total_count"] == 1
    assert body["results"][0]["hostname"] == "Alpha Centauri X"


async def test_search_by_discovery_method(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/search", params={"q": "Imaging"})
    body = resp.json()
    assert body["total_count"] == 1
    assert body["results"][0]["discovery_method"] == "Direct Imaging"


async def test_search_no_results(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/search", params={"q": "zzzzz"})
    body = resp.json()
    assert body["total_count"] == 0
    assert body["results"] == []


async def test_search_pagination(client: AsyncClient):
    resp = await client.get(
        "/api/v1/exoplanets/search", params={"q": "Test", "limit": 2}
    )
    body = resp.json()
    assert body["total_count"] == 3
    assert len(body["results"]) == 2


async def test_none_fields_excluded(client: AsyncClient):
    resp = await client.get("/api/v1/exoplanets/Test-3 d")
    body = resp.json()
    assert "pl_eqt" not in body


async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body


async def test_metrics_endpoint(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert b"http_requests_total" in resp.content
