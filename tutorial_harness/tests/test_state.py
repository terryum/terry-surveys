from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from tutorial_harness.state import complete_task, new_state, ready_tasks, resume_state, save_state, start_task
from tutorial_harness.tests.helpers import make_passing_content, make_repo, write_json


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

    def complete_fixture(self):
        config = json.loads((self.base / "survey.json").read_text())
        config["status"] = "active"
        for part in config["parts"]:
            for chapter in part["chapters"]:
                chapter["status"] = "ready"
                make_passing_content(self.base, chapter["num"])
        write_json(self.base / "survey.json", config)
        (self.base / "_workspace/inputs/input_manifest.md").write_text("Authoring contract; imported material is briefing-only.\n")
        (self.base / "_tutorial/roadmap.md").write_text("Audience: engineers. Final goal: run demo. First success: see ok.\n")
        (self.base / "_tutorial/source_ledger.jsonl").write_text("\n".join(json.dumps({"chapter": ch, "official": True, "url": f"https://example.com/ch{ch}"}) for ch in (1, 2)) + "\n")
        state = new_state(self.root, "demo-tutorial")
        for task in state["tasks"]:
            if task["phase"] == "release":
                continue
            start_task(state, task["id"], f"agent-{task['id']}")
            complete_task(self.root, state, task["id"])
        return state

    def test_resume_reuses_unchanged_work_and_archives_previous_state(self):
        state = self.complete_fixture()
        save_state(self.root, state)
        self.assertEqual(resume_state(self.root, state), [])
        self.assertEqual(len(list((self.base / "_workspace/state_history").glob("*.json"))), 1)

    def test_chapter_input_change_reopens_only_consumer_and_descendants(self):
        state = self.complete_fixture()
        packet = self.base / "_tutorial/chapter_packets/ch01.json"
        data = json.loads(packet.read_text())
        data["first_action"] = "run corrected demo"
        write_json(packet, data)
        reopened = resume_state(self.root, state)
        self.assertEqual(set(reopened), {"lab-ch01", "write-ch01", "verify-ch01", "qa-ch01"})
        self.assertEqual(next(task for task in state["tasks"] if task["id"] == "qa-ch02")["status"], "completed")

    def test_changed_shared_chapter_ledger_reopens_affected_research_descendants(self):
        # The global producer must revalidate the ledger, while chapter-scoped
        # snapshots independently prove unrelated chapter consumers unchanged.
        state = self.complete_fixture()
        ledger = self.base / "_tutorial/source_ledger.jsonl"
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        rows[0]["url"] = "https://example.com/revised"
        ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        from harness_runtime import revalidate_inputs
        chapter_two = next(task for task in state["tasks"] if task["id"] == "write-ch02")
        self.assertEqual(revalidate_inputs({"repo": self.root, "content": self.base}, chapter_two["input_snapshot"]), [])

    def test_skill_change_invalidates_prior_completed_work(self):
        state = self.complete_fixture()
        skill = self.root / ".codex/skills/tutorial/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("Updated authoring contract")
        reopened = resume_state(self.root, state)
        self.assertIn("normalize-input", reopened)
        self.assertIn("qa-ch02", reopened)

    def test_legacy_completion_requires_fingerprints_and_identity(self):
        state = self.complete_fixture()
        state["schema_version"] = "1.0"
        for task in state["tasks"]:
            task.pop("input_snapshot", None)
            task.pop("output_snapshot", None)
        reopened = resume_state(self.root, state)
        self.assertIn("normalize-input", reopened)
        self.assertEqual(state["schema_version"], "2.1")
        self.assertIn("unverified input snapshot", state["tasks"][0]["reopened_reason"])

    def test_changed_read_only_input_is_rejected_at_completion(self):
        state = new_state(self.root, "demo-tutorial")
        source = self.base / "_workspace/inputs/source.md"
        source.write_text("original")
        start_task(state, "normalize-input", "agent-normalizer")
        source.write_text("changed mid-run")
        (self.base / "_workspace/inputs/input_manifest.md").write_text("Authoring contract; briefing-only.")
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            complete_task(self.root, state, "normalize-input")

    def test_shared_config_ownership_serializes_chapter_writers(self):
        state = self.complete_fixture()
        for task in state["tasks"]:
            if task["phase"] in {"write", "verify", "qa"}:
                task["status"] = "pending"
        self.assertEqual([task["id"] for task in ready_tasks(state)], ["write-ch01"])
        start_task(state, "write-ch01", "writer-one")
        with self.assertRaisesRegex(ValueError, "not ready"):
            start_task(state, "write-ch02", "writer-two")

    def test_completion_requires_recorded_active_agent(self):
        state = new_state(self.root, "demo-tutorial")
        task = state["tasks"][0]
        task["status"] = "running"
        with self.assertRaisesRegex(ValueError, "active agent identity"):
            complete_task(self.root, state, task["id"])

    def test_existing_artifacts_cannot_authorize_unverified_dependencies(self):
        state = new_state(self.root, "demo-tutorial")
        state["tasks"][0]["status"] = "completed"
        with self.assertRaisesRegex(ValueError, "stale or unverified"):
            start_task(state, "roadmap", "architect-two")

    def test_authorized_readiness_updates_preserve_completed_research(self):
        state = self.complete_fixture()
        for task in state["tasks"]:
            if task["id"] in {"write-ch01", "verify-ch01", "qa-ch01"}:
                task["status"] = "pending"
        config_path = self.base / "survey.json"
        data = json.loads(config_path.read_text())
        data["parts"][0]["chapters"][0]["status"] = "planned"
        data["status"] = "wip"
        write_json(config_path, data)
        start_task(state, "write-ch01", "writer-corrected")
        data["parts"][0]["chapters"][0]["status"] = "ready"
        data["status"] = "active"
        write_json(config_path, data)
        complete_task(self.root, state, "write-ch01")
        self.assertEqual(resume_state(self.root, state), [])


if __name__ == "__main__":
    unittest.main()
