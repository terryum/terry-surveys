from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shared.build_site import build_chapter_html, build_survey, build_toc_html
from tutorial_harness.tests.helpers import make_passing_content, make_repo

ROOT = Path(__file__).resolve().parents[2]


class BuilderTests(unittest.TestCase):
    def config(self, statuses=True):
        chapters = [
            {"num": 1, "title": {"ko": "하나", "en": "One"}, "summary": {"ko": "요약", "en": "Summary"}, **({"status": "planned"} if statuses else {})},
            {"num": 3, "title": {"ko": "셋", "en": "Three"}, "summary": {"ko": "요약", "en": "Summary"}, **({"status": "ready"} if statuses else {})},
        ]
        return {"title": {"ko": "제목", "en": "Title"}, "subtitle": {"ko": "부제", "en": "Subtitle"}, "description": {"ko": "설명", "en": "Description"}, "dates": {}, "features": {}, "parts": [{"name": {"ko": "파트", "en": "Part"}, "chapters": chapters}]}

    def test_planned_card_is_disabled_and_first_ready_starts(self):
        html = build_toc_html(self.config(), "ko")
        self.assertIn('class="chapter-card chapter-card-planned', html)
        self.assertNotIn('href="ch01.html"', html)
        self.assertIn('href="ch03.html" class="btn-primary"', html)
        self.assertIn("준비 중", html)

    def test_missing_status_remains_ready_for_legacy_surveys(self):
        html = build_toc_html(self.config(statuses=False), "en")
        self.assertIn('href="ch01.html" class="chapter-card', html)
        self.assertIn('href="ch03.html" class="chapter-card', html)

    def test_non_contiguous_navigation_uses_existing_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp)
            (book / "ch01.md").write_text("---\nchapter: 1\n---\n\n# One\n", encoding="utf-8")
            (book / "ch03.md").write_text("---\nchapter: 3\n---\n\n# Three\n", encoding="utf-8")
            meta = {1: {"title": "One", "part": "Part", "part_num": 1}, 3: {"title": "Three", "part": "Part", "part_num": 1}}
            first = build_chapter_html(1, "en", meta, str(book), "en", [1, 3])
            last = build_chapter_html(3, "en", meta, str(book), "en", [1, 3])
            self.assertIn('href="ch03.html" class="next"', first)
            self.assertIn('href="ch01.html" class="prev"', last)
            self.assertNotIn("ch02.html", first + last)

    def test_build_emits_only_ready_chapters_and_removes_stale_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base = make_repo(repo, chapters=((1, "planned"), (3, "ready")))
            make_passing_content(base, 3)
            stale = base / "docs/ko/ch01.html"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("stale", encoding="utf-8")
            build_survey({}, str(base), str(ROOT / "shared"))
            self.assertFalse(stale.exists())
            self.assertTrue((base / "docs/ko/ch03.html").is_file())
            self.assertTrue((base / "docs/en/ch03.html").is_file())
            self.assertFalse((base / "docs/en/ch01.html").exists())


if __name__ == "__main__":
    unittest.main()
