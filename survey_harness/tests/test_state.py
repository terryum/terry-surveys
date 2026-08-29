from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from survey_harness.state import (
    complete_task,
    load_state,
    new_state,
    plan_remediation,
    record_score,
    ready_tasks,
    release_receipt_errors,
    resume_state,
    save_state,
    start_task,
    update_release,
)
from survey_harness.tests.helpers import make_repo


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.survey = make_repo(self.root, chapters=(1, 2))

    def tearDown(self):
        self.temp.cleanup()

    def test_dag_starts_with_one_task_and_unlocks_strategy(self):
        state = new_state(self.root, "test-survey", "mini")
        self.assertEqual([task["id"] for task in ready_tasks(state)], ["kg-seed"])
        evidence = next(task for task in state["tasks"] if task["id"] == "evidence-synthesis")
        kg_seed = next(task for task in state["tasks"] if task["id"] == "kg-seed")
        self.assertIn("_workspace/inputs/input_manifest.md", kg_seed["artifacts"])
        self.assertIn("_analysis/chapter_source_packets/ch01.json", evidence["artifacts"])
        self.assertIn("_analysis/chapter_source_packets/ch02.json", evidence["artifacts"])
        qa_one = next(task for task in state["tasks"] if task["id"] == "qa-ch01")
        self.assertNotIn("_analysis/chapter_source_packets/ch02.json", qa_one["artifacts"])
        for rel in ("_research/kg_seed.json", "_analysis/prior_survey_absorption.md"):
            path = self.survey / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"anchors": ["paper0"]}\n' if rel.endswith("kg_seed.json") else "Prior survey absorption evidence with enough detail.\n", encoding="utf-8")
        start_task(state, "kg-seed", "agent-123")
        complete_task(self.root, state, "kg-seed")
        self.assertEqual([task["id"] for task in ready_tasks(state)], ["source-strategy"])

    def test_completion_requires_declared_artifacts(self):
        state = new_state(self.root, "test-survey", "mini")
        start_task(state, "kg-seed", "agent-123")
        with self.assertRaisesRegex(ValueError, "artifacts missing"):
            complete_task(self.root, state, "kg-seed")

    def test_remediation_exhausts_after_configured_attempts(self):
        state = new_state(self.root, "test-survey", "full")
        failure = [{"id": "depth-ko-ch01", "owner": "book_writer", "message": "too short"}]
        for _ in range(3):
            tasks = plan_remediation(state, failure)
            self.assertEqual(len(tasks), 1)
            task = tasks[0]
            evidence = self.survey / task["artifacts"][0]
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text('{"failure_ids":["depth-ko-ch01"],"before":{"words":100},"after":{"words":3000},"changed_artifacts":["book/ko/ch01.md"],"evidence":"word count increased"}\n', encoding="utf-8")
            start_task(state, task["id"], f"agent-repair-{_}")
            complete_task(self.root, state, task["id"])
        self.assertEqual(plan_remediation(state, failure), [])
        self.assertEqual(state["status"], "blocked")
        self.assertIn("depth-ko-ch01", state["quality"]["blocked_reason"])

    def test_remediation_groups_by_owner_and_chapter_with_direction_contract(self):
        state = new_state(self.root, "test-survey", "full")
        failures = [
            {"id": "depth-ko-ch01", "owner": "book_writer", "message": "too short"},
            {"id": "apparatus-en-ch01", "owner": "book_writer", "message": "table too heavy"},
            {"id": "bloat-ko-ch02", "owner": "book_writer", "message": "too long"},
        ]
        tasks = plan_remediation(state, failures)
        self.assertEqual([task["id"] for task in tasks], ["repair-book_writer-ch01-r0", "repair-book_writer-ch02-r0"])
        first = tasks[0]["brief"]
        self.assertIn("[depth-ko-ch01][direction=add]", first)
        self.assertIn("[apparatus-en-ch01][direction=cut]", first)
        self.assertIn("분량·구조 게이트를 표·소제목·체크리스트 추가로 통과시키지 마라.", first)
        self.assertIn("부족분은 논증과 사례로 채우고, 초과분은 삭제로 해결하라.", first)
        self.assertIn("감사 항목 나열표를 새로 만들지 마라.", first)
        self.assertIn("_analysis/chapter_source_packets/ch01.json", first)
        self.assertIn("role-contracts-v2.md#book-writereditor", first)
        self.assertIn("[bloat-ko-ch02][direction=cut]", tasks[1]["brief"])

    def test_write_completion_enforces_tolerant_word_band(self):
        for lang in ("ko", "en"):
            chapter = self.survey / f"book/{lang}/ch01.md"
            chapter.parent.mkdir(parents=True, exist_ok=True)
            chapter.write_text(" ".join(f"word{i}" for i in range(2900)), encoding="utf-8")
        state = new_state(self.root, "test-survey", "full")
        next(task for task in state["tasks"] if task["id"] == "evidence-synthesis")["status"] = "completed"
        start_task(state, "write-ch01", "writer-band-1")
        complete_task(self.root, state, "write-ch01")
        self.assertEqual(next(task for task in state["tasks"] if task["id"] == "write-ch01")["status"], "completed")

        for lang in ("ko", "en"):
            (self.survey / f"book/{lang}/ch01.md").write_text(
                " ".join(f"word{i}" for i in range(4700)), encoding="utf-8"
            )
        state = new_state(self.root, "test-survey", "full")
        next(task for task in state["tasks"] if task["id"] == "evidence-synthesis")["status"] = "completed"
        start_task(state, "write-ch01", "writer-band-2")
        with self.assertRaisesRegex(ValueError, "maximum is 4600; cut, do not add"):
            complete_task(self.root, state, "write-ch01")

    def test_resume_requeues_abandoned_running_task(self):
        state = new_state(self.root, "test-survey", "mini")
        start_task(state, "kg-seed", "agent-123")
        resume_state(self.root, state)
        self.assertEqual(state["tasks"][0]["status"], "pending")
        self.assertEqual(state["status"], "running")

    def test_resume_reopens_blocked_and_invalid_completed_tasks(self):
        state = new_state(self.root, "test-survey", "mini")
        for rel in ("_research/kg_seed.json", "_analysis/prior_survey_absorption.md"):
            path = self.survey / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"anchors": ["paper0"]}\n' if rel.endswith("kg_seed.json") else "Prior survey absorption evidence.\n", encoding="utf-8")
        start_task(state, "kg-seed", "agent-123")
        complete_task(self.root, state, "kg-seed")
        (self.survey / "_research/kg_seed.json").unlink()
        source = next(task for task in state["tasks"] if task["id"] == "source-strategy")
        source["status"] = "blocked"
        errors = resume_state(self.root, state)
        self.assertIn("kg-seed", errors)
        self.assertEqual(state["tasks"][0]["status"], "pending")
        self.assertEqual(source["status"], "pending")

    def test_resource_locks_prevent_parallel_aggregate_writers(self):
        state = new_state(self.root, "test-survey", "mini")
        for task in state["tasks"]:
            task["status"] = "completed"
            task["agent_ids"] = [f"agent-{task['id']}"]
        for task_id in ("image-ch01", "image-ch02"):
            next(task for task in state["tasks"] if task["id"] == task_id)["status"] = "pending"
        ready = [task["id"] for task in ready_tasks(state)]
        self.assertEqual(ready, ["image-ch01"])

    def test_optimistic_revision_rejects_stale_save(self):
        state = new_state(self.root, "test-survey", "mini")
        save_state(self.root, state)
        first = load_state(self.root, "test-survey")
        stale = load_state(self.root, "test-survey")
        first["status"] = "remediating"
        save_state(self.root, first)
        stale["status"] = "blocked"
        with self.assertRaisesRegex(ValueError, "stale state revision"):
            save_state(self.root, stale)

    def test_score_profile_must_match_state(self):
        state = new_state(self.root, "test-survey", "mini")
        with self.assertRaisesRegex(ValueError, "does not match"):
            record_score(state, "_quality/scorecard.json", {"profile": "full", "score": 90, "passed": True, "dimensions": {}, "hard_blockers": []})

    def test_state_roundtrip_and_release_gate(self):
        state = new_state(self.root, "test-survey", "mini")
        save_state(self.root, state)
        self.assertEqual(load_state(self.root, "test-survey")["run_id"], state["run_id"])
        with self.assertRaises(ValueError):
            update_release(state, "running")
        state["profile"] = "full"
        state["release"]["policy"] = "auto"
        for task in state["tasks"]:
            task["status"] = "completed"
            task["agent_ids"] = [f"agent-{task['id']}"]
        state["quality"]["history"].append({"passed": True, "score": 90})
        state["status"] = "ready"
        update_release(state, "running", artifacts={"pages_url": "https://survey-test.pages.dev", "kg_baseline_sha256": "b" * 64})
        with self.assertRaisesRegex(ValueError, "not successful"):
            update_release(state, "released", artifacts={"live_ko_url": "https://terryum.ai/ko/surveys/test-survey", "live_en_url": "https://terryum.ai/en/surveys/test-survey", "survey_commit": "abc1234", "gallery_commit": "def4567", "workflow_id": "42", "live_ko": "failed", "live_en": "passed", "asset_validation": "passed", "workers_status": "success", "source_push": "passed", "kg_sync": "passed", "iframe_check": "passed", "not_found_check": "passed", "release_receipt": "_quality/release_receipt.json", "release_receipt_sha256": "a" * 64})
        update_release(state, "released", artifacts={"live_ko_url": "https://terryum.ai/ko/surveys/test-survey", "live_en_url": "https://terryum.ai/en/surveys/test-survey", "survey_commit": "abc1234", "gallery_commit": "def4567", "workflow_id": "42", "live_ko": "passed", "live_en": "passed", "asset_validation": "passed", "workers_status": "success", "source_push": "passed", "kg_sync": "passed", "iframe_check": "passed", "not_found_check": "passed", "release_receipt": "_quality/release_receipt.json", "release_receipt_sha256": "a" * 64})
        self.assertEqual(state["status"], "released")

    def test_release_rejects_one_agent_reused_across_producer_roles(self):
        state = new_state(self.root, "test-survey", "full")
        for task in state["tasks"]:
            task["status"] = "completed"
            task["agent_ids"] = ["qa-agent-unique" if task["owner"] == "qa_reviewer" else "one-production-agent"]
        state["quality"]["history"].append({"passed": True, "score": 90, "content_digest": "fixture"})
        state["status"] = "ready"
        with self.assertRaisesRegex(ValueError, "distinct role workers"):
            update_release(state, "running")

    def test_split_release_requires_content_and_framework_commits(self):
        state = new_state(self.root, "test-survey", "full")
        state["repository_layout"] = "split-v1"
        state["release"]["status"] = "running"
        state["release"]["artifacts"] = {
            "pages_url": "https://survey-test.pages.dev",
            "live_ko_url": "https://terryum.ai/ko/surveys/test-survey",
            "live_en_url": "https://terryum.ai/en/surveys/test-survey",
            "survey_commit": "abc1234",
            "gallery_commit": "def4567",
            "workflow_id": "42",
            "kg_baseline_sha256": "b" * 64,
            "live_ko": "passed",
            "live_en": "passed",
            "asset_validation": "passed",
            "workers_status": "success",
            "source_push": "passed",
            "kg_sync": "passed",
            "iframe_check": "passed",
            "not_found_check": "passed",
            "release_receipt": "_quality/release_receipt.json",
            "release_receipt_sha256": "a" * 64,
        }
        with self.assertRaisesRegex(ValueError, "content_commit, framework_commit"):
            update_release(state, "released")

    def test_split_release_receipt_uses_split_commit_labels(self):
        state = new_state(self.root, "test-survey", "full")
        state["repository_layout"] = "split-v1"
        state["status"] = "released"
        state["quality"]["history"].append({"content_digest": "digest"})
        labels = {
            "content-commit", "content-commit-remote", "framework-commit", "framework-commit-remote",
            "gallery-commit", "gallery-commit-remote", "scored-content-commit", "workers-workflow",
            "pages_url", "live_ko_url", "live_en_url", "asset-validation", "kg-sync",
        }
        payload = (json.dumps({
            "slug": "test-survey",
            "content_digest": "digest",
            "checks": [{"label": label, "exit_code": 0} for label in sorted(labels)],
        }) + "\n").encode()
        receipt = self.survey / "_quality/release_receipt.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_bytes(payload)
        state["release"]["artifacts"] = {
            "release_receipt": "_quality/release_receipt.json",
            "release_receipt_sha256": hashlib.sha256(payload).hexdigest(),
        }
        self.assertEqual(release_receipt_errors(self.root, state), [])


if __name__ == "__main__":
    unittest.main()
