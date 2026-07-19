#!/usr/bin/env python3
"""Fail if a survey's generated agent context is still scaffold/stale.

Usage:
  python3 check_bootstrap_readiness.py <slug> [--repo-root /path/to/terry-surveys]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_REPO_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
AGENTS = {
    "book-writer.md",
    "deep-researcher-foundations.md",
    "deep-researcher-frontier.md",
    "evidence-librarian.md",
    "fact-checker.md",
    "image-curator.md",
    "kg-mapper.md",
    "qa-reviewer.md",
}
BAD_PATTERNS = [
    r"One-line core question",
    r"Ch1: First Chapter",
    r"<fill in",
    r"\{\{[A-Z_]+\}\}",
]


def repo_root(explicit: str | None) -> Path:
    root = Path(explicit).expanduser().resolve() if explicit else DEFAULT_REPO_ROOT
    if not (root / "build.py").exists() or not (root / "surveys").is_dir():
        raise SystemExit(f"ERROR: repo root is not terry-surveys: {root}")
    return root


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: invalid JSON ({exc})")
        return None


def chapter_titles(cfg: dict) -> list[str]:
    titles: list[str] = []
    for part in cfg.get("parts", []):
        for ch in part.get("chapters", []):
            num = ch.get("num")
            title = ch.get("title", {})
            text = title.get("en") or title.get("ko") if isinstance(title, dict) else str(title)
            if num and text:
                titles.append(f"Ch{num}: {text}")
    return titles


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--repo-root")
    args = parser.parse_args(argv)

    root = repo_root(args.repo_root)
    survey_dir = root / "surveys" / args.slug
    errors: list[str] = []
    warnings: list[str] = []
    if not survey_dir.is_dir():
        raise SystemExit(f"ERROR: survey not found: {survey_dir}")

    cfg = load_json(survey_dir / "survey.json", errors) if (survey_dir / "survey.json").exists() else None
    titles = chapter_titles(cfg or {})
    if len(titles) < 2:
        errors.append("survey.json still looks like a one-chapter scaffold")

    agents_dir = survey_dir / ".claude" / "agents"
    if not agents_dir.is_dir():
        errors.append("missing .claude/agents directory")
    else:
        present = {p.name for p in agents_dir.glob("*.md")}
        missing = sorted(AGENTS - present)
        extra_single = "deep-researcher.md" in present
        if missing:
            errors.append("missing agent file(s): " + ", ".join(missing))
        if extra_single:
            warnings.append("legacy deep-researcher.md still present")

        joined_titles = "\n".join(titles[:8])
        for path in sorted(agents_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in BAD_PATTERNS:
                if re.search(pattern, text):
                    errors.append(f"{path.relative_to(survey_dir)} contains unresolved scaffold marker: {pattern}")
                    break
            if titles and not any(title in text for title in titles[: min(3, len(titles))]):
                errors.append(
                    f"{path.relative_to(survey_dir)} does not include current chapter map "
                    f"(expected one of: {joined_titles})"
                )

    if warnings:
        print("WARNINGS:")
        for item in warnings:
            print(f"  - {item}")
    if errors:
        print("ERRORS:")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"OK: bootstrap readiness passed for {args.slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
