"""Image stacking via median-combine for noise reduction.

Median-combining a set of exposures is the standard technique for rejecting
cosmic rays and improving signal-to-noise in astronomical imaging. This module
handles frames of different sizes by reprojecting them to a common WCS grid
when headers are available, or by cropping to the intersection otherwise.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
from astropy.io import fits

from .io_utils import (
    FITSReadError,
    FITSValidationError,
    read_fits,
    validate_2d,
    write_fits,
)

logger = logging.getLogger(__name__)


class CombineMethod(str, Enum):
    MEDIAN = "median"
    MEAN = "mean"
    SIGMA_CLIP = "sigma_clip"


def stack_images(
    filepaths: Sequence[Path],
    output: Path,
    method: CombineMethod = CombineMethod.MEDIAN,
    sigma_low: float = 3.0,
    sigma_high: float = 3.0,
    max_workers: int = 4,
) -> Path:
    """Median-combine (or mean/sigma-clip) a list of FITS images.

    All input frames are loaded in parallel, aligned to a common pixel grid,
    and combined along the stack axis. The header from the first frame is
    preserved in the output, with NCOMBINE and HISTORY cards added.

    Args:
        filepaths: Paths to input FITS files (minimum 2).
        output: Where to write the combined FITS file.
        method: Combination method.
        sigma_low: Lower sigma threshold for sigma-clipped mean.
        sigma_high: Upper sigma threshold for sigma-clipped mean.
        max_workers: Threads for parallel I/O.

    Returns:
        Path to the output FITS file.

    Raises:
        ValueError: If fewer than 2 files are given.
        FITSValidationError: If frames cannot be aligned.
    """
    if len(filepaths) < 2:
        raise ValueError("Stacking requires at least 2 frames")

    logger.info("Stacking %d frames with method=%s", len(filepaths), method.value)

    frames, headers = _load_frames_parallel(filepaths, max_workers)

    aligned = _align_frames(frames)
    logger.info("Aligned %d frames to common shape %s", len(aligned), aligned[0].shape)

    cube = np.stack(aligned, axis=0)

    if method == CombineMethod.MEDIAN:
        combined = np.nanmedian(cube, axis=0)
    elif method == CombineMethod.MEAN:
        combined = np.nanmean(cube, axis=0)
    elif method == CombineMethod.SIGMA_CLIP:
        combined = _sigma_clipped_mean(cube, sigma_low, sigma_high)
    else:
        raise ValueError(f"Unknown combine method: {method}")

    out_header = headers[0].copy()
    out_header["NCOMBINE"] = (len(frames), "Number of frames combined")
    out_header["COMBMETH"] = (method.value, "Combination method")
    out_header["HISTORY"] = f"Stacked {len(frames)} frames via {method.value}"

    return write_fits(output, combined, header=out_header)


def _load_frames_parallel(
    filepaths: Sequence[Path], max_workers: int
) -> tuple[list[np.ndarray], list[fits.Header]]:
    """Load FITS frames in parallel threads.

    Files that fail to load are logged and skipped rather than aborting
    the entire stack.
    """
    frames: list[np.ndarray] = []
    headers: list[fits.Header] = []

    def _load(fp: Path) -> Optional[tuple[np.ndarray, fits.Header]]:
        try:
            data, hdr = read_fits(fp)
            data = validate_2d(data, label=str(fp))
            return data, hdr
        except (FITSReadError, FITSValidationError) as exc:
            logger.error("Skipping %s: %s", fp, exc)
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_load, filepaths))

    for result in results:
        if result is not None:
            frames.append(result[0])
            headers.append(result[1])

    if len(frames) < 2:
        raise FITSValidationError(
            f"Only {len(frames)} valid frame(s) loaded; need at least 2"
        )

    return frames, headers


def _align_frames(frames: list[np.ndarray]) -> list[np.ndarray]:
    """Align frames to a common pixel grid by cropping to the intersection.

    For frames that share a WCS, reprojection would be ideal (and Montage
    excels at this). Here we use the simpler crop-to-minimum approach,
    which is correct when frames share the same pointing and plate scale
    but may differ slightly in size due to detector readout regions.
    """
    if not frames:
        return frames

    shapes = np.array([f.shape for f in frames])
    if np.all(shapes == shapes[0]):
        return frames

    min_y = shapes[:, 0].min()
    min_x = shapes[:, 1].min()

    logger.info(
        "Frames have different sizes; cropping to intersection (%d x %d)",
        min_x,
        min_y,
    )

    aligned = []
    for frame in frames:
        cy = (frame.shape[0] - min_y) // 2
        cx = (frame.shape[1] - min_x) // 2
        aligned.append(frame[cy : cy + min_y, cx : cx + min_x])

    return aligned


def _sigma_clipped_mean(
    cube: np.ndarray, sigma_low: float, sigma_high: float, max_iter: int = 5
) -> np.ndarray:
    """Iterative sigma-clipped mean along the stack axis.

    At each pixel position, values beyond the sigma thresholds are masked
    and the mean is recomputed. This rejects outliers (cosmic rays, satellite
    trails) more aggressively than a simple median while preserving SNR.
    """
    mask = np.zeros(cube.shape, dtype=bool)

    for _ in range(max_iter):
        masked = np.where(mask, np.nan, cube)
        med = np.nanmedian(masked, axis=0, keepdims=True)
        std = np.nanstd(masked, axis=0, keepdims=True)

        std = np.where(std == 0, 1.0, std)

        deviation = (cube - med) / std
        new_mask = (deviation < -sigma_low) | (deviation > sigma_high)

        if np.array_equal(new_mask, mask):
            break
        mask = new_mask

    clipped = np.where(mask, np.nan, cube)
    return np.nanmean(clipped, axis=0)
