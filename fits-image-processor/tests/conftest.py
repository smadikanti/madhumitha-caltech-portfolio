"""Fixtures that generate synthetic FITS files for testing.

These fixtures create realistic-looking astronomical data with proper headers,
WCS solutions, and calibration frames — without requiring real telescope data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS


@pytest.fixture
def tmp_fits_dir(tmp_path: Path) -> Path:
    """A temporary directory for FITS file output."""
    d = tmp_path / "fits_data"
    d.mkdir()
    return d


@pytest.fixture
def synthetic_star_field(tmp_fits_dir: Path) -> Path:
    """A 512x512 image with synthetic stars, sky background, and WCS.

    Simulates a typical CCD observation: Poisson sky background at ~1000 ADU,
    read noise of ~10 ADU, and a handful of Gaussian point sources.
    """
    rng = np.random.default_rng(42)
    ny, nx = 512, 512

    sky_level = 1000.0
    read_noise = 10.0
    data = rng.poisson(sky_level, size=(ny, nx)).astype(np.float64)
    data += rng.normal(0, read_noise, size=(ny, nx))

    star_positions = [(256, 256), (100, 400), (400, 100), (300, 300), (50, 50)]
    star_fluxes = [50000, 20000, 30000, 15000, 10000]
    yy, xx = np.mgrid[0:ny, 0:nx]

    for (sy, sx), flux in zip(star_positions, star_fluxes):
        sigma = 3.0
        gaussian = flux * np.exp(-0.5 * ((xx - sx) ** 2 + (yy - sy) ** 2) / sigma**2)
        data += gaussian

    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [nx / 2, ny / 2]
    wcs.wcs.crval = [180.0, 45.0]
    wcs.wcs.cdelt = [-0.001, 0.001]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    header = wcs.to_header()
    header["OBJECT"] = "Test Star Field"
    header["FILTER"] = "V"
    header["EXPTIME"] = 120.0
    header["DATE-OBS"] = "2024-06-15T03:45:00"
    header["INSTRUME"] = "TestCam"
    header["TELESCOP"] = "Synthetic 1m"
    header["OBSERVER"] = "pytest"
    header["AIRMASS"] = 1.15
    header["GAIN"] = 1.5
    header["RDNOISE"] = 10.0
    header["IMAGETYP"] = "SCIENCE"
    header["BUNIT"] = "ADU"
    header["RA"] = 180.0
    header["DEC"] = 45.0

    filepath = tmp_fits_dir / "star_field.fits"
    hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
    hdu.writeto(filepath, overwrite=True)
    return filepath


@pytest.fixture
def synthetic_bias(tmp_fits_dir: Path) -> Path:
    """A 512x512 master bias frame (zero-exposure read noise pattern)."""
    rng = np.random.default_rng(99)
    data = rng.normal(200.0, 10.0, size=(512, 512))

    header = fits.Header()
    header["IMAGETYP"] = "BIAS"
    header["EXPTIME"] = 0.0
    header["INSTRUME"] = "TestCam"

    filepath = tmp_fits_dir / "master_bias.fits"
    hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
    hdu.writeto(filepath, overwrite=True)
    return filepath


@pytest.fixture
def synthetic_dark(tmp_fits_dir: Path) -> Path:
    """A 512x512 master dark frame (thermal current pattern)."""
    rng = np.random.default_rng(77)
    data = rng.normal(200.0, 10.0, size=(512, 512))
    yy, xx = np.mgrid[0:512, 0:512]
    hot_pixel_mask = rng.random(size=(512, 512)) < 0.001
    data[hot_pixel_mask] += rng.uniform(500, 5000, size=np.count_nonzero(hot_pixel_mask))

    header = fits.Header()
    header["IMAGETYP"] = "DARK"
    header["EXPTIME"] = 120.0
    header["INSTRUME"] = "TestCam"

    filepath = tmp_fits_dir / "master_dark.fits"
    hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
    hdu.writeto(filepath, overwrite=True)
    return filepath


@pytest.fixture
def synthetic_flat(tmp_fits_dir: Path) -> Path:
    """A 512x512 master flat frame simulating vignetting and dust donuts."""
    ny, nx = 512, 512
    yy, xx = np.mgrid[0:ny, 0:nx]

    cy, cx = ny / 2, nx / 2
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    vignette = 1.0 - 0.3 * (r / (nx / 2)) ** 2
    vignette = np.clip(vignette, 0.3, 1.0)

    rng = np.random.default_rng(55)
    pixel_response = 1.0 + rng.normal(0, 0.02, size=(ny, nx))

    flat = vignette * pixel_response * 30000.0

    header = fits.Header()
    header["IMAGETYP"] = "FLAT"
    header["EXPTIME"] = 5.0
    header["FILTER"] = "V"
    header["INSTRUME"] = "TestCam"

    filepath = tmp_fits_dir / "master_flat.fits"
    hdu = fits.PrimaryHDU(data=flat.astype(np.float32), header=header)
    hdu.writeto(filepath, overwrite=True)
    return filepath


@pytest.fixture
def multiple_star_fields(tmp_fits_dir: Path) -> list[Path]:
    """Three slightly different frames of the same field for stacking tests."""
    rng = np.random.default_rng(123)
    ny, nx = 256, 256
    paths = []

    for i in range(3):
        sky = 1000.0 + i * 50
        data = rng.poisson(sky, size=(ny, nx)).astype(np.float64)
        data += rng.normal(0, 10, size=(ny, nx))

        yy, xx = np.mgrid[0:ny, 0:nx]
        star = 20000 * np.exp(-0.5 * ((xx - 128) ** 2 + (yy - 128) ** 2) / 3.0**2)
        data += star

        if i == 1:
            data[100, 100] = 65000.0

        header = fits.Header()
        header["OBJECT"] = "Stack Test Field"
        header["EXPTIME"] = 60.0
        header["FILTER"] = "R"
        header["DATE-OBS"] = f"2024-06-15T0{i}:00:00"

        filepath = tmp_fits_dir / f"frame_{i:03d}.fits"
        hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
        hdu.writeto(filepath, overwrite=True)
        paths.append(filepath)

    return paths


@pytest.fixture
def fits_with_nan(tmp_fits_dir: Path) -> Path:
    """A FITS file with NaN pixels simulating bad/masked regions."""
    rng = np.random.default_rng(11)
    data = rng.normal(1000, 50, size=(128, 128))
    data[10:20, 10:20] = np.nan
    data[50, 50] = np.inf

    header = fits.Header()
    header["OBJECT"] = "NaN Test"
    header["EXPTIME"] = 30.0

    filepath = tmp_fits_dir / "with_nan.fits"
    hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
    hdu.writeto(filepath, overwrite=True)
    return filepath
