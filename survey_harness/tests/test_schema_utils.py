from __future__ import annotations

import builtins
import unittest
from unittest.mock import patch

from survey_harness.schema_utils import validate_schema


class SchemaFallbackTests(unittest.TestCase):
    def test_dependency_free_validator_checks_nested_and_union_types(self):
        real_import = builtins.__import__

        def import_without_jsonschema(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("simulated dependency-free environment")
            return real_import(name, *args, **kwargs)

        invalid = {
            "schema_version": "2.0",
            "survey": "fixture",
            "chapters": {
                "ch01": [{
                    "figure_id": None,
                    "path": None,
                    "insertion_anchor": "after paragraph",
                    "source_type": "author_created",
                    "license_basis": "author-created",
                    "status": "inserted",
                }]
            },
        }
        with patch("builtins.__import__", side_effect=import_without_jsonschema):
            errors = validate_schema(invalid, "image-plan.schema.json")
        self.assertTrue(any("figure_id" in error for error in errors), errors)
        self.assertTrue(any("/path" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
