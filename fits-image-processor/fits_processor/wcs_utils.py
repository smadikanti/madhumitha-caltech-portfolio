"""WCS coordinate utilities for extracting sky positions and field geometry."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

from .io_utils import get_wcs

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FieldGeometry:
    """Describes the on-sky footprint of a FITS image.

    Attributes:
        center: Sky coordinate of the image center.
        fov_arcmin: (width, height) field of view in arcminutes.
        pixel_scale_arcsec: Mean pixel scale in arcseconds/pixel.
        rotation_deg: Position angle (N through E) in degrees.
        projection: WCS projection type (e.g. TAN, SIN, AIT).
        corners: Sky coordinates of the four image corners.
    """

    center: SkyCoord
    fov_arcmin: tuple[float, float]
    pixel_scale_arcsec: float
    rotation_deg: float
    projection: str
    corners: SkyCoord


def compute_field_geometry(
    header: fits.Header, shape: tuple[int, int]
) -> Optional[FieldGeometry]:
    """Derive on-sky field geometry from a WCS-bearing header.

    Args:
        header: FITS header with WCS keywords.
        shape: (nrows, ncols) of the image array.

    Returns:
        FieldGeometry if WCS is present and valid, else None.
    """
    wcs = get_wcs(header)
    if wcs is None:
        return None

    ny, nx = shape

    try:
        center_sky = wcs.pixel_to_world(nx / 2.0, ny / 2.0)

        scales = proj_plane_pixel_scales(wcs)
        pixel_scale_deg = np.mean(scales)
        pixel_scale_arcsec = pixel_scale_deg * 3600.0

        fov_x = scales[0] * nx * 60.0
        fov_y = scales[1] * ny * 60.0

        rotation = _compute_rotation(wcs)

        projection = header.get("CTYPE1", "")
        if "-" in projection:
            projection = projection.split("-")[-1]
        else:
            projection = "UNKNOWN"

        corner_pixels = np.array([
            [0, 0],
            [nx - 1, 0],
            [nx - 1, ny - 1],
            [0, ny - 1],
        ], dtype=float)
        corners = wcs.pixel_to_world(corner_pixels[:, 0], corner_pixels[:, 1])

        return FieldGeometry(
            center=center_sky,
            fov_arcmin=(round(fov_x, 2), round(fov_y, 2)),
            pixel_scale_arcsec=round(pixel_scale_arcsec, 4),
            rotation_deg=round(rotation, 2),
            projection=projection,
            corners=corners,
        )
    except Exception as exc:
        logger.warning("Failed to compute field geometry: %s", exc)
        return None


def pixel_to_sky(
    wcs: WCS, x: np.ndarray, y: np.ndarray
) -> SkyCoord:
    """Convert pixel coordinates to sky coordinates.

    Args:
        wcs: Astropy WCS object.
        x: Pixel X coordinates (0-indexed, FITS column).
        y: Pixel Y coordinates (0-indexed, FITS row).

    Returns:
        SkyCoord with RA/Dec for each input position.
    """
    return wcs.pixel_to_world(x, y)


def sky_to_pixel(
    wcs: WCS, coord: SkyCoord
) -> tuple[np.ndarray, np.ndarray]:
    """Convert sky coordinates to pixel coordinates.

    Args:
        wcs: Astropy WCS object.
        coord: Sky positions.

    Returns:
        (x, y) pixel coordinate arrays.
    """
    return wcs.world_to_pixel(coord)


def separation_from_center(
    header: fits.Header, shape: tuple[int, int], coord: SkyCoord
) -> Optional[float]:
    """Compute angular separation between a sky position and image center.

    Args:
        header: FITS header with WCS.
        shape: Image (nrows, ncols).
        coord: Target sky position.

    Returns:
        Separation in arcminutes, or None if WCS is unavailable.
    """
    geom = compute_field_geometry(header, shape)
    if geom is None:
        return None
    return geom.center.separation(coord).arcmin


def _compute_rotation(wcs: WCS) -> float:
    """Extract the image rotation angle (position angle N through E).

    Uses the CD matrix if present, falling back to CROTA2.
    """
    if wcs.wcs.has_cd():
        cd = wcs.wcs.cd
        return np.degrees(np.arctan2(cd[0, 1], cd[0, 0]))

    if hasattr(wcs.wcs, "crota") and wcs.wcs.crota[1] != 0:
        return wcs.wcs.crota[1]

    return 0.0
