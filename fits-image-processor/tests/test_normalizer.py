"""Tests for CCD reduction pipeline (bias, dark, flat correction)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from fits_processor.normalizer import (
    apply_flat,
    create_master_bias,
    reduce,
    subtract_bias,
    subtract_dark,
)


class TestSubtractBias:
    def test_bias_subtraction_lowers_mean(self) -> None:
        data = np.full((64, 64), 1000.0)
        bias = np.full((64, 64), 200.0)
        result = subtract_bias(data, bias)

        np.testing.assert_allclose(result, 800.0)

    def test_shape_mismatch_raises(self) -> None:
        data = np.zeros((64, 64))
        bias = np.zeros((32, 32))
        with pytest.raises(ValueError, match="shape"):
            subtract_bias(data, bias)


class TestSubtractDark:
    def test_dark_scaling(self) -> None:
        """Dark should be scaled by the exposure time ratio."""
        data = np.full((64, 64), 1000.0)
        dark = np.full((64, 64), 100.0)

        result = subtract_dark(data, dark, science_exptime=120.0, dark_exptime=60.0)
        np.testing.assert_allclose(result, 800.0)

    def test_no_scaling_without_exptime(self) -> None:
        data = np.full((64, 64), 1000.0)
        dark = np.full((64, 64), 100.0)

        result = subtract_dark(data, dark)
        np.testing.assert_allclose(result, 900.0)


class TestApplyFlat:
    def test_flat_correction_uniformity(self) -> None:
        """After flat correction, a uniformly illuminated frame should be flat."""
        rng = np.random.default_rng(42)
        flat = rng.uniform(0.8, 1.2, size=(64, 64))
        illuminated = 10000.0 * flat

        corrected = apply_flat(illuminated, flat)
        np.testing.assert_allclose(corrected, 10000.0, rtol=0.01)

    def test_low_flat_values_become_nan(self) -> None:
        """Pixels where the flat is near zero should be masked as NaN."""
        flat = np.ones((64, 64)) * 30000.0
        flat[10:15, 10:15] = 0.0
        data = np.ones((64, 64)) * 10000.0

        corrected = apply_flat(data, flat)
        assert np.all(np.isnan(corrected[10:15, 10:15]))


class TestFullReduction:
    def test_reduce_with_all_calibrations(
        self,
        synthetic_star_field: Path,
        synthetic_bias: Path,
        synthetic_dark: Path,
        synthetic_flat: Path,
        tmp_fits_dir: Path,
    ) -> None:
        output = tmp_fits_dir / "reduced_science.fits"
        result = reduce(
            science_path=synthetic_star_field,
            output=output,
            bias_path=synthetic_bias,
            dark_path=synthetic_dark,
            flat_path=synthetic_flat,
        )

        assert result.exists()
        with fits.open(result) as hdul:
            header = hdul[0].header
            data = hdul[0].data

        assert data is not None
        assert header["CALSTAT"] == "REDUCED"
        assert any("Bias" in str(h) for h in header["HISTORY"])

    def test_reduce_bias_only(
        self,
        synthetic_star_field: Path,
        synthetic_bias: Path,
        tmp_fits_dir: Path,
    ) -> None:
        output = tmp_fits_dir / "bias_only.fits"
        result = reduce(
            science_path=synthetic_star_field,
            output=output,
            bias_path=synthetic_bias,
        )
        assert result.exists()

    def test_reduce_no_calibrations(
        self,
        synthetic_star_field: Path,
        tmp_fits_dir: Path,
    ) -> None:
        """Reduction with no calibration frames should still produce output."""
        output = tmp_fits_dir / "no_cal.fits"
        result = reduce(science_path=synthetic_star_field, output=output)
        assert result.exists()


class TestCreateMasterBias:
    def test_master_bias_from_multiple(self, tmp_fits_dir: Path) -> None:
        rng = np.random.default_rng(0)
        paths = []
        for i in range(5):
            data = rng.normal(200, 10, size=(64, 64)).astype(np.float32)
            p = tmp_fits_dir / f"bias_{i}.fits"
            header = fits.Header()
            header["IMAGETYP"] = "BIAS"
            header["EXPTIME"] = 0.0
            fits.PrimaryHDU(data=data, header=header).writeto(p, overwrite=True)
            paths.append(p)

        master, header = create_master_bias(paths)

        assert master.shape == (64, 64)
        assert header["NCOMBINE"] == 5
        assert abs(np.nanmean(master) - 200.0) < 5.0
