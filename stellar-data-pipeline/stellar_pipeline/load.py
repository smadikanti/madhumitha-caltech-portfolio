"""PostgreSQL data loader with upsert logic and batch processing.

Manages database connections, creates schema if needed, and loads
transformed exoplanet records using INSERT ... ON CONFLICT DO UPDATE
for idempotent ingestion.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional

import psycopg2
import psycopg2.extras

from stellar_pipeline.config import DatabaseConfig
from stellar_pipeline.exceptions import LoadError
from stellar_pipeline.models import Exoplanet, PipelineResult

logger = logging.getLogger(__name__)

UPSERT_SQL = """
    INSERT INTO exoplanets (
        pl_name, hostname, discovery_method, disc_year,
        orbital_period_days, radius_earth, radius_jupiter,
        mass_earth, mass_jupiter, equilibrium_temp_k,
        stellar_teff_k, stellar_radius_solar, stellar_mass_solar,
        distance_pc, is_habitable_zone, run_id, ingested_at, updated_at
    ) VALUES (
        %(pl_name)s, %(hostname)s, %(discovery_method)s, %(disc_year)s,
        %(orbital_period_days)s, %(radius_earth)s, %(radius_jupiter)s,
        %(mass_earth)s, %(mass_jupiter)s, %(equilibrium_temp_k)s,
        %(stellar_teff_k)s, %(stellar_radius_solar)s, %(stellar_mass_solar)s,
        %(distance_pc)s, %(is_habitable_zone)s, %(run_id)s, NOW(), NOW()
    )
    ON CONFLICT (pl_name) DO UPDATE SET
        hostname = EXCLUDED.hostname,
        discovery_method = EXCLUDED.discovery_method,
        disc_year = EXCLUDED.disc_year,
        orbital_period_days = EXCLUDED.orbital_period_days,
        radius_earth = EXCLUDED.radius_earth,
        radius_jupiter = EXCLUDED.radius_jupiter,
        mass_earth = EXCLUDED.mass_earth,
        mass_jupiter = EXCLUDED.mass_jupiter,
        equilibrium_temp_k = EXCLUDED.equilibrium_temp_k,
        stellar_teff_k = EXCLUDED.stellar_teff_k,
        stellar_radius_solar = EXCLUDED.stellar_radius_solar,
        stellar_mass_solar = EXCLUDED.stellar_mass_solar,
        distance_pc = EXCLUDED.distance_pc,
        is_habitable_zone = EXCLUDED.is_habitable_zone,
        run_id = EXCLUDED.run_id,
        updated_at = NOW()
"""

RECORD_RUN_SQL = """
    INSERT INTO pipeline_runs (
        run_id, started_at, completed_at, status,
        records_extracted, records_validated, records_failed_validation,
        records_transformed, records_loaded, error_message
    ) VALUES (
        %(run_id)s, %(started_at)s, %(completed_at)s, %(status)s,
        %(records_extracted)s, %(records_validated)s, %(records_failed_validation)s,
        %(records_transformed)s, %(records_loaded)s, %(error_message)s
    )
"""

RECENT_RUNS_SQL = """
    SELECT run_id, started_at, completed_at, status,
           records_extracted, records_validated, records_failed_validation,
           records_transformed, records_loaded, error_message
    FROM pipeline_runs
    ORDER BY started_at DESC
    LIMIT %s
