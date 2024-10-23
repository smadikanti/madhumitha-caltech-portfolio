"""CCD reduction pipeline: bias subtraction, dark current removal, flat-field correction.

Standard CCD reduction follows the formula:

    corrected = (raw - master_bias - master_dark * exposure_scale) / normalized_flat

where exposure_scale = science_exptime / dark_exptime. This module implements
each step independently so they can be applied selectively, and also provides
a single-call ``reduce`` function for the full pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from astropy.io import fits

from .io_utils import read_fits, validate_2d, write_fits

logger = logging.getLogger(__name__)


def reduce(
    science_path: Path,
    output: Path,
    bias_path: Optional[Path] = None,
    dark_path: Optional[Path] = None,
    flat_path: Optional[Path] = None,
) -> Path:
    """Apply the full CCD reduction pipeline to a science frame.

    Steps are applied in the canonical order: bias, dark, flat.
    Any calibration frame that is None is skipped.

    Args:
        science_path: Raw science frame.
        output: Where to write the corrected frame.
        bias_path: Master bias (zero-exposure frame capturing read noise).
        dark_path: Master dark (thermal current accumulation).
        flat_path: Master flat (pixel-to-pixel sensitivity variation).

    Returns:
        Path to the corrected output FITS file.
    """
    data, header = read_fits(science_path)
    data = validate_2d(data, label="science")

    science_exptime = header.get("EXPTIME", None)

    if bias_path is not None:
        bias, _ = read_fits(bias_path)
        bias = validate_2d(bias, label="bias")
        data = subtract_bias(data, bias)
        header["HISTORY"] = f"Bias subtracted: {bias_path.name}"

    if dark_path is not None:
        dark_data, dark_header = read_fits(dark_path)
        dark_data = validate_2d(dark_data, label="dark")
        dark_exptime = dark_header.get("EXPTIME", None)
        data = subtract_dark(data, dark_data, science_exptime, dark_exptime)
        header["HISTORY"] = f"Dark subtracted: {dark_path.name}"

    if flat_path is not None:
        flat, _ = read_fits(flat_path)
        flat = validate_2d(flat, label="flat")
        data = apply_flat(data, flat)
        header["HISTORY"] = f"Flat corrected: {flat_path.name}"

    header["CALSTAT"] = ("REDUCED", "Calibration status")
    return write_fits(output, data, header=header)


def subtract_bias(data: np.ndarray, master_bias: np.ndarray) -> np.ndarray:
    """Subtract master bias from image data.

    The bias frame captures the fixed electronic offset (pedestal) that the
    readout electronics add to every pixel. Subtracting it removes this
    systematic offset so pixel values reflect actual photon counts.

    Args:
        data: Science or dark frame in ADU.
        master_bias: Master bias frame (same dimensions).

    Returns:
        Bias-subtracted image.
    """
    _check_shape_match(data, master_bias, "bias")
    result = data - master_bias
    logger.info(
        "Bias subtracted — mean shift: %.1f ADU",
        np.nanmean(master_bias),
    )
    return result


def subtract_dark(
    data: np.ndarray,
    master_dark: np.ndarray,
    science_exptime: Optional[float] = None,
    dark_exptime: Optional[float] = None,
) -> np.ndarray:
    """Subtract scaled master dark to remove thermal current.

    Dark current accumulates linearly with exposure time. If the dark frame
    was taken with a different exposure than the science frame, we scale it
    by the ratio of exposure times before subtraction.

    Args:
        data: Bias-subtracted science frame.
        master_dark: Master dark frame (should already be bias-subtracted).
        science_exptime: Science exposure time in seconds.
        dark_exptime: Dark exposure time in seconds.

    Returns:
        Dark-subtracted image.
    """
    _check_shape_match(data, master_dark, "dark")

    if science_exptime is not None and dark_exptime is not None and dark_exptime > 0:
        scale = science_exptime / dark_exptime
        if abs(scale - 1.0) > 0.01:
            logger.info(
                "Scaling dark by %.3f (science=%.1fs, dark=%.1fs)",
                scale,
                science_exptime,
                dark_exptime,
            )
        scaled_dark = master_dark * scale
    else:
        logger.warning(
            "Exposure times unavailable — applying dark without scaling"
        )
        scaled_dark = master_dark

    return data - scaled_dark


def apply_flat(data: np.ndarray, master_flat: np.ndarray) -> np.ndarray:
    """Divide by a normalized flat field to correct pixel sensitivity.

    Each pixel on a CCD has a slightly different quantum efficiency.
    The flat field captures this variation; dividing by it makes the
    response uniform. The flat is normalized to its median so division
    preserves the flux scale of the science data.

    Args:
        data: Bias- and dark-subtracted science frame.
        master_flat: Master flat field frame.

    Returns:
        Flat-corrected image.
    """
    _check_shape_match(data, master_flat, "flat")

    normalized = _normalize_flat(master_flat)
    result = data / normalized

    bad = ~np.isfinite(result)
    n_bad = np.count_nonzero(bad)
    if n_bad > 0:
        result[bad] = np.nan
        logger.warning(
            "Flat correction produced %d non-finite pixels (low-sensitivity regions)",
            n_bad,
        )

    return result


def create_master_bias(
    bias_paths: list[Path],
) -> tuple[np.ndarray, fits.Header]:
    """Combine bias frames into a master bias via median.

    Args:
        bias_paths: Paths to individual bias frames.

    Returns:
        (master_bias_data, header_from_first_frame).
    """
    frames = []
    header = None
    for p in bias_paths:
        data, hdr = read_fits(p)
        data = validate_2d(data)
        frames.append(data)
        if header is None:
            header = hdr

    cube = np.stack(frames, axis=0)
    master = np.nanmedian(cube, axis=0)
    header["NCOMBINE"] = len(frames)
    header["IMAGETYP"] = "MASTER_BIAS"
    logger.info("Created master bias from %d frames", len(frames))
    return master, header


def create_master_dark(
    dark_paths: list[Path],
    master_bias: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, fits.Header]:
    """Combine dark frames into a master dark via median.

    If a master bias is provided, it is subtracted from each dark frame
    before combining. This isolates the thermal signal.

    Args:
        dark_paths: Paths to individual dark frames.
        master_bias: Optional bias to subtract first.

    Returns:
        (master_dark_data, header_from_first_frame).
    """
    frames = []
    header = None
    for p in dark_paths:
        data, hdr = read_fits(p)
        data = validate_2d(data)
        if master_bias is not None:
            data = subtract_bias(data, master_bias)
        frames.append(data)
        if header is None:
            header = hdr

    cube = np.stack(frames, axis=0)
    master = np.nanmedian(cube, axis=0)
    header["NCOMBINE"] = len(frames)
    header["IMAGETYP"] = "MASTER_DARK"
    logger.info("Created master dark from %d frames", len(frames))
    return master, header


def create_master_flat(
    flat_paths: list[Path],
    master_bias: Optional[np.ndarray] = None,
    master_dark: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, fits.Header]:
    """Combine flat frames into a normalized master flat.

    Bias and dark are subtracted from each flat before combining. The
    combined flat is then normalized by its median so the result has
    a mean near 1.0.

    Args:
        flat_paths: Paths to individual flat frames.
        master_bias: Optional master bias.
        master_dark: Optional master dark (should be bias-subtracted).

    Returns:
        (normalized_master_flat, header_from_first_frame).
    """
    frames = []
    header = None
    for p in flat_paths:
        data, hdr = read_fits(p)
        data = validate_2d(data)
        if master_bias is not None:
            data = subtract_bias(data, master_bias)
        if master_dark is not None:
            data = data - master_dark
        frames.append(data)
        if header is None:
            header = hdr

    cube = np.stack(frames, axis=0)
    master = np.nanmedian(cube, axis=0)
    master = _normalize_flat(master)
    header["NCOMBINE"] = len(frames)
    header["IMAGETYP"] = "MASTER_FLAT"
    logger.info("Created master flat from %d frames", len(frames))
    return master, header


def _normalize_flat(flat: np.ndarray) -> np.ndarray:
    """Normalize a flat field to its median value.

    Pixels below 10% of the median are set to NaN to prevent division
    by near-zero values at vignetted or dead-pixel regions.
    """
    med = np.nanmedian(flat)
    if med <= 0:
        logger.error("Flat field median is non-positive (%.2f); returning ones", med)
        return np.ones_like(flat)

    normalized = flat / med
    low_threshold = 0.1
    bad = normalized < low_threshold
    if np.any(bad):
        logger.warning(
            "%d flat pixels below %.0f%% threshold — masking as NaN",
            np.count_nonzero(bad),
            low_threshold * 100,
        )
        normalized[bad] = np.nan

    return normalized


def _check_shape_match(
    data: np.ndarray, calibration: np.ndarray, cal_name: str
) -> None:
    """Verify that a calibration frame matches the science frame dimensions."""
    if data.shape != calibration.shape:
        raise ValueError(
            f"{cal_name} frame shape {calibration.shape} does not match "
            f"science frame shape {data.shape}"
        )
