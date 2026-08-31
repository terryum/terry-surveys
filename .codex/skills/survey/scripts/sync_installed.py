#!/usr/bin/env python3
"""Atomically synchronize canonical survey and tutorial skills into Codex home."""

from __future__ import annotations

import argparse
import filecmp
import fcntl
import os
import shutil
import tempfile
import time
from pathlib import Path

CANONICAL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST_ROOT = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"
REQUIRED = {
    "survey": ("scripts/survey_harness.py", "references/orchestration-v2.md", "agents/openai.yaml"),
    "tutorial": ("scripts/tutorial_harness.py", "references/orchestration.md", "agents/openai.yaml"),
}


def visible_files(root: Path):
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"))


def diff(source: Path, destination: Path):
    source_files = set(visible_files(source))
    destination_files = set(visible_files(destination)) if destination.exists() else set()
    changed = [str(rel) for rel in sorted(source_files & destination_files) if not filecmp.cmp(source / rel, destination / rel, shallow=False)]
    return {"add": [str(x) for x in sorted(source_files - destination_files)], "change": changed, "remove": [str(x) for x in sorted(destination_files - source_files)]}


def _validate_staged(path: Path, name: str) -> None:
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n") or f"name: {name}" not in text.split("---", 2)[1]:
        raise SystemExit(f"ERROR: staged {name} skill failed frontmatter validation")
    for rel in REQUIRED[name]:
        if not (path / rel).is_file():
            raise SystemExit(f"ERROR: staged {name} skill missing {rel}")


def install(names: list[str], destination_root: Path) -> None:
    destination_root.mkdir(parents=True, exist_ok=True)
    lock_path = destination_root / ".survey-tutorial-skills-install.lock"
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        backup_root = Path(tempfile.mkdtemp(prefix="codex-survey-tutorial-skills-backup-"))
        stage_root = Path(tempfile.mkdtemp(prefix=".survey-tutorial-stage-", dir=destination_root))
        old_paths: dict[str, Path] = {}
        installed: list[str] = []
        try:
            for name in names:
                staged = stage_root / name
                shutil.copytree(CANONICAL_ROOT / name, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                _validate_staged(staged, name)
                destination = destination_root / name
                if destination.exists():
                    shutil.copytree(destination, backup_root / name)
            stamp = f"{os.getpid()}-{int(time.time())}"
            for name in names:
                destination = destination_root / name
                old = destination_root / f".{name}-skill-old-{stamp}"
                if destination.exists():
                    destination.rename(old)
                    old_paths[name] = old
            for name in names:
                (stage_root / name).rename(destination_root / name)
                installed.append(name)
        except Exception:
            for name in reversed(installed):
                shutil.rmtree(destination_root / name, ignore_errors=True)
            for name, old in old_paths.items():
                if old.exists():
                    old.rename(destination_root / name)
            raise
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
        for old in old_paths.values():
            shutil.rmtree(old, ignore_errors=True)
        print(f"SYNCED {', '.join(names)} -> {destination_root}")
        print(f"BACKUP {backup_root}")
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skill", choices=["all", "survey", "tutorial"], default="all")
    args = parser.parse_args(argv)
    names = ["survey", "tutorial"] if args.skill == "all" else [args.skill]
    destination_root = DEFAULT_DEST_ROOT.expanduser().resolve()
    for name in names:
        source = CANONICAL_ROOT / name
        destination = destination_root / name
        if destination == source or source in destination.parents or destination in source.parents:
            raise SystemExit(f"ERROR: unsafe install destination overlaps canonical source: {destination}")
        changes = diff(source, destination)
        for kind in ("add", "change", "remove"):
            for rel in changes[kind]:
                print(f"{name:8} {kind.upper():6} {rel}")
    if not args.apply:
        print("DRY RUN: pass --apply to synchronize")
        return 0
    install(names, destination_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
