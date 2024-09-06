"""Tests for the exoplanet record validation module."""

from __future__ import annotations

import pytest

from stellar_pipeline.exceptions import ValidationError
from stellar_pipeline.models import RawExoplanet
from stellar_pipeline.validate import ExoplanetValidator


@pytest.fixture
def validator() -> ExoplanetValidator:
    return ExoplanetValidator()


class TestRequiredFieldChecks:
    def test_valid_record_passes(
        self, validator: ExoplanetValidator, raw_exoplanet: RawExoplanet
    ) -> None:
        report = validator.validate([raw_exoplanet])
        assert report.valid_count == 1
        assert report.invalid_count == 0

    def test_missing_pl_name_fails(self, validator: ExoplanetValidator) -> None:
        record = RawExoplanet(pl_name=None, hostname="Star-1")
        report = validator.validate([record])
        assert report.invalid_count == 1
        reasons = report.invalid_records[0][1]
        assert any("pl_name" in r for r in reasons)

    def test_missing_hostname_fails(self, validator: ExoplanetValidator) -> None:
        record = RawExoplanet(pl_name="Planet-1", hostname=None)
        report = validator.validate([record])
        assert report.invalid_count == 1
        reasons = report.invalid_records[0][1]
        assert any("hostname" in r for r in reasons)

    def test_empty_string_pl_name_fails(self, validator: ExoplanetValidator) -> None:
        record = RawExoplanet(pl_name="   ", hostname="Star-1")
        report = validator.validate([record])
        assert report.invalid_count == 1

    def test_both_required_missing_collects_all_errors(
        self, validator: ExoplanetValidator
    ) -> None:
        record = RawExoplanet()
        report = validator.validate([record])
        assert report.invalid_count == 1
        reasons = report.invalid_records[0][1]
        assert len(reasons) >= 2


class TestRangeChecks:
    def test_negative_orbital_period_fails(
        self, validator: ExoplanetValidator
    ) -> None:
        record = RawExoplanet(
            pl_name="Bad-Planet", hostname="Star-1", pl_orbper=-5.0
        )
        report = validator.validate([record])
        assert report.invalid_count == 1
        reasons = report.invalid_records[0][1]
        assert any("pl_orbper" in r for r in reasons)

    def test_zero_radius_fails(self, validator: ExoplanetValidator) -> None:
        record = RawExoplanet(
            pl_name="Zero-R", hostname="Star-1", pl_rade=0.0
        )
        report = validator.validate([record])
        assert report.invalid_count == 1

    def test_null_optional_fields_pass(self, validator: ExoplanetValidator) -> None:
        record = RawExoplanet(
            pl_name="Minimal", hostname="Star-1",
            pl_orbper=None, pl_rade=None, pl_bmasse=None,
        )
        report = validator.validate([record])
        assert report.valid_count == 1

    def test_stellar_temp_above_max_fails(
        self, validator: ExoplanetValidator
    ) -> None:
        record = RawExoplanet(
            pl_name="Hot-Host", hostname="Star-1", st_teff=200_000.0
        )
        report = validator.validate([record])
        assert report.invalid_count == 1

    def test_valid_boundary_values_pass(
        self, validator: ExoplanetValidator
    ) -> None:
        record = RawExoplanet(
            pl_name="Edge-Case",
            hostname="Star-1",
            pl_orbper=0.01,
            pl_rade=0.01,
            disc_year=2024,
        )
        report = validator.validate([record])
        assert report.valid_count == 1


class TestDuplicateDetection:
    def test_duplicates_are_counted(self, validator: ExoplanetValidator) -> None:
        records = [
            RawExoplanet(pl_name="Planet-1", hostname="Star-1"),
            RawExoplanet(pl_name="Planet-1", hostname="Star-1"),
            RawExoplanet(pl_name="Planet-2", hostname="Star-2"),
        ]
        report = validator.validate(records)
        assert report.valid_count == 2
        assert report.duplicate_count == 1

    def test_whitespace_variants_are_duplicates(
        self, validator: ExoplanetValidator
    ) -> None:
        records = [
            RawExoplanet(pl_name="Planet-1", hostname="Star-1"),
            RawExoplanet(pl_name="Planet-1 ", hostname="Star-1"),
        ]
        report = validator.validate(records)
        assert report.duplicate_count == 1


class TestEdgeCases:
    def test_empty_list_returns_empty_report(
        self, validator: ExoplanetValidator
    ) -> None:
        report = validator.validate([])
        assert report.valid_count == 0
        assert report.invalid_count == 0
        assert report.duplicate_count == 0

    def test_non_list_input_raises(self, validator: ExoplanetValidator) -> None:
        with pytest.raises(ValidationError, match="Expected list"):
            validator.validate("not a list")  # type: ignore

    def test_mixed_valid_and_invalid(
        self, validator: ExoplanetValidator
    ) -> None:
        records = [
            RawExoplanet(pl_name="Good-1", hostname="Star-1", pl_orbper=10.0),
            RawExoplanet(pl_name=None, hostname="Star-2"),
            RawExoplanet(pl_name="Good-2", hostname="Star-3", pl_orbper=5.0),
        ]
        report = validator.validate(records)
        assert report.valid_count == 2
        assert report.invalid_count == 1
