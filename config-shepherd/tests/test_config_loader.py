"""Tests for config_loader — YAML loading and deep merge with inheritance."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from config_shepherd.config_loader import (
    ConfigError,
    deep_merge,
    load_all_environments,
    load_yaml,
    merge_configs,
    resolve_inheritance,
)


class TestDeepMerge:
    def test_flat_override(self) -> None:
        base = {"a": 1, "b": 2}
        overlay = {"b": 99}
        assert deep_merge(base, overlay) == {"a": 1, "b": 99}

    def test_nested_merge(self) -> None:
        base = {"db": {"host": "localhost", "port": 5432}}
        overlay = {"db": {"host": "prod-db"}}
        result = deep_merge(base, overlay)
        assert result == {"db": {"host": "prod-db", "port": 5432}}

    def test_overlay_adds_new_keys(self) -> None:
        base = {"a": 1}
        overlay = {"b": 2}
        assert deep_merge(base, overlay) == {"a": 1, "b": 2}

    def test_does_not_mutate_inputs(self) -> None:
        base = {"nested": {"x": 1}}
        overlay = {"nested": {"y": 2}}
        deep_merge(base, overlay)
        assert base == {"nested": {"x": 1}}
        assert overlay == {"nested": {"y": 2}}

    def test_overlay_replaces_non_dict_with_dict(self) -> None:
        base = {"a": "string"}
        overlay = {"a": {"nested": True}}
        assert deep_merge(base, overlay) == {"a": {"nested": True}}

    def test_overlay_replaces_dict_with_scalar(self) -> None:
        base = {"a": {"nested": True}}
        overlay = {"a": "flat"}
        assert deep_merge(base, overlay) == {"a": "flat"}

    def test_empty_overlay(self) -> None:
        base = {"a": 1, "b": 2}
        assert deep_merge(base, {}) == {"a": 1, "b": 2}

    def test_empty_base(self) -> None:
        overlay = {"x": 10}
        assert deep_merge({}, overlay) == {"x": 10}

    def test_deeply_nested(self) -> None:
        base = {"l1": {"l2": {"l3": {"val": "old", "keep": True}}}}
        overlay = {"l1": {"l2": {"l3": {"val": "new"}}}}
        result = deep_merge(base, overlay)
        assert result["l1"]["l2"]["l3"] == {"val": "new", "keep": True}


class TestLoadYaml:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump({"key": "value"}))
        assert load_yaml(f) == {"key": "value"}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("")
        assert load_yaml(f) == {}

    def test_non_dict_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n")
        with pytest.raises(ConfigError, match="expected a YAML mapping"):
            load_yaml(f)


class TestResolveInheritance:
    def test_base_no_parent(self, tmp_config_dir: Path) -> None:
        cfg = resolve_inheritance(tmp_config_dir, "base")
        assert cfg["app"]["name"] == "test-app"
        assert "inherits" not in cfg

    def test_dev_inherits_base(self, tmp_config_dir: Path) -> None:
        cfg = resolve_inheritance(tmp_config_dir, "dev")
        assert cfg["app"]["debug"] is True
        assert cfg["app"]["name"] == "test-app"
        assert cfg["database"]["pool_size"] == 2
        assert cfg["database"]["host"] == "localhost"

    def test_prod_inherits_chain(self, tmp_config_dir: Path) -> None:
        cfg = resolve_inheritance(tmp_config_dir, "prod")
        assert cfg["app"]["debug"] is True  # from dev
        assert cfg["app"]["log_level"] == "WARNING"  # from prod
        assert cfg["database"]["host"] == "prod-db.internal"
        assert cfg["database"]["port"] == 5432  # from base

    def test_circular_inheritance_raises(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(yaml.dump({"inherits": "b", "x": 1}))
        (tmp_path / "b.yaml").write_text(yaml.dump({"inherits": "a", "y": 2}))
        with pytest.raises(ConfigError, match="Circular inheritance"):
            resolve_inheritance(tmp_path, "a")

    def test_missing_parent_raises(self, tmp_path: Path) -> None:
        (tmp_path / "child.yaml").write_text(yaml.dump({"inherits": "nonexistent"}))
        with pytest.raises(ConfigError, match="Config file not found"):
            resolve_inheritance(tmp_path, "child")

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Config file not found"):
            resolve_inheritance(tmp_path, "nope")


class TestLoadAllEnvironments:
    def test_loads_all_yamls(self, tmp_config_dir: Path) -> None:
        envs = load_all_environments(tmp_config_dir)
        assert set(envs.keys()) == {"base", "dev", "prod"}

    def test_each_env_is_resolved(self, tmp_config_dir: Path) -> None:
        envs = load_all_environments(tmp_config_dir)
        assert envs["prod"]["database"]["host"] == "prod-db.internal"
        assert envs["base"]["database"]["host"] == "localhost"

    def test_invalid_dir_raises(self) -> None:
        with pytest.raises(ConfigError, match="Not a directory"):
            load_all_environments(Path("/nonexistent/dir"))


class TestMergeConfigs:
    def test_merges_two_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(yaml.dump({"x": 1, "y": {"z": 2}}))
        (tmp_path / "b.yaml").write_text(yaml.dump({"y": {"z": 99, "w": 3}}))
        result = merge_configs(tmp_path / "a.yaml", tmp_path / "b.yaml")
        assert result == {"x": 1, "y": {"z": 99, "w": 3}}
