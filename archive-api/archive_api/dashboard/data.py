"""Synchronous data access layer for the Dash dashboard.

Dash is built on Flask (synchronous), so it needs a sync database
connection separate from the async engine used by FastAPI. The engine
is created lazily to avoid connection failures during test imports.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

_COLUMNS = [
    "pl_name",
    "hostname",
    "discovery_method",
    "disc_year",
    "orbital_period",
    "pl_rade",
    "pl_bmasse",
    "pl_eqt",
    "st_teff",
    "st_rad",
    "sy_dist",
    "ra",
    "dec",
]

_RENAME = {
    "pl_name": "Planet",
    "hostname": "Host Star",
    "discovery_method": "Method",
    "disc_year": "Year",
    "orbital_period": "Period (days)",
    "pl_rade": "Radius (R⊕)",
    "pl_bmasse": "Mass (M⊕)",
    "pl_eqt": "Eq. Temp (K)",
    "st_teff": "Stellar Teff (K)",
    "st_rad": "Stellar Radius (R☉)",
    "sy_dist": "Distance (pc)",
    "ra": "RA (°)",
    "dec": "Dec (°)",
}


def _sync_url() -> str:
    url = os.getenv(
        "ARCHIVE_DATABASE_URL",
        "postgresql+asyncpg://archive:archive@localhost:5432/exoplanets",
    )
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


@lru_cache(maxsize=1)
def load_planets() -> pd.DataFrame:
    """Load all confirmed exoplanets into a DataFrame.

    Results are cached for the process lifetime. Returns a DataFrame
    with human-readable column aliases alongside the archive-standard
    column names used for plotting.
    """
    try:
        engine = create_engine(_sync_url(), pool_pre_ping=True)
        query = text(f"SELECT {', '.join(_COLUMNS)} FROM exoplanets ORDER BY pl_name")
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        engine.dispose()
    except Exception:
        logger.warning("dashboard: database unavailable, using empty dataset")
        df = pd.DataFrame(columns=_COLUMNS)

    return df.rename(columns=_RENAME)
