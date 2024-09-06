"""Shared pytest fixtures for the stellar data pipeline test suite."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from stellar_pipeline.config import ApiConfig, Config, DatabaseConfig, PipelineConfig
from stellar_pipeline.models import Exoplanet, RawExoplanet


@pytest.fixture
def sample_api_row() -> dict:
    """A single valid row as returned by the TAP API JSON response."""
    return {
        "pl_name": "Kepler-22 b",
        "hostname": "Kepler-22",
        "discoverymethod": "Transit",
        "disc_year": 2011,
        "pl_orbper": 289.8623,
        "pl_rade": 2.38,
        "pl_bmasse": 9.1,
        "pl_eqt": 262.0,
        "st_teff": 5518.0,
        "st_rad": 0.979,
        "st_mass": 0.97,
        "sy_dist": 190.12,
    }


@pytest.fixture
def sample_api_rows(sample_api_row: dict) -> list[dict]:
    """Multiple valid rows as returned by the TAP API."""
    return [
        sample_api_row,
        {
            "pl_name": "TRAPPIST-1 e",
            "hostname": "TRAPPIST-1",
            "discoverymethod": "Transit",
            "disc_year": 2017,
            "pl_orbper": 6.0996,
            "pl_rade": 0.92,
            "pl_bmasse": 0.692,
            "pl_eqt": 251.0,
            "st_teff": 2566.0,
            "st_rad": 0.121,
            "st_mass": 0.0898,
            "sy_dist": 12.43,
        },
        {
            "pl_name": "51 Peg b",
            "hostname": "51 Peg",
            "discoverymethod": "Radial Velocity",
            "disc_year": 1995,
            "pl_orbper": 4.2308,
            "pl_rade": 13.21,
            "pl_bmasse": 146.7,
            "pl_eqt": 1260.0,
            "st_teff": 5793.0,
            "st_rad": 1.266,
            "st_mass": 1.11,
            "sy_dist": 15.53,
        },
    ]


@pytest.fixture
def raw_exoplanet() -> RawExoplanet:
    """A valid RawExoplanet instance."""
    return RawExoplanet(
        pl_name="Kepler-22 b",
        hostname="Kepler-22",
        discoverymethod="Transit",
        disc_year=2011,
        pl_orbper=289.8623,
        pl_rade=2.38,
        pl_bmasse=9.1,
        pl_eqt=262.0,
        st_teff=5518.0,
        st_rad=0.979,
        st_mass=0.97,
        sy_dist=190.12,
    )


@pytest.fixture
def raw_exoplanet_list() -> list[RawExoplanet]:
    """Multiple valid RawExoplanet instances."""
    return [
        RawExoplanet(
            pl_name="Kepler-22 b",
            hostname="Kepler-22",
            discoverymethod="Transit",
            disc_year=2011,
            pl_orbper=289.8623,
            pl_rade=2.38,
            pl_bmasse=9.1,
            pl_eqt=262.0,
            st_teff=5518.0,
            st_rad=0.979,
            st_mass=0.97,
            sy_dist=190.12,
        ),
        RawExoplanet(
            pl_name="TRAPPIST-1 e",
            hostname="TRAPPIST-1",
            discoverymethod="Transit",
            disc_year=2017,
            pl_orbper=6.0996,
            pl_rade=0.92,
            pl_bmasse=0.692,
            pl_eqt=251.0,
            st_teff=2566.0,
            st_rad=0.121,
            st_mass=0.0898,
            sy_dist=12.43,
        ),
    ]


@pytest.fixture
def transformed_exoplanet() -> Exoplanet:
    """A transformed Exoplanet instance ready for loading."""
    return Exoplanet(
        pl_name="Kepler-22 b",
        hostname="Kepler-22",
        discovery_method="Transit",
        disc_year=2011,
        orbital_period_days=289.8623,
        radius_earth=2.38,
        radius_jupiter=2.38 / 11.209,
        mass_earth=9.1,
        mass_jupiter=9.1 / 317.828,
        equilibrium_temp_k=262.0,
        stellar_teff_k=5518.0,
        stellar_radius_solar=0.979,
        stellar_mass_solar=0.97,
        distance_pc=190.12,
        is_habitable_zone=True,
    )


@pytest.fixture
def test_config() -> Config:
    """Configuration for testing with non-default values."""
    return Config(
        database=DatabaseConfig(
            host="localhost",
            port=5432,
            name="test_stellar",
            user="test_user",
            password="test_pass",
        ),
        api=ApiConfig(
            base_url="https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
            timeout=10,
            max_retries=2,
            backoff_base=1.0,
            backoff_max=5.0,
        ),
        pipeline=PipelineConfig(
            batch_size=100,
            log_file="test_pipeline.log",
            log_level="DEBUG",
        ),
    )


@pytest.fixture
def mock_db_connection():
    """A mock psycopg2 connection with cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor
