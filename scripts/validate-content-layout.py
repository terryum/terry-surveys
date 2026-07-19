#!/usr/bin/env python3
"""Validate the contract between the public framework and private contents."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "../terry-surveys-contents").resolve()
    surveys = root / "surveys"
    if not (root / ".git").exists() or not surveys.is_dir():
        raise SystemExit(f"not a survey contents repository: {root}")
    errors: list[str] = []
    slugs: list[str] = []
    for path in sorted(surveys.iterdir()):
        config_path = path / "survey.json"
        if not path.is_dir() or not config_path.is_file():
            continue
        slugs.append(path.name)
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid survey.json: {exc}")
            continue
        if config.get("github_repo") != "terryum/terry-surveys-contents":
            errors.append(f"{path.name}: github_repo is not the canonical contents repository")
        if config.get("github_repo_visibility") != "private":
            errors.append(f"{path.name}: github_repo_visibility must be private")
        if (path / ".github").exists():
            errors.append(f"{path.name}: per-survey .github directory must be centralized")
    if not slugs:
        errors.append("no survey directories found")
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors), file=sys.stderr)
        return 1
    print(f"validated private content layout: {len(slugs)} surveys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
