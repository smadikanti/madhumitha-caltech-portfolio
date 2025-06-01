"""Tests for software inventory tracking and drift detection."""

from __future__ import annotations

from pathlib import Path

import yaml

from config_shepherd.inventory import (
    build_version_matrix,
    detect_drift,
    extract_inventory,
    format_inventory_table,
    load_inventories,
)
from config_shepherd.models import SoftwareInventory


class TestExtractInventory:
    def test_extracts_packages(self) -> None:
        config = {
            "software": {
                "os_version": "Ubuntu 22.04",
                "python_version": "3.11.7",
                "packages": {"fastapi": "0.109.0", "numpy": "1.26.3"},
                "system_packages": {"postgresql": "15.5"},
            }
        }
        inv = extract_inventory("dev", config)
        assert inv.environment == "dev"
        assert inv.packages == {"fastapi": "0.109.0", "numpy": "1.26.3"}
        assert inv.system_packages == {"postgresql": "15.5"}
        assert inv.os_version == "Ubuntu 22.04"
        assert inv.python_version == "3.11.7"

    def test_missing_software_section(self) -> None:
        inv = extract_inventory("bare", {"app": {"name": "x"}})
        assert inv.packages == {}
        assert inv.system_packages == {}
        assert inv.os_version == ""

    def test_partial_software_section(self) -> None:
        config = {"software": {"packages": {"flask": "3.0.0"}}}
        inv = extract_inventory("test", config)
        assert inv.packages == {"flask": "3.0.0"}
        assert inv.system_packages == {}


class TestBuildVersionMatrix:
    def test_matrix_structure(self) -> None:
        invs = [
            SoftwareInventory(environment="dev", packages={"fastapi": "0.109.0"}),
            SoftwareInventory(environment="prod", packages={"fastapi": "0.109.2"}),
        ]
        matrix = build_version_matrix(invs)
        assert matrix == {"fastapi": {"dev": "0.109.0", "prod": "0.109.2"}}

    def test_includes_system_packages(self) -> None:
        invs = [
            SoftwareInventory(environment="dev", system_packages={"pg": "15.5"}),
        ]
        matrix = build_version_matrix(invs)
        assert "pg" in matrix

    def test_empty_inventories(self) -> None:
        assert build_version_matrix([]) == {}


class TestDetectDrift:
    def test_detects_version_difference(self) -> None:
        invs = [
            SoftwareInventory(environment="dev", packages={"numpy": "1.26.3"}),
            SoftwareInventory(environment="prod", packages={"numpy": "1.26.4"}),
        ]
        drift = detect_drift(invs)
        assert "numpy" in drift

    def test_no_drift_when_versions_match(self) -> None:
        invs = [
            SoftwareInventory(environment="dev", packages={"numpy": "1.26.3"}),
            SoftwareInventory(environment="prod", packages={"numpy": "1.26.3"}),
        ]
        drift = detect_drift(invs)
        assert drift == {}

    def test_missing_in_one_env_counts_as_drift(self) -> None:
        invs = [
            SoftwareInventory(environment="dev", packages={"extra": "1.0"}),
            SoftwareInventory(environment="prod", packages={}),
        ]
        drift = detect_drift(invs)
        assert "extra" in drift


class TestFormatInventoryTable:
    def test_empty_inventories(self) -> None:
        assert format_inventory_table([]) == "No environments found."

    def test_table_contains_env_names(self) -> None:
        invs = [
            SoftwareInventory(environment="dev", packages={"fastapi": "0.109.0"}),
            SoftwareInventory(environment="prod", packages={"fastapi": "0.109.2"}),
        ]
        table = format_inventory_table(invs)
        assert "dev" in table
        assert "prod" in table
        assert "fastapi" in table
        assert "DRIFT" in table

    def test_table_shows_runtime(self) -> None:
        invs = [
            SoftwareInventory(
                environment="dev",
                os_version="Ubuntu 22.04",
                python_version="3.11.7",
                packages={"x": "1"},
            ),
        ]
        table = format_inventory_table(invs)
        assert "Ubuntu 22.04" in table
        assert "3.11.7" in table


class TestLoadInventories:
    def test_loads_from_config_dir(self, tmp_config_dir: Path) -> None:
        inventories = load_inventories(tmp_config_dir)
        assert len(inventories) == 3
        env_names = {inv.environment for inv in inventories}
        assert env_names == {"base", "dev", "prod"}
