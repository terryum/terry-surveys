#!/usr/bin/env python3
"""Synchronize the repo-canonical survey skill to the installed Codex skill."""

from __future__ import annotations

import argparse
import filecmp
import fcntl
import os
import shutil
import tempfile
import time
from pathlib import Path


CANONICAL = Path(__file__).resolve().parents[1]
DEFAULT_DEST = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills" / "survey"


def visible_files(root: Path):
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"))


def diff(source: Path, destination: Path):
    source_files = set(visible_files(source))
    destination_files = set(visible_files(destination)) if destination.exists() else set()
    changed = []
    for rel in sorted(source_files & destination_files):
        if not filecmp.cmp(source / rel, destination / rel, shallow=False):
            changed.append(str(rel))
    return {"add": [str(x) for x in sorted(source_files - destination_files)], "change": changed, "remove": [str(x) for x in sorted(destination_files - source_files)]}


def install(canonical: Path, destination: Path) -> None:
    lock_path = destination.parent / ".survey-skill-install.lock"
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        backup_root = Path(tempfile.mkdtemp(prefix="codex-survey-skill-backup-"))
        stage_root = Path(tempfile.mkdtemp(prefix=".survey-skill-stage-", dir=destination.parent))
        stage_skill = stage_root / "survey"
        shutil.copytree(canonical, stage_skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        skill_text = (stage_skill / "SKILL.md").read_text(encoding="utf-8")
        if not skill_text.startswith("---\n") or "name: survey" not in skill_text.split("---", 2)[1]:
            shutil.rmtree(stage_root, ignore_errors=True)
            raise SystemExit("ERROR: staged skill failed frontmatter validation")
        for required in ("scripts/survey_harness.py", "references/orchestration-v2.md", "agents/openai.yaml"):
            if not (stage_skill / required).is_file():
                shutil.rmtree(stage_root, ignore_errors=True)
                raise SystemExit(f"ERROR: staged skill missing {required}")
        if destination.exists():
            shutil.copytree(destination, backup_root / "survey")
        old = destination.with_name(f".survey-skill-old-{os.getpid()}-{int(time.time())}")
        try:
            if destination.exists():
                destination.rename(old)
            stage_skill.rename(destination)
        except Exception:
            if not destination.exists() and old.exists():
                old.rename(destination)
            raise
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
        print(f"SYNCED {canonical} -> {destination}")
        print(f"BACKUP {backup_root / 'survey'}")
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    destination = DEFAULT_DEST.expanduser().resolve()
    canonical = CANONICAL.resolve()
    if destination == canonical or canonical in destination.parents or destination in canonical.parents:
        raise SystemExit(f"ERROR: unsafe install destination overlaps canonical source: {destination}")
    changes = diff(CANONICAL, destination)
    for kind in ("add", "change", "remove"):
        for rel in changes[kind]:
            print(f"{kind.upper():6} {rel}")
    if not args.apply:
        print("DRY RUN: pass --apply to synchronize")
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    install(canonical, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
