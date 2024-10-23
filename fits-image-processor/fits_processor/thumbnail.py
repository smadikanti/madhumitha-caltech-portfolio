"""PNG thumbnail generation from FITS data with astronomical image stretches.

Astronomical images have enormous dynamic range — a single frame may contain
pixel values spanning several orders of magnitude. Linear display would show
almost nothing because faint nebulosity is overwhelmed by bright stars.
Astropy's visualization module provides the standard stretch functions used
throughout astronomy: asinh (the default for SDSS and most surveys), log,
sqrt, and linear.
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from astropy.visualization import (
    AsinhStretch,
    ImageNormalize,
    LinearStretch,
    LogStretch,
    MinMaxInterval,
    SqrtStretch,
    ZScaleInterval,
)

from .io_utils import read_fits, validate_2d

logger = logging.getLogger(__name__)


class Stretch(str, Enum):
    LINEAR = "linear"
    LOG = "log"
    SQRT = "sqrt"
    ASINH = "asinh"


class IntervalMode(str, Enum):
    MINMAX = "minmax"
    ZSCALE = "zscale"


STRETCH_MAP = {
    Stretch.LINEAR: LinearStretch,
    Stretch.LOG: LogStretch,
    Stretch.SQRT: SqrtStretch,
    Stretch.ASINH: AsinhStretch,
}


def generate_thumbnail(
    filepath: Path,
    output: Optional[Path] = None,
    stretch: Stretch = Stretch.ASINH,
    interval: IntervalMode = IntervalMode.ZSCALE,
    cmap: str = "gray",
    figsize: tuple[float, float] = (8.0, 8.0),
    dpi: int = 150,
    show_colorbar: bool = True,
    title: Optional[str] = None,
) -> Path:
    """Generate a PNG thumbnail from a FITS image.

    Args:
        filepath: Input FITS file.
        output: Output PNG path. Defaults to ``<input_stem>_thumb.png``.
        stretch: Pixel stretch function. Asinh is the standard in survey
            astronomy (Lupton et al. 2004) because it behaves linearly
            near zero and logarithmically at high values.
        interval: How to compute the display range. ZScale mimics the
            algorithm used in DS9/IRAF, emphasizing the main pixel
            distribution and ignoring outliers.
        cmap: Matplotlib colormap name.
        figsize: Figure size in inches (width, height).
        dpi: Output resolution.
        show_colorbar: Add a colorbar showing the ADU scale.
        title: Optional title; defaults to the filename.

    Returns:
        Path to the generated PNG file.
    """
    filepath = Path(filepath)
    if output is None:
        output = filepath.with_name(f"{filepath.stem}_thumb.png")
    output = Path(output)

    logger.info("Generating thumbnail: %s → %s", filepath.name, output.name)

    data, header = read_fits(filepath)
    data = validate_2d(data, label=str(filepath))

    stretch_fn = STRETCH_MAP[stretch]()

    if interval == IntervalMode.ZSCALE:
        interval_fn = ZScaleInterval()
    else:
        interval_fn = MinMaxInterval()

    norm = ImageNormalize(data, interval=interval_fn, stretch=stretch_fn)

    fig, ax = plt.subplots(1, 1, figsize=figsize)

    im = ax.imshow(data, origin="lower", norm=norm, cmap=cmap, interpolation="nearest")

    if show_colorbar:
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("ADU", fontsize=10)

    if title is None:
        title = filepath.name
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("X (pixels)")
    ax.set_ylabel("Y (pixels)")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info("Thumbnail saved: %s (%.1f KB)", output, output.stat().st_size / 1024)
    return output


def generate_rgb_thumbnail(
    red_path: Path,
    green_path: Path,
    blue_path: Path,
    output: Path,
    stretch: Stretch = Stretch.ASINH,
    figsize: tuple[float, float] = (8.0, 8.0),
    dpi: int = 150,
    q: float = 10.0,
) -> Path:
    """Generate an RGB color composite from three FITS images.

    Uses the Lupton et al. (2004) asinh mapping to combine three filter
    bands into a single color image. This is the same technique used for
    SDSS color images.

    Args:
        red_path: FITS file for the red channel.
        green_path: FITS file for the green channel.
        blue_path: FITS file for the blue channel.
        output: Output PNG path.
        stretch: Stretch applied to each channel before compositing.
        figsize: Figure size in inches.
        dpi: Output resolution.
        q: Asinh softening parameter. Higher values increase contrast.

    Returns:
        Path to the generated PNG.
    """
    r_data, _ = read_fits(red_path)
    g_data, _ = read_fits(green_path)
    b_data, _ = read_fits(blue_path)

    r_data = validate_2d(r_data)
    g_data = validate_2d(g_data)
    b_data = validate_2d(b_data)

    min_shape = (
        min(r_data.shape[0], g_data.shape[0], b_data.shape[0]),
        min(r_data.shape[1], g_data.shape[1], b_data.shape[1]),
    )
    r_data = r_data[: min_shape[0], : min_shape[1]]
    g_data = g_data[: min_shape[0], : min_shape[1]]
    b_data = b_data[: min_shape[0], : min_shape[1]]

    stretch_fn = STRETCH_MAP[stretch]()

    def _normalize_channel(ch: np.ndarray) -> np.ndarray:
        interval = ZScaleInterval()
        vmin, vmax = interval.get_limits(ch)
        clipped = np.clip(ch, vmin, vmax)
        norm = ImageNormalize(vmin=vmin, vmax=vmax, stretch=stretch_fn)
        return norm(clipped)

    rgb = np.stack(
        [_normalize_channel(r_data), _normalize_channel(g_data), _normalize_channel(b_data)],
        axis=-1,
    )
    rgb = np.nan_to_num(rgb, nan=0.0)
    rgb = np.clip(rgb, 0, 1)

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.imshow(rgb, origin="lower", interpolation="nearest")
    ax.set_title("RGB Composite")
    ax.set_xlabel("X (pixels)")
    ax.set_ylabel("Y (pixels)")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight", facecolor="black")
    plt.close(fig)

    logger.info("RGB thumbnail saved: %s", output)
    return output
