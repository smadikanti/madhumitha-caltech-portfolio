"""Pipeline orchestrator implementing the Extract-Validate-Transform-Load pattern.

Coordinates the four pipeline stages, tracks run metadata, and handles
error propagation with structured logging throughout.
"""

from __future__ import annotations

import logging
from typing import Optional

from stellar_pipeline.config import Config
from stellar_pipeline.exceptions import PipelineError
from stellar_pipeline.extract import TAPClient
from stellar_pipeline.load import PostgreSQLLoader
from stellar_pipeline.logging_config import PipelineLogger
from stellar_pipeline.models import PipelineResult, ValidationReport
from stellar_pipeline.transform import ExoplanetTransformer
from stellar_pipeline.validate import ExoplanetValidator

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the full EVTL data ingestion pipeline.

    Manages the lifecycle of a single pipeline run: extraction from the
    NASA Exoplanet Archive TAP API, validation, transformation, and
    loading into PostgreSQL.

    Args:
        config: Fully loaded pipeline configuration.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._extractor = TAPClient(config.api)
        self._validator = ExoplanetValidator()
        self._transformer = ExoplanetTransformer()
        self._loader = PostgreSQLLoader(config.database, config.pipeline.batch_size)

    def run(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Execute the full pipeline or a dry run (extract + validate only).

        Args:
            limit: Maximum number of records to extract. None for all.
            dry_run: If True, skip the load stage and log what would happen.

        Returns:
            PipelineResult with metadata about the run.
        """
        result = PipelineResult()
        run_log = PipelineLogger(logger, str(result.run_id))
        run_log.info(f"Pipeline run started (dry_run={dry_run})")

        try:
            raw_records = self._extract(run_log, result, limit)
            report = self._validate(run_log, result, raw_records)
            transformed = self._transform(run_log, result, report)

            if dry_run:
                run_log.info(
                    f"Dry run complete: {result.records_transformed} records "
                    f"would be loaded"
                )
                result.mark_complete(status="dry_run")
            else:
                self._load(run_log, result, transformed)
                result.mark_complete()

        except PipelineError as exc:
            result.mark_failed(str(exc))
            run_log.error(f"Pipeline failed: {exc}")
            raise
        except Exception as exc:
            result.mark_failed(str(exc))
            run_log.error(f"Unexpected error: {exc}")
            raise PipelineError(f"Unexpected pipeline failure: {exc}") from exc
        finally:
            self._record_run(run_log, result)
            duration = result.duration_seconds
            run_log.info(
                f"Pipeline finished: status={result.status}, "
                f"duration={duration:.2f}s" if duration else
                f"Pipeline finished: status={result.status}"
            )

        return result

    def validate_only(
        self, limit: Optional[int] = None
    ) -> tuple[PipelineResult, ValidationReport]:
        """Run extraction and validation without transforming or loading.

        Useful for inspecting data quality before committing to a full run.

        Args:
            limit: Maximum number of records to extract.

        Returns:
            Tuple of (PipelineResult, ValidationReport).
        """
        result = PipelineResult()
        run_log = PipelineLogger(logger, str(result.run_id))
        run_log.info("Validation-only run started")

        try:
            raw_records = self._extract(run_log, result, limit)
            report = self._validate(run_log, result, raw_records)
            result.mark_complete(status="validated")
        except PipelineError as exc:
            result.mark_failed(str(exc))
            run_log.error(f"Validation run failed: {exc}")
            raise
        else:
            return result, report

    def _extract(self, run_log, result, limit):
        run_log.info("Stage 1/4: Extracting data from TAP API")
        with self._extractor as client:
            raw_records = client.fetch(limit=limit)
        result.records_extracted = len(raw_records)
        run_log.info(f"Extracted {len(raw_records)} records")
        return raw_records

    def _validate(self, run_log, result, raw_records):
        run_log.info("Stage 2/4: Validating records")
        report = self._validator.validate(raw_records)
        result.records_validated = report.valid_count
        result.records_failed_validation = report.invalid_count + report.duplicate_count
        run_log.info(
            f"Validation: {report.valid_count} valid, "
            f"{report.invalid_count} invalid, "
            f"{report.duplicate_count} duplicates"
        )
        return report

    def _transform(self, run_log, result, report):
        run_log.info("Stage 3/4: Transforming records")
        transformed = self._transformer.transform(report.valid_records)
        result.records_transformed = len(transformed)
        run_log.info(f"Transformed {len(transformed)} records")
        return transformed

    def _load(self, run_log, result, transformed):
        run_log.info("Stage 4/4: Loading into PostgreSQL")
        self._loader.ensure_schema()
        loaded = self._loader.load(transformed, result.run_id)
        result.records_loaded = loaded
        run_log.info(f"Loaded {loaded} records")

    def _record_run(self, run_log, result):
        try:
            self._loader.record_run(result)
        except Exception as exc:
            run_log.warning(f"Failed to persist run metadata: {exc}")
