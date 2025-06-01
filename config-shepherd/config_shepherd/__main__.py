"""CLI entry point for config-shepherd.

Usage:
    python -m config_shepherd <command> [options]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config_shepherd import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="config-shepherd",
        description="Configuration management tool for multi-environment deployments.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate configs against a JSON Schema")
    p_val.add_argument("config_dir", type=Path, help="Directory containing YAML configs")
    p_val.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/app_config.schema.json"),
        help="Path to JSON Schema file",
    )

    # diff
    p_diff = sub.add_parser("diff", help="Compare two environment configs")
    p_diff.add_argument("env1", help="First environment name (e.g. dev)")
    p_diff.add_argument("env2", help="Second environment name (e.g. prod)")
    p_diff.add_argument("--config-dir", type=Path, default=Path("examples"), help="Config directory")
    p_diff.add_argument("--no-color", action="store_true", help="Disable colored output")

    # scan
    p_scan = sub.add_parser("scan", help="Scan files for secrets")
    p_scan.add_argument("path", type=Path, help="File or directory to scan")
    p_scan.add_argument("--recursive", action="store_true", default=True, help="Recurse into subdirectories")

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Capture current environment state")
    p_snap.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("snapshot.yaml"),
        help="Output file path",
    )
    p_snap.add_argument("--no-env", action="store_true", help="Exclude environment variables")

    # inventory
    p_inv = sub.add_parser("inventory", help="Show software inventory across environments")
    p_inv.add_argument("config_dir", type=Path, help="Directory containing YAML configs")

    # merge
    p_merge = sub.add_parser("merge", help="Merge two config files (base + overlay)")
    p_merge.add_argument("base", type=Path, help="Base config file")
    p_merge.add_argument("overlay", type=Path, help="Overlay config file")

    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    from config_shepherd.validator import validate_directory

    results = validate_directory(args.config_dir, args.schema)
    has_errors = False
    for env_name, errors in sorted(results.items()):
        if errors:
            has_errors = True
            print(f"\n✗ {env_name}:")
            for err in errors:
                print(f"  {err}")
        else:
            print(f"✓ {env_name}: valid")
    return 1 if has_errors else 0


def cmd_diff(args: argparse.Namespace) -> int:
    from config_shepherd.config_loader import resolve_inheritance
    from config_shepherd.differ import diff_configs, format_diff

    left = resolve_inheritance(args.config_dir, args.env1)
    right = resolve_inheritance(args.config_dir, args.env2)
    entries = diff_configs(left, right)
    print(format_diff(entries, args.env1, args.env2, color=not args.no_color))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    from config_shepherd.secret_scanner import SecretScanner

    scanner = SecretScanner()
    path: Path = args.path
    if path.is_dir():
        findings = scanner.scan_directory(path, recursive=args.recursive)
    else:
        findings = scanner.scan_file(path)

    if not findings:
        print("No secrets detected.")
        return 0

    for finding in findings:
        print(finding)
    print(f"\n{len(findings)} potential secret(s) found.")
    return 1


def cmd_snapshot(args: argparse.Namespace) -> int:
    from config_shepherd.snapshot import capture_snapshot, save_snapshot

    snap = capture_snapshot(include_env=not args.no_env)
    dest = save_snapshot(snap, args.output)
    print(f"Snapshot saved to {dest}")
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    from config_shepherd.inventory import format_inventory_table, load_inventories

    inventories = load_inventories(args.config_dir)
    print(format_inventory_table(inventories))
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    import yaml

    from config_shepherd.config_loader import merge_configs

    merged = merge_configs(args.base, args.overlay)
    print(yaml.dump(merged, default_flow_style=False, sort_keys=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "validate": cmd_validate,
        "diff": cmd_diff,
        "scan": cmd_scan,
        "snapshot": cmd_snapshot,
        "inventory": cmd_inventory,
        "merge": cmd_merge,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
