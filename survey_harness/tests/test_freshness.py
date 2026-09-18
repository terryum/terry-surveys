from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from survey_harness.state import (
    block_task, build_tasks, complete_task, completed_task_errors, new_state, plan_remediation,
    ready_tasks, resume_state, save_state, start_task,
)
from survey_harness.tests.helpers import make_passing_mini, write_current_reviews


class SurveyFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = make_passing_mini(self.root)
        self.state = new_state(self.root, "test-survey", "mini")

    def task(self, key):
        return next(task for task in self.state["tasks"] if task["id"] == key)

    def until(self, target=None):
        while ready_tasks(self.state):
            task = ready_tasks(self.state)[0]
            if task["id"] == target:
                return
            agent = "agent-reviewer-123" if task["owner"] == "qa_reviewer" else f"fixture-{task['id']}"
            start_task(self.state, task["id"], agent)
            complete_task(self.root, self.state, task["id"])

    def test_first_chapter_acceptance_gates_later_writers(self):
        tasks = {task["id"]: task for task in build_tasks([1, 2])}
        self.assertIn("critical-analysis", tasks["editorial-contract"]["dependencies"])
        self.assertIn("editorial-contract", tasks["evidence-synthesis"]["dependencies"])
        self.assertIn("packet-ch02", tasks["write-ch02"]["dependencies"])
        self.assertEqual(tasks["write-ch02"]["acceptance_dependencies"], ["qa-ch01"])
        self.assertEqual(tasks["qa-ch01"]["artifacts"], ["_quality/chapters/ch01.json"])
        self.assertNotEqual(tasks["qa-ch01"]["artifacts"], tasks["qa-ch02"]["artifacts"])

    def test_unchanged_resume_reuses_all_completed_results_and_archives(self):
        self.until()
        self.assertEqual(completed_task_errors(self.root, self.state), {})
        previous = self.state["run_id"]
        self.assertEqual(resume_state(self.root, self.state), {})
        self.assertTrue(all(task["status"] == "completed" for task in self.state["tasks"]))
        self.assertEqual(self.state["parent_run_id"], previous)
        self.assertTrue((self.base / f"_workspace/runs/{previous}-r0.json").is_file())

    def test_packet_edit_reopens_its_consumers_but_reuses_research(self):
        self.until()
        packet = self.base / "_analysis/chapter_source_packets/ch01.json"
        packet.write_text(packet.read_text().replace("specific chapter thesis", "corrected chapter thesis"))
        errors = resume_state(self.root, self.state)
        self.assertIn("packet-ch01", errors)
        self.assertEqual(self.task("write-ch01")["status"], "pending")
        self.assertEqual(self.task("qa-ch01")["status"], "pending")
        self.assertEqual(self.task("evidence-synthesis")["status"], "completed")
        self.assertEqual(self.task("research-frontier")["status"], "completed")

    def test_mutated_read_only_input_cannot_complete_running_writer(self):
        self.until("write-ch01")
        start_task(self.state, "write-ch01", "fixture-writer")
        contract = self.base / "_analysis/editorial_contract.md"
        contract.write_text(contract.read_text() + "Changed intended audience.")
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            complete_task(self.root, self.state, "write-ch01")

    def test_changed_transitive_ancestor_requires_resume_before_start(self):
        self.until("write-ch01")
        protocol = self.base / "_research/search_protocol.md"
        protocol.write_text(protocol.read_text() + "Changed inclusion criteria.")
        with self.assertRaisesRegex(ValueError, "stale or unverified"):
            start_task(self.state, "write-ch01", "fixture-writer")

    def test_metadata_timestamp_is_not_a_new_editorial_contract(self):
        self.until("write-ch01")
        path = self.base / "survey.json"
        metadata = json.loads(path.read_text())
        metadata["last_updated"] = "2026-09-18"
        path.write_text(json.dumps(metadata))
        self.assertEqual(completed_task_errors(self.root, self.state), {})
        metadata["audience"] = "Changed intended reader"
        path.write_text(json.dumps(metadata))
        self.assertIn("editorial-contract", completed_task_errors(self.root, self.state))

    def test_changed_skill_invalidates_consumer_without_research_rerun(self):
        self.until()
        role = self.root / ".codex/skills/survey/references/agent-template/book-writer.md"
        role.parent.mkdir(parents=True)
        role.write_text("Changed writer instructions.")
        errors = resume_state(self.root, self.state)
        self.assertIn("write-ch01", errors)
        self.assertEqual(self.task("critical-analysis")["status"], "completed")

    def test_authorized_image_edit_preserves_writer_completion(self):
        self.until("image-ch01")
        start_task(self.state, "image-ch01", "fixture-image")
        chapter = self.base / "book/en/ch01.md"
        chapter.write_text(chapter.read_text().replace("![first]", "![First source figure]"))
        complete_task(self.root, self.state, "image-ch01")
        self.assertNotIn("write-ch01", completed_task_errors(self.root, self.state))
        self.assertEqual(self.task("write-ch01")["artifact_successors"], ["image-ch01"])

    def test_external_edit_before_handoff_is_not_blessed(self):
        self.until("image-ch01")
        chapter = self.base / "book/en/ch01.md"
        chapter.write_text(chapter.read_text() + "Unreviewed external edit.")
        with self.assertRaisesRegex(ValueError, "stale|unverified"):
            start_task(self.state, "image-ch01", "fixture-image")

    def test_authorized_image_successor_preserves_completed_writer_repair(self):
        self.until("qa-ch01")
        repair = plan_remediation(self.state, [{
            "id": "editorial-ch01-comparison", "owner": "book_writer",
            "message": "Clarify the supported comparison.", "action": "rewrite",
        }])[0]
        start_task(self.state, repair["id"], "fixture-writer-repair")
        chapter = self.base / "book/en/ch01.md"
        chapter.write_text(chapter.read_text() + "\nA more precise comparison.\n")
        evidence = self.base / repair["artifacts"][0]
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps({
            "failure_ids": repair["failure_ids"], "before": "unclear comparison",
            "after": "supported comparison", "changed_artifacts": ["book/en/ch01.md"],
            "evidence": "Clarified the source-supported comparison.",
        }))
        complete_task(self.root, self.state, repair["id"])

        block_task(self.state, "image-ch01", "Refresh the figure caption after the comparison repair.")
        resume_state(self.root, self.state)
        start_task(self.state, "image-ch01", "fixture-image")
        chapter.write_text(chapter.read_text().replace("![first]", "![Clarified source figure]"))
        complete_task(self.root, self.state, "image-ch01")

        self.assertEqual(completed_task_errors(self.root, self.state), {})
        self.assertEqual(resume_state(self.root, self.state), {})
        self.assertEqual(repair["status"], "completed")
        self.assertIn("image-ch01", repair["artifact_successors"])

    def test_factcheck_receipt_does_not_invalidate_source_packet(self):
        self.until("factcheck-ch01")
        start_task(self.state, "factcheck-ch01", "fixture-factchecker")
        path = self.base / "_analysis/claim_evidence.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        rows[0]["checked_at"] = "2026-09-18"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        complete_task(self.root, self.state, "factcheck-ch01")
        self.assertEqual(completed_task_errors(self.root, self.state), {})
        start_task(self.state, "qa-ch01", "agent-reviewer-123")

    def test_failed_chapter_review_creates_diagnosis_not_numeric_writer_repair(self):
        self.until("qa-ch01")
        review_path = self.base / "_quality/chapters/ch01.json"
        review = json.loads(review_path.read_text())
        review["synthesis"]["score"] = 40
        review_path.write_text(json.dumps(review))
        start_task(self.state, "qa-ch01", "agent-reviewer-123")
        complete_task(self.root, self.state, "qa-ch01")
        repairs = [task for task in self.state["tasks"] if task["phase"] == "remediate"]
        self.assertFalse(self.task("qa-ch01")["accepted"])
        self.assertEqual(len(repairs), 1)
        self.assertEqual(repairs[0]["owner"], "qa_reviewer")

    def test_reviewer_cannot_reuse_writer_identity(self):
        self.until("qa-ch01")
        writer = self.task("write-ch01")["agent_ids"][0]
        with self.assertRaisesRegex(ValueError, "independent"):
            start_task(self.state, "qa-ch01", writer)

    def test_qa_repair_recomputes_acceptance_and_requeues_remaining_defect(self):
        self.until("qa-ch01")
        path = self.base / "_quality/chapters/ch01.json"
        review = json.loads(path.read_text())
        review["synthesis"]["score"] = 40
        path.write_text(json.dumps(review))
        start_task(self.state, "qa-ch01", "agent-reviewer-123")
        complete_task(self.root, self.state, "qa-ch01")
        for score in (40, 92):
            repair = next(task for task in self.state["tasks"] if task["phase"] == "remediate" and task["status"] == "pending")
            start_task(self.state, repair["id"], "agent-reviewer-123")
            review["synthesis"]["score"] = score
            path.write_text(json.dumps(review))
            evidence = self.base / repair["artifacts"][0]
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps({"failure_ids": repair["failure_ids"], "before": 40, "after": score, "changed_artifacts": ["_quality/chapters/ch01.json"], "evidence": "Reviewed specific comparison and qualifying explanation.", "revised_diagnosis": "Re-read the concrete comparison with the source conditions."}))
            complete_task(self.root, self.state, repair["id"])
            self.assertEqual(self.task("qa-ch01")["accepted"], score == 92)
        self.assertIn("qa-book", [task["id"] for task in ready_tasks(self.state)])

    def test_legacy_resume_preserves_evidence_without_fabricating_freshness(self):
        self.until()
        self.state["schema_version"] = "2.0"
        old = self.state["run_id"]
        resume_state(self.root, self.state)
        self.assertEqual(self.state["schema_version"], "2.1")
        self.assertTrue(all(task["status"] == "pending" for task in self.state["tasks"]))
        archived = json.loads((self.base / f"_workspace/runs/{old}-r0.json").read_text())
        self.assertEqual(archived["schema_version"], "2.0")
        self.assertTrue(all(task["status"] == "completed" for task in archived["tasks"]))

    def test_saturated_capacity_returns_no_ready_tasks(self):
        self.state["max_parallel"] = 1
        start_task(self.state, "kg-seed", "fixture-kg")
        self.assertEqual(ready_tasks(self.state), [])


if __name__ == "__main__":
    unittest.main()
