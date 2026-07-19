#!/usr/bin/env bash
# bootstrap.sh — /survey MODE A 부트스트랩 헬퍼.
#
# 호출: bash scripts/bootstrap.sh <slug> <title_ko> <title_en> <domain> [--visibility=group --group=<grp>] [--repo-root=<path>] [--skill-dir=<path>] [--dry-run]
#
# 역할:
#  1) python3 build.py --new <slug>
#     - 모든 소스는 terry-surveys-contents/surveys/<slug>/ 에 scaffold
#     - public/group은 reader visibility만 바꾸며 저장소 위치는 동일
#  2) .claude/agents/ 디렉토리 생성 + v2 역할 8개 복사
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
REPO_ROOT="/Users/terrytaewoongum/Codes/personal/terry-surveys"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --visibility=*) VISIBILITY="${1#--visibility=}" ;;
    --group=*) GROUP="${1#--group=}" ;;
    --repo-root=*) REPO_ROOT="${1#--repo-root=}" ;;
    --skill-dir=*) SKILL_DIR="${1#--skill-dir=}" ;;
    --dry-run) DRY_RUN="--dry-run" ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$VISIBILITY" = "group" ] && [ -z "$GROUP" ]; then
  echo "ERROR: --visibility=group requires --group=<grp>" >&2
  exit 2
fi

REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
if [ ! -f "$REPO_ROOT/build.py" ] || [ ! -d "$REPO_ROOT/surveys" ]; then
  echo "ERROR: --repo-root is not terry-surveys: $REPO_ROOT" >&2
  exit 1
fi
if ! "$REPO_ROOT/scripts/setup-contents.sh" --check >/dev/null; then
  echo "ERROR: terry-surveys-contents sibling workspace is not ready" >&2
  exit 1
fi
SKILL_DIR="$(cd "$SKILL_DIR" && pwd)"
TEMPLATE_DIR="$SKILL_DIR/references/agent-template"
if [ ! -d "$TEMPLATE_DIR" ]; then
  TEMPLATE_DIR="$REPO_ROOT/.claude/skills/survey/references/agent-template"
fi
if [ ! -d "$TEMPLATE_DIR" ]; then
  echo "ERROR: agent template directory not found" >&2
  exit 1
fi
SCAFFOLD_DIR="$REPO_ROOT/surveys/$SLUG"
SURVEY_DIR="$SCAFFOLD_DIR"
SCAFFOLD_LOCATION="terry-surveys-contents/surveys/$SLUG (private source; reader visibility: ${VISIBILITY:-public})"

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
say "scaffold target: $SCAFFOLD_LOCATION"
say "scaffolding via build.py --new $SLUG"
run "cd '$REPO_ROOT' && python3 build.py --new '$SLUG'"

# --- 2) .claude/agents/ ------------------------------------------------
say "creating .claude/agents/ and copying v2 template × 8"
run "mkdir -p '$SURVEY_DIR/.claude/agents'"
AGENT_SPECS=(
  "kg-mapper:kg-mapper:"
  "deep-researcher:deep-researcher-foundations:foundations"
  "deep-researcher:deep-researcher-frontier:frontier"
  "evidence-librarian:evidence-librarian:"
  "book-writer:book-writer:"
  "image-curator:image-curator:"
  "fact-checker:fact-checker:"
  "qa-reviewer:qa-reviewer:"
)
for spec in "${AGENT_SPECS[@]}"; do
  IFS=':' read -r template out role <<< "$spec"
  run "cp '$TEMPLATE_DIR/$template.md' '$SURVEY_DIR/.claude/agents/$out.md'"
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
    role=""
    case "$(basename "$f")" in
      deep-researcher-foundations.md) role="foundations" ;;
      deep-researcher-frontier.md) role="frontier" ;;
    esac
    # macOS/BSD sed 호환: -i '' 사용
    sed -i '' \
      -e "s|{{SURVEY_SLUG}}|$SLUG|g" \
      -e "s|{{DOMAIN}}|$DOMAIN|g" \
      -e "s|{{CHAPTERS}}|$CHAPTERS_VALUE|g" \
      -e "s|{{TERMS}}|$TERMS_VALUE|g" \
      -e "s|{{SURVEY_DIR}}|$SURVEY_DIR_VALUE|g" \
      -e "s|{{RESEARCHER_ROLE}}|$role|g" \
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
cfg["github_repo"] = "terryum/terry-surveys-contents"
cfg["github_repo_visibility"] = "private"
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
cat <<EOF

  1) Edit surveys/$SLUG/survey.json — chapter structure (parts[].chapters[])
     (the symlink writes to terry-surveys-contents/surveys/$SLUG/)
  2) Run the v2 controller loop: /survey --orchestrate $SLUG
  3) Use /survey --sync-agents $SLUG only when refreshing generated role context
  4) Commit + push: cd ../terry-surveys-contents && git add surveys/$SLUG/ && git commit && git push
  5) After deploy, register using the requested reader visibility (${VISIBILITY:-public})

EOF
