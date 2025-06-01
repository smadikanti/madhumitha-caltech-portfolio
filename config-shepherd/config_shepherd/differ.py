"""Configuration diff engine with colored terminal output."""

from __future__ import annotations

from typing import Any

from config_shepherd.models import DiffEntry, DiffOp


class _ANSI:
    """ANSI escape sequences for colored terminal output."""

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def diff_configs(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    _prefix: str = "",
) -> list[DiffEntry]:
    """Compute a flat list of differences between two nested dicts.

    Keys are represented as dot-separated paths (e.g. ``database.host``).
    """
    entries: list[DiffEntry] = []
    all_keys = sorted(set(left.keys()) | set(right.keys()))

    for key in all_keys:
        path = f"{_prefix}.{key}" if _prefix else key
        in_left = key in left
        in_right = key in right

        if in_left and not in_right:
            entries.append(DiffEntry(key_path=path, operation=DiffOp.REMOVED, old_value=left[key]))
        elif in_right and not in_left:
            entries.append(DiffEntry(key_path=path, operation=DiffOp.ADDED, new_value=right[key]))
        elif isinstance(left[key], dict) and isinstance(right[key], dict):
            entries.extend(diff_configs(left[key], right[key], _prefix=path))
        elif left[key] != right[key]:
            entries.append(
                DiffEntry(
                    key_path=path,
                    operation=DiffOp.CHANGED,
                    old_value=left[key],
                    new_value=right[key],
                )
            )

    return entries


def format_diff(
    entries: list[DiffEntry],
    left_name: str = "left",
    right_name: str = "right",
    *,
    color: bool = True,
) -> str:
    """Render a diff as a human-readable string with optional ANSI colors."""
    if not entries:
        return f"No differences between {left_name} and {right_name}."

    a = _ANSI if color else _NoColor
    lines: list[str] = [
        f"{a.BOLD}Comparing {left_name} ↔ {right_name}{a.RESET}",
        "",
    ]

    added = [e for e in entries if e.operation == DiffOp.ADDED]
    removed = [e for e in entries if e.operation == DiffOp.REMOVED]
    changed = [e for e in entries if e.operation == DiffOp.CHANGED]

    if added:
        lines.append(f"{a.GREEN}Added ({len(added)}):{a.RESET}")
        for e in added:
            lines.append(f"  {a.GREEN}+ {e.key_path}: {e.new_value!r}{a.RESET}")
        lines.append("")

    if removed:
        lines.append(f"{a.RED}Removed ({len(removed)}):{a.RESET}")
        for e in removed:
            lines.append(f"  {a.RED}- {e.key_path}: {e.old_value!r}{a.RESET}")
        lines.append("")

    if changed:
        lines.append(f"{a.YELLOW}Changed ({len(changed)}):{a.RESET}")
        for e in changed:
            lines.append(
                f"  {a.YELLOW}~ {e.key_path}:{a.RESET} "
                f"{a.RED}{e.old_value!r}{a.RESET} → {a.GREEN}{e.new_value!r}{a.RESET}"
            )
        lines.append("")

    summary = (
        f"{a.CYAN}Summary: "
        f"{len(added)} added, {len(removed)} removed, {len(changed)} changed"
        f"{a.RESET}"
    )
    lines.append(summary)
    return "\n".join(lines)


class _NoColor:
    """Drop-in replacement that emits no escape codes."""

    RED = ""
    GREEN = ""
    YELLOW = ""
    CYAN = ""
    BOLD = ""
    RESET = ""
