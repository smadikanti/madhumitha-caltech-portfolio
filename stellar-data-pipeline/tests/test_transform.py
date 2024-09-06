"""Tests for the exoplanet record transformation module."""

from __future__ import annotations

import pytest

from stellar_pipeline.models import Exoplanet, RawExoplanet
from stellar_pipeline.transform import (
    HABITABLE_ZONE_TEMP_MAX_K,
    HABITABLE_ZONE_TEMP_MIN_K,
    JUPITER_MASS_IN_EARTH_MASSES,
    JUPITER_RADIUS_IN_EARTH_RADII,
    ExoplanetTransformer,
    earth_mass_to_jupiter,
    earth_radii_to_jupiter,
    is_habitable_zone,
    normalize_string,
)


class TestUnitConversions:
    def test_earth_radii_to_jupiter(self) -> None:
        result = earth_radii_to_jupiter(11.209)
        assert result == pytest.approx(1.0, rel=1e-3)

    def test_earth_radii_to_jupiter_small(self) -> None:
        result = earth_radii_to_jupiter(1.0)
        assert result == pytest.approx(1.0 / JUPITER_RADIUS_IN_EARTH_RADII, rel=1e-6)

    def test_earth_radii_to_jupiter_none(self) -> None:
        assert earth_radii_to_jupiter(None) is None

    def test_earth_mass_to_jupiter(self) -> None:
        result = earth_mass_to_jupiter(317.828)
        assert result == pytest.approx(1.0, rel=1e-3)

    def test_earth_mass_to_jupiter_none(self) -> None:
        assert earth_mass_to_jupiter(None) is None


class TestHabitableZone:
    def test_habitable_temperature(self) -> None:
        assert is_habitable_zone(250.0) is True

    def test_too_cold(self) -> None:
        assert is_habitable_zone(100.0) is False

    def test_too_hot(self) -> None:
        assert is_habitable_zone(500.0) is False

    def test_lower_boundary(self) -> None:
        assert is_habitable_zone(HABITABLE_ZONE_TEMP_MIN_K) is True

    def test_upper_boundary(self) -> None:
        assert is_habitable_zone(HABITABLE_ZONE_TEMP_MAX_K) is True

    def test_just_below_lower_boundary(self) -> None:
        assert is_habitable_zone(HABITABLE_ZONE_TEMP_MIN_K - 0.1) is False

    def test_just_above_upper_boundary(self) -> None:
        assert is_habitable_zone(HABITABLE_ZONE_TEMP_MAX_K + 0.1) is False

    def test_none_temperature(self) -> None:
        assert is_habitable_zone(None) is False


class TestNormalizeString:
    def test_strips_whitespace(self) -> None:
        assert normalize_string("  Transit  ") == "Transit"

    def test_none_returns_none(self) -> None:
        assert normalize_string(None) is None

    def test_empty_string(self) -> None:
        assert normalize_string("") == ""


class TestExoplanetTransformer:
    @pytest.fixture
    def transformer(self) -> ExoplanetTransformer:
        return ExoplanetTransformer()

    def test_transforms_single_record(
        self, transformer: ExoplanetTransformer, raw_exoplanet: RawExoplanet
    ) -> None:
        results = transformer.transform([raw_exoplanet])
        assert len(results) == 1

        planet = results[0]
        assert isinstance(planet, Exoplanet)
        assert planet.pl_name == "Kepler-22 b"
        assert planet.hostname == "Kepler-22"
        assert planet.discovery_method == "Transit"

    def test_radius_conversion(
        self, transformer: ExoplanetTransformer, raw_exoplanet: RawExoplanet
    ) -> None:
        results = transformer.transform([raw_exoplanet])
        planet = results[0]
        assert planet.radius_earth == 2.38
        assert planet.radius_jupiter == pytest.approx(
            2.38 / JUPITER_RADIUS_IN_EARTH_RADII, rel=1e-6
        )

    def test_mass_conversion(
        self, transformer: ExoplanetTransformer, raw_exoplanet: RawExoplanet
    ) -> None:
        results = transformer.transform([raw_exoplanet])
        planet = results[0]
        assert planet.mass_earth == 9.1
        assert planet.mass_jupiter == pytest.approx(
            9.1 / JUPITER_MASS_IN_EARTH_MASSES, rel=1e-6
        )

    def test_habitable_zone_flag_set(
        self, transformer: ExoplanetTransformer, raw_exoplanet: RawExoplanet
    ) -> None:
        results = transformer.transform([raw_exoplanet])
        assert results[0].is_habitable_zone is True

    def test_non_habitable_planet(
        self, transformer: ExoplanetTransformer
    ) -> None:
        hot_planet = RawExoplanet(
            pl_name="Hot-1", hostname="Star-1", pl_eqt=2000.0
        )
        results = transformer.transform([hot_planet])
        assert results[0].is_habitable_zone is False

    def test_null_optional_fields_preserved(
        self, transformer: ExoplanetTransformer
    ) -> None:
        minimal = RawExoplanet(pl_name="Minimal", hostname="Star-1")
        results = transformer.transform([minimal])
        planet = results[0]
        assert planet.radius_earth is None
        assert planet.radius_jupiter is None
        assert planet.mass_earth is None
        assert planet.mass_jupiter is None
        assert planet.is_habitable_zone is False

    def test_batch_transform(
        self, transformer: ExoplanetTransformer, raw_exoplanet_list: list[RawExoplanet]
    ) -> None:
        results = transformer.transform(raw_exoplanet_list)
        assert len(results) == len(raw_exoplanet_list)
        names = {r.pl_name for r in results}
        assert "Kepler-22 b" in names
        assert "TRAPPIST-1 e" in names

    def test_empty_list_returns_empty(
        self, transformer: ExoplanetTransformer
    ) -> None:
        assert transformer.transform([]) == []
