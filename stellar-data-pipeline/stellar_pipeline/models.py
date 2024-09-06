"""Data models for the stellar data pipeline.

Uses dataclasses to represent exoplanet records at each pipeline stage
and metadata about pipeline execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


TAP_COLUMNS = [
    "pl_name", "hostname", "discoverymethod", "disc_year",
    "pl_orbper", "pl_rade", "pl_bmasse", "pl_eqt",
    "st_teff", "st_rad", "st_mass", "sy_dist",
]

REQUIRED_FIELDS = ("pl_name", "hostname")


@dataclass
class RawExoplanet:
    """Raw record from the TAP API before validation.

    All fields are optional because the API may return nulls or
    omit columns for certain records.
    """

    pl_name: Optional[str] = None
    hostname: Optional[str] = None
    discoverymethod: Optional[str] = None
    disc_year: Optional[int] = None
    pl_orbper: Optional[float] = None
    pl_rade: Optional[float] = None
    pl_bmasse: Optional[float] = None
    pl_eqt: Optional[float] = None
    st_teff: Optional[float] = None
    st_rad: Optional[float] = None
    st_mass: Optional[float] = None
    sy_dist: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> RawExoplanet:
        """Construct from an API response dictionary, ignoring unknown keys."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class Exoplanet:
    """Validated and transformed exoplanet record ready for database loading."""

    pl_name: str
    hostname: str
    discovery_method: Optional[str] = None
    disc_year: Optional[int] = None
    orbital_period_days: Optional[float] = None
    radius_earth: Optional[float] = None
    radius_jupiter: Optional[float] = None
    mass_earth: Optional[float] = None
    mass_jupiter: Optional[float] = None
    equilibrium_temp_k: Optional[float] = None
    stellar_teff_k: Optional[float] = None
    stellar_radius_solar: Optional[float] = None
    stellar_mass_solar: Optional[float] = None
    distance_pc: Optional[float] = None
    is_habitable_zone: bool = False


@dataclass
class ValidationReport:
    """Summary of a validation pass over raw records."""

    valid_records: list[RawExoplanet] = field(default_factory=list)
    invalid_records: list[tuple[RawExoplanet, list[str]]] = field(default_factory=list)
    duplicate_count: int = 0

    @property
    def total_checked(self) -> int:
        return len(self.valid_records) + len(self.invalid_records) + self.duplicate_count

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_records)


@dataclass
class PipelineResult:
    """Metadata and outcome of a single pipeline run."""

    run_id: uuid.UUID = field(default_factory=uuid.uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"
    records_extracted: int = 0
    records_validated: int = 0
    records_failed_validation: int = 0
    records_transformed: int = 0
    records_loaded: int = 0
    error_message: Optional[str] = None

    def mark_complete(self, status: str = "success") -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.status = status

    def mark_failed(self, error: str) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.status = "failed"
        self.error_message = error

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()
