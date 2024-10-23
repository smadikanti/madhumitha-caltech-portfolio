"""Tests for PNG thumbnail generation from FITS data."""

from __future__ import annotations

from pathlib import Path

import pytest

from fits_processor.thumbnail import (
    IntervalMode,
    Stretch,
    generate_thumbnail,
)


class TestGenerateThumbnail:
    def test_default_thumbnail(
        self, synthetic_star_field: Path, tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "thumb.png"
        result = generate_thumbnail(synthetic_star_field, output=output)

        assert result.exists()
        assert result.suffix == ".png"
        assert result.stat().st_size > 0

    def test_auto_output_name(
        self, synthetic_star_field: Path
    ) -> None:
        result = generate_thumbnail(synthetic_star_field)
        assert result.exists()
        assert "star_field" in result.stem
        assert result.suffix == ".png"
        result.unlink()

    @pytest.mark.parametrize("stretch", list(Stretch))
    def test_all_stretches(
        self, synthetic_star_field: Path, tmp_fits_dir: Path, stretch: Stretch
    ) -> None:
        output = tmp_fits_dir / f"thumb_{stretch.value}.png"
        result = generate_thumbnail(
            synthetic_star_field, output=output, stretch=stretch
        )
        assert result.exists()
        assert result.stat().st_size > 0

    def test_minmax_interval(
        self, synthetic_star_field: Path, tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "thumb_minmax.png"
        result = generate_thumbnail(
            synthetic_star_field, output=output, interval=IntervalMode.MINMAX
        )
        assert result.exists()

    def test_custom_cmap(
        self, synthetic_star_field: Path, tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "thumb_hot.png"
        result = generate_thumbnail(
            synthetic_star_field, output=output, cmap="hot"
        )
        assert result.exists()

    def test_no_colorbar(
        self, synthetic_star_field: Path, tmp_fits_dir: Path
    ) -> None:
        output = tmp_fits_dir / "thumb_nocbar.png"
        result = generate_thumbnail(
            synthetic_star_field, output=output, show_colorbar=False
        )
        assert result.exists()

    def test_nan_image_thumbnail(
        self, fits_with_nan: Path, tmp_fits_dir: Path
    ) -> None:
        """Thumbnail generation should handle NaN pixels gracefully."""
        output = tmp_fits_dir / "thumb_nan.png"
        result = generate_thumbnail(fits_with_nan, output=output)
        assert result.exists()
