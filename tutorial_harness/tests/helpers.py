from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_repo(root: Path, chapters=((1, "planned"), (2, "ready"))) -> Path:
    (root / "build.py").write_text("# fixture\n", encoding="utf-8")
    base = root / "surveys/demo-tutorial"
    base.mkdir(parents=True)
    write_json(base / "survey.json", {
        "id": "demo-tutorial",
        "content_type": "tutorial",
        "tutorial_number": 1,
        "visibility": "private",
        "status": "wip" if any(status == "planned" for _, status in chapters) else "active",
        "github_repo": "terryum/terry-surveys-contents",
        "github_repo_visibility": "private",
        "title": {"ko": "데모", "en": "Demo"},
        "short_title": {"ko": "데모", "en": "Demo"},
        "subtitle": {"ko": "부제", "en": "Subtitle"},
        "description": {"ko": "설명", "en": "Description"},
        "dates": {},
        "features": {"glossary": False, "pdf": False, "paper": False},
        "parts": [{"name": {"ko": "파트", "en": "Part"}, "chapters": [
            {"num": number, "title": {"ko": f"장 {number}", "en": f"Chapter {number}"}, "summary": {"ko": "요약", "en": "Summary"}, "status": status}
            for number, status in chapters
        ]}],
    })
    (base / "_workspace/inputs").mkdir(parents=True)
    (base / "_workspace/inputs/input_manifest.md").write_text("# Input\n", encoding="utf-8")
    (base / "_tutorial/chapter_packets").mkdir(parents=True)
    (base / "_tutorial/roadmap.md").write_text("# Roadmap\n", encoding="utf-8")
    write_json(base / "_tutorial/environment_matrix.json", {"checked_at": "2026-08-31"})
    (base / "_tutorial/source_ledger.jsonl").write_text('', encoding="utf-8")
    (base / "_tutorial/user_validation.jsonl").write_text('', encoding="utf-8")
    for number, status in chapters:
        if status != "ready":
            continue
        for lang in ("ko", "en"):
            path = base / f"book/{lang}/ch{number:02d}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"ready {lang} chapter {number}\n", encoding="utf-8")
    return base


def make_passing_content(base: Path, chapter: int = 2) -> None:
    packet = {
        "chapter": chapter,
        "first_action": "run demo",
        "first_success_minutes": 5,
        "steps": [{"action": "run", "expected": "ok", "recovery": "retry", "validation": "checked"}],
    }
    write_json(base / f"_tutorial/chapter_packets/ch{chapter:02d}.json", packet)
    write_json(base / f"labs/ch{chapter:02d}/manifest.json", {"files": ["demo.txt"]})
    for lang in ("ko", "en"):
        action = "행동" if lang == "ko" else "Action"
        expected = "기대 결과" if lang == "ko" else "Expected"
        recovery = "복구" if lang == "ko" else "Recovery"
        sources = "출처" if lang == "ko" else "Sources"
        text = f"""---
chapter: {chapter}
title: Demo
part: Part
---

# Demo

**{action}**: run demo

**{expected}**: `ok`

**{recovery}**: retry once

## {sources}

- [Official guide](https://example.com/official)
"""
        path = base / f"book/{lang}/ch{chapter:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (base / "_tutorial/source_ledger.jsonl").write_text(json.dumps({"chapters": [chapter], "official": True, "url": "https://example.com/official"}) + "\n", encoding="utf-8")
    write_json(base / f"_quality/example_verification/ch{chapter:02d}.json", {"checks": [{"name": "syntax", "status": "checked"}], "broken_links": []})
    write_json(base / f"_quality/pedagogy/ch{chapter:02d}.json", {"independent": True, "verdict": "pass"})
