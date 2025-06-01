"""Environment snapshot — captures installed packages, OS info, and env vars."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from config_shepherd.models import EnvironmentSnapshot, PackageInfo

SAFE_ENV_PREFIXES = ("PATH", "HOME", "USER", "SHELL", "LANG", "LC_", "TERM", "EDITOR")


def capture_snapshot(*, include_env: bool = True) -> EnvironmentSnapshot:
    """Capture the current machine state."""
    return EnvironmentSnapshot(
        hostname=platform.node(),
        os_name=platform.system(),
        os_version=platform.release(),
        python_version=platform.python_version(),
        packages=_pip_packages(),
        env_vars=_safe_env_vars() if include_env else {},
    )


def save_snapshot(snapshot: EnvironmentSnapshot, dest: Path) -> Path:
    """Write a snapshot to a YAML file and return the path."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        yaml.dump(snapshot.to_dict(), fh, default_flow_style=False, sort_keys=False)
    return dest


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load a snapshot YAML back as a plain dict."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _pip_packages() -> list[PackageInfo]:
    """List packages installed in the current Python environment."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        import json
        packages = json.loads(result.stdout)
        return [
            PackageInfo(name=p["name"], version=p["version"], source="pip")
            for p in packages
        ]
    except (subprocess.SubprocessError, ValueError, KeyError):
        return []


def _safe_env_vars() -> dict[str, str]:
    """Return environment variables that are safe to record (no secrets)."""
    return {
        key: val
        for key, val in sorted(os.environ.items())
        if any(key.startswith(prefix) for prefix in SAFE_ENV_PREFIXES)
    }
