#!/usr/bin/env python3
"""Minimal dependency-free validation for a Codex SKILL.md package."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    skill_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".codex/skills/survey")
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise SystemExit(f"missing skill file: {skill_file}")
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        raise SystemExit("SKILL.md must start with YAML frontmatter")
    frontmatter = match.group(1)
    for field in ("name", "description"):
        if not re.search(rf"^{field}:\s*\S", frontmatter, flags=re.MULTILINE):
            raise SystemExit(f"SKILL.md frontmatter is missing {field}")
    if not any(skill_dir.joinpath(name).is_dir() for name in ("references", "scripts")):
        raise SystemExit("skill must include references/ or scripts/")
    print(f"validated: {skill_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
