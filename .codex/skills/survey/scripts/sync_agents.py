#!/usr/bin/env python3
"""sync_agents.py — agent template → per-survey .claude/agents/ 동기화.

Usage:
    python3 sync_agents.py [<slug> | --all] [--dry-run] [--retrofit] [--apply]
                           [--repo-root /path/to/terry-surveys] [--skill-dir /path/to/skill]

동작:
    - <slug>  : 해당 서베이만 대상. 생략 시 모든 서베이 처리 대상.
    - --all   : 모든 서베이 (surveys/*).
    - --dry-run: diff만 출력 (기본값).
    - --apply : 실제 파일 수정.
    - --retrofit: 대상 서베이에 .claude/agents/가 없으면 새로 생성하고 placeholder 치환.

Placeholder 보존 전략:
    템플릿(agent-template/*.md)의 placeholder {{DOMAIN}} 등은 공통 영역이므로 sync 시
    per-survey 값({{DOMAIN}} 치환된 값)은 **보존**하고, 나머지 공통 섹션만 템플릿
    기준으로 업데이트한다.

    구현: 템플릿 파일에는 원본 {{...}}가 있고, per-survey 파일에는 치환된 값이 있음.
    1) 템플릿에서 placeholder 위치 추출.
    2) per-survey 파일에서 그 위치에 어떤 값이 있는지 추출 → 보존 dict.
    3) 템플릿에 보존 dict로 재치환 → 새 per-survey 파일 생성.
    4) 새 vs 현재 per-survey 파일을 diff 출력. --apply 시 실제 쓰기.

Placeholder가 여러 번 등장할 수 있으므로 치환 값은 per-placeholder **하나의 canonical
value**로 취급 (여러 다른 값이 섞여 있으면 경고하고 첫 값을 채택).

이 스크립트는 도메인 주입 값(slug, domain, chapters, terms)을 per-survey에서 **그대로**
뽑아내므로, `survey.json`의 title·description·chapter 구조를 미리 정리해두는 것이
best effort. 주입 값이 없으면 placeholder의 기본값("<fill in ...>")을 유지한다.
"""

import argparse
import difflib
import os
import re
import sys
import json
import hashlib
from pathlib import Path

DEFAULT_REPO_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
REPO_ROOT = DEFAULT_REPO_ROOT
SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_DIR / "references/agent-template"
SURVEYS_DIR = REPO_ROOT / "surveys"
# Template -> output-file mapping.
# deep-researcher.md is expanded twice with RESEARCHER_ROLE = foundations|frontier
# to produce deep-researcher-foundations.md + deep-researcher-frontier.md.
AGENT_SPECS = [
    # (template_filename_without_ext, output_filename_without_ext, extra_values_dict)
    ("kg-mapper",       "kg-mapper",       {}),
    ("deep-researcher", "deep-researcher-foundations", {"RESEARCHER_ROLE": "foundations"}),
    ("deep-researcher", "deep-researcher-frontier",    {"RESEARCHER_ROLE": "frontier"}),
    ("evidence-librarian", "evidence-librarian", {}),
    ("book-writer",      "book-writer",      {}),
    ("image-curator",    "image-curator",    {}),
    ("fact-checker",     "fact-checker",     {}),
    ("qa-reviewer",      "qa-reviewer",      {}),
]
# Legacy alias for external callers that imported AGENT_NAMES.
AGENT_NAMES = [out for (_, out, _) in AGENT_SPECS]
PLACEHOLDERS = ["{{SURVEY_SLUG}}", "{{DOMAIN}}", "{{CHAPTERS}}", "{{TERMS}}", "{{SURVEY_DIR}}", "{{RESEARCHER_ROLE}}"]
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")


