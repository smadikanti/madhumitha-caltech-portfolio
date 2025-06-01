"""Software inventory tracking across environments.

Reads ``software`` sections from environment configs and compares package
versions to surface drift between environments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config_shepherd.config_loader import load_all_environments
from config_shepherd.models import SoftwareInventory


def extract_inventory(env_name: str, config: dict[str, Any]) -> SoftwareInventory:
    """Pull software inventory fields from a resolved config."""
    sw = config.get("software", {})
    return SoftwareInventory(
        environment=env_name,
        packages=sw.get("packages", {}),
        system_packages=sw.get("system_packages", {}),
        os_version=sw.get("os_version", ""),
        python_version=sw.get("python_version", ""),
    )


def load_inventories(config_dir: Path) -> list[SoftwareInventory]:
    """Load all environment configs and extract their software inventories."""
    envs = load_all_environments(config_dir)
    return [extract_inventory(name, cfg) for name, cfg in sorted(envs.items())]


def build_version_matrix(inventories: list[SoftwareInventory]) -> dict[str, dict[str, str]]:
    """Build a ``{package_name: {env: version}}`` matrix from all inventories.

    Merges both pip packages and system packages.
    """
    matrix: dict[str, dict[str, str]] = {}
    for inv in inventories:
        for pkg, ver in {**inv.packages, **inv.system_packages}.items():
            matrix.setdefault(pkg, {})[inv.environment] = ver
    return matrix


def detect_drift(inventories: list[SoftwareInventory]) -> dict[str, dict[str, str]]:
    """Return only packages whose version differs across environments.

    A package counts as drifted if its version varies or if it's absent
    from at least one environment that declares any software inventory.
    """
    matrix = build_version_matrix(inventories)
    all_envs = {inv.environment for inv in inventories}
    return {
        pkg: versions
        for pkg, versions in matrix.items()
        if len(set(versions.values())) > 1 or set(versions.keys()) != all_envs
    }


def format_inventory_table(inventories: list[SoftwareInventory]) -> str:
    """Render a human-readable table of all inventories."""
    if not inventories:
        return "No environments found."

    matrix = build_version_matrix(inventories)
    env_names = [inv.environment for inv in inventories]

    pkg_col_width = max((len(p) for p in matrix), default=7)
    pkg_col_width = max(pkg_col_width, 7)
    ver_col_width = 14

    header = f"{'Package':<{pkg_col_width}}"
    for env in env_names:
        header += f"  {env:<{ver_col_width}}"
    sep = "-" * len(header)

    lines = [header, sep]
    drift = detect_drift(inventories)
    for pkg in sorted(matrix):
        row = f"{pkg:<{pkg_col_width}}"
        for env in env_names:
            ver = matrix[pkg].get(env, "-")
            row += f"  {ver:<{ver_col_width}}"
        if pkg in drift:
            row += "  ← DRIFT"
        lines.append(row)

    os_lines: list[str] = []
    for inv in inventories:
        if inv.os_version or inv.python_version:
            os_lines.append(
                f"  {inv.environment}: OS={inv.os_version or '?'}, "
                f"Python={inv.python_version or '?'}"
            )
    if os_lines:
        lines.append("")
        lines.append("Runtime versions:")
        lines.extend(os_lines)

    return "\n".join(lines)
