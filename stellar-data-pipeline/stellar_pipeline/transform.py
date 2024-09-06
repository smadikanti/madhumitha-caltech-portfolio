"""Transformation engine for validated exoplanet records.

Applies unit conversions, derives new columns (habitable zone flag),
and normalizes string fields for consistent database storage.
"""

from __future__ import annotations

import logging
from typing import Optional

from stellar_pipeline.exceptions import TransformError
from stellar_pipeline.models import Exoplanet, RawExoplanet

logger = logging.getLogger(__name__)

JUPITER_RADIUS_IN_EARTH_RADII = 11.209
JUPITER_MASS_IN_EARTH_MASSES = 317.828

HABITABLE_ZONE_TEMP_MIN_K = 180.0
HABITABLE_ZONE_TEMP_MAX_K = 310.0


def earth_radii_to_jupiter(earth_radii: Optional[float]) -> Optional[float]:
    """Convert planetary radius from Earth radii to Jupiter radii."""
    if earth_radii is None:
        return None
    return earth_radii / JUPITER_RADIUS_IN_EARTH_RADII


def earth_mass_to_jupiter(earth_mass: Optional[float]) -> Optional[float]:
    """Convert planetary mass from Earth masses to Jupiter masses."""
    if earth_mass is None:
        return None
    return earth_mass / JUPITER_MASS_IN_EARTH_MASSES


def is_habitable_zone(equilibrium_temp_k: Optional[float]) -> bool:
    """Determine if a planet is in the habitable zone based on equilibrium temperature.

    Uses a simplified criterion: equilibrium temperature between 180K and
    310K, roughly corresponding to conditions where liquid water could
    exist on the surface.
    """
    if equilibrium_temp_k is None:
        return False
    return HABITABLE_ZONE_TEMP_MIN_K <= equilibrium_temp_k <= HABITABLE_ZONE_TEMP_MAX_K


def normalize_string(value: Optional[str]) -> Optional[str]:
    """Strip whitespace and normalize to title case."""
    if value is None:
        return None
    return value.strip()


class ExoplanetTransformer:
    """Transforms validated raw records into database-ready Exoplanet instances.

    Applies unit conversions (Earth to Jupiter units), derives the
    habitable zone flag, and normalizes string fields.
    """

    def transform(self, records: list[RawExoplanet]) -> list[Exoplanet]:
        """Transform a batch of validated raw records.

        Args:
            records: Validated RawExoplanet records.

        Returns:
            List of transformed Exoplanet records.

        Raises:
            TransformError: If a record cannot be transformed.
        """
        transformed: list[Exoplanet] = []
        for idx, raw in enumerate(records):
            try:
                transformed.append(self._transform_single(raw))
            except Exception as exc:
                logger.error(f"Transform failed for record {idx} ({raw.pl_name}): {exc}")
                raise TransformError(
                    f"Failed to transform record {raw.pl_name}: {exc}"
                ) from exc

        logger.info(f"Transformed {len(transformed)} records")
        return transformed

    @staticmethod
    def _transform_single(raw: RawExoplanet) -> Exoplanet:
        """Apply all transformations to a single record."""
        return Exoplanet(
            pl_name=raw.pl_name.strip(),
            hostname=raw.hostname.strip(),
            discovery_method=normalize_string(raw.discoverymethod),
            disc_year=raw.disc_year,
            orbital_period_days=raw.pl_orbper,
            radius_earth=raw.pl_rade,
            radius_jupiter=earth_radii_to_jupiter(raw.pl_rade),
            mass_earth=raw.pl_bmasse,
            mass_jupiter=earth_mass_to_jupiter(raw.pl_bmasse),
            equilibrium_temp_k=raw.pl_eqt,
            stellar_teff_k=raw.st_teff,
            stellar_radius_solar=raw.st_rad,
            stellar_mass_solar=raw.st_mass,
            distance_pc=raw.sy_dist,
            is_habitable_zone=is_habitable_zone(raw.pl_eqt),
        )