def configure_paths(repo_root=None, skill_dir=None):
    global REPO_ROOT, SKILL_DIR, TEMPLATE_DIR, SURVEYS_DIR
    if repo_root:
        REPO_ROOT = Path(repo_root).expanduser().resolve()
    elif DEFAULT_REPO_ROOT.exists():
        REPO_ROOT = DEFAULT_REPO_ROOT
    else:
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "build.py").exists() and (parent / "surveys").is_dir():
                REPO_ROOT = parent
                break
    if not (REPO_ROOT / "build.py").exists() or not (REPO_ROOT / "surveys").is_dir():
        raise SystemExit(f"ERROR: repo root is not terry-surveys: {REPO_ROOT}")

    SKILL_DIR = Path(skill_dir).expanduser().resolve() if skill_dir else Path(__file__).resolve().parents[1]
    TEMPLATE_DIR = SKILL_DIR / "references/agent-template"
    SURVEYS_DIR = REPO_ROOT / "surveys"
    if not TEMPLATE_DIR.is_dir():
        legacy = REPO_ROOT / ".claude/skills/survey/references/agent-template"
        if legacy.is_dir():
            TEMPLATE_DIR = legacy
        else:
            raise SystemExit(f"ERROR: agent-template directory not found: {TEMPLATE_DIR}")


def list_survey_slugs():
    return sorted(
        p.name for p in SURVEYS_DIR.iterdir()
        if p.is_dir() and (p / "survey.json").exists()
    )


def derive_terms(slug: str, limit: int = 24) -> str:
    terms = []
    for rel in (Path('book') / 'ko' / 'glossary.md', Path('book') / 'en' / 'glossary.md'):
        path = SURVEYS_DIR / slug / rel
        if not path.exists():
            continue
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw.strip().lstrip('-').strip()
            if not line or line.startswith('#'):
                continue
            line = re.split(r'[:：]| - | — ', line, maxsplit=1)[0].strip('`* ')
            if 2 <= len(line) <= 60 and line not in terms:
                terms.append(line)
            if len(terms) >= limit:
                break
        if len(terms) >= limit:
            break
    return ', '.join(terms) if terms else f"<fill in from surveys/{slug}/book/{{ko,en}}/glossary.md>"


def derive_domain_context(slug: str) -> dict:
    """survey.json에서 sync용 placeholder 기본값을 추출."""
    sjson = SURVEYS_DIR / slug / "survey.json"
    ctx = {
        "SURVEY_SLUG": slug,
        "DOMAIN": f"<set description in surveys/{slug}/survey.json>",
        "CHAPTERS": f"<fill in after chapter plan; see surveys/{slug}/survey.json>",
        "TERMS": derive_terms(slug),
        "SURVEY_DIR": f"surveys/{slug}",
    }
    if not sjson.exists():
        return ctx
    try:
        cfg = json.loads(sjson.read_text(encoding="utf-8"))
    except Exception:
        return ctx
    desc = cfg.get("description", {})
    if isinstance(desc, dict):
        # prefer en then ko for agent readability
        d = desc.get("en") or desc.get("ko") or ""
    else:
        d = str(desc)
    if d:
        ctx["DOMAIN"] = d

    # chapters summary from parts[].chapters[]
    chapter_parts = []
    for part in cfg.get("parts", []):
        for ch in part.get("chapters", []):
            num = ch.get("num")
            title = ch.get("title", {})
            tstr = title.get("en") or title.get("ko") if isinstance(title, dict) else str(title)
            if num and tstr:
                chapter_parts.append(f"Ch{num}: {tstr}")
    if chapter_parts:
        ctx["CHAPTERS"] = ", ".join(chapter_parts)

    return ctx


def build_pattern_from_template(template_text: str):
    """템플릿을 placeholder 경계로 쪼개고, 각 placeholder 이름을 리턴."""
    parts = []  # list of ("literal", text) or ("ph", name)
    pos = 0
    for m in PLACEHOLDER_RE.finditer(template_text):
        if m.start() > pos:
            parts.append(("literal", template_text[pos:m.start()]))
        parts.append(("ph", m.group(1)))
        pos = m.end()
    if pos < len(template_text):
        parts.append(("literal", template_text[pos:]))
    return parts


