"""Endpoints for querying the exoplanet catalog."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from archive_api.database import get_db
from archive_api.models import Exoplanet
from archive_api.schemas import ExoplanetResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/exoplanets", tags=["exoplanets"])

SORTABLE_COLUMNS = {
    "pl_name",
    "hostname",
    "discovery_method",
    "disc_year",
    "pl_bmasse",
    "pl_rade",
    "orbital_period",
    "sy_dist",
}


@router.get(
    "/search",
    response_model=PaginatedResponse,
    response_model_exclude_none=True,
    summary="Full-text search across planet name, host star, and discovery method",
)
async def search_exoplanets(
    q: str = Query(..., min_length=1, description="Search term"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """Return planets whose name, hostname, or discovery method match *q*."""
    pattern = f"%{q}%"
    where_clause = (
        Exoplanet.pl_name.ilike(pattern)
        | Exoplanet.hostname.ilike(pattern)
        | Exoplanet.discovery_method.ilike(pattern)
    )

    total = (
        await db.execute(
            select(func.count()).select_from(Exoplanet).where(where_clause)
        )
    ).scalar_one()

    rows = (
        (
            await db.execute(
                select(Exoplanet)
                .where(where_clause)
                .order_by(Exoplanet.pl_name)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedResponse(
        total_count=total, offset=offset, limit=limit, results=rows
    )


@router.get(
    "/{planet_name}",
    response_model=ExoplanetResponse,
    response_model_exclude_none=True,
    summary="Get a single exoplanet by its designation",
)
async def get_exoplanet(
    planet_name: str,
    db: AsyncSession = Depends(get_db),
) -> ExoplanetResponse:
    """Look up one planet by exact pl_name."""
    row = (
        await db.execute(select(Exoplanet).where(Exoplanet.pl_name == planet_name))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Planet '{planet_name}' not found")
    return row


@router.get(
    "",
    response_model=PaginatedResponse,
    response_model_exclude_none=True,
    summary="List exoplanets with filtering, sorting, and pagination",
)
async def list_exoplanets(
    discovery_method: str | None = Query(None, description="Exact discovery method"),
    hostname: str | None = Query(None, description="Exact host star name"),
    year_min: int | None = Query(None, ge=1900, description="Earliest discovery year"),
    year_max: int | None = Query(None, le=2100, description="Latest discovery year"),
    mass_min: float | None = Query(None, ge=0, description="Min mass (Earth masses)"),
    mass_max: float | None = Query(None, description="Max mass (Earth masses)"),
    radius_min: float | None = Query(None, ge=0, description="Min radius (Earth radii)"),
    radius_max: float | None = Query(None, description="Max radius (Earth radii)"),
    sort_by: str = Query("pl_name", description="Column to sort by"),
    sort_order: Literal["asc", "desc"] = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """Return a filtered, sorted, paginated list of confirmed exoplanets."""
    if sort_by not in SORTABLE_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by must be one of {sorted(SORTABLE_COLUMNS)}",
        )

    stmt = select(Exoplanet)
    count_stmt = select(func.count()).select_from(Exoplanet)

    filters = _build_filters(
        discovery_method=discovery_method,
        hostname=hostname,
        year_min=year_min,
        year_max=year_max,
        mass_min=mass_min,
        mass_max=mass_max,
        radius_min=radius_min,
        radius_max=radius_max,
    )
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    total = (await db.execute(count_stmt)).scalar_one()

    col = getattr(Exoplanet, sort_by)
    order = col.desc() if sort_order == "desc" else col.asc()
    stmt = stmt.order_by(order).offset(offset).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        total_count=total, offset=offset, limit=limit, results=rows
    )


def _build_filters(
    *,
    discovery_method: str | None,
    hostname: str | None,
    year_min: int | None,
    year_max: int | None,
    mass_min: float | None,
    mass_max: float | None,
    radius_min: float | None,
    radius_max: float | None,
) -> list:
    """Translate query parameters into SQLAlchemy filter clauses."""
    clauses = []
    if discovery_method is not None:
        clauses.append(Exoplanet.discovery_method == discovery_method)
    if hostname is not None:
        clauses.append(Exoplanet.hostname == hostname)
    if year_min is not None:
        clauses.append(Exoplanet.disc_year >= year_min)
    if year_max is not None:
        clauses.append(Exoplanet.disc_year <= year_max)
    if mass_min is not None:
        clauses.append(Exoplanet.pl_bmasse >= mass_min)
    if mass_max is not None:
        clauses.append(Exoplanet.pl_bmasse <= mass_max)
    if radius_min is not None:
        clauses.append(Exoplanet.pl_rade >= radius_min)
    if radius_max is not None:
        clauses.append(Exoplanet.pl_rade <= radius_max)
    return clauses
