"""Deterministic action-first tutorial gates."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _rough_words(text: str) -> int:
    text = re.sub(r"^---\s*$.*?^---\s*$", "", text, count=1, flags=re.M | re.S)
    before_action = re.split(r"\*\*(?:Action|행동)\*\*", text, maxsplit=1)[0]
    english = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", before_action)
    korean = re.findall(r"[가-힣]+", before_action)
    return len(english) + sum(max(1, len(chunk) // 2) for chunk in korean)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def content_digest(base: Path) -> str:
    hasher = hashlib.sha256()
    survey = json.loads((base / "survey.json").read_text(encoding="utf-8"))
    survey.pop("visibility", None)
    hasher.update(b"survey.json")
    hasher.update(json.dumps(survey, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    paths = [base / "_tutorial/roadmap.md", base / "_tutorial/environment_matrix.json", base / "_tutorial/source_ledger.jsonl"]
    paths.extend(sorted((base / "book").glob("**/ch*.md")))
    paths.extend(sorted((base / "_tutorial/chapter_packets").glob("ch*.json")))
    paths.extend(sorted((base / "labs").glob("ch*/**/*")))
    for path in paths:
        if path.is_file():
            hasher.update(str(path.relative_to(base)).encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def evaluate(base: Path) -> dict[str, Any]:
    config = json.loads((base / "survey.json").read_text(encoding="utf-8"))
    ready = [int(chapter["num"]) for part in config.get("parts", []) for chapter in part.get("chapters", []) if chapter.get("status", "ready") == "ready"]
    blockers = []
    ledger_path = base / "_tutorial/source_ledger.jsonl"
    ledger = _jsonl(ledger_path) if ledger_path.is_file() else []
    for chapter in ready:
        packet_path = base / f"_tutorial/chapter_packets/ch{chapter:02d}.json"
        verification_path = base / f"_quality/example_verification/ch{chapter:02d}.json"
        if not packet_path.is_file():
            blockers.append({"id": f"packet-ch{chapter:02d}", "owner": "lab_builder", "message": "chapter packet missing"})
            continue
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        if float(packet.get("first_success_minutes", 999)) > 10:
            blockers.append({"id": f"first-success-ch{chapter:02d}", "owner": "lab_builder", "message": "first success exceeds 10 minutes"})
        steps = packet.get("steps", [])
        for index, step in enumerate(steps, 1):
            if any(not step.get(field) for field in ("action", "expected", "recovery", "validation")):
                blockers.append({"id": f"step-contract-ch{chapter:02d}-{index}", "owner": "lab_builder", "message": "action/expected/recovery/validation incomplete"})
        texts = {}
        for lang in ("ko", "en"):
            path = base / f"book/{lang}/ch{chapter:02d}.md"
            if not path.is_file():
                blockers.append({"id": f"missing-{lang}-ch{chapter:02d}", "owner": "chapter_writer", "message": "ready chapter manuscript missing"})
                continue
            text = path.read_text(encoding="utf-8")
            texts[lang] = text
            if _rough_words(text) > 200 or not re.search(r"\*\*(?:Action|행동)\*\*", text):
                blockers.append({"id": f"first-action-{lang}-ch{chapter:02d}", "owner": "chapter_writer", "message": "first action is missing or appears after 200 rough words"})
            action_count = len(re.findall(r"\*\*(?:Action|행동)\*\*", text))
            expected_count = len(re.findall(r"\*\*(?:Expected|기대 결과)\*\*", text))
            recovery_count = len(re.findall(r"\*\*(?:Recovery|복구)\*\*", text))
            if not action_count or not (action_count == expected_count == recovery_count):
                blockers.append({"id": f"step-triad-{lang}-ch{chapter:02d}", "owner": "chapter_writer", "message": "each action needs expected output and recovery"})
            if not re.search(r"^##\s+(?:Sources|출처)\s*$", text, re.M):
                blockers.append({"id": f"sources-{lang}-ch{chapter:02d}", "owner": "source_version_researcher", "message": "short Sources section missing"})
        if set(texts) == {"ko", "en"}:
            ko_steps = len(re.findall(r"\*\*행동\*\*", texts["ko"]))
            en_steps = len(re.findall(r"\*\*Action\*\*", texts["en"]))
            if ko_steps != en_steps:
                blockers.append({"id": f"parity-ch{chapter:02d}", "owner": "pedagogy_reviewer", "message": "KO/EN action counts differ"})
        official = [row for row in ledger if chapter in row.get("chapters", []) and row.get("official") is True and str(row.get("url", "")).startswith("https://")]
        if not official:
            blockers.append({"id": f"official-source-ch{chapter:02d}", "owner": "source_version_researcher", "message": "no official HTTPS source recorded for chapter"})
        if not verification_path.is_file():
            blockers.append({"id": f"verification-ch{chapter:02d}", "owner": "example_verifier", "message": "verification evidence missing"})
        else:
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            if verification.get("broken_links"):
                blockers.append({"id": f"broken-links-ch{chapter:02d}", "owner": "example_verifier", "message": "official source link is broken"})
            reader_required = any(check.get("status") == "reader_test_required" for check in verification.get("checks", []))
            if reader_required and any(re.search(r"(?:검증 완료|테스트 완료|fully tested)", text, re.I) for text in texts.values()):
                blockers.append({"id": f"false-tested-claim-ch{chapter:02d}", "owner": "example_verifier", "message": "reader-test-required work is described as tested"})
    return {
        "schema_version": "1.0",
        "passed": not blockers,
        "ready_chapters": ready,
        "hard_blockers": blockers,
        "content_digest": content_digest(base),
    }


def write_scorecard(base: Path, scorecard: dict[str, Any]) -> Path:
    path = base / "_quality/tutorial_scorecard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
