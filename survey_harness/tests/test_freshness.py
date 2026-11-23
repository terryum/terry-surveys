from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from survey_harness.state import (
    block_task, build_tasks, complete_task, completed_task_errors, new_state, plan_remediation,
    ready_tasks, resume_state, save_state, start_task, task_packet,
)
from survey_harness.editorial import manuscript_digests
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
        self.assertIn({"root": "content", "path": "_quality/chapters/ch01.json"}, tasks["write-ch02"]["inputs"])
        self.assertEqual(tasks["qa-book"]["acceptance_dependencies"], ["qa-ch01", "qa-ch02"])
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

    def test_index_and_renderer_changes_invalidate_book_review(self):
        self.until()
        path = self.base / "survey.json"
        metadata = json.loads(path.read_text())
        metadata["cover"] = "assets/cover.png"
        path.write_text(json.dumps(metadata))
        custom_build = self.base / "scripts/build_book.py"
        custom_build.parent.mkdir()
        custom_build.write_text("# Add a custom deployment builder.\n")
        renderer = self.root / "shared/build_site.py"
        renderer.parent.mkdir()
        renderer.write_text("# Change the index renderer.\n")

        errors = completed_task_errors(self.root, self.state)["qa-book"]
        for selector in ("content:survey.json", "content:scripts/build_book.py", "repo:shared/build_site.py"):
            with self.subTest(selector=selector):
                self.assertIn(selector, errors)

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
        self.assertFalse(self.task("qa-ch01")["accepted"])
        self.assertEqual(self.task("qa-ch01")["pending_diagnosis"], "chapter-synthesis-ch01")
        self.assertEqual([task["id"] for task in ready_tasks(self.state)], ["qa-ch01"])

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
            start_task(self.state, "qa-ch01", "agent-reviewer-456")
            review["reviewer_id"] = "agent-reviewer-456"
            review["synthesis"]["score"] = score
            path.write_text(json.dumps(review))
            complete_task(self.root, self.state, "qa-ch01")
            self.assertEqual(self.task("qa-ch01")["accepted"], score == 92)
        self.assertIn("qa-book", [task["id"] for task in ready_tasks(self.state)])

    def test_two_repairs_recheck_stable_failure_and_preserve_evidence_through_resume(self):
        self.until("qa-ch01")
        qa = self.task("qa-ch01")
        review_path = self.base / qa["artifacts"][0]
        review = json.loads(review_path.read_text())
        finding = {
            "id": "missing-comparison", "severity": "blocker",
            "location": {"path": "book/en/ch01.md", "anchor": "Foundations"},
            "excerpt": "enevidence0 enevidence1 enevidence2",
            "problem": "The comparison lacks a common test condition.",
            "impact": "Readers cannot interpret the difference between methods.",
            "expected": "Name the shared experimental condition in the comparison.",
            "action": "rewrite",
        }
        review["synthesis"]["score"] = 40
        review["findings"] = [finding]
        review_path.write_text(json.dumps(review))
        start_task(self.state, qa["id"], "agent-reviewer-123")
        complete_task(self.root, self.state, qa["id"])
        archived_receipts = {}
        chapter = self.base / finding["location"]["path"]
        for index, status in enumerate(("open", "resolved")):
            repair, = ready_tasks(self.state)
            self.assertEqual(repair["owner"], "book_writer")
            self.assertNotIn("pending_diagnosis", qa)
            start_task(self.state, repair["id"], f"fixture-repair-{index}")
            receipt = self.base / repair["artifacts"][0]
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps({
                "failure_ids": repair["failure_ids"], "before": "Unclear comparison",
                "after": "A clearer comparison", "changed_artifacts": [finding["location"]["path"]],
                "evidence": "Clarified the comparison condition in the prose.",
            }))
            with self.assertRaisesRegex(ValueError, "actual manuscript changes"):
                complete_task(self.root, self.state, repair["id"])
            corrected = f"The benchmark ran under comparison condition {index + 1}."
            chapter.write_text(chapter.read_text() + "\n" + corrected + "\n")
            resume_state(self.root, self.state)
            self.assertEqual([task["id"] for task in ready_tasks(self.state)], [repair["id"]])
            start_task(self.state, repair["id"], f"fixture-repair-resumed-{index}")
            complete_task(self.root, self.state, repair["id"])
            self.assertTrue(repair["revision_check"]["required"])
            archived_receipts[receipt] = receipt.read_bytes()
            self.until(qa["id"])
            packet = task_packet(self.root, self.state, qa)
            failure_id, = repair["failure_ids"]
            self.assertEqual(packet["review_findings"], {repair["id"]: {failure_id: finding}})
            start_task(self.state, qa["id"], "agent-reviewer-456")
            review["reviewer_id"] = "agent-reviewer-456"
            review["manuscript_digests"] = manuscript_digests(self.base, 1)
            review["synthesis"]["score"] = 40 if status == "open" else 92
            review["findings"] = [finding] if status == "open" else []
            review.pop("rechecks", None)
            review_path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "rechecks"):
                complete_task(self.root, self.state, qa["id"])
            review["rechecks"] = {repair["id"]: {failure_id: {
                "status": status, "path": finding["location"]["path"], "excerpt": corrected,
                "reason": "The revised section is tied to the benchmark comparison.",
            }}}
            review_path.write_text(json.dumps(review))
            complete_task(self.root, self.state, qa["id"])
            self.assertEqual(qa["accepted"], status == "resolved")
            for path, payload in archived_receipts.items():
                self.assertEqual(path.read_bytes(), payload)
        self.assertEqual([task["id"] for task in ready_tasks(self.state)], ["qa-book"])
        self.assertEqual([list(item["review"].get("rechecks", {})) for item in qa["review_history"]],
                         [[], *([path.stem] for path in archived_receipts)])
        self.assertEqual(self.state["quality"]["remediation_attempts"][failure_id], 2)

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
