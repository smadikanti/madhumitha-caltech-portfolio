"""Tests for config diff engine."""

from __future__ import annotations

from config_shepherd.differ import diff_configs, format_diff
from config_shepherd.models import DiffOp


class TestDiffConfigs:
    def test_identical_configs(self) -> None:
        cfg = {"a": 1, "b": {"c": 2}}
        assert diff_configs(cfg, cfg) == []

    def test_added_key(self) -> None:
        left: dict = {}
        right = {"new_key": "value"}
        entries = diff_configs(left, right)
        assert len(entries) == 1
        assert entries[0].operation == DiffOp.ADDED
        assert entries[0].key_path == "new_key"
        assert entries[0].new_value == "value"

    def test_removed_key(self) -> None:
        left = {"old_key": "value"}
        right: dict = {}
        entries = diff_configs(left, right)
        assert len(entries) == 1
        assert entries[0].operation == DiffOp.REMOVED
        assert entries[0].old_value == "value"

    def test_changed_value(self) -> None:
        left = {"x": 1}
        right = {"x": 2}
        entries = diff_configs(left, right)
        assert len(entries) == 1
        assert entries[0].operation == DiffOp.CHANGED
        assert entries[0].old_value == 1
        assert entries[0].new_value == 2

    def test_nested_diff(self) -> None:
        left = {"db": {"host": "localhost", "port": 5432}}
        right = {"db": {"host": "prod-db", "port": 5432}}
        entries = diff_configs(left, right)
        assert len(entries) == 1
        assert entries[0].key_path == "db.host"
        assert entries[0].operation == DiffOp.CHANGED

    def test_deeply_nested_addition(self) -> None:
        left = {"a": {"b": {}}}
        right = {"a": {"b": {"c": "new"}}}
        entries = diff_configs(left, right)
        assert len(entries) == 1
        assert entries[0].key_path == "a.b.c"
        assert entries[0].operation == DiffOp.ADDED

    def test_mixed_operations(self) -> None:
        left = {"keep": 1, "remove": 2, "change": 3}
        right = {"keep": 1, "add": 4, "change": 99}
        entries = diff_configs(left, right)
        ops = {e.key_path: e.operation for e in entries}
        assert ops["add"] == DiffOp.ADDED
        assert ops["remove"] == DiffOp.REMOVED
        assert ops["change"] == DiffOp.CHANGED
        assert "keep" not in ops

    def test_both_empty(self) -> None:
        assert diff_configs({}, {}) == []

    def test_type_change_dict_to_scalar(self) -> None:
        left = {"x": {"nested": True}}
        right = {"x": "flat"}
        entries = diff_configs(left, right)
        assert len(entries) == 1
        assert entries[0].operation == DiffOp.CHANGED


class TestFormatDiff:
    def test_no_differences(self) -> None:
        output = format_diff([], "dev", "prod", color=False)
        assert "No differences" in output

    def test_colored_output_contains_ansi(self) -> None:
        entries = diff_configs({"a": 1}, {"a": 2})
        output = format_diff(entries, "dev", "prod", color=True)
        assert "\033[" in output

    def test_no_color_clean(self) -> None:
        entries = diff_configs({"a": 1}, {"a": 2})
        output = format_diff(entries, "dev", "prod", color=False)
        assert "\033[" not in output

    def test_summary_line(self) -> None:
        entries = diff_configs(
            {"a": 1, "b": 2},
            {"a": 99, "c": 3},
        )
        output = format_diff(entries, "left", "right", color=False)
        assert "1 added" in output
        assert "1 removed" in output
        assert "1 changed" in output

    def test_diff_entry_str(self) -> None:
        from config_shepherd.models import DiffEntry
        added = DiffEntry(key_path="x", operation=DiffOp.ADDED, new_value=1)
        assert "+ x:" in str(added)
        removed = DiffEntry(key_path="y", operation=DiffOp.REMOVED, old_value=2)
        assert "- y:" in str(removed)
        changed = DiffEntry(key_path="z", operation=DiffOp.CHANGED, old_value=1, new_value=2)
        assert "~" in str(changed)
        assert "→" in str(changed)
