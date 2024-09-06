"""CLI entry point for the stellar data pipeline.

Usage:
    python -m stellar_pipeline ingest [--limit N] [--dry-run] [--config PATH]
    python -m stellar_pipeline validate [--limit N] [--config PATH]
    python -m stellar_pipeline status [--last N] [--config PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stellar_pipeline import __version__
from stellar_pipeline.config import load_config
from stellar_pipeline.exceptions import ConfigError, LoadError, PipelineError
from stellar_pipeline.load import PostgreSQLLoader
from stellar_pipeline.logging_config import setup_logging
from stellar_pipeline.pipeline import Pipeline

DEFAULT_CONFIG = "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="stellar_pipeline",
        description="NASA Exoplanet Archive data ingestion pipeline",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Pipeline commands")

    ingest_parser = subparsers.add_parser("ingest", help="Run the full EVTL pipeline")
    ingest_parser.add_argument(
        "--limit", type=int, default=None, help="Max records to fetch from API"
    )
    ingest_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract, validate, and transform without loading to DB",
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Extract and validate only (no transform/load)"
    )
    validate_parser.add_argument(
        "--limit", type=int, default=None, help="Max records to fetch from API"
    )

    status_parser = subparsers.add_parser(
        "status", help="Show recent pipeline run history"
    )
    status_parser.add_argument(
        "--last", type=int, default=10, help="Number of recent runs to display"
    )

    return parser


def cmd_ingest(args: argparse.Namespace) -> int:
    """Execute the full ingestion pipeline."""
    config = load_config(args.config)
    setup_logging(config.pipeline.log_file, config.pipeline.log_level)

    pipeline = Pipeline(config)
    result = pipeline.run(limit=args.limit, dry_run=args.dry_run)

    print(f"\nPipeline run {result.run_id} completed")
    print(f"  Status:     {result.status}")
    print(f"  Extracted:  {result.records_extracted}")
    print(f"  Validated:  {result.records_validated}")
    print(f"  Failed:     {result.records_failed_validation}")
    print(f"  Transformed:{result.records_transformed}")
    print(f"  Loaded:     {result.records_loaded}")
    if result.duration_seconds is not None:
        print(f"  Duration:   {result.duration_seconds:.2f}s")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Run extraction and validation, reporting data quality."""
    config = load_config(args.config)
    setup_logging(config.pipeline.log_file, config.pipeline.log_level)

    pipeline = Pipeline(config)
    result, report = pipeline.validate_only(limit=args.limit)

    print(f"\nValidation run {result.run_id} completed")
    print(f"  Extracted: {result.records_extracted}")
    print(f"  Valid:     {report.valid_count}")
    print(f"  Invalid:   {report.invalid_count}")
    print(f"  Duplicates:{report.duplicate_count}")

    if report.invalid_records:
        print(f"\nSample invalid records (showing up to 5):")
        for record, reasons in report.invalid_records[:5]:
            name = record.pl_name or "<unnamed>"
            print(f"  {name}: {'; '.join(reasons)}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Display recent pipeline run history from the database."""
    config = load_config(args.config)
    setup_logging(config.pipeline.log_file, config.pipeline.log_level)

    loader = PostgreSQLLoader(config.database)
    runs = loader.get_recent_runs(count=args.last)

    if not runs:
        print("No pipeline runs found.")
        return 0

    print(f"\nRecent pipeline runs (last {len(runs)}):")
    print(f"{'Run ID':>36}  {'Status':<10} {'Extracted':>9} {'Loaded':>7} {'Started':>20}")
    print("-" * 90)

    for run in runs:
        run_id = str(run["run_id"])[:8] + "..."
        started = run["started_at"].strftime("%Y-%m-%d %H:%M:%S") if run["started_at"] else "N/A"
        print(
            f"{run_id:>36}  {run['status']:<10} "
            f"{run.get('records_extracted', 0):>9} "
            f"{run.get('records_loaded', 0):>7} "
            f"{started:>20}"
        )

    return 0


COMMANDS = {
    "ingest": cmd_ingest,
    "validate": cmd_validate,
    "status": cmd_status,
}


def main() -> int:
    """Parse arguments and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except LoadError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return 1
    except PipelineError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
