"""Schema validation helpers for measurement_case outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@dataclass
class SchemaValidationResult:
    valid: bool
    errors: list[str]
    schema_path: str


def validate_measurement_case_schema(repo_root: Path, measurement_case: dict[str, Any]) -> SchemaValidationResult:
    """Validate a measurement_case payload against the project JSON schema."""
    schema_path = repo_root / "assets" / "schemas" / "measurement_case.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    errors: list[str] = []
    for err in sorted(validator.iter_errors(measurement_case), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "<root>"
        errors.append(f"{path}: {err.message}")

    return SchemaValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        schema_path=str(schema_path),
    )

