"""Tests for the PostgreSQL data loading module."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from stellar_pipeline.config import DatabaseConfig
from stellar_pipeline.exceptions import LoadError
from stellar_pipeline.load import PostgreSQLLoader, _record_to_params
from stellar_pipeline.models import Exoplanet, PipelineResult


@pytest.fixture
def db_config() -> DatabaseConfig:
    return DatabaseConfig(
        host="localhost",
        port=5432,
        name="test_db",
        user="test_user",
        password="test_pass",
    )


@pytest.fixture
def loader(db_config: DatabaseConfig) -> PostgreSQLLoader:
    return PostgreSQLLoader(db_config, batch_size=2)


@pytest.fixture
def run_id() -> uuid.UUID:
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_exoplanets() -> list[Exoplanet]:
    return [
        Exoplanet(
            pl_name=f"Planet-{i}",
            hostname=f"Star-{i}",
            discovery_method="Transit",
            disc_year=2020,
            orbital_period_days=float(i * 10),
            radius_earth=float(i),
            radius_jupiter=float(i) / 11.209,
            mass_earth=float(i * 5),
            mass_jupiter=float(i * 5) / 317.828,
            equilibrium_temp_k=250.0,
            is_habitable_zone=True,
        )
        for i in range(1, 6)
    ]


class TestRecordToParams:
    def test_converts_all_fields(self, transformed_exoplanet: Exoplanet) -> None:
        run_id = uuid.uuid4()
        params = _record_to_params(transformed_exoplanet, run_id)

        assert params["pl_name"] == "Kepler-22 b"
        assert params["hostname"] == "Kepler-22"
        assert params["discovery_method"] == "Transit"
        assert params["run_id"] == str(run_id)
        assert params["is_habitable_zone"] is True

    def test_handles_none_values(self) -> None:
        minimal = Exoplanet(pl_name="Min", hostname="Star")
        params = _record_to_params(minimal, uuid.uuid4())
        assert params["radius_earth"] is None
        assert params["mass_jupiter"] is None


class TestPostgreSQLLoader:
    @patch("stellar_pipeline.load.psycopg2.extras.execute_batch")
    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_load_batches_records(
        self,
        mock_connect: MagicMock,
        mock_exec_batch: MagicMock,
        loader: PostgreSQLLoader,
        sample_exoplanets: list[Exoplanet],
        run_id: uuid.UUID,
    ) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        loaded = loader.load(sample_exoplanets, run_id)

        assert loaded == 5
        assert mock_conn.commit.call_count == 3  # ceil(5/2) = 3 batches
        assert mock_exec_batch.call_count == 3

    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_load_empty_list_returns_zero(
        self, mock_connect: MagicMock, loader: PostgreSQLLoader, run_id: uuid.UUID
    ) -> None:
        loaded = loader.load([], run_id)
        assert loaded == 0
        mock_connect.assert_not_called()

    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_load_rolls_back_on_error(
        self,
        mock_connect: MagicMock,
        loader: PostgreSQLLoader,
        sample_exoplanets: list[Exoplanet],
        run_id: uuid.UUID,
    ) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        import psycopg2

        mock_cursor.execute = MagicMock()

        from stellar_pipeline.load import UPSERT_SQL

        with patch("stellar_pipeline.load.psycopg2.extras.execute_batch") as mock_exec:
            mock_exec.side_effect = psycopg2.Error("insert failed")

            with pytest.raises(LoadError, match="Batch insert failed"):
                loader.load(sample_exoplanets, run_id)

        mock_conn.rollback.assert_called()

    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_connection_failure_raises_load_error(
        self,
        mock_connect: MagicMock,
        loader: PostgreSQLLoader,
        sample_exoplanets: list[Exoplanet],
        run_id: uuid.UUID,
    ) -> None:
        import psycopg2

        mock_connect.side_effect = psycopg2.Error("connection refused")

        with pytest.raises(LoadError, match="Database connection failed"):
            loader.load(sample_exoplanets, run_id)

    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_record_run_persists_metadata(
        self, mock_connect: MagicMock, loader: PostgreSQLLoader
    ) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = PipelineResult()
        result.records_extracted = 100
        result.records_loaded = 95
        result.mark_complete()

        loader.record_run(result)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_get_recent_runs(
        self, mock_connect: MagicMock, loader: PostgreSQLLoader
    ) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "run_id": uuid.uuid4(),
                "status": "success",
                "records_extracted": 50,
                "records_loaded": 48,
                "started_at": None,
                "completed_at": None,
                "records_validated": 49,
                "records_failed_validation": 1,
                "records_transformed": 49,
                "error_message": None,
            }
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        runs = loader.get_recent_runs(count=5)

        assert len(runs) == 1
        assert runs[0]["status"] == "success"

    @patch("stellar_pipeline.load.psycopg2.connect")
    def test_ensure_schema_executes_sql(
        self, mock_connect: MagicMock, loader: PostgreSQLLoader
    ) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        with patch("stellar_pipeline.load._load_schema_sql", return_value="CREATE TABLE test();"):
            loader.ensure_schema()

        mock_cursor.execute.assert_called_once_with("CREATE TABLE test();")
        mock_conn.commit.assert_called_once()
