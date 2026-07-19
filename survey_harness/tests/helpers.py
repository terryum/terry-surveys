from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def make_repo(root: Path, slug: str = "test-survey", chapters=(1,)) -> Path:
    (root / "build.py").write_text("# fixture\n", encoding="utf-8")
    survey = root / "surveys" / slug
    survey.mkdir(parents=True)
    write_json(survey / "survey.json", {
        "id": slug,
        "parts": [{"name": {"ko": "Part", "en": "Part"}, "chapters": [{"num": ch, "title": {"ko": f"장 {ch}", "en": f"Chapter {ch}"}} for ch in chapters]}],
    })
    manifest = survey / "_workspace/inputs/input_manifest.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("# Input manifest\n\n- fixture authoring contract\n", encoding="utf-8")
    return survey


def make_passing_mini(root: Path, slug: str = "test-survey") -> Path:
    survey = make_repo(root, slug)
    for lang in ("ko", "en"):
        if lang == "ko":
            body_a = "\n\n".join(" ".join(f"근거{chr(0xAC00 + i)}" for i in range(start, start + 100)) for start in range(0, 700, 100))
            body_b = "\n\n".join(" ".join(f"분석{chr(0xB000 + i)}" for i in range(start, start + 100)) for start in range(0, 700, 100))
        else:
            body_a = "\n\n".join(" ".join(f"{lang}evidence{i}" for i in range(start, start + 100)) for start in range(0, 700, 100))
            body_b = "\n\n".join(" ".join(f"{lang}analysis{i}" for i in range(start, start + 100)) for start in range(0, 700, 100))
        learning = "> **이 장을 읽고 나면...** 근거를 비교할 수 있다." if lang == "ko" else "> **After reading this chapter...** you can compare the evidence."
        table = "| Method | Evidence |\n|---|---|\n| A | Primary |"
        title = "장 1" if lang == "ko" else "Chapter 1"
        chapter = f"---\nchapter: 1\ntitle: \"{title}\"\npart: \"Part\"\n---\n\n# Chapter\n\n{learning}\n\n## Foundations\n\n<!-- claim:ch01-c01 -->\n\n{body_a}\n\n[Paper summary](https://terryum.ai/papers/paper0)\n\n![first](../../assets/figures/first.png)\n\n{table}\n\n## Analysis\n\n{body_b}\n\n![late](../../assets/figures/late.png)\n\n## References\n" + "\n".join(f"{i}. Source {i}" for i in range(1, 9))
        path = survey / "book" / lang / "ch01.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(chapter + "\n", encoding="utf-8")
    for name in ("first.png", "late.png", "0.png", "1.png"):
        asset = survey / "assets" / "figures" / name
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"fixture-image")
    papers = [{"title": f"Unique Research Paper {i}", "bibtex_key": f"paper{i}", "method_summary": "A substantive method summary", "limitations": ["A documented limitation"], "chapter_hint": "Ch1"} for i in range(30)]
    write_json(survey / "_research/papers.json", papers)
    write_json(survey / "_research/papers_foundations.json", papers[:15])
    write_json(survey / "_research/papers_frontier.json", papers[15:])
    write_json(survey / "_research/kg_seed.json", {"anchors": ["paper0"]})
    (survey / "_analysis/prior_survey_absorption.md").parent.mkdir(parents=True, exist_ok=True)
    (survey / "_analysis/prior_survey_absorption.md").write_text("Prior survey absorption and reusable KG evidence.\n", encoding="utf-8")
    (survey / "_research/search_protocol.md").write_text("query families, inclusion, exclusion, snowballing, saturation\n", encoding="utf-8")
    for rel in ("_research/groups_foundations.md", "_research/timeline_foundations.md", "_research/groups_frontier.md", "_research/timeline_frontier.md"):
        (survey / rel).write_text("Fixture research grouping and timeline evidence.\n", encoding="utf-8")
    ledger = [{"source_id": f"paper{i}", "title": f"Unique Research Paper {i}", "source_type": "paper", "evidence_tier": "primary", "chapter_hints": [1], "verification_status": "verified", "terry_link_eligible": i == 0, "terry_link": "https://terryum.ai/papers/paper0" if i == 0 else None} for i in range(30)]
    write_jsonl(survey / "_research/source_ledger.jsonl", ledger)
    from survey_harness.quality import claim_anchor_digest
    anchors = {}
    for lang in ("ko", "en"):
        digest, error = claim_anchor_digest((survey / f"book/{lang}/ch01.md").read_text(encoding="utf-8"), "ch01-c01")
        if error:
            raise AssertionError(error)
        anchors[lang] = digest
    canonical_claim = " ".join(f"enevidence{i}" for i in range(12))
    claims = [{"claim_id": "ch01-c01", "chapter": 1, "claim": canonical_claim, "risk": "high", "source_ids": ["paper0"], "verification_status": "verified", "manuscript_anchors": anchors}]
    write_jsonl(survey / "_analysis/claim_evidence.jsonl", claims)
    write_json(survey / "_analysis/chapter_source_packets/ch01.json", {"chapter": 1, "thesis": "A sufficiently specific chapter thesis for the fixture", "sections": ["history", "frontier"], "sources": [f"paper{i}" for i in range(15)], "counterevidence": ["paper15"], "visual_candidates": ["paper0:fig1"]})
    refs = [{"ch": "01", "lang": lang, "bibtex_key": f"paper{i}", "arxiv_id": f"2601.{i:05d}", "verification_status": "verified_primary_paper_url"} for lang in ("ko", "en") for i in range(8)]
    write_json(survey / "_refs_extracted.json", refs)
    images = {"schema_version": "2.0", "survey": slug, "chapters": {"ch01": [{"figure_id": f"fig{i}", "path": f"assets/figures/{name}", "insertion_anchor": f"section-{i}", "source_type": "paper_figure", "source_url": f"https://arxiv.org/abs/2601.{i:05d}", "license_basis": "academic review", "status": "inserted"} for i, name in enumerate(("first.png", "late.png"))]}}
    write_json(survey / "_workspace/image_plan.json", images)
    write_json(survey / "_quality/reviewer_scores.json", {"reviewer_id": "agent-reviewer-123", "independent": True, "dimensions": {name: {"score": 92, "evidence": "Independent fixture review evidence"} for name in ("evidence", "synthesis", "accuracy", "visuals", "links", "bilingual", "release")}})
    write_json(survey / "_quality/build_validation.json", {"passed": True, "commands": ["fixture"]})
    (survey / "_factcheck_report.md").write_text("# Factcheck\n\nChapter 1: primary-source verification passed.\n", encoding="utf-8")
    (survey / "_qa_report.md").write_text("# QA\n\nChapter 1: independent evidence review passed.\n\nREADY FOR RELEASE\n", encoding="utf-8")
    return survey
