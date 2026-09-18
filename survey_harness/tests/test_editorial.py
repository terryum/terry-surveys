from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from survey_harness.editorial import (
    book_review_errors, chapter_review_errors, manuscript_digests, review_chapters,
)
from survey_harness.schema_utils import _validate_without_dependency
from survey_harness.tests.helpers import make_passing_mini, write_current_reviews, write_json


class EditorialReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.survey = make_passing_mini(self.root)
        write_current_reviews(self.survey, write_state=True)
        self.state = json.loads((self.survey / "_workspace/harness_state.json").read_text())
        self.review_path = self.survey / "_quality/chapters/ch01.json"
        self.review = json.loads(self.review_path.read_text())

    def save_review(self):
        write_json(self.review_path, self.review)

    def finding(self):
        return {
            "id": "missing-comparison", "severity": "blocker",
            "location": {"path": "book/en/ch01.md", "anchor": "Foundations"},
            "excerpt": "enevidence0 enevidence1 enevidence2",
            "problem": "The comparison does not explain the relevant tradeoff.",
            "impact": "Readers cannot choose between the methods in the stated setting.",
            "expected": "Explain the differing assumptions and give a supported judgment.",
            "action": "rewrite",
        }

    def test_valid_reviews_bind_exact_current_manuscripts_and_task(self):
        self.assertEqual(chapter_review_errors(self.survey, 1, self.state), [])
        self.assertEqual(book_review_errors(self.survey, [1], self.state), [])
        self.assertEqual(set(manuscript_digests(self.survey, 1)), {"ko", "en"})

    def test_any_manuscript_change_invalidates_chapter_and_book_review(self):
        chapter = self.survey / "book/en/ch01.md"
        chapter.write_text(chapter.read_text() + "\n")
        self.assertIn("manuscript_digests", " ".join(chapter_review_errors(self.survey, 1, self.state)))
        self.assertIn("manuscript_digests", " ".join(book_review_errors(self.survey, [1], self.state)))

    def test_missing_language_cannot_match_an_incomplete_digest(self):
        (self.survey / "book/ko/ch01.md").unlink()
        self.review["manuscript_digests"].pop("ko")
        self.save_review()
        self.assertTrue(chapter_review_errors(self.survey, 1, self.state))

    def test_reviewer_must_match_its_specific_qa_task(self):
        self.state["tasks"] = [task for task in self.state["tasks"] if task["id"] == "qa-book"]
        self.assertIn("qa-ch01", " ".join(chapter_review_errors(self.survey, 1, self.state)))

    def test_prior_attempt_reviewer_cannot_certify_current_attempt(self):
        task = next(task for task in self.state["tasks"] if task["id"] == "qa-ch01")
        task["agent_ids"].append("current-reviewer-456")
        self.assertIn("qa-ch01", " ".join(chapter_review_errors(self.survey, 1, self.state)))
        self.review["reviewer_id"] = "current-reviewer-456"
        self.save_review()
        self.assertEqual(chapter_review_errors(self.survey, 1, self.state), [])

    def test_missing_execution_state_is_not_independence_evidence(self):
        self.assertTrue(chapter_review_errors(self.survey, 1, {}))
        self.assertTrue(book_review_errors(self.survey, [1], {}))

    def test_writer_cannot_review_under_the_same_agent_identity(self):
        self.state["tasks"].append({"id": "write-ch01", "owner": "book_writer", "agent_ids": [self.review["reviewer_id"]]})
        self.assertIn("non-QA", " ".join(chapter_review_errors(self.survey, 1, self.state)))

    def test_valid_blocking_findings_can_complete_a_review_and_route_a_repair(self):
        self.review["findings"] = [self.finding()]
        self.save_review()
        self.assertEqual(chapter_review_errors(self.survey, 1, self.state), [])
        metrics, failures, warnings = review_chapters(self.survey, [1], {"dimension_floor": 75}, self.state)
        self.assertEqual(metrics["ch01"]["score"], 92)
        self.assertEqual(failures[0]["owner"], "book_writer")
        self.assertEqual(failures[0]["finding"]["action"], "rewrite")
        self.assertEqual(warnings, [])

    def test_numeric_score_alone_routes_to_diagnosis_not_writer_padding(self):
        self.review["synthesis"]["score"] = 40
        self.save_review()
        self.assertEqual(chapter_review_errors(self.survey, 1, self.state), [])
        _, failures, _ = review_chapters(self.survey, [1], {"dimension_floor": 75}, self.state)
        self.assertTrue(failures)
        self.assertTrue(all(failure["owner"] == "qa_reviewer" for failure in failures))

    def test_low_chapter_score_cannot_be_compensated_by_other_chapters(self):
        for lang in ("ko", "en"):
            (self.survey / f"book/{lang}/ch02.md").write_bytes((self.survey / f"book/{lang}/ch01.md").read_bytes())
        write_current_reviews(self.survey, chapters=(1, 2), write_state=True)
        self.state = json.loads((self.survey / "_workspace/harness_state.json").read_text())
        self.review["synthesis"]["score"] = 70
        self.save_review()
        metrics, failures, _ = review_chapters(self.survey, [1, 2], {"dimension_floor": 75}, self.state)
        self.assertGreater(sum(row["score"] for row in metrics.values()) / 2, 75)
        self.assertIn("chapter-synthesis-ch01", {row["id"] for row in failures})

    def test_findings_need_real_excerpts_and_concrete_locations(self):
        for mutation in ("excerpt", "location", "impact"):
            with self.subTest(mutation=mutation):
                finding = self.finding()
                if mutation == "location":
                    finding["location"]["path"] = "../../outside.md"
                elif mutation == "excerpt":
                    finding["excerpt"] = "invented text absent from the manuscript"
                else:
                    finding["impact"] = " " * 20
                self.review["findings"] = [finding]
                self.save_review()
                self.assertTrue(chapter_review_errors(self.survey, 1, self.state))

    def test_warning_finding_does_not_block(self):
        finding = self.finding()
        finding["severity"] = "warning"
        self.review["findings"] = [finding]
        self.save_review()
        _, failures, warnings = review_chapters(self.survey, [1], {"dimension_floor": 75}, self.state)
        self.assertEqual(failures, [])
        self.assertEqual(len(warnings), 1)

    def test_book_review_needs_every_chapter_and_current_schema(self):
        review_path = self.survey / "_quality/reviewer_scores.json"
        book = json.loads(review_path.read_text())
        book["manuscript_digests"] = {}
        write_json(review_path, book)
        self.assertTrue(book_review_errors(self.survey, [1], self.state))
        book.pop("schema_version")
        write_json(review_path, book)
        self.assertIn("2.1", " ".join(book_review_errors(self.survey, [1], self.state)))

    def test_dependency_free_schema_checks_nested_scores_and_findings(self):
        schema_dir = Path(__file__).parents[1] / "schemas"
        for name, data in (
            ("chapter-review.schema.json", self.review),
            ("reviewer-scores.schema.json", json.loads((self.survey / "_quality/reviewer_scores.json").read_text())),
        ):
            schema = json.loads((schema_dir / name).read_text())
            self.assertEqual(_validate_without_dependency(data, schema), [])
            data["findings"] = [{"id": "not-concrete", "severity": "blocker"}]
            self.assertTrue(_validate_without_dependency(data, schema))
        self.review["synthesis"]["score"] = 110
        schema = json.loads((schema_dir / "chapter-review.schema.json").read_text())
        self.assertTrue(_validate_without_dependency(self.review, schema))


if __name__ == "__main__":
    unittest.main()
