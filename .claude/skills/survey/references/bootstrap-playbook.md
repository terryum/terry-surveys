# MODE A — Bootstrap Playbook

`/survey "<책 제목>"` 이 terry-surveys 모노레포 내부에서 호출됐을 때 실행되는 **새 책 부트스트랩** 단계별 세부 가이드. SKILL.md 본문은 이 문서를 요약 포인터로만 가리키며, 실제 에러 복구·엣지케이스·검증 기준은 여기에 둔다.

## 선행 조건

- cwd가 `/Users/terrytaewoongum/Codes/personal/terry-surveys` 내부.
- Python 3, `python3 build.py --help`가 응답.
- `.claude/skills/survey/references/agent-template/` 디렉토리와 그 하위 6개 에이전트 md + README 존재.
- 루트 `bibtex/references.bib` 존재 (인덱스 재생성에 필요).

선행 조건 중 하나라도 깨지면 사용자에게 구체적 오류 메시지와 함께 중단한다. **스킵·우회 금지** (빠진 것을 만들어 버리는 순간 canonical이 훼손된다).

## 입력 파싱

```
/survey "<책 제목>" [--domain="..."] [--slug=<kebab-case>]
```

- **제목 (필수)**: 따옴표로 감싼 제목 문자열. 한글/영문 모두 허용. 양국어 제목을 동시에 주고 싶으면 `--title-ko="..." --title-en="..."` 플래그 사용.
- **`--domain`**: 이후 에이전트 정의의 `{{DOMAIN}}` 치환에 쓰일 한 문장. 생략 시 제목을 그대로 씀.
- **`--slug`**: 파일 시스템 slug를 명시적으로 지정. 생략 시 제목을 kebab-case로 자동 변환.

### Slug 도출 규칙
- 영문·숫자·하이픈만 허용. 공백·특수문자는 하이픈으로.
- 대문자는 모두 소문자로.
- 너무 길면(40자 초과) 주요 명사만 추려 단축 제안.
- 한글 제목인 경우 사용자에게 직접 slug를 물어볼 것 (자동 romanization 금지 — 일관성 없음).

## 실행 단계

### Step 1. Slug 충돌 체크

```bash
[ -d "surveys/<slug>" ] && { echo "ERROR: surveys/<slug> already exists"; exit 1; }
```

중복 시 사용자에게 다른 slug 입력 요청. **기존 디렉토리를 덮어쓰지 않는다.**

### Step 2. 공개 구조 스캐폴딩

```bash
python3 build.py --new <slug>
```

