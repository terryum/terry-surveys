#!/usr/bin/env bash
# bootstrap.sh — /survey MODE A 부트스트랩 헬퍼.
#
# 호출: bash scripts/bootstrap.sh <slug> <title_ko> <title_en> <domain> [--dry-run]
#
# 역할:
#  1) python3 build.py --new <slug>  (shared/scaffold.py가 공개 구조 생성)
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
  echo "Usage: $0 <slug> <title_ko> <title_en> <domain> [--dry-run]" >&2
  exit 2
fi

SLUG="$1"
TITLE_KO="$2"
TITLE_EN="$3"
DOMAIN="$4"
DRY_RUN="${5:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/.claude/skills/survey/references/agent-template"
SURVEY_DIR="$REPO_ROOT/surveys/$SLUG"

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
  say "ERROR: surveys/$SLUG already exists. Aborting to avoid overwrite."
  exit 1
fi

say "scaffolding public structure via build.py --new $SLUG"
run "cd '$REPO_ROOT' && python3 build.py --new '$SLUG'"

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
  say "seeding survey.json title/description with CLI args"
  python3 - "$SURVEY_DIR/survey.json" "$TITLE_KO" "$TITLE_EN" "$DOMAIN" <<'PY'
import json, sys, datetime
path, title_ko, title_en, domain = sys.argv[1:]
with open(path, encoding='utf-8') as f:
    cfg = json.load(f)
cfg["title"] = {"ko": title_ko, "en": title_en}
cfg["description"] = {"ko": domain, "en": domain}
cfg["dates"] = {
    "first_published": datetime.date.today().isoformat(),
    "last_updated": datetime.date.today().isoformat(),
}
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
  2) Populate book/ko/ and book/en/ via deep-researcher → book-writer pipeline
  3) Run: /survey --sync-agents $SLUG   (to refresh {{CHAPTERS}}/{{TERMS}} placeholders)
  4) After deploy: /survey <cloudflare-url>   (to register in homepage gallery)

EOF
