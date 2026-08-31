from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tutorial_harness.state import complete_task, new_state, ready_tasks, start_task
from tutorial_harness.tests.helpers import make_repo


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = make_repo(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_and_single_chapter_dags(self):
        full = new_state(self.root, "demo-tutorial")
        self.assertEqual(full["selected_chapters"], [1, 2])
        self.assertIn("write-ch01", [task["id"] for task in full["tasks"]])
        self.assertIn("write-ch02", [task["id"] for task in full["tasks"]])
        single = new_state(self.root, "demo-tutorial", [1])
        self.assertIn("roadmap", [task["id"] for task in single["tasks"]])
        self.assertIn("write-ch01", [task["id"] for task in single["tasks"]])
        self.assertNotIn("write-ch02", [task["id"] for task in single["tasks"]])

    def test_non_target_ready_chapter_is_immutable(self):
        state = new_state(self.root, "demo-tutorial", [1])
        start_task(state, "normalize-input", "architect-1")
        (self.base / "book/en/ch02.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-target ready chapters changed"):
            complete_task(self.root, state, "normalize-input")

    def test_reviewer_cannot_be_the_writer(self):
        state = new_state(self.root, "demo-tutorial", [1])
        for task in state["tasks"]:
            if task["id"] == "write-ch01":
                task["status"] = "completed"
                task["agent_ids"] = ["writer-1"]
            elif task["id"] == "verify-ch01":
                task["status"] = "completed"
        with self.assertRaisesRegex(ValueError, "independent"):
            start_task(state, "qa-ch01", "writer-1")

    def test_max_parallel_is_three(self):
        state = new_state(self.root, "demo-tutorial")
        for task in state["tasks"]:
            if task["id"] in {"normalize-input", "roadmap", "version-research"}:
                task["status"] = "completed"
        self.assertLessEqual(len(ready_tasks(state)), 3)


if __name__ == "__main__":
    unittest.main()
