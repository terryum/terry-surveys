#!/usr/bin/env bash
# bootstrap.sh — /survey MODE A 부트스트랩 헬퍼.
#
# 호출: bash scripts/bootstrap.sh <slug> <title_ko> <title_en> <domain> [--visibility=group --group=<grp>] [--dry-run]
#
# 역할:
#  1) python3 build.py --new <slug>  (shared/scaffold.py가 공개 구조 생성)
#     - public 흐름: terry-surveys/surveys/<slug>/ 에 직접 scaffold
#     - --visibility=group 흐름: terry-private/surveys/<slug>/ 에 scaffold + symlink
#       (필요한 정확한 이유 — 2026-04-29 physical-ai-manufacturing leak 사고)
#  2) .claude/agents/ 디렉토리 생성 + 템플릿 6개 복사
#  3) 각 agent md의 placeholder ({{SURVEY_SLUG}}, {{DOMAIN}}, {{CHAPTERS}},
#     {{TERMS}}, {{SURVEY_DIR}}) 치환
#  4) python3 build.py --index && python3 build.py --validate <slug>
#
# Placeholder 값의 출처:
#  - SURVEY_SLUG  : 첫 인자
#  - DOMAIN       : 네번째 인자 (사용자 입력)
#  - CHAPTERS     : surveys/<slug>/survey.json에서 읽어 한 줄로 요약 (Ch1: ..., Ch2: ...)
#                   (초기 스캐폴드엔 1개 챕터만 있으므로 placeholder는 "<fill in after chapter plan>"
#                    로 채우고, 챕터 구조가 확정되면 sync_agents.py로 재적용 권장)
#  - TERMS        : 초기엔 "<fill in from glossary>" placeholder. 용어집 정비 후 sync 재적용.
#  - SURVEY_DIR   : "surveys/<slug>"
#
# 이 스크립트는 실패 시 즉시 중단한다 (set -euo pipefail).

set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <slug> <title_ko> <title_en> <domain> [--visibility=group --group=<grp>] [--dry-run]" >&2
  exit 2
fi

SLUG="$1"
TITLE_KO="$2"
TITLE_EN="$3"
DOMAIN="$4"
shift 4

VISIBILITY=""
GROUP=""
DRY_RUN=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --visibility=*) VISIBILITY="${1#--visibility=}" ;;
    --group=*) GROUP="${1#--group=}" ;;
    --dry-run) DRY_RUN="--dry-run" ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$VISIBILITY" = "group" ] && [ -z "$GROUP" ]; then
  echo "ERROR: --visibility=group requires --group=<grp>" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/.claude/skills/survey/references/agent-template"
PRIVATE_ROOT="$(cd "$REPO_ROOT/../terry-private" 2>/dev/null && pwd || echo '')"

# Pick the actual scaffold target based on visibility.
# Public surveys live directly in terry-surveys; private ones live in
# terry-private and are linked back via scripts/link-private.sh.
# Strategy for private: scaffold into terry-surveys (build.py --new is
# hardcoded to surveys/<slug>/), then mv to terry-private + create symlink
# before any commit can be made. This keeps scaffold.py unchanged while
# guaranteeing private content never lands in a terry-surveys commit.
SCAFFOLD_DIR="$REPO_ROOT/surveys/$SLUG"
if [ "$VISIBILITY" = "group" ]; then
  if [ -z "$PRIVATE_ROOT" ] || [ ! -d "$PRIVATE_ROOT/surveys" ]; then
    echo "ERROR: --visibility=group requires terry-private at ../terry-private/surveys/" >&2
    echo "  clone it: git clone git@github.com:terryum/terry-private.git ../terry-private" >&2
    exit 1
  fi
  PRIVATE_TARGET="$PRIVATE_ROOT/surveys/$SLUG"
  if [ -e "$PRIVATE_TARGET" ]; then
    echo "ERROR: $PRIVATE_TARGET already exists. Aborting to avoid overwrite." >&2
    exit 1
  fi
  SURVEY_DIR="$PRIVATE_TARGET"
  SCAFFOLD_LOCATION="terry-private/surveys/$SLUG (private — symlinked back into terry-surveys)"
else
  SURVEY_DIR="$SCAFFOLD_DIR"
  SCAFFOLD_LOCATION="terry-surveys/surveys/$SLUG (public)"
fi

say() { printf "[bootstrap] %s\n" "$*"; }
run() {
  if [ "$DRY_RUN" = "--dry-run" ]; then
    printf "[dry-run] %s\n" "$*"
  else
    eval "$@"
  fi
}

# --- 1) scaffold --------------------------------------------------------
if [ -d "$SURVEY_DIR" ]; then
  say "ERROR: $SURVEY_DIR already exists. Aborting to avoid overwrite."
  exit 1
fi
if [ "$VISIBILITY" = "group" ] && [ -d "$SCAFFOLD_DIR" ]; then
  say "ERROR: $SCAFFOLD_DIR already exists (would collide with scaffold step). Aborting."
  exit 1
fi

say "scaffold target: $SCAFFOLD_LOCATION"
say "scaffolding via build.py --new $SLUG"
run "cd '$REPO_ROOT' && python3 build.py --new '$SLUG'"

