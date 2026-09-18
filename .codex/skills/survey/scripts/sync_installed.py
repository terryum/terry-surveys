#!/usr/bin/env python3
"""Atomically synchronize canonical survey and tutorial skills into Codex home."""

from __future__ import annotations

import argparse
import filecmp
import fcntl
import importlib.util
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

_SOURCE_PROJECT = Path(__file__).resolve().parents[4]
PROJECT_ROOT = Path(os.environ.get("TERRY_SURVEYS_ROOT", _SOURCE_PROJECT if (_SOURCE_PROJECT / "survey_harness").is_dir() else "/Users/terrytaewoongum/Codes/personal/terry-surveys")).expanduser().resolve()
CANONICAL_ROOT = PROJECT_ROOT / ".codex/skills"
DEFAULT_DEST_ROOT = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"
LEGACY_ORCHESTRATORS = ("tactile-book-orchestrator", "research-book-orchestrator", "survey-lite")
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


def reconcile_discovery(names: list[str], project_root: Path, archive_legacy: bool = False) -> None:
    """Preserve old project skills outside discovery before linking canonical skills."""
    discovery = project_root / ".agents/skills"
    discovery.mkdir(parents=True, exist_ok=True)
    backup_root = Path(tempfile.mkdtemp(prefix="codex-skill-discovery-backup-"))
    manifest = []
    changed = []
    try:
        for name in names + (list(LEGACY_ORCHESTRATORS) if archive_legacy else []):
            target = discovery / name
            source = CANONICAL_ROOT / name
            if name in names and target.is_symlink() and target.resolve() == source.resolve():
                continue
            if target.exists() or target.is_symlink():
                archived = backup_root / name
                # Copy first: cross-filesystem moves must never erase the only copy.
                if target.is_symlink():
                    archived.symlink_to(os.readlink(target))
                    target.unlink()
                else:
                    shutil.copytree(target, archived, symlinks=True)
                    shutil.rmtree(target)
                manifest.append({"original": str(target), "backup": str(archived), "action": "canonical-link" if name in names else "archive-legacy"})
            changed.append((target, backup_root / name))
            if name in names:
                target.symlink_to(os.path.relpath(source, discovery), target_is_directory=True)
        (backup_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except Exception:
        for target, archived in reversed(changed):
            if target.is_symlink():
                target.unlink()
            if archived.is_symlink():
                target.symlink_to(os.readlink(archived))
            elif archived.exists():
                shutil.copytree(archived, target, symlinks=True)
        raise
    print(f"DISCOVERY {discovery}")
    print(f"DISCOVERY BACKUP {backup_root}")


def check_discovery(names: list[str], project_root: Path) -> list[str]:
    errors = []
    for name in names:
        target = project_root / ".agents/skills" / name
        if not target.is_symlink() or target.resolve() != (CANONICAL_ROOT / name).resolve():
            errors.append(f"{target} must link to the canonical skill")
    return errors


def audit_warnings(project_root: Path) -> None:
    spec = importlib.util.spec_from_file_location("codex_discovery_audit", PROJECT_ROOT / "scripts/audit-codex-harness.py")
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.audit([project_root / ".agents/skills"])
    for finding in result["findings"]:
        print("AUDIT WARNING " + json.dumps(finding, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true", help="Fail on installed drift or canonical discovery-link drift; report other legacy findings as warnings")
    parser.add_argument("--skill", choices=["all", "survey", "tutorial"], default="all")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="Project discovery root; override for isolated tests")
    parser.add_argument("--archive-legacy", action="store_true", help="With --apply, preserve and remove three superseded project orchestrators from discovery")
    args = parser.parse_args(argv)
    names = ["survey", "tutorial"] if args.skill == "all" else [args.skill]
    destination_root = DEFAULT_DEST_ROOT.expanduser().resolve()
    project_root = args.project_root.expanduser().resolve()
    has_drift = False
    for name in names:
        source = CANONICAL_ROOT / name
        destination = destination_root / name
        if destination == source or source in destination.parents or destination in source.parents:
            raise SystemExit(f"ERROR: unsafe install destination overlaps canonical source: {destination}")
        changes = diff(source, destination)
        has_drift = has_drift or any(changes.values())
        for kind in ("add", "change", "remove"):
            for rel in changes[kind]:
                print(f"{name:8} {kind.upper():6} {rel}")
    discovery_errors = check_discovery(names, project_root)
    for error in discovery_errors:
        print(f"DISCOVERY DRIFT {error}")
    if args.check:
        audit_warnings(project_root)
        if has_drift or discovery_errors:
            print("CHECK FAILED: pass --apply to synchronize")
            return 1
        print("CHECK PASSED: installed skills and project discovery match canonical sources")
        return 0
    if not args.apply:
        print("DRY RUN: pass --apply to synchronize")
        return 0
    install(names, destination_root)
    reconcile_discovery(names, project_root, args.archive_legacy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