def extract_values_from_survey(survey_text: str, parts):
    """템플릿 parts를 기준으로 현재 survey 파일에서 각 placeholder 값을 역추출.

    가장 간단한 전략: literal 세그먼트를 앵커로 사이 값을 뽑는다.
    literal이 충분히 고유해야 동작한다 — 템플릿이 복잡해지면 실패 가능.
    실패 시 빈 dict 반환 → 호출자가 기본값으로 폴백.
    """
    values = {}
    i = 0
    pos = 0
    while i < len(parts):
        kind, val = parts[i]
        if kind == "literal":
            idx = survey_text.find(val, pos)
            if idx < 0:
                # 템플릿 구조가 크게 바뀌었음
                return None
            pos = idx + len(val)
            i += 1
        else:
            # placeholder: 다음 literal을 앵커로
            name = val
            nxt_literal = None
            for j in range(i + 1, len(parts)):
                if parts[j][0] == "literal":
                    nxt_literal = parts[j][1]
                    break
            if nxt_literal is None:
                # 파일 끝까지가 이 placeholder 값
                values.setdefault(name, survey_text[pos:])
                pos = len(survey_text)
            else:
                end = survey_text.find(nxt_literal, pos)
                if end < 0:
                    return None
                candidate = survey_text[pos:end]
                if name in values and values[name] != candidate:
                    # placeholder가 여러 번 등장했는데 값이 다름 → 경고하고 첫 값 유지
                    pass
                else:
                    values[name] = candidate
                pos = end
            i += 1
    return values


def render_template(template_text: str, values: dict) -> str:
    def repl(m):
        name = m.group(1)
        return values.get(name, m.group(0))
    return PLACEHOLDER_RE.sub(repl, template_text)


def diff(a_text: str, b_text: str, fromfile: str, tofile: str) -> str:
    return "".join(
        difflib.unified_diff(
            a_text.splitlines(keepends=True),
            b_text.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )


def sync_one(slug: str, apply: bool, retrofit: bool, force_context: bool = False) -> dict:
    agents_dir = SURVEYS_DIR / slug / ".claude/agents"
    results = {"slug": slug, "actions": [], "diffs": []}
    if not agents_dir.exists():
        if not retrofit:
            results["actions"].append(f"SKIP: no .claude/agents/ and --retrofit not set")
            return results
        if apply:
            agents_dir.mkdir(parents=True, exist_ok=True)
        results["actions"].append(f"RETROFIT: creating .claude/agents/")

    ctx_defaults = derive_domain_context(slug)
    # Legacy cleanup: older surveys may have a single `deep-researcher.md` from the
    # pre-split template. Rename to `deep-researcher-foundations.md` so the
    # foundations role keeps the existing per-survey context rather than regenerating.
    legacy_single = agents_dir / "deep-researcher.md"
    legacy_target = agents_dir / "deep-researcher-foundations.md"
    if legacy_single.exists() and not legacy_target.exists():
        if apply:
            legacy_single.rename(legacy_target)
            results["actions"].append("MIGRATED deep-researcher.md → deep-researcher-foundations.md")
        else:
            results["actions"].append("WOULD MIGRATE deep-researcher.md → deep-researcher-foundations.md")

    for template_name, out_name, extra_values in AGENT_SPECS:
        tpath = TEMPLATE_DIR / f"{template_name}.md"
        spath = agents_dir / f"{out_name}.md"
        template_text = tpath.read_text(encoding="utf-8")
        parts = build_pattern_from_template(template_text)

        if spath.exists():
            current_text = spath.read_text(encoding="utf-8")
            extracted = None if force_context else extract_values_from_survey(current_text, parts)
            if force_context:
                values = dict(ctx_defaults)
                results["actions"].append(f"FORCE-CONTEXT {out_name}: using survey.json/glossary values")
            elif extracted is None:
                values = dict(ctx_defaults)
                results["actions"].append(
                    f"WARN {out_name}: template structure diverged — using ctx defaults"
                )
            else:
                stale = {k: v for k, v in extracted.items() if v and ("One-line core question" in v or "First Chapter" in v or "<fill in" in v)}
                values = {**ctx_defaults, **{k: v for k, v in extracted.items() if v and k not in stale}}
                if stale:
                    results["actions"].append(f"REPLACED stale placeholder context in {out_name}: {', '.join(sorted(stale))}")
        else:
            current_text = ""
            values = dict(ctx_defaults)

        # extra_values (e.g. RESEARCHER_ROLE) are source-of-truth from AGENT_SPECS,
        # never overridden by legacy extracted values.
        values.update(extra_values)

        new_text = render_template(template_text, values)
        if current_text != new_text:
            d = diff(current_text, new_text, f"{spath} (current)", f"{spath} (new)")
            results["diffs"].append(d)
            if apply:
                spath.write_text(new_text, encoding="utf-8")
                results["actions"].append(f"WROTE {out_name}.md")
            else:
                results["actions"].append(f"WOULD WRITE {out_name}.md")
        else:
            results["actions"].append(f"UNCHANGED {out_name}.md")
    return results



def file_sha256(path: Path):
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_context_sync(slug: str) -> Path:
    survey_dir = SURVEYS_DIR / slug
    files = []
    for path in [
        survey_dir / "survey.json",
        survey_dir / "CLAUDE.md",
        survey_dir / "book" / "ko" / "glossary.md",
        survey_dir / "book" / "en" / "glossary.md",
    ]:
        if path.exists():
            files.append(path)
    files.extend(sorted(TEMPLATE_DIR.glob("*.md")))
    files.extend(sorted((survey_dir / ".claude" / "agents").glob("*.md")))
    payload = {
        "slug": slug,
        "files": [
            {
                "path": str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path),
                "sha256": file_sha256(path),
            }
            for path in files
        ],
    }
    out = survey_dir / "_workspace" / "context_sync.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def unresolved_agent_context(slug: str) -> list[str]:
    markers = [
        "One-line core question",
        "Ch1: First Chapter",
        "<fill in",
    ]
    errors = []
    agents_dir = SURVEYS_DIR / slug / ".claude" / "agents"
    for path in sorted(agents_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for marker in markers) or PLACEHOLDER_RE.search(text):
            errors.append(f"{path.relative_to(SURVEYS_DIR / slug)} has unresolved scaffold context")
    return errors

