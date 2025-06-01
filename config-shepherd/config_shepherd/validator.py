"""JSON Schema-based configuration validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import jsonschema.validators

from config_shepherd.models import Severity, ValidationError


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load a JSON Schema file from disk."""
    with open(schema_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_config(
    config: dict[str, Any],
    schema: dict[str, Any],
) -> list[ValidationError]:
    """Validate *config* against *schema* and return all errors found.

    Uses ``jsonschema.Draft7Validator`` so that all errors are collected
    rather than failing on the first one.
    """
    validator_cls = jsonschema.validators.validator_for(schema, default=jsonschema.Draft7Validator)
    validator = validator_cls(schema)

    errors: list[ValidationError] = []
    for err in sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path)):
        json_path = ".".join(str(p) for p in err.absolute_path)
        schema_path = ".".join(str(p) for p in err.absolute_schema_path)
        errors.append(
            ValidationError(
                path=json_path,
                message=err.message,
                severity=Severity.ERROR,
                schema_path=schema_path,
            )
        )
    return errors


def validate_directory(
    config_dir: Path,
    schema_path: Path,
) -> dict[str, list[ValidationError]]:
    """Validate every resolved environment config in *config_dir*.

    Returns ``{env_name: [errors]}``. Environments with no errors still
    appear in the result with an empty list.
    """
    from config_shepherd.config_loader import load_all_environments

    schema = load_schema(schema_path)
    envs = load_all_environments(config_dir)

    results: dict[str, list[ValidationError]] = {}
    for env_name, config in envs.items():
        results[env_name] = validate_config(config, schema)
    return results
