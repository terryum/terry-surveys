from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tutorial_harness.quality import evaluate
from tutorial_harness.tests.helpers import make_passing_content, make_repo, write_json


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = make_repo(self.root, chapters=((2, "ready"),))
        make_passing_content(self.base, 2)

    def tearDown(self):
        self.temp.cleanup()

    def test_passing_action_first_chapter(self):
        result = evaluate(self.base)
        self.assertTrue(result["passed"], result["hard_blockers"])

    def test_long_policy_intro_fails(self):
        path = self.base / "book/en/ch02.md"
        path.write_text(" ".join(f"policy{i}" for i in range(230)) + "\n\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        ids = {item["id"] for item in evaluate(self.base)["hard_blockers"]}
        self.assertIn("first-action-en-ch02", ids)

    def test_missing_expected_output_fails(self):
        path = self.base / "book/en/ch02.md"
        path.write_text(path.read_text(encoding="utf-8").replace("**Expected**", "**Observation**"), encoding="utf-8")
        ids = {item["id"] for item in evaluate(self.base)["hard_blockers"]}
        self.assertIn("step-triad-en-ch02", ids)

    def test_reader_test_required_is_allowed_but_false_tested_claim_is_not(self):
        verification = self.base / "_quality/example_verification/ch02.json"
        write_json(verification, {"checks": [{"name": "robot", "status": "reader_test_required"}], "broken_links": []})
        self.assertTrue(evaluate(self.base)["passed"])
        en = self.base / "book/en/ch02.md"
        en.write_text(en.read_text(encoding="utf-8") + "\nFully tested on the robot.\n", encoding="utf-8")
        ids = {item["id"] for item in evaluate(self.base)["hard_blockers"]}
        self.assertIn("false-tested-claim-ch02", ids)

    def test_broken_official_link_fails(self):
        write_json(self.base / "_quality/example_verification/ch02.json", {"checks": [{"name": "links", "status": "checked"}], "broken_links": ["https://example.com/official"]})
        ids = {item["id"] for item in evaluate(self.base)["hard_blockers"]}
        self.assertIn("broken-links-ch02", ids)


if __name__ == "__main__":
    unittest.main()
