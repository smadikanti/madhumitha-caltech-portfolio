"""Tests for image stacking / median combine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from fits_processor.stacker import CombineMethod, stack_images


class TestStackImages:
    def test_median_stack(
        self, multiple_star_fields: list[Path], tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "stacked.fits"
        result = stack_images(multiple_star_fields, output, method=CombineMethod.MEDIAN)

        assert result.exists()
        with fits.open(result) as hdul:
            data = hdul[0].data
            header = hdul[0].header

        assert data is not None
        assert data.ndim == 2
        assert header["NCOMBINE"] == 3
        assert header["COMBMETH"] == "median"

    def test_mean_stack(
        self, multiple_star_fields: list[Path], tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "mean_stacked.fits"
        result = stack_images(multiple_star_fields, output, method=CombineMethod.MEAN)

        assert result.exists()
        with fits.open(result) as hdul:
            assert hdul[0].header["COMBMETH"] == "mean"

    def test_sigma_clip_stack(
        self, multiple_star_fields: list[Path], tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "sigma_stacked.fits"
        result = stack_images(
            multiple_star_fields, output, method=CombineMethod.SIGMA_CLIP
        )

        assert result.exists()
        with fits.open(result) as hdul:
            data = hdul[0].data
        assert data is not None

    def test_cosmic_ray_rejection(
        self, multiple_star_fields: list[Path], tmp_fits_dir: Path
    ) -> None:
        """Median stacking should reject the synthetic cosmic ray at (100,100)."""
        output = tmp_fits_dir / "cr_rejected.fits"
        stack_images(multiple_star_fields, output)

        with fits.open(output) as hdul:
            stacked = hdul[0].data

        # frame_001 has a 65000 ADU cosmic ray at (100,100);
        # the median of the three frames should be much lower
        assert stacked[100, 100] < 10000

    def test_minimum_frames_error(self, tmp_fits_dir: Path) -> None:
        single = tmp_fits_dir / "single.fits"
        data = np.zeros((64, 64), dtype=np.float32)
        fits.PrimaryHDU(data=data).writeto(single, overwrite=True)

        with pytest.raises(ValueError, match="at least 2"):
            stack_images([single], tmp_fits_dir / "out.fits")

    def test_different_sizes(self, tmp_fits_dir: Path) -> None:
        """Frames of different sizes should be cropped to intersection."""
        paths = []
        for i, shape in enumerate([(100, 120), (110, 120), (100, 130)]):
            data = np.random.default_rng(i).normal(1000, 50, size=shape).astype(
                np.float32
            )
            p = tmp_fits_dir / f"size_{i}.fits"
            fits.PrimaryHDU(data=data).writeto(p, overwrite=True)
            paths.append(p)

        output = tmp_fits_dir / "mixed_size_stack.fits"
        result = stack_images(paths, output)

        with fits.open(result) as hdul:
            assert hdul[0].data.shape == (100, 120)