`shared/scaffold.py`가 canonical 구조를 만든다:
- `survey.json` (placeholder 값으로 초기화)
- `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, `LICENSE`, `.gitignore`
- `.github/ISSUE_TEMPLATE/` × 4
- `book/{ko,en}/ch01.md`, `book/{ko,en}/glossary.md`, `book/references.bib`
- `assets/figures/`, `docs/`
- `scripts/push.sh`

### Step 3. .claude/agents/ 디렉토리 + 템플릿 복사

```bash
mkdir -p surveys/<slug>/.claude/agents
cp .claude/skills/survey/references/agent-template/*.md surveys/<slug>/.claude/agents/
# README.md는 템플릿 폴더 전용이므로 복사 대상에서 제외
rm surveys/<slug>/.claude/agents/README.md
```

**또는** `scripts/bootstrap.sh <slug> <title_ko> <title_en> <domain>`으로 위 전 과정 한 번에 실행.

### Step 4. Placeholder 치환

부트스트랩 시점에는 `{{CHAPTERS}}` · `{{TERMS}}`가 아직 확정되지 않았을 가능성이 높다. 다음 전략을 사용:

- `{{SURVEY_SLUG}}`, `{{SURVEY_DIR}}`: 즉시 확정값 치환.
- `{{DOMAIN}}`: 사용자 제공 `--domain` 또는 제목 재사용.
- `{{CHAPTERS}}`, `{{TERMS}}`: 임시 플레이스홀더 문자열로 치환 (`"<fill in after chapter plan>"`, `"<fill in from glossary>"`). 이후 사용자가 survey.json의 parts/chapters를 편집하면 `/survey --sync-agents <slug>`로 재적용.

`scripts/bootstrap.sh`가 macOS/BSD sed로 이 치환을 수행한다.

### Step 5. survey.json 초벌 채우기

- `title.ko`, `title.en` → 사용자 입력 적용.
- `description.ko/en` → **KO ≤ 90자, EN ≤ 140자**. "핵심 질문 한 줄 — N Parts, M Chapters" 패턴. 챕터·회사 나열 금지 (Chapter Grid가 그 역할).
- `cover_image` → `""`로 초기화. MODE B 등록(`/survey <cloudflare-url>`) 시 생성된 `terryum-ai/public/images/projects/survey-<slug>-og.jpg` (16:9)를 `surveys/<slug>/assets/cover.jpg`로 복사한 뒤 `"../assets/cover.jpg"`로 설정. 없을 때만 `/image-gen`으로 새로 생성 (cinematic hero banner, 16:9, 2K). **이미 있는 자산을 새로 생성하지 말 것** (2026-04 humanoid-revolution 사고 예방).
- `dates.first_published`, `dates.last_updated` → 오늘 날짜.
- `parts[].chapters[]` → scaffold가 만든 1개 챕터 유지. 사용자가 이후 편집.
- 하이라이트·acknowledgment 등 나머지 필드 → placeholder 유지, 사용자 편집 안내.

### Step 6. 인덱스 + 검증

```bash
python3 build.py --index
python3 build.py --validate <slug>
```

- `--index`: 루트 `bibtex/refs_index.json` 재생성. 새 서베이는 빈 refs여도 엔트리가 추가된다.
- `--validate`: 스키마·인용·figure·subset 기본 검증. 빈 책이라 warning만 나올 수 있음 — critical error만 중단 사유.

### Step 7. Git 초기 커밋 (선택, 사용자 확인 후)

```bash
git add surveys/<slug>/ .claude/skills/survey/ bibtex/refs_index.json
git commit -m "feat(<slug>): bootstrap survey scaffold + agents"
```

**사용자가 명시 동의할 때만 커밋.** 기본은 변경사항만 만들고 커밋은 사용자 재량.

### Step 8. Next-steps 안내

```
DONE. next steps:
  1) Edit surveys/<slug>/survey.json — chapter structure (parts[].chapters[])
  2) Run: /survey --sync-agents <slug>     (to refresh {{CHAPTERS}}/{{TERMS}})
  3) Populate book/ko/ and book/en/ via deep-researcher → book-writer pipeline
     - 팀 호출: Agent(subagent_type="general-purpose", prompt="...", model="opus")로
       각 에이전트 md의 system prompt를 로드하여 팀 작업 개시
  4) After deploy: /survey <cloudflare-url>  (to register in homepage gallery)
```

## 에러 복구

| 증상 | 원인 | 대응 |
|---|---|---|
| `build.py --new` 실패 | scaffold.py 버그 또는 디스크 권한 | 스택트레이스 그대로 사용자에게 출력 후 중단. Step 3+ 실행 안 함 |
| 템플릿 파일 누락 | agent-template/ 손상 | `git status`로 삭제 여부 확인. 복구 후 재시도 |
| `--validate` FAIL | scaffold의 placeholder가 validator에 걸림 | Critical vs warning 구분. Critical은 스캐폴드 결함이니 scaffold.py 수정 |
| 인덱스 재생성 실패 | bibtex/references.bib 파싱 오류 | 마스터 bibtex의 문법 오류 우선 수정, 이후 재실행 |
| Placeholder 치환 깨짐 | sed 특수문자 (URL, `&` 등이 DOMAIN에 포함) | bootstrap.sh는 안전한 구분자(`|`)를 쓰지만 값에 `|` 포함 시 문제. 해당 값만 escape |

## 검증 체크리스트

부트스트랩 완료 후 아래 모두 충족해야 성공:

- [ ] `surveys/<slug>/` 존재
- [ ] `surveys/<slug>/.claude/agents/*.md` 6개 파일 존재
- [ ] 각 agent md에 `{{` placeholder가 남아있지 않음 (grep `{{[A-Z_]+}}` → 0줄)
- [ ] `surveys/<slug>/survey.json` 파싱 가능 + `title.ko/en` 입력값 반영
- [ ] `bibtex/refs_index.json`에 `"<slug>"` 키 존재
- [ ] `python3 build.py --validate <slug>` critical error 없음

## 자주 묻는 시나리오

**Q. 이미 `surveys/<slug>/.claude/agents/`가 있으면?**
A. 기존 디렉토리를 덮어쓰지 않는다. 대신 `/survey --sync-agents <slug>`를 안내.

**Q. 부트스트랩 중간에 취소하면?**
A. 이미 만든 파일은 남는다. 사용자가 `rm -rf surveys/<slug>/`로 정리한 뒤 재시도 권장.

**Q. 템플릿이 업데이트됐는데 이미 부트스트랩한 책에 반영하려면?**
A. `/survey --sync-agents <slug> --dry-run`으로 diff 확인 후 `--apply`.
