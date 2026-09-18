#!/usr/bin/env python3
"""Read-only audit of Codex skill discovery; pass --root for additional skill roots."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEAD_API = re.compile(r"\b(?:TeamCreate|TaskCreate|TaskUpdate|SendMessage)\s*\(")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def audit(roots: list[Path]) -> dict:
    """Deduplicate symlink aliases, but report independently discoverable copies."""
    findings: list[dict] = []
    skills: dict[str, list[str]] = {}
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        entries = [root] if (root / "SKILL.md").is_file() or (root / "skill.md").is_file() else sorted(root.iterdir())
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_symlink() and not entry.exists():
                findings.append({"kind": "broken-symlink", "path": str(entry)})
                continue
            if not entry.is_dir():
                continue
            canonical = entry.resolve()
            if canonical in seen:
                continue
            seen.add(canonical)
            skill = entry / "SKILL.md"
            if not skill.is_file():
                if (entry / "skill.md").is_file():
                    findings.append({"kind": "skill-filename-case", "path": str(entry / "skill.md")})
                    skill = entry / "skill.md"
                else:
                    continue
            text = skill.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            match = re.search(r"(?m)^name:\s*['\"]?([^\n'\"]+)", parts[1] if text.startswith("---") and len(parts) == 3 else "")
            name = match.group(1).strip() if match else entry.name
            skills.setdefault(name, []).append(str(skill.resolve()))
            if not match:
                findings.append({"kind": "missing-name", "path": str(skill)})
            # Scan skill resources, not generated caches or embedded source projects.
            for path in sorted(entry.rglob("*")):
                if path.is_symlink() and not path.exists():
                    findings.append({"kind": "broken-symlink", "path": str(path)})
                if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml"}:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
                fenced = False
                for number, line in enumerate(content.splitlines(), 1):
                    if ".Codex" in line:
                        findings.append({"kind": "codex-path-case", "path": str(path), "line": number})
                    if DEAD_API.search(line):
                        findings.append({"kind": "unavailable-runtime-api", "path": str(path), "line": number})
                    if line.lstrip().startswith(("```", "~~~")):
                        fenced = not fenced
                    link_text = "" if fenced else re.sub(r"`[^`]*`", "", line)
                    for link in LINK.findall(link_text):
                        target = link.split("#", 1)[0].strip("<>")
                        if not target or re.match(r"[a-zA-Z][\w+.-]*:", target) or any(x in target for x in ("<", "{", "*", " ")):
                            continue
                        if target.startswith("/"):
                            continue  # Host-dependent absolute references are not portable link checks.
                        if not (path.parent / target).exists():
                            findings.append({"kind": "broken-relative-link", "path": str(path), "line": number, "target": target})
    for name, paths in sorted(skills.items()):
        if len(paths) > 1:
            findings.append({"kind": "duplicate-name", "name": name, "paths": paths})
    return {"roots": [str(root) for root in roots], "skills": skills, "findings": findings, "ok": not findings}


def audit_agents(roots: list[Path]) -> list[dict]:
    """Surface portability hazards without changing native runtime settings."""
    findings = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.toml")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if ".Codex" in line or DEAD_API.search(line):
                    findings.append({"kind": "legacy-native-agent-instruction", "path": str(path), "line": number})
                if re.match(r"\s*model\s*=", line):
                    findings.append({"kind": "pinned-agent-model", "path": str(path), "line": number})
                if re.search(r"TacGlove|TacTeleOp|TacPlay|2023.2026|촉각 센싱, 사람 손", line):
                    findings.append({"kind": "book-specific-agent-context", "path": str(path), "line": number})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, help="Skill directory or container root; repeat for paper/write or other repositories. Overrides defaults.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--agent-root", action="append", type=Path, help="Optional native-agent directory; read-only portability warnings")
    args = parser.parse_args(argv)
    roots = args.root or [ROOT / ".agents/skills", ROOT / ".codex/skills", Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"]
    result = audit([path.expanduser() for path in roots])
    result["agent_warnings"] = audit_agents([path.expanduser() for path in (args.agent_root or [])])
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"AUDIT {len(result['skills'])} skill names, {len(result['findings'])} findings")
        for finding in result["findings"]:
            print(json.dumps(finding, ensure_ascii=False))
        for finding in result["agent_warnings"]:
            print("AGENT WARNING " + json.dumps(finding, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
