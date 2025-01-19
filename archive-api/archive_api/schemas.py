"""Pydantic models for request validation and response serialization."""

from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Exoplanet
# ---------------------------------------------------------------------------

class ExoplanetBase(BaseModel):
    """Shared fields across create/response schemas."""

    pl_name: str = Field(..., description="Planet designation (e.g. 'Kepler-442 b')")
    hostname: str = Field(..., description="Host star name")
    discovery_method: str = Field(..., description="Detection technique")
    disc_year: int | None = Field(None, ge=1900, le=2100, description="Year of discovery")
    orbital_period: float | None = Field(None, gt=0, description="Orbital period in days")
    pl_rade: float | None = Field(None, gt=0, description="Planet radius in Earth radii")
    pl_bmasse: float | None = Field(None, gt=0, description="Planet mass in Earth masses")
    pl_eqt: float | None = Field(None, gt=0, description="Equilibrium temperature in K")
    st_teff: float | None = Field(None, gt=0, description="Stellar effective temperature in K")
    st_rad: float | None = Field(None, gt=0, description="Stellar radius in solar radii")
    sy_dist: float | None = Field(None, gt=0, description="Distance in parsecs")
    ra: float | None = Field(None, ge=0, le=360, description="Right ascension in degrees")
    dec: float | None = Field(None, ge=-90, le=90, description="Declination in degrees")


class ExoplanetResponse(ExoplanetBase):
    """Single exoplanet returned by the API."""

    model_config = {"from_attributes": True}

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PaginatedResponse(BaseModel):
    """Paginated list of exoplanets with total count."""

    total_count: int
    offset: int
    limit: int
    results: list[ExoplanetResponse]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

class DiscoveryMethodCount(BaseModel):
    method: str
    count: int


class YearCount(BaseModel):
    year: int
    count: int


class ParameterDistribution(BaseModel):
    parameter: str
    min_val: float | None = None
    max_val: float | None = None
    mean_val: float | None = None


class StatisticsResponse(BaseModel):
    total_planets: int
    by_discovery_method: list[DiscoveryMethodCount]
    by_year: list[YearCount]
    parameter_distributions: list[ParameterDistribution]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class ExportFormat(str, Enum):
    csv = "csv"
    json = "json"
    votable = "votable"


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
