from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from survey_harness.cli import main
from survey_harness.state import load_state, save_state
from survey_harness.tests.helpers import make_passing_mini


class CliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        make_passing_mini(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            rc = main(["--repo-root", str(self.root), *args])
        return rc, json.loads(output.getvalue())

    def test_init_score_and_release_lifecycle(self):
        rc, initialized = self.run_cli("init", "test-survey", "--profile", "mini")
        self.assertEqual(rc, 0)
        self.assertEqual(initialized["ready_tasks"], ["kg-seed"])

        state = load_state(self.root, "test-survey")
        for task in state["tasks"]:
            task["status"] = "completed"
            task["agent_ids"] = ["agent-reviewer-123" if task["owner"] == "qa_reviewer" else f"agent-{task['id']}"]
        save_state(self.root, state)

        rc, score = self.run_cli("score", "test-survey", "--profile", "mini", "--write", "--record")
        self.assertEqual(rc, 0, score.get("hard_blockers"))
        self.assertTrue(score["passed"])
        self.assertEqual(load_state(self.root, "test-survey")["status"], "ready")

        with redirect_stderr(StringIO()):
            self.assertEqual(main(["--repo-root", str(self.root), "release", "test-survey", "running"]), 1)

    def test_recorded_score_requires_written_scorecard(self):
        self.run_cli("init", "test-survey", "--profile", "mini")
        with redirect_stderr(StringIO()):
            rc = main(["--repo-root", str(self.root), "score", "test-survey", "--profile", "mini", "--record"])
        self.assertEqual(rc, 1)
        self.assertFalse((self.root / "surveys/test-survey/_quality/scorecard.json").exists())

    def test_release_reruns_quality_after_manuscript_changes(self):
        self.run_cli("init", "test-survey", "--profile", "mini")
        state = load_state(self.root, "test-survey")
        for task in state["tasks"]:
            task["status"] = "completed"
            task["agent_ids"] = ["agent-reviewer-123" if task["owner"] == "qa_reviewer" else f"agent-{task['id']}"]
        save_state(self.root, state)
        rc, score = self.run_cli("score", "test-survey", "--profile", "mini", "--write", "--record")
        self.assertEqual(rc, 0, score.get("hard_blockers"))
        chapter = self.root / "surveys/test-survey/book/en/ch01.md"
        chapter.write_text(chapter.read_text(encoding="utf-8").replace("<!-- claim:ch01-c01 -->", ""), encoding="utf-8")
        stderr = StringIO()
        with redirect_stderr(stderr):
            rc = main(["--repo-root", str(self.root), "release", "test-survey", "running"])
        self.assertEqual(rc, 1)
        self.assertIn("fresh quality evaluation failed", stderr.getvalue())

    def test_release_digest_detects_quality_equivalent_edits(self):
        self.run_cli("init", "test-survey", "--profile", "mini")
        state = load_state(self.root, "test-survey")
        for task in state["tasks"]:
            task["status"] = "completed"
            task["agent_ids"] = ["agent-reviewer-123" if task["owner"] == "qa_reviewer" else f"agent-{task['id']}"]
        save_state(self.root, state)
        rc, score = self.run_cli("score", "test-survey", "--profile", "mini", "--write", "--record")
        self.assertEqual(rc, 0, score.get("hard_blockers"))
        chapter = self.root / "surveys/test-survey/book/en/ch01.md"
        chapter.write_text(chapter.read_text(encoding="utf-8").replace("enanalysis699", "changedconcept699"), encoding="utf-8")
        stderr = StringIO()
        with redirect_stderr(stderr):
            rc = main(["--repo-root", str(self.root), "release", "test-survey", "running"])
        self.assertEqual(rc, 1)
        self.assertIn("manuscript changed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
