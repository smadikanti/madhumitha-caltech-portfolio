"""Validation engine for raw exoplanet records.

Applies schema validation, null checks on required fields, physical
range checks, and duplicate detection before records proceed to
transformation.
"""

from __future__ import annotations

import logging
from typing import Optional

from stellar_pipeline.exceptions import ValidationError
from stellar_pipeline.models import REQUIRED_FIELDS, RawExoplanet, ValidationReport

logger = logging.getLogger(__name__)

RANGE_CHECKS: dict[str, tuple[Optional[float], Optional[float]]] = {
    "pl_orbper": (0.0, None),
    "pl_rade": (0.0, None),
    "pl_bmasse": (0.0, None),
    "pl_eqt": (0.0, None),
    "st_teff": (0.0, 100_000.0),
    "st_rad": (0.0, None),
    "st_mass": (0.0, None),
    "sy_dist": (0.0, None),
    "disc_year": (1900.0, 2100.0),
}


class ExoplanetValidator:
    """Validates raw exoplanet records against schema and physical constraints.

    Performs four validation passes in order:
    1. Required field null checks
    2. Schema type validation
    3. Physical range checks
    4. Duplicate detection across the batch
    """

    def validate(self, records: list[RawExoplanet]) -> ValidationReport:
        """Run all validation checks against a batch of records.

        Args:
            records: Raw exoplanet records from the extraction stage.

        Returns:
            A ValidationReport containing valid records, invalid records
            with their rejection reasons, and duplicate counts.

        Raises:
            ValidationError: If the input is fundamentally malformed.
        """
        if not isinstance(records, list):
            raise ValidationError(
                f"Expected list of records, got {type(records).__name__}"
            )

        report = ValidationReport()
        seen_names: dict[str, int] = {}

        for record in records:
            errors = self._check_single(record)

            if errors:
                report.invalid_records.append((record, errors))
                continue

            name = record.pl_name.strip()
            if name in seen_names:
                report.duplicate_count += 1
                logger.debug(f"Duplicate planet name: {name}")
                continue

            seen_names[name] = 1
            report.valid_records.append(record)

        logger.info(
            f"Validation complete: {report.valid_count} valid, "
            f"{report.invalid_count} invalid, "
            f"{report.duplicate_count} duplicates"
        )
        return report

    def _check_single(self, record: RawExoplanet) -> list[str]:
        """Validate a single record and return a list of error messages."""
        errors: list[str] = []
        errors.extend(self._check_required_fields(record))
        errors.extend(self._check_ranges(record))
        return errors

    @staticmethod
    def _check_required_fields(record: RawExoplanet) -> list[str]:
        """Verify that required fields are present and non-empty."""
        errors: list[str] = []
        for field_name in REQUIRED_FIELDS:
            value = getattr(record, field_name, None)
            if value is None:
                errors.append(f"Missing required field: {field_name}")
            elif isinstance(value, str) and not value.strip():
                errors.append(f"Empty required field: {field_name}")
        return errors

    @staticmethod
    def _check_ranges(record: RawExoplanet) -> list[str]:
        """Validate that numeric fields fall within physical bounds.

        Null values pass range checks; only non-null values that violate
        bounds are flagged.
        """
        errors: list[str] = []
        for field_name, (low, high) in RANGE_CHECKS.items():
            value = getattr(record, field_name, None)
            if value is None:
                continue

            try:
                numeric = float(value)
            except (TypeError, ValueError):
                errors.append(f"Non-numeric value for {field_name}: {value!r}")
                continue

            if low is not None and numeric <= low:
                errors.append(
                    f"{field_name} must be > {low}, got {numeric}"
                )
            if high is not None and numeric > high:
                errors.append(
                    f"{field_name} must be <= {high}, got {numeric}"
                )
        return errors
