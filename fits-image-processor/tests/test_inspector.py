"""Tests for FITS header inspection and metadata extraction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from fits_processor.inspector import (
    ImageStatistics,
    InspectionReport,
    format_report,
    inspect_file,
)


class TestInspectFile:
    def test_basic_inspection(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field)

        assert isinstance(report, InspectionReport)
        assert report.filepath == synthetic_star_field
        assert report.extensions >= 1

    def test_image_statistics(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field, compute_stats=True)

        assert report.stats is not None
        s = report.stats
        assert s.shape == (512, 512)
        assert s.min_adu < s.mean_adu < s.max_adu
        assert s.std_adu > 0
        assert 0.0 <= s.nan_fraction <= 1.0

    def test_observation_metadata(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field)

        assert report.observation.get("OBJECT") == "Test Star Field"
        assert report.observation.get("FILTER") == "V"
        assert report.observation.get("EXPTIME") == 120.0
        assert report.observation.get("INSTRUME") == "TestCam"
        assert "DATE-OBS" in report.observation

    def test_wcs_field_geometry(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field)

        assert report.field_geometry is not None
        g = report.field_geometry
        assert abs(g.center.ra.deg - 180.0) < 1.0
        assert abs(g.center.dec.deg - 45.0) < 1.0
        assert g.pixel_scale_arcsec > 0
        assert g.fov_arcmin[0] > 0
        assert g.fov_arcmin[1] > 0
        assert g.projection == "TAN"

    def test_skip_stats(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field, compute_stats=False)
        assert report.stats is None

    def test_nan_handling(self, fits_with_nan: Path) -> None:
        report = inspect_file(fits_with_nan)
        assert report.stats is not None
        assert report.stats.nan_fraction > 0

    def test_all_keywords(self, synthetic_star_field: Path) -> None:
        report = inspect_file(
            synthetic_star_field, include_all_keywords=True
        )
        assert len(report.all_keywords) > 0
        assert "NAXIS1" in report.all_keywords


class TestFormatReport:
    def test_format_produces_string(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field)
        text = format_report(report)

        assert isinstance(text, str)
        assert "FITS Inspection" in text
        assert "star_field.fits" in text

    def test_format_includes_wcs(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field)
        text = format_report(report)

        assert "WCS" in text
        assert "RA" in text
        assert "TAN" in text

    def test_format_includes_stats(self, synthetic_star_field: Path) -> None:
        report = inspect_file(synthetic_star_field)
        text = format_report(report)

        assert "ADU" in text
        assert "512 x 512" in text


class TestFileNotFound:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        from fits_processor.io_utils import FITSReadError

        with pytest.raises(FITSReadError, match="File not found"):
            inspect_file(tmp_path / "nonexistent.fits")
