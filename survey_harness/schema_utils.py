"""Validate bundled artifact schemas with a dependency-light fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

SCHEMA_DIR = Path(__file__).parent / "schemas"


def validate_schema(instance: Any, schema_name: str) -> List[str]:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except ImportError:  # pragma: no cover
        if not isinstance(instance, dict):
            return ["expected object"]
        return [f"missing required property: {field}" for field in schema.get("required", []) if field not in instance]
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in sorted(validator.iter_errors(instance), key=lambda item: "/".join(str(part) for part in item.absolute_path))]
