#!/usr/bin/env python3
"""sync_agents.py — agent template → per-survey .claude/agents/ 동기화.

Usage:
    python3 sync_agents.py [<slug> | --all] [--dry-run] [--retrofit] [--apply]

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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_DIR = REPO_ROOT / ".claude/skills/survey/references/agent-template"
SURVEYS_DIR = REPO_ROOT / "surveys"
# Template -> output-file mapping.
# deep-researcher.md is expanded twice with RESEARCHER_ROLE = foundations|frontier
# to produce deep-researcher-foundations.md + deep-researcher-frontier.md.
AGENT_SPECS = [
    # (template_filename_without_ext, output_filename_without_ext, extra_values_dict)
    ("deep-researcher", "deep-researcher-foundations", {"RESEARCHER_ROLE": "foundations"}),
    ("deep-researcher", "deep-researcher-frontier",    {"RESEARCHER_ROLE": "frontier"}),
    ("critical-analyst", "critical-analyst", {}),
    ("book-writer",      "book-writer",      {}),
    ("image-curator",    "image-curator",    {}),
    ("fact-checker",     "fact-checker",     {}),
    ("qa-reviewer",      "qa-reviewer",      {}),
]
# Legacy alias for external callers that imported AGENT_NAMES.
AGENT_NAMES = [out for (_, out, _) in AGENT_SPECS]
PLACEHOLDERS = ["{{SURVEY_SLUG}}", "{{DOMAIN}}", "{{CHAPTERS}}", "{{TERMS}}", "{{SURVEY_DIR}}", "{{RESEARCHER_ROLE}}"]
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")


def list_survey_slugs():
    return sorted(
        p.name for p in SURVEYS_DIR.iterdir()
        if p.is_dir() and (p / "survey.json").exists()
    )


def derive_domain_context(slug: str) -> dict:
    """survey.json에서 sync용 placeholder 기본값을 추출."""
    sjson = SURVEYS_DIR / slug / "survey.json"
    ctx = {
        "SURVEY_SLUG": slug,
        "DOMAIN": f"<set description in surveys/{slug}/survey.json>",
        "CHAPTERS": f"<fill in after chapter plan; see surveys/{slug}/survey.json>",
        "TERMS": f"<fill in from surveys/{slug}/book/{{ko,en}}/glossary.md>",
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


def sync_one(slug: str, apply: bool, retrofit: bool) -> dict:
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
            extracted = extract_values_from_survey(current_text, parts)
            if extracted is None:
                values = dict(ctx_defaults)
                results["actions"].append(
                    f"WARN {out_name}: template structure diverged — using ctx defaults"
                )
            else:
                values = {**ctx_defaults, **{k: v for k, v in extracted.items() if v}}
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


def main(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("slug", nargs="?", help="survey slug (omit with --all for every survey)")
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--retrofit", action="store_true",
                   help="create .claude/agents/ for surveys that lack one")
    args = p.parse_args(argv)

    if args.apply and args.dry_run:
        p.error("--apply and --dry-run are mutually exclusive")
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
        res = sync_one(slug, apply=apply, retrofit=args.retrofit)
        print(f"\n=== {slug} ===")
        for action in res["actions"]:
            print(f"  • {action}")
        for d in res["diffs"]:
            if d:
                any_changes = True
                print(d)
    if not apply and any_changes:
        print("\n(dry-run) pass --apply to write the changes above.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