# Private flow: relocate scaffold to terry-private and symlink back.
# We do this BEFORE any further file writes so private content is only
# ever rooted in terry-private from this point on.
if [ "$VISIBILITY" = "group" ]; then
  say "relocating scaffold to terry-private + creating symlink (private flow)"
  if [ "$DRY_RUN" = "--dry-run" ]; then
    printf "[dry-run] would: mv %s %s\n" "$SCAFFOLD_DIR" "$PRIVATE_TARGET"
    printf "[dry-run] would: ln -s ../../terry-private/surveys/%s %s\n" "$SLUG" "$SCAFFOLD_DIR"
  else
    mv "$SCAFFOLD_DIR" "$PRIVATE_TARGET"
    ln -s "../../terry-private/surveys/$SLUG" "$SCAFFOLD_DIR"
  fi
fi

# --- 2) .claude/agents/ ------------------------------------------------
say "creating .claude/agents/ and copying template × 6"
run "mkdir -p '$SURVEY_DIR/.claude/agents'"
for f in deep-researcher critical-analyst book-writer image-curator fact-checker qa-reviewer; do
  run "cp '$TEMPLATE_DIR/$f.md' '$SURVEY_DIR/.claude/agents/$f.md'"
done

# --- 3) placeholder 치환 -----------------------------------------------
#
# 초기에는 {{CHAPTERS}} / {{TERMS}}는 확정되지 않았을 가능성이 높으므로,
# "<fill in after chapter plan>" / "<fill in from glossary>"로 채워두고
# 이후 survey.json 업데이트 후 `sync_agents.py --apply <slug>`로 재적용한다.
say "substituting placeholders in agent files"
CHAPTERS_VALUE="<fill in after chapter plan; run: /survey --sync-agents $SLUG>"
TERMS_VALUE="<fill in from glossary; run: /survey --sync-agents $SLUG>"
SURVEY_DIR_VALUE="surveys/$SLUG"

if [ "$DRY_RUN" != "--dry-run" ]; then
  for f in "$SURVEY_DIR"/.claude/agents/*.md; do
    # macOS/BSD sed 호환: -i '' 사용
    sed -i '' \
      -e "s|{{SURVEY_SLUG}}|$SLUG|g" \
      -e "s|{{DOMAIN}}|$DOMAIN|g" \
      -e "s|{{CHAPTERS}}|$CHAPTERS_VALUE|g" \
      -e "s|{{TERMS}}|$TERMS_VALUE|g" \
      -e "s|{{SURVEY_DIR}}|$SURVEY_DIR_VALUE|g" \
      "$f"
  done
else
  printf "[dry-run] would substitute placeholders in %s/.claude/agents/*.md\n" "$SURVEY_DIR"
fi

# --- 3b) survey.json의 제목·설명 초안 반영 -----------------------------
if [ "$DRY_RUN" != "--dry-run" ]; then
  say "seeding survey.json title/description/visibility with CLI args"
  python3 - "$SURVEY_DIR/survey.json" "$TITLE_KO" "$TITLE_EN" "$DOMAIN" "$VISIBILITY" "$GROUP" <<'PY'
import json, sys, datetime
path, title_ko, title_en, domain, visibility, group = sys.argv[1:]
with open(path, encoding='utf-8') as f:
    cfg = json.load(f)
cfg["title"] = {"ko": title_ko, "en": title_en}
cfg["description"] = {"ko": domain, "en": domain}
cfg["dates"] = {
    "first_published": datetime.date.today().isoformat(),
    "last_updated": datetime.date.today().isoformat(),
}
cfg["visibility"] = visibility if visibility else "public"
cfg["group"] = group if group else None
with open(path, "w", encoding='utf-8') as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
PY
fi

# --- 4) 인덱스 + 검증 ---------------------------------------------------
say "rebuilding refs_index and validating"
run "cd '$REPO_ROOT' && python3 build.py --index"
run "cd '$REPO_ROOT' && python3 build.py --validate '$SLUG'"

say "DONE. next steps:"
if [ "$VISIBILITY" = "group" ]; then
cat <<EOF

  PRIVATE FLOW — content lives in terry-private (group: $GROUP)

  1) Edit surveys/$SLUG/survey.json — chapter structure (parts[].chapters[])
     (file is symlinked; edits land in terry-private/surveys/$SLUG/)
  2) Populate book/ko/ and book/en/ via deep-researcher → book-writer pipeline
  3) Run: /survey --sync-agents $SLUG   (to refresh {{CHAPTERS}}/{{TERMS}} placeholders)
  4) Commit + push: cd ../terry-private && git add surveys/$SLUG/ && git commit && git push
     (NEVER commit from terry-surveys — only the symlink itself is tracked here, .gitignored)
  5) After deploy: /survey <cloudflare-url> --visibility=group --group=$GROUP
     (registers in Supabase private_content, NOT the public surveys.json)

EOF
else
cat <<EOF

  1) Edit surveys/$SLUG/survey.json — chapter structure (parts[].chapters[])
  2) Populate book/ko/ and book/en/ via deep-researcher → book-writer pipeline
  3) Run: /survey --sync-agents $SLUG   (to refresh {{CHAPTERS}}/{{TERMS}} placeholders)
  4) After deploy: /survey <cloudflare-url>   (to register in homepage gallery)

EOF
fi
