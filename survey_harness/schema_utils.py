"""Validate bundled artifact schemas with a dependency-light fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List

SCHEMA_DIR = Path(__file__).parent / "schemas"


def validate_schema(instance: Any, schema_name: str) -> List[str]:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except ImportError:  # pragma: no cover
        return _validate_without_dependency(instance, schema)
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in sorted(validator.iter_errors(instance), key=lambda item: "/".join(str(part) for part in item.absolute_path))]


def _validate_without_dependency(instance: Any, schema: dict, path: str = "<root>") -> List[str]:
    """Validate the schema keywords used by the bundled survey contracts.

    GitHub Actions intentionally runs the harness without optional Python
    packages, so the fallback must reject malformed nested rows as well as
    missing top-level fields.
    """
    errors: List[str] = []
    expected = schema.get("type")
    type_checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "null": lambda value: value is None,
    }
    if expected in type_checks and not type_checks[expected](instance):
        return [f"{path}: expected {expected}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if schema.get("pattern") and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: string does not match pattern")
    if isinstance(instance, dict):
        for field in schema.get("required", []):
            if field not in instance:
                errors.append(f"{path}: missing required property: {field}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties")
        property_names = schema.get("propertyNames", {})
        for key, value in instance.items():
            child_path = f"{path}/{key}"
            if property_names.get("pattern") and re.search(property_names["pattern"], str(key)) is None:
                errors.append(f"{child_path}: property name does not match pattern")
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                errors.extend(_validate_without_dependency(value, child_schema, child_path))
    if isinstance(instance, list) and isinstance(schema.get("items"), dict):
        for index, value in enumerate(instance):
            errors.extend(_validate_without_dependency(value, schema["items"], f"{path}/{index}"))
    for conditional in schema.get("allOf", []):
        condition = conditional.get("if", {})
        if not _validate_without_dependency(instance, condition, path):
            errors.extend(_validate_without_dependency(instance, conditional.get("then", {}), path))
    return errors
