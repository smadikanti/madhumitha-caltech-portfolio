"""CLI entry point for the FITS image processor.

Usage:
    python -m fits_processor inspect <file>
    python -m fits_processor stack <files...> -o stacked.fits
    python -m fits_processor normalize <file> --bias master_bias.fits --flat master_flat.fits
    python -m fits_processor thumbnail <file> --stretch asinh
    python -m fits_processor catalog <directory> --format csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand."""
    parser = argparse.ArgumentParser(
        prog="fits_processor",
        description="FITS image processing toolkit for astronomical image analysis",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_inspect_parser(subparsers)
    _add_stack_parser(subparsers)
    _add_normalize_parser(subparsers)
    _add_thumbnail_parser(subparsers)
    _add_catalog_parser(subparsers)

    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    if args.command is None:
        parser.print_help()
        return 1

    handlers = {
        "inspect": _run_inspect,
        "stack": _run_stack,
        "normalize": _run_normalize,
        "thumbnail": _run_thumbnail,
        "catalog": _run_catalog,
    }

    try:
        return handlers[args.command](args)
    except Exception as exc:
        logging.getLogger(__name__).error("%s", exc)
        if args.verbose >= 2:
            raise
        return 1


def _add_inspect_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("inspect", help="Inspect FITS file headers and metadata")
    p.add_argument("file", type=Path, help="FITS file to inspect")
    p.add_argument(
        "--no-stats",
        action="store_true",
        help="Skip loading pixel data for statistics",
    )
    p.add_argument(
        "--all-keywords",
        action="store_true",
        help="Include all header keywords in output",
    )


def _add_stack_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "stack", help="Median-combine FITS images for noise reduction"
    )
    p.add_argument("files", type=Path, nargs="+", help="FITS files to stack")
    p.add_argument(
        "-o", "--output", type=Path, default=Path("stacked.fits"), help="Output path"
    )
    p.add_argument(
        "--method",
        choices=["median", "mean", "sigma_clip"],
        default="median",
        help="Combination method (default: median)",
    )
    p.add_argument(
        "--sigma-low", type=float, default=3.0, help="Lower sigma clip threshold"
    )
    p.add_argument(
        "--sigma-high", type=float, default=3.0, help="Upper sigma clip threshold"
    )
    p.add_argument(
        "--workers", type=int, default=4, help="Parallel I/O threads"
    )


def _add_normalize_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "normalize", help="Apply CCD reduction (bias/dark/flat correction)"
    )
    p.add_argument("file", type=Path, help="Science frame to reduce")
    p.add_argument(
        "-o", "--output", type=Path, default=None, help="Output path"
    )
    p.add_argument("--bias", type=Path, default=None, help="Master bias frame")
    p.add_argument("--dark", type=Path, default=None, help="Master dark frame")
    p.add_argument("--flat", type=Path, default=None, help="Master flat frame")


def _add_thumbnail_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "thumbnail", help="Generate PNG thumbnail from FITS data"
    )
    p.add_argument("file", type=Path, help="FITS file")
    p.add_argument("-o", "--output", type=Path, default=None, help="Output PNG path")
    p.add_argument(
        "--stretch",
        choices=["linear", "log", "sqrt", "asinh"],
        default="asinh",
        help="Pixel stretch function (default: asinh)",
    )
    p.add_argument(
        "--interval",
        choices=["zscale", "minmax"],
        default="zscale",
        help="Display interval (default: zscale)",
    )
    p.add_argument("--cmap", default="gray", help="Matplotlib colormap")
    p.add_argument("--dpi", type=int, default=150, help="Output DPI")
    p.add_argument(
        "--no-colorbar", action="store_true", help="Omit the colorbar"
    )


def _add_catalog_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "catalog", help="Scan directory and produce metadata catalog"
    )
    p.add_argument("directory", type=Path, help="Directory to scan")
    p.add_argument("-o", "--output", type=Path, default=None, help="Output catalog path")
    p.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        dest="fmt",
        help="Output format (default: csv)",
    )
    p.add_argument(
        "--recursive", action="store_true", help="Search subdirectories"
    )
    p.add_argument(
        "--workers", type=int, default=4, help="Parallel header-read threads"
    )


def _run_inspect(args: argparse.Namespace) -> int:
    from .inspector import format_report, inspect_file

    report = inspect_file(
        args.file,
        compute_stats=not args.no_stats,
        include_all_keywords=args.all_keywords,
    )
    print(format_report(report))
    return 0


def _run_stack(args: argparse.Namespace) -> int:
    from .stacker import CombineMethod, stack_images

    method = CombineMethod(args.method)
    result = stack_images(
        filepaths=args.files,
        output=args.output,
        method=method,
        sigma_low=args.sigma_low,
        sigma_high=args.sigma_high,
        max_workers=args.workers,
    )
    print(f"Stacked image written to: {result}")
    return 0


def _run_normalize(args: argparse.Namespace) -> int:
    from .normalizer import reduce

    output = args.output
    if output is None:
        output = args.file.with_name(f"{args.file.stem}_reduced.fits")

    result = reduce(
        science_path=args.file,
        output=output,
        bias_path=args.bias,
        dark_path=args.dark,
        flat_path=args.flat,
    )
    print(f"Reduced frame written to: {result}")
    return 0


def _run_thumbnail(args: argparse.Namespace) -> int:
    from .thumbnail import IntervalMode, Stretch, generate_thumbnail

    result = generate_thumbnail(
        filepath=args.file,
        output=args.output,
        stretch=Stretch(args.stretch),
        interval=IntervalMode(args.interval),
        cmap=args.cmap,
        dpi=args.dpi,
        show_colorbar=not args.no_colorbar,
    )
    print(f"Thumbnail saved to: {result}")
    return 0


def _run_catalog(args: argparse.Namespace) -> int:
    from .cataloger import (
        OutputFormat,
        catalog_directory,
        extract_metadata,
        format_catalog_table,
    )

    fmt = OutputFormat(args.fmt)

    catalog_path = catalog_directory(
        directory=args.directory,
        output=args.output,
        fmt=fmt,
        recursive=args.recursive,
        max_workers=args.workers,
    )

    from .cataloger import _find_fits_files

    files = _find_fits_files(args.directory, args.recursive)
    entries = [extract_metadata(f) for f in files]
    print(format_catalog_table(entries))
    print(f"\nCatalog written to: {catalog_path}")
    return 0


def _configure_logging(verbosity: int) -> None:
    """Set up logging based on CLI verbosity flags."""
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity >= 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    sys.exit(main())
