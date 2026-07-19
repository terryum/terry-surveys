#!/usr/bin/env python3
"""Verify required survey role artifacts and minimum non-empty content.

Usage:
  python3 verify_agent_artifacts.py <slug> [--repo-root /path/to/terry-surveys]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

DEFAULT_REPO_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
REQUIRED_FILES = [
    "_research/papers_foundations.json",
    "_research/groups_foundations.md",
    "_research/timeline_foundations.md",
    "_research/papers_frontier.json",
    "_research/groups_frontier.md",
    "_research/timeline_frontier.md",
    "_research/papers.json",
    "_research/groups.md",
    "_research/timeline.md",
    "_analysis/gaps.md",
    "_analysis/novelty_matrix.md",
    "_analysis/positioning.md",
    "_analysis/prior_survey_absorption.md",
    "_workspace/04_image_manifest.json",
    "_assets_log.md",
    "_refs_extracted.json",
    "_factcheck_report.md",
    "_qa_report.md",
]


def repo_root(explicit: str | None) -> Path:
    root = Path(explicit).expanduser().resolve() if explicit else DEFAULT_REPO_ROOT
    if not (root / "build.py").exists() or not (root / "surveys").is_dir():
        raise SystemExit(f"ERROR: repo root is not terry-surveys: {root}")
    return root


def json_list_len(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("papers", "items", "figures", "images"):
            if isinstance(data.get(key), list):
                return len(data[key])
        chapters = data.get("chapters")
        if isinstance(chapters, dict):
            return sum(len(v) for v in chapters.values() if isinstance(v, list))
    return None


def chapter_nums(survey_dir: Path) -> list[int]:
    try:
        cfg = json.loads((survey_dir / "survey.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    nums = []
    for part in cfg.get("parts", []):
        for chapter in part.get("chapters", []):
            if chapter.get("num") is not None:
                nums.append(int(chapter["num"]))
    return nums


def mentioned_chapters(text: str, nums: list[int]) -> set[int]:
    found: set[int] = set()
    for num in nums:
        patterns = [
            rf"\bch{num:02d}\b",
            rf"\bChapter\s+{num}\b",
            rf"\bCh\.\s*{num}\b",
            rf"\b{num}\s*장\b",
        ]
        if any(re.search(pattern, text, flags=re.I) for pattern in patterns):
            found.add(num)
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--repo-root")
    args = parser.parse_args(argv)
    root = repo_root(args.repo_root)
    survey_dir = root / "surveys" / args.slug
    errors: list[str] = []
    if not survey_dir.is_dir():
        raise SystemExit(f"ERROR: survey not found: {survey_dir}")
    nums = chapter_nums(survey_dir)

    for rel in REQUIRED_FILES:
        path = survey_dir / rel
        if not path.exists():
            errors.append(f"missing required role artifact: {rel}")
            continue
        if path.stat().st_size < 80:
            errors.append(f"artifact too small to be credible: {rel}")

    for rel, minimum in [
        ("_research/papers_foundations.json", 1),
        ("_research/papers_frontier.json", 1),
        ("_research/papers.json", 1),
        ("_refs_extracted.json", 1),
        ("_workspace/04_image_manifest.json", 1),
    ]:
        path = survey_dir / rel
        if path.exists():
            length = json_list_len(path)
            if length is None:
                errors.append(f"{rel}: JSON artifact is not a list-like object")
            elif length < minimum:
                errors.append(f"{rel}: contains {length} items, requires >= {minimum}")

    for rel in ["_analysis/gaps.md", "_analysis/novelty_matrix.md", "_analysis/positioning.md", "_factcheck_report.md", "_qa_report.md"]:
        path = survey_dir / rel
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "TODO" in text or "TBD" in text:
                errors.append(f"{rel}: contains TODO/TBD marker")

    for rel, line_floor, chapter_ratio in [
        ("_factcheck_report.md", max(60, 4 * len(nums)), 0.75),
        ("_qa_report.md", max(80, 6 * len(nums)), 0.75),
    ]:
        path = survey_dir / rel
        if path.exists() and nums:
            text = path.read_text(encoding="utf-8", errors="ignore")
            line_count = len([line for line in text.splitlines() if line.strip()])
            if line_count < line_floor:
                errors.append(f"{rel}: too short for chapter-level evidence ({line_count} non-empty lines, requires >= {line_floor})")
            required_mentions = max(1, math.ceil(chapter_ratio * len(nums)))
            found = mentioned_chapters(text, nums)
            if len(found) < required_mentions:
                errors.append(
                    f"{rel}: lacks chapter-level audit trail "
                    f"({len(found)} chapter mentions, requires >= {required_mentions})"
                )

    if errors:
        print("ERRORS:")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"OK: required agent artifacts passed for {args.slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
