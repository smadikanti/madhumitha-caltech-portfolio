"""Safe FITS I/O with structured error handling and data validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

logger = logging.getLogger(__name__)


class FITSReadError(Exception):
    """Raised when a FITS file cannot be read or is corrupt."""


class FITSValidationError(Exception):
    """Raised when FITS data fails validation checks."""


def read_fits(
    filepath: Path,
    ext: int = 0,
    memmap: bool = True,
) -> tuple[np.ndarray, fits.Header]:
    """Read image data and header from a FITS extension.

    Args:
        filepath: Path to the FITS file.
        ext: Extension index to read. Defaults to the primary HDU.
        memmap: Use memory mapping for large files.

    Returns:
        Tuple of (image_data, header). Image data is always returned as
        float64 with NaN replacing non-finite values.

    Raises:
        FITSReadError: If the file is missing, corrupt, or contains no
            image data in the requested extension.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FITSReadError(f"File not found: {filepath}")

    try:
        hdul = fits.open(filepath, memmap=memmap)
    except Exception as exc:
        raise FITSReadError(f"Cannot open FITS file {filepath}: {exc}") from exc

    try:
        hdu = hdul[ext]
        header = hdu.header.copy()
        data = hdu.data

        if data is None:
            for i, h in enumerate(hdul):
                if h.data is not None and h.data.ndim >= 2:
                    data = h.data
                    header = h.header.copy()
                    logger.info("No data in ext %d; using ext %d instead", ext, i)
                    break

        if data is None:
            raise FITSReadError(
                f"No image data found in {filepath} (checked all extensions)"
            )

        data = np.array(data, dtype=np.float64)
        data = _sanitize_image_data(data)
        return data, header

    finally:
        hdul.close()


def read_header(filepath: Path, ext: int = 0) -> fits.Header:
    """Read only the header from a FITS extension without loading pixel data.

    Args:
        filepath: Path to the FITS file.
        ext: Extension index.

    Returns:
        The FITS header.

    Raises:
        FITSReadError: If the file cannot be read.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FITSReadError(f"File not found: {filepath}")
    try:
        return fits.getheader(filepath, ext=ext)
    except Exception as exc:
        raise FITSReadError(f"Cannot read header from {filepath}: {exc}") from exc


def write_fits(
    filepath: Path,
    data: np.ndarray,
    header: Optional[fits.Header] = None,
    overwrite: bool = True,
) -> Path:
    """Write image data to a FITS file.

    Args:
        filepath: Output path.
        data: Image array. Will be cast to float32 for storage efficiency.
        header: Optional FITS header. A HISTORY card documenting the
            processing is appended automatically.
        overwrite: Replace existing file.

    Returns:
        The path written to.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if header is None:
        header = fits.Header()

    header["HISTORY"] = "Processed by fits-image-processor"

    hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
    hdu.writeto(filepath, overwrite=overwrite)
    logger.info("Wrote FITS file: %s", filepath)
    return filepath


def get_wcs(header: fits.Header) -> Optional[WCS]:
    """Attempt to construct a WCS from a FITS header.

    Returns None (rather than raising) if the header lacks WCS keywords,
    which is common for calibration frames.
    """
    required = {"CTYPE1", "CTYPE2"}
    if not required.issubset(set(header.keys())):
        return None
    try:
        return WCS(header, naxis=2)
    except Exception as exc:
        logger.warning("WCS construction failed: %s", exc)
        return None


def _sanitize_image_data(data: np.ndarray) -> np.ndarray:
    """Replace inf/-inf with NaN and warn about non-finite pixel fractions.

    Astronomers expect NaN to mark bad pixels; inf values from saturated
    detectors or arithmetic overflow should be treated identically.
    """
    non_finite = ~np.isfinite(data)
    count = np.count_nonzero(non_finite)
    if count > 0:
        frac = count / data.size
        logger.warning(
            "%.2f%% of pixels are non-finite — replacing with NaN", frac * 100
        )
        data[non_finite] = np.nan
    return data


def validate_2d(data: np.ndarray, label: str = "image") -> np.ndarray:
    """Ensure data is 2-D, squeezing degenerate higher dimensions.

    Multi-extension FITS and data cubes sometimes carry shape (1, NY, NX).
    We squeeze those but reject genuinely 3-D+ data.

    Args:
        data: Array to validate.
        label: Human-readable label for error messages.

    Returns:
        A guaranteed 2-D array.

    Raises:
        FITSValidationError: If the data cannot be reduced to 2-D.
    """
    data = np.squeeze(data)
    if data.ndim != 2:
        raise FITSValidationError(
            f"{label} has {data.ndim} dimensions after squeezing; expected 2"
        )
    return data
