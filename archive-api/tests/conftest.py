"""Shared test fixtures — in-memory SQLite via aiosqlite."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from archive_api.database import get_db
from archive_api.models import Base, Exoplanet

TEST_DATABASE_URL = "sqlite+aiosqlite://"

SAMPLE_PLANETS: list[dict] = [
    {
        "pl_name": "Test-1 b",
        "hostname": "Test-1",
        "discovery_method": "Transit",
        "disc_year": 2020,
        "orbital_period": 5.0,
        "pl_rade": 1.5,
        "pl_bmasse": 3.0,
        "pl_eqt": 300,
        "st_teff": 5000,
        "st_rad": 1.0,
        "sy_dist": 50.0,
        "ra": 180.0,
        "dec": 45.0,
    },
    {
        "pl_name": "Test-2 c",
        "hostname": "Test-2",
        "discovery_method": "Radial Velocity",
        "disc_year": 2015,
        "orbital_period": 100.0,
        "pl_rade": 11.0,
        "pl_bmasse": 300.0,
        "pl_eqt": 1200,
        "st_teff": 6000,
        "st_rad": 1.2,
        "sy_dist": 100.0,
        "ra": 90.0,
        "dec": -30.0,
    },
    {
        "pl_name": "Test-3 d",
        "hostname": "Test-3",
        "discovery_method": "Direct Imaging",
        "disc_year": 2010,
        "orbital_period": 50000.0,
        "pl_rade": 12.0,
        "pl_bmasse": 2000.0,
        "pl_eqt": None,
        "st_teff": 7000,
        "st_rad": 1.5,
        "sy_dist": 20.0,
        "ra": 270.0,
        "dec": 10.0,
    },
    {
        "pl_name": "Alpha Centauri Xb",
        "hostname": "Alpha Centauri X",
        "discovery_method": "Transit",
        "disc_year": 2022,
        "orbital_period": 12.5,
        "pl_rade": 2.0,
        "pl_bmasse": 5.5,
        "pl_eqt": 280,
        "st_teff": 5200,
        "st_rad": 0.9,
        "sy_dist": 1.3,
        "ra": 220.0,
        "dec": -60.0,
    },
    {
        "pl_name": "Kepler-999 b",
        "hostname": "Kepler-999",
        "discovery_method": "Transit",
        "disc_year": 2018,
        "orbital_period": 250.0,
        "pl_rade": 1.1,
        "pl_bmasse": 1.0,
        "pl_eqt": 260,
        "st_teff": 4800,
        "st_rad": 0.7,
        "sy_dist": 200.0,
        "ra": 300.0,
        "dec": 50.0,
    },
]


@pytest.fixture()
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture()
async def seeded_session(db_engine):
    """Return a session pre-loaded with SAMPLE_PLANETS."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        for data in SAMPLE_PLANETS:
            session.add(Exoplanet(**data))
        await session.commit()
        yield session


@pytest.fixture()
async def client(db_engine, seeded_session):
    """HTTP test client wired to the in-memory SQLite backend."""
    from archive_api.main import create_app

    app = create_app()
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
