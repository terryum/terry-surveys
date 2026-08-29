from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from survey_harness.quality import (
    content_digest,
    evaluate,
    korean_prose_language_stats,
    prose,
    survey_metadata_latin_terms,
    word_count,
)
from survey_harness.tests.helpers import make_passing_mini


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.survey = make_passing_mini(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_mini_fixture_passes(self):
        scorecard = evaluate(self.root, "test-survey", "mini")
        self.assertTrue(scorecard["passed"], scorecard["hard_blockers"])
        self.assertGreaterEqual(scorecard["score"], scorecard["release_score"])

    def test_long_titles_route_to_book_writer(self):
        config_path = self.survey / "survey.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["parts"][0]["name"]["en"] = "Part I: " + "A" * 70
        config["parts"][0]["chapters"][0]["title"]["en"] = "B" * 90
        config_path.write_text(json.dumps(config), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertEqual(failures["title-part-length-en"]["owner"], "book_writer")
        self.assertEqual(failures["title-chapter-length-en"]["owner"], "book_writer")
        self.assertIn("title-chapter-median-en", failures)

    def test_title_metadata_drift_is_blocked(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8").replace('title: "Chapter 1"', 'title: "Different title"')
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertEqual(failures["title-metadata-sync"]["owner"], "book_writer")

    def test_missing_claim_contract_routes_to_fact_checker(self):
        (self.survey / "_analysis/claim_evidence.jsonl").unlink()
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertFalse(scorecard["passed"])
        self.assertEqual(failures["claim-matrix-empty"]["owner"], "fact_checker")

    def test_claim_rows_must_be_anchored_in_both_manuscripts(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8").replace("<!-- claim:ch01-c01 -->", "")
        chapter.write_text(text + "\n<!-- claim:ch01-c01 -->\n", encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertEqual(failures["claim-manuscript-anchors"]["owner"], "fact_checker")

    def test_claim_text_must_match_its_bound_english_excerpt(self):
        claims_path = self.survey / "_analysis/claim_evidence.jsonl"
        row = json.loads(claims_path.read_text(encoding="utf-8"))
        row["claim"] = "An unrelated assertion that never appears in the manuscript excerpt"
        claims_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("claim-manuscript-anchors", failures)

    def test_front_loaded_figures_route_to_image_curator(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8")
        text = text.replace("\n\n![first](../../assets/figures/first.png)", "")
        text = text.replace("\n\n![late](../../assets/figures/late.png)", "")
        text = text.replace("\n\n| Method | Evidence |\n|---|---|\n| A | Primary |", "")
        text = text.replace("# Chapter\n\n", "# Chapter\n\n![first](../../assets/figures/first.png)\n![second](../../assets/figures/second.png)\n\n", 1)
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        pacing = [item for item in scorecard["hard_blockers"] if item["id"] == "visual-pacing-en-ch01"]
        self.assertEqual(pacing[0]["owner"], "image_curator")

    def test_reviewer_cannot_reuse_a_non_qa_worker_identity(self):
        state_path = self.survey / "_workspace/harness_state.json"
        state_path.write_text(json.dumps({"tasks": [
            {"owner": "book_writer", "agent_ids": ["agent-reviewer-123"]},
            {"owner": "qa_reviewer", "agent_ids": ["agent-reviewer-123"]},
        ]}), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertIn("reviewer-independence", failures)
        self.assertEqual(failures["reviewer-independence"]["owner"], "qa_reviewer")

    def test_unverified_reference_status_is_rejected(self):
        refs_path = self.survey / "_refs_extracted.json"
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
        for row in refs:
            row["verification_status"] = "not_verified"
        refs_path.write_text(json.dumps(refs), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertIn("reference-verification", failures)

    def test_bibliography_padding_does_not_satisfy_depth(self):
        for lang in ("ko", "en"):
            chapter = self.survey / f"book/{lang}/ch01.md"
            chapter.write_text(
                "# Chapter\n\n## One\n\n<!-- claim:ch01-c01 -->\nVery short supported prose.\n\n"
                "![first](../../assets/figures/first.png)\n\n## Two\n\n"
                "[Paper summary](https://terryum.ai/papers/paper0)\n\n"
                "![late](../../assets/figures/late.png)\n\n## References\n"
                + " ".join(f"citation{i}" for i in range(1500)),
                encoding="utf-8",
            )
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("depth-en-ch01", failures)
        self.assertLess(scorecard["metrics"]["chapters"]["ch01"]["en"]["words"], 100)

    def test_repeated_token_prose_is_blocked(self):
        repeated = " ".join(["evidence"] * 1300)
        for lang in ("ko", "en"):
            chapter = self.survey / f"book/{lang}/ch01.md"
            chapter.write_text(
                f"# Chapter\n\n## One\n\n<!-- claim:ch01-c01 -->\n{repeated}\n\n"
                "![first](../../assets/figures/first.png)\n\n## Two\n\n"
                "[Paper summary](https://terryum.ai/papers/paper0)\n\n"
                "![late](../../assets/figures/late.png)\n\n## References\n1. Source",
                encoding="utf-8",
            )
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("dominant-token-en-ch01", failures)

    def test_excessive_english_prose_in_korean_chapter_is_blocked(self):
        chapter = self.survey / "book/ko/ch01.md"
        text = chapter.read_text(encoding="utf-8")
        english = " ".join(f"ordinaryword{i} explains untranslated engineering prose" for i in range(350))
        chapter.write_text(text.replace("## Analysis", f"{english}\n\n## Analysis"), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertIn("korean-language-ko-ch01", failures)
        self.assertEqual(failures["korean-language-ko-ch01"]["owner"], "book_writer")
        self.assertGreater(scorecard["metrics"]["chapters"]["ch01"]["ko"]["latin_prose_fraction"], 0.15)

    def test_depth_gate_allows_five_percent_tolerance(self):
        chapter = self.survey / "book/en/ch01.md"
        compact = " ".join(f"compact{i}" for i in range(1130))
        chapter.write_text(
            "# Chapter\n\n> **After reading this chapter...** compare evidence.\n\n"
            f"## One\n\n{compact}\n\n## Two\n\n"
            "| Method | Evidence |\n|---|---|\n| A | Primary |\n\n"
            "![first](../../assets/figures/first.png)\n\n"
            "![late](../../assets/figures/late.png)\n\n## References\n1. Source\n",
            encoding="utf-8",
        )
        measured = word_count(prose(chapter.read_text(encoding="utf-8")))
        self.assertGreaterEqual(measured, 1140)
        self.assertLess(measured, 1200)
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertNotIn("depth-en-ch01", failures)

    def test_bloat_gate_requires_cutting(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8")
        text = text.replace("## Analysis", " ".join(f"excess{i}" for i in range(4700)) + "\n\n## Analysis")
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertIn("bloat-en-ch01", failures)
        self.assertIn("Cut, do not add", failures["bloat-en-ch01"]["message"])

    def test_apparatus_gate_and_synthesis_score_measure_table_weight(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8")
        heavy_table = "| Method | Evidence |\n|---|---|\n| A | " + ("heavy " * 400) + "|"
        text = text.replace("| Method | Evidence |\n|---|---|\n| A | Primary |", heavy_table)
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"]: item for item in scorecard["hard_blockers"]}
        self.assertIn("apparatus-en-ch01", failures)
        self.assertIn("Cut, do not add", failures["apparatus-en-ch01"]["message"])
        self.assertLess(scorecard["dimensions"]["synthesis"]["automatic"], 100)

    def test_repeated_english_gloss_is_metric_only(self):
        chapter = self.survey / "book/ko/ch01.md"
        text = chapter.read_text(encoding="utf-8").replace(
            "## Analysis", "속도(velocity)를 정하고 목표 속도(velocity)를 확인한다.\n\n## Analysis"
        )
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertEqual(scorecard["metrics"]["chapters"]["ch01"]["ko"]["repeated_english_glosses"], 1)
        self.assertNotIn("korean-language-ko-ch01", failures)

    def test_korean_language_metric_ignores_expected_latin_contexts(self):
        text = """# 한국어 장

속도(velocity)는 로봇의 상태다. velocity를 다시 영어로 쓰면 검사한다.
NASA와 PyTorch, Terry Um은 고유 이름과 약어다.
2 cm와 5 kg은 측정 단위다.
`model.step()`과 $x = velocity$도 코드와 수식이다.
[English paper title](https://example.com/paper) [Smith et al., 2025]

```python
ordinary english code should be ignored
```

## 참고문헌
1. English references are ignored.
"""
        stats = korean_prose_language_stats(text)
        self.assertEqual(stats["latin_prose_tokens"], 1)
        self.assertEqual(stats["top_latin_tokens"], [{"token": "velocity", "count": 1}])

    def test_korean_language_metric_allows_citations_latex_and_common_terms(self):
        stats = korean_prose_language_stats(
            "로봇은 et al 표기와 dot ddot cmd frac 명령을 쓴다. "
            "action head와 diffusion policy, end-effector, sim-to-real, "
            "teacher-student, backdrivability, proprioceptive, proprioception, "
            "rollout, checkpoint, fine-tuning, co-training, pre-training, "
            "post-training, tokenizer, embodiment를 그대로 쓴다."
        )
        self.assertEqual(stats["latin_prose_tokens"], 0)

    def test_korean_language_metric_allows_survey_metadata_names(self):
        papers_path = self.survey / "_research/papers.json"
        papers = json.loads(papers_path.read_text(encoding="utf-8"))
        papers[0]["venue"] = "OpenAI Codex MuJoCo libfranka"
        papers_path.write_text(json.dumps(papers), encoding="utf-8")
        allowed = survey_metadata_latin_terms(self.survey)
        stats = korean_prose_language_stats("openai codex mujoco libfranka를 사용한다.", allowed)
        self.assertEqual(stats["latin_prose_tokens"], 0)

    def test_repeated_chapter_gloss_is_detected_after_first_allowance(self):
        stats = korean_prose_language_stats("속도(velocity)는 상태다. 목표 속도(velocity)를 정한다.")
        self.assertEqual(stats["repeated_english_glosses"], 1)
        self.assertEqual(stats["top_repeated_english_glosses"], [{"term": "velocity", "count": 1}])

    def test_korean_parenthetical_attribution_is_not_an_english_gloss(self):
        stats = korean_prose_language_stats(
            "저자 제작(Codex 보조). 다른 그림도 저자 제작(Codex 보조)."
        )
        self.assertEqual(stats["repeated_english_glosses"], 0)

    def test_korean_language_metric_checks_figure_caption_but_not_image_path(self):
        stats = korean_prose_language_stats(
            "![그림. ordinary untranslated caption words](../../assets/figures/english_file_name.png)"
        )
        self.assertEqual(stats["latin_prose_tokens"], 4)
        self.assertEqual(
            stats["top_latin_tokens"],
            [
                {"token": "caption", "count": 1},
                {"token": "ordinary", "count": 1},
                {"token": "untranslated", "count": 1},
                {"token": "words", "count": 1},
            ],
        )

    def test_repeated_long_paragraphs_without_learning_structure_are_blocked(self):
        for lang in ("ko", "en"):
            paragraph = " ".join(f"{lang}concept{i}" for i in range(520))
            chapter = self.survey / f"book/{lang}/ch01.md"
            chapter.write_text(
                f"# Chapter\n\n## One\n\n<!-- claim:ch01-c01 -->\n\n{paragraph}\n\n{paragraph}\n\n"
                f"![first](../../assets/figures/first.png)\n\n## Two\n\n{paragraph}\n\n{paragraph}\n\n"
                f"![late](../../assets/figures/late.png)\n\n{paragraph}\n\n{paragraph}\n\n"
                "[Paper summary](https://terryum.ai/papers/paper0)\n\n## References\n1. Source",
                encoding="utf-8",
            )
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("repeated-paragraphs", failures)
        self.assertIn("learning-outcomes-en-ch01", failures)
        self.assertIn("tables-en-ch01", failures)
        self.assertIn("paragraph-p90-en-ch01", failures)

    def test_comments_and_pipe_prose_do_not_spoof_learning_or_tables(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8")
        text = text.replace("> **After reading this chapter...** you can compare the evidence.", "<!-- After reading this chapter... -->")
        text = text.replace("| Method | Evidence |\n|---|---|\n| A | Primary |", "This prose contains one | separator and another | separator.")
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("learning-outcomes-en-ch01", failures)
        self.assertIn("tables-en-ch01", failures)

    def test_two_repeated_long_paragraphs_are_detected(self):
        chapter = self.survey / "book/en/ch01.md"
        text = chapter.read_text(encoding="utf-8")
        repeated = " ".join(f"duplicatedconcept{i}" for i in range(70))
        text = text.replace("## Analysis", f"{repeated}\n\n{repeated}\n\n## Analysis")
        chapter.write_text(text, encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("repeated-paragraphs", failures)

    def test_null_image_plan_values_are_rejected(self):
        plan_path = self.survey / "_workspace/image_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for row in plan["chapters"]["ch01"]:
            row["figure_id"] = None
            row["path"] = None
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("image-plan-schema", failures)
        self.assertIn("image-plan-coverage", failures)

    def test_content_digest_binds_manifest_not_r2_binary(self):
        before = content_digest(self.survey)
        figure = self.survey / "assets/figures/first.png"
        figure.write_bytes(b"r2-only-binary-change")
        self.assertEqual(before, content_digest(self.survey))

        manifest = self.survey / "_workspace/04_image_manifest.json"
        manifest.write_text(json.dumps({"schema_version": "2.0", "assets": [{"path": "first.png", "sha256": "abc"}]}), encoding="utf-8")
        self.assertNotEqual(before, content_digest(self.survey))

    def test_reviewer_id_must_match_a_qa_worker(self):
        state_path = self.survey / "_workspace/harness_state.json"
        state_path.write_text(json.dumps({"tasks": [
            {"owner": "book_writer", "agent_ids": ["writer-123"]},
            {"owner": "qa_reviewer", "agent_ids": ["different-reviewer-456"]},
        ]}), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("reviewer-identity-binding", failures)

    def test_reference_floors_use_unique_source_identity(self):
        refs_path = self.survey / "_refs_extracted.json"
        duplicate = {"ch": "01", "lang": "en", "bibtex_key": "same-paper", "arxiv_id": "2601.00001", "verification_status": "verified"}
        refs_path.write_text(json.dumps([duplicate] * 40), encoding="utf-8")
        scorecard = evaluate(self.root, "test-survey", "mini")
        self.assertEqual(scorecard["metrics"]["references"], 1)
        failures = {item["id"] for item in scorecard["hard_blockers"]}
        self.assertIn("academic-references", failures)


if __name__ == "__main__":
    unittest.main()
