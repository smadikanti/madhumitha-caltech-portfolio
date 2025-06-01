"""YAML configuration loader with inheritance support.

Loads a hierarchy of YAML files (base → dev → staging → prod) and deep-merges
them so child configs override parent values at any nesting depth.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised for any configuration loading problem."""


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overlay* into a copy of *base*.

    - Dict values are merged recursively.
    - All other types in *overlay* replace the *base* value.
    - Keys present only in *base* are preserved.
    """
    merged = copy.deepcopy(base)
    for key, overlay_val in overlay.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(overlay_val, dict)
        ):
            merged[key] = deep_merge(merged[key], overlay_val)
        else:
            merged[key] = copy.deepcopy(overlay_val)
    return merged


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file and return its content as a dict.

    Returns an empty dict for empty files.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a YAML mapping at the top level, got {type(data).__name__}")
    return data


def resolve_inheritance(
    config_dir: Path,
    target: str,
    *,
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    """Load *target*.yaml from *config_dir*, resolving its ``inherits`` chain.

    Detects circular inheritance and raises ``ConfigError``.
    """
    if _seen is None:
        _seen = set()

    if target in _seen:
        chain = " → ".join(_seen) + f" → {target}"
        raise ConfigError(f"Circular inheritance detected: {chain}")
    _seen.add(target)

    path = config_dir / f"{target}.yaml"
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    data = load_yaml(path)
    parent_name = data.pop("inherits", None)

    if parent_name is None:
        return data

    parent = resolve_inheritance(config_dir, parent_name, _seen=_seen)
    return deep_merge(parent, data)


def load_all_environments(config_dir: Path) -> dict[str, dict[str, Any]]:
    """Load every YAML file in *config_dir* with inheritance resolved.

    Returns ``{env_name: merged_config}``.
    """
    config_dir = Path(config_dir)
    if not config_dir.is_dir():
        raise ConfigError(f"Not a directory: {config_dir}")

    envs: dict[str, dict[str, Any]] = {}
    for yaml_file in sorted(config_dir.glob("*.yaml")):
        env_name = yaml_file.stem
        envs[env_name] = resolve_inheritance(config_dir, env_name)
    return envs


def merge_configs(base_path: Path, overlay_path: Path) -> dict[str, Any]:
    """Load two standalone YAML files and deep-merge the overlay onto the base."""
    base = load_yaml(Path(base_path))
    overlay = load_yaml(Path(overlay_path))
    return deep_merge(base, overlay)