def main(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("slug", nargs="?", help="survey slug (omit with --all for every survey)")
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--retrofit", action="store_true",
                   help="create .claude/agents/ for surveys that lack one")
    p.add_argument("--force-context", action="store_true",
                   help="discard stale extracted placeholder values and regenerate SURVEY_SLUG/DOMAIN/CHAPTERS/TERMS/SURVEY_DIR from survey.json and glossary")
    p.add_argument("--check", action="store_true", help="return non-zero if agents would change or scaffold placeholders remain")
    p.add_argument("--write-context-sync", action="store_true", help="write _workspace/context_sync.json with source and generated-agent hashes")
    p.add_argument("--repo-root", help="path to terry-surveys repo")
    p.add_argument("--skill-dir", help="path to the Codex survey skill directory")
    args = p.parse_args(argv)
    configure_paths(args.repo_root, args.skill_dir)

    if args.apply and args.dry_run:
        p.error("--apply and --dry-run are mutually exclusive")
    if args.check and args.apply:
        p.error("--check is read-only; do not combine with --apply")
    if args.check and args.apply:
        p.error("--check is read-only; do not combine with --apply")
    # default: dry-run if neither
    apply = args.apply

    if args.all:
        slugs = list_survey_slugs()
    elif args.slug:
        slugs = [args.slug]
    else:
        p.error("provide <slug> or --all")

    any_changes = False
    for slug in slugs:
        res = sync_one(slug, apply=apply, retrofit=args.retrofit, force_context=args.force_context)
        print(f"\n=== {slug} ===")
        for action in res["actions"]:
            print(f"  • {action}")
        for d in res["diffs"]:
            if d:
                any_changes = True
                print(d)
    check_errors = []
    if args.write_context_sync:
        for slug in slugs:
            out = write_context_sync(slug)
            print(f"WROTE {out}")
    if args.check:
        if any_changes:
            check_errors.append("agent templates are out of sync; rerun with --apply")
        for slug in slugs:
            check_errors.extend(unresolved_agent_context(slug))
        if check_errors:
            print("\nCHECK FAILED:")
            for error in check_errors:
                print(f"  - {error}")
            return 1
    check_errors = []
    if args.write_context_sync:
        for slug in slugs:
            out = write_context_sync(slug)
            print(f"WROTE {out}")
    if args.check:
        if any_changes:
            check_errors.append("agent templates are out of sync; rerun with --apply")
        for slug in slugs:
            check_errors.extend(unresolved_agent_context(slug))
        if check_errors:
            print("\nCHECK FAILED:")
            for error in check_errors:
                print(f"  - {error}")
            return 1
    if not apply and any_changes:
        print("\n(dry-run) pass --apply to write the changes above.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
