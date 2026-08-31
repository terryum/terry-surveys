from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shared.validate import Issues, check_chapters, check_survey_json, check_tutorial_artifacts
from tutorial_harness.tests.helpers import make_repo


class ValidatorTests(unittest.TestCase):
    def test_planned_markdown_is_optional_but_ready_markdown_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_repo(Path(tmp), chapters=((1, "planned"), (3, "ready")))
            for lang in ("ko", "en"):
                (base / f"book/{lang}/ch03.md").unlink()
            issues = Issues()
            metadata = check_survey_json(str(base), issues)
            self.assertEqual(metadata["chapter_nums"], [3])
            self.assertEqual(metadata["all_chapter_nums"], [1, 3])
            check_chapters(str(base), metadata["chapter_nums"], issues, metadata["all_chapter_nums"])
            self.assertTrue(any("ch03.md missing" in error for error in issues.errors))
            self.assertFalse(any("ch01.md missing" in error for error in issues.errors))

    def test_tutorial_number_and_status_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_repo(Path(tmp), chapters=((1, "planned"),))
            config_path = base / "survey.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["tutorial_number"] = "T1"
            config["status"] = "active"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            issues = Issues()
            check_survey_json(str(base), issues)
            self.assertTrue(any("positive integer tutorial_number" in error for error in issues.errors))
            self.assertTrue(any("status must be wip" in error for error in issues.errors))

    def test_ready_tutorial_tracking_artifacts_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = make_repo(Path(tmp), chapters=((2, "ready"),))
            issues = Issues()
            check_tutorial_artifacts(str(base), [2], issues)
            self.assertTrue(any("chapter_packets/ch02.json" in error for error in issues.errors))
            self.assertTrue(any("labs/ch02/manifest.json" in error for error in issues.errors))


if __name__ == "__main__":
    unittest.main()