"""


def _record_to_params(record: Exoplanet, run_id: uuid.UUID) -> dict:
    """Convert an Exoplanet dataclass to a dict for parameterized SQL."""
    return {
        "pl_name": record.pl_name,
        "hostname": record.hostname,
        "discovery_method": record.discovery_method,
        "disc_year": record.disc_year,
        "orbital_period_days": record.orbital_period_days,
        "radius_earth": record.radius_earth,
        "radius_jupiter": record.radius_jupiter,
        "mass_earth": record.mass_earth,
        "mass_jupiter": record.mass_jupiter,
        "equilibrium_temp_k": record.equilibrium_temp_k,
        "stellar_teff_k": record.stellar_teff_k,
        "stellar_radius_solar": record.stellar_radius_solar,
        "stellar_mass_solar": record.stellar_mass_solar,
        "distance_pc": record.distance_pc,
        "is_habitable_zone": record.is_habitable_zone,
        "run_id": str(run_id),
    }


class PostgreSQLLoader:
    """Loads transformed exoplanet records into PostgreSQL.

    Uses batch inserts with upsert semantics for idempotent ingestion.
    All writes within a batch are wrapped in a single transaction.

    Args:
        config: Database connection configuration.
        batch_size: Number of records per INSERT batch.
    """

    def __init__(self, config: DatabaseConfig, batch_size: int = 500) -> None:
        self._config = config
        self._batch_size = batch_size

    @contextmanager
    def _connect(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Open a database connection as a context manager."""
        conn = None
        try:
            conn = psycopg2.connect(self._config.dsn)
            yield conn
        except psycopg2.Error as exc:
            raise LoadError(f"Database connection failed: {exc}") from exc
        finally:
            if conn is not None:
                conn.close()

    def ensure_schema(self) -> None:
        """Create the required tables if they do not exist.

        Raises:
            LoadError: If schema creation fails.
        """
        schema_sql = _load_schema_sql()
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
                conn.commit()
            logger.info("Database schema verified")
        except psycopg2.Error as exc:
            raise LoadError(f"Schema creation failed: {exc}") from exc

    def load(
        self,
        records: list[Exoplanet],
        run_id: uuid.UUID,
    ) -> int:
        """Load transformed records into PostgreSQL using batched upserts.

        Args:
            records: Transformed exoplanet records to insert/update.
            run_id: Unique identifier for this pipeline run.

        Returns:
            Number of records successfully loaded.

        Raises:
            LoadError: If a batch fails to commit.
        """
        if not records:
            logger.warning("No records to load")
            return 0

        total_loaded = 0

        with self._connect() as conn:
            for batch_start in range(0, len(records), self._batch_size):
                batch = records[batch_start : batch_start + self._batch_size]
                try:
                    with conn.cursor() as cur:
                        params_list = [
                            _record_to_params(r, run_id) for r in batch
                        ]
                        psycopg2.extras.execute_batch(
                            cur, UPSERT_SQL, params_list
                        )
                    conn.commit()
                    total_loaded += len(batch)
                    logger.info(
                        f"Loaded batch of {len(batch)} records "
                        f"({total_loaded}/{len(records)} total)"
                    )
                except psycopg2.Error as exc:
                    conn.rollback()
                    raise LoadError(
                        f"Batch insert failed at offset {batch_start}: {exc}"
                    ) from exc

        logger.info(f"Load complete: {total_loaded} records upserted")
        return total_loaded

    def record_run(self, result: PipelineResult) -> None:
        """Persist pipeline run metadata to the pipeline_runs table.

        Args:
            result: The completed PipelineResult to record.

        Raises:
            LoadError: If the metadata insert fails.
        """
        params = {
            "run_id": str(result.run_id),
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "status": result.status,
            "records_extracted": result.records_extracted,
            "records_validated": result.records_validated,
            "records_failed_validation": result.records_failed_validation,
            "records_transformed": result.records_transformed,
            "records_loaded": result.records_loaded,
            "error_message": result.error_message,
        }
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(RECORD_RUN_SQL, params)
                conn.commit()
        except psycopg2.Error as exc:
            logger.error(f"Failed to record pipeline run: {exc}")

    def get_recent_runs(self, count: int = 10) -> list[dict]:
        """Retrieve recent pipeline run metadata.

        Args:
            count: Number of recent runs to return.

        Returns:
            List of run metadata dictionaries ordered by most recent first.

        Raises:
            LoadError: If the query fails.
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(RECENT_RUNS_SQL, (count,))
                    return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as exc:
            raise LoadError(f"Failed to retrieve pipeline runs: {exc}") from exc


def _load_schema_sql() -> str:
    """Load the SQL schema file from the project's sql/ directory."""
    from pathlib import Path

    schema_path = Path(__file__).parent.parent / "sql" / "schema.sql"
    if not schema_path.exists():
        raise LoadError(f"Schema file not found: {schema_path}")
    return schema_path.read_text(encoding="utf-8")
