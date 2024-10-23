"""FITS header inspection with WCS, image statistics, and observation metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from astropy.io import fits

from .io_utils import FITSReadError, read_fits, read_header
from .wcs_utils import FieldGeometry, compute_field_geometry

logger = logging.getLogger(__name__)

OBSERVATION_KEYWORDS = [
    ("OBJECT", "Target name"),
    ("RA", "Right ascension"),
    ("DEC", "Declination"),
    ("FILTER", "Filter band"),
    ("EXPTIME", "Exposure time (s)"),
    ("DATE-OBS", "Observation date"),
    ("INSTRUME", "Instrument"),
    ("TELESCOP", "Telescope"),
    ("OBSERVER", "Observer"),
    ("AIRMASS", "Airmass"),
    ("GAIN", "Detector gain (e-/ADU)"),
    ("RDNOISE", "Read noise (e-)"),
    ("IMAGETYP", "Frame type"),
    ("BUNIT", "Pixel unit"),
]


@dataclass
class ImageStatistics:
    """Basic pixel statistics for a FITS image (ignoring NaN pixels)."""

    shape: tuple[int, ...]
    dtype: str
    min_adu: float
    max_adu: float
    mean_adu: float
    median_adu: float
    std_adu: float
    nan_fraction: float


@dataclass
class InspectionReport:
    """Complete inspection result for a single FITS file.

    Attributes:
        filepath: Path that was inspected.
        extensions: Number of HDU extensions.
        stats: Pixel-level statistics.
        observation: Dict of observation metadata keywords found.
        field_geometry: On-sky footprint if WCS is present.
        all_keywords: Full keyword listing for advanced users.
    """

    filepath: Path
    extensions: int
    stats: Optional[ImageStatistics]
    observation: dict[str, Any]
    field_geometry: Optional[FieldGeometry]
    all_keywords: dict[str, Any] = field(default_factory=dict)


def inspect_file(
    filepath: Path,
    compute_stats: bool = True,
    include_all_keywords: bool = False,
) -> InspectionReport:
    """Inspect a FITS file and produce a structured report.

    Args:
        filepath: Path to the FITS file.
        compute_stats: Whether to load pixel data for statistics.
        include_all_keywords: Include all header keywords in the report.

    Returns:
        InspectionReport with metadata, statistics, and WCS info.
    """
    filepath = Path(filepath)
    logger.info("Inspecting %s", filepath)

    header = read_header(filepath)

    with fits.open(filepath) as hdul:
        n_ext = len(hdul)

    obs_meta = _extract_observation_metadata(header)

    stats = None
    geom = None

    if compute_stats:
        try:
            data, data_header = read_fits(filepath)
            stats = _compute_statistics(data)
            geom = compute_field_geometry(data_header, data.shape)
        except FITSReadError as exc:
            logger.warning("Cannot compute stats for %s: %s", filepath, exc)

    all_kw = {}
    if include_all_keywords:
        all_kw = {k: _header_value_safe(header[k]) for k in header if k}

    return InspectionReport(
        filepath=filepath,
        extensions=n_ext,
        stats=stats,
        observation=obs_meta,
        field_geometry=geom,
        all_keywords=all_kw,
    )


def format_report(report: InspectionReport) -> str:
    """Render an inspection report as human-readable text.

    Args:
        report: An InspectionReport to format.

    Returns:
        Multi-line string suitable for terminal output.
    """
    lines = [
        f"{'=' * 60}",
        f"  FITS Inspection: {report.filepath.name}",
        f"{'=' * 60}",
        f"  Path:       {report.filepath}",
        f"  Extensions: {report.extensions}",
    ]

    if report.stats:
        s = report.stats
        lines += [
            "",
            "  Image Data:",
            f"    Shape:      {s.shape[1]} x {s.shape[0]} px",
            f"    Dtype:      {s.dtype}",
            f"    Min ADU:    {s.min_adu:.2f}",
            f"    Max ADU:    {s.max_adu:.2f}",
            f"    Mean ADU:   {s.mean_adu:.2f}",
            f"    Median ADU: {s.median_adu:.2f}",
            f"    Std ADU:    {s.std_adu:.2f}",
            f"    NaN pixels: {s.nan_fraction:.4%}",
        ]

    if report.observation:
        lines += ["", "  Observation Metadata:"]
        for key, description in OBSERVATION_KEYWORDS:
            if key in report.observation:
                lines.append(f"    {description:.<30} {report.observation[key]}")

    if report.field_geometry:
        g = report.field_geometry
        ra = g.center.ra.deg
        dec = g.center.dec.deg
        lines += [
            "",
            "  WCS / Field Geometry:",
            f"    Center RA:      {ra:.6f} deg  ({g.center.ra.to_string(unit='hourangle', sep=':', precision=2)})",
            f"    Center Dec:     {dec:+.6f} deg  ({g.center.dec.to_string(sep=':', precision=1)})",
            f"    Field of View:  {g.fov_arcmin[0]:.2f}' x {g.fov_arcmin[1]:.2f}'",
            f"    Pixel Scale:    {g.pixel_scale_arcsec:.3f} arcsec/px",
            f"    Rotation:       {g.rotation_deg:.2f} deg",
            f"    Projection:     {g.projection}",
        ]

    lines.append(f"\n{'=' * 60}")
    return "\n".join(lines)


def _extract_observation_metadata(header: fits.Header) -> dict[str, Any]:
    """Pull standard observation keywords from a FITS header."""
    meta = {}
    for key, _ in OBSERVATION_KEYWORDS:
        val = header.get(key)
        if val is not None:
            meta[key] = _header_value_safe(val)
    return meta


def _compute_statistics(data: np.ndarray) -> ImageStatistics:
    """Compute image statistics, masking NaN pixels."""
    nan_mask = np.isnan(data)
    nan_frac = np.count_nonzero(nan_mask) / data.size if data.size > 0 else 0.0

    valid = data[~nan_mask] if np.any(nan_mask) else data

    if valid.size == 0:
        return ImageStatistics(
            shape=data.shape,
            dtype=str(data.dtype),
            min_adu=float("nan"),
            max_adu=float("nan"),
            mean_adu=float("nan"),
            median_adu=float("nan"),
            std_adu=float("nan"),
            nan_fraction=nan_frac,
        )

    return ImageStatistics(
        shape=data.shape,
        dtype=str(data.dtype),
        min_adu=float(np.min(valid)),
        max_adu=float(np.max(valid)),
        mean_adu=float(np.mean(valid)),
        median_adu=float(np.median(valid)),
        std_adu=float(np.std(valid)),
        nan_fraction=nan_frac,
    )


def _header_value_safe(value: Any) -> Any:
    """Convert FITS header values to JSON-safe Python types."""
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)
