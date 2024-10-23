"""Scan directories of FITS files and produce metadata catalogs.

Produces CSV or JSON catalogs containing standard observation metadata
extracted from FITS headers: target name, coordinates, filter, exposure
time, instrument, and observation date. This is a common first step when
organizing an observing run's data for reduction.
"""

from __future__ import annotations

import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence

from .io_utils import FITSReadError, read_header
from .wcs_utils import compute_field_geometry

logger = logging.getLogger(__name__)

FITS_EXTENSIONS = {".fits", ".fit", ".fts", ".fits.gz", ".fit.gz", ".fts.gz"}

CATALOG_FIELDS = [
    "filename",
    "object",
    "ra_deg",
    "dec_deg",
    "filter",
    "exptime",
    "instrument",
    "telescope",
    "date_obs",
    "imagetyp",
    "naxis1",
    "naxis2",
    "airmass",
    "fov_arcmin",
]


class OutputFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


@dataclass
class CatalogEntry:
    """Metadata for a single FITS file in the catalog."""

    filename: str
    object: Optional[str] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    filter: Optional[str] = None
    exptime: Optional[float] = None
    instrument: Optional[str] = None
    telescope: Optional[str] = None
    date_obs: Optional[str] = None
    imagetyp: Optional[str] = None
    naxis1: Optional[int] = None
    naxis2: Optional[int] = None
    airmass: Optional[float] = None
    fov_arcmin: Optional[str] = None


def catalog_directory(
    directory: Path,
    output: Optional[Path] = None,
    fmt: OutputFormat = OutputFormat.CSV,
    recursive: bool = False,
    max_workers: int = 4,
) -> Path:
    """Scan a directory for FITS files and produce a metadata catalog.

    Args:
        directory: Directory to scan.
        output: Output catalog path. Defaults to ``<directory>/catalog.<ext>``.
        fmt: Output format (CSV or JSON).
        recursive: Search subdirectories.
        max_workers: Threads for parallel header reads.

    Returns:
        Path to the generated catalog file.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Not a directory: {directory}")

    fits_files = _find_fits_files(directory, recursive)
    logger.info("Found %d FITS files in %s", len(fits_files), directory)

    if not fits_files:
        logger.warning("No FITS files found in %s", directory)
        fits_files = []

    entries = _extract_metadata_parallel(fits_files, max_workers)
    entries.sort(key=lambda e: e.date_obs or "")

    if output is None:
        ext = "csv" if fmt == OutputFormat.CSV else "json"
        output = directory / f"catalog.{ext}"

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if fmt == OutputFormat.CSV:
        _write_csv(entries, output)
    else:
        _write_json(entries, output)

    logger.info("Catalog written: %s (%d entries)", output, len(entries))
    return output


def extract_metadata(filepath: Path) -> CatalogEntry:
    """Extract catalog-relevant metadata from a single FITS file.

    Args:
        filepath: Path to a FITS file.

    Returns:
        CatalogEntry populated from the file's header.
    """
    filepath = Path(filepath)
    try:
        header = read_header(filepath)
    except FITSReadError as exc:
        logger.error("Cannot read %s: %s", filepath, exc)
        return CatalogEntry(filename=filepath.name)

    ra = _get_float(header, "RA")
    dec = _get_float(header, "DEC")
    if ra is None:
        ra = _get_float(header, "CRVAL1")
    if dec is None:
        dec = _get_float(header, "CRVAL2")

    naxis1 = header.get("NAXIS1")
    naxis2 = header.get("NAXIS2")

    fov_str = None
    if naxis1 is not None and naxis2 is not None:
        try:
            geom = compute_field_geometry(header, (naxis2, naxis1))
            if geom is not None:
                fov_str = f"{geom.fov_arcmin[0]:.1f}x{geom.fov_arcmin[1]:.1f}"
        except Exception:
            pass

    return CatalogEntry(
        filename=filepath.name,
        object=header.get("OBJECT"),
        ra_deg=ra,
        dec_deg=dec,
        filter=header.get("FILTER"),
        exptime=_get_float(header, "EXPTIME"),
        instrument=header.get("INSTRUME"),
        telescope=header.get("TELESCOP"),
        date_obs=header.get("DATE-OBS"),
        imagetyp=header.get("IMAGETYP"),
        naxis1=naxis1,
        naxis2=naxis2,
        airmass=_get_float(header, "AIRMASS"),
        fov_arcmin=fov_str,
    )


def format_catalog_table(entries: Sequence[CatalogEntry]) -> str:
    """Render catalog entries as an aligned text table for terminal output.

    Args:
        entries: Catalog entries to display.

    Returns:
        Formatted table string.
    """
    if not entries:
        return "No entries."

    headers = ["Filename", "Object", "RA", "Dec", "Filter", "Exp(s)", "Date-Obs"]
    rows = []
    for e in entries:
        rows.append([
            e.filename or "",
            e.object or "",
            f"{e.ra_deg:.4f}" if e.ra_deg is not None else "",
            f"{e.dec_deg:+.4f}" if e.dec_deg is not None else "",
            e.filter or "",
            f"{e.exptime:.1f}" if e.exptime is not None else "",
            e.date_obs or "",
        ])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt_row = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt_row.format(*headers), "-" * (sum(widths) + 2 * (len(widths) - 1))]
    for row in rows:
        lines.append(fmt_row.format(*row))

    return "\n".join(lines)


def _find_fits_files(directory: Path, recursive: bool) -> list[Path]:
    """Locate FITS files by extension."""
    pattern = "**/*" if recursive else "*"
    files = []
    for p in directory.glob(pattern):
        if p.is_file() and _is_fits_file(p):
            files.append(p)
    return sorted(files)


def _is_fits_file(path: Path) -> bool:
    """Check if a path has a recognized FITS extension."""
    name = path.name.lower()
    for ext in FITS_EXTENSIONS:
        if name.endswith(ext):
            return True
    return False


def _extract_metadata_parallel(
    filepaths: list[Path], max_workers: int
) -> list[CatalogEntry]:
    """Read metadata from multiple FITS files in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        entries = list(pool.map(extract_metadata, filepaths))
    return entries


def _write_csv(entries: list[CatalogEntry], output: Path) -> None:
    """Write catalog entries as CSV."""
    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(asdict(entry))


def _write_json(entries: list[CatalogEntry], output: Path) -> None:
    """Write catalog entries as JSON."""
    data = [asdict(e) for e in entries]
    with open(output, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _get_float(header, key: str) -> Optional[float]:
    """Safely extract a float value from a FITS header."""
    val = header.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
