"""Aggregate statistics over the exoplanet catalog."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from archive_api.database import get_db
from archive_api.models import Exoplanet
from archive_api.schemas import (
    DiscoveryMethodCount,
    ParameterDistribution,
    StatisticsResponse,
    YearCount,
)

router = APIRouter(prefix="/api/v1/statistics", tags=["statistics"])

_NUMERIC_PARAMS: list[tuple[str, object]] = [
    ("orbital_period", Exoplanet.orbital_period),
    ("pl_rade", Exoplanet.pl_rade),
    ("pl_bmasse", Exoplanet.pl_bmasse),
    ("pl_eqt", Exoplanet.pl_eqt),
    ("st_teff", Exoplanet.st_teff),
]


@router.get(
    "",
    response_model=StatisticsResponse,
    summary="Aggregate statistics across the full catalog",
)
async def get_statistics(
    db: AsyncSession = Depends(get_db),
) -> StatisticsResponse:
    """Return counts by discovery method, by year, and parameter distributions."""
    total = (
        await db.execute(select(func.count()).select_from(Exoplanet))
    ).scalar_one()

    method_rows = (
        await db.execute(
            select(Exoplanet.discovery_method, func.count())
            .group_by(Exoplanet.discovery_method)
            .order_by(func.count().desc())
        )
    ).all()
    by_method = [DiscoveryMethodCount(method=r[0], count=r[1]) for r in method_rows]

    year_rows = (
        await db.execute(
            select(Exoplanet.disc_year, func.count())
            .where(Exoplanet.disc_year.is_not(None))
            .group_by(Exoplanet.disc_year)
            .order_by(Exoplanet.disc_year)
        )
    ).all()
    by_year = [YearCount(year=r[0], count=r[1]) for r in year_rows]

    distributions: list[ParameterDistribution] = []
    for name, col in _NUMERIC_PARAMS:
        row = (
            await db.execute(
                select(func.min(col), func.max(col), func.avg(col)).where(
                    col.is_not(None)
                )
            )
        ).one()
        distributions.append(
            ParameterDistribution(
                parameter=name,
                min_val=round(row[0], 4) if row[0] is not None else None,
                max_val=round(row[1], 4) if row[1] is not None else None,
                mean_val=round(float(row[2]), 4) if row[2] is not None else None,
            )
        )

    return StatisticsResponse(
        total_planets=total,
        by_discovery_method=by_method,
        by_year=by_year,
        parameter_distributions=distributions,
    )
