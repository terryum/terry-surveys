---
name: survey
description: "Survey 책 생애주기 전 단계를 관리한다. terry-surveys 모노레포에서 호출하면 MODE A(새 책 부트스트랩 = scaffold + .claude/agents/ 템플릿 복사 + 하네스 구성), 배포된 Cloudflare Pages URL을 주면 MODE B(홈페이지 Surveys 갤러리 등록 + /cite-post 자동 호출). **집필은 기본적으로 --orchestrate로 멀티에이전트 하네스 팀이 자율 병렬 수행** (deep-researcher-foundations·deep-researcher-frontier·critical-analyst·book-writer·image-curator·fact-checker·qa-reviewer 7종 — deep-researcher는 시간대로 2-way 병렬, 샤드 merge 후 canonical papers.json; 나머지 5인은 TeamCreate + SendMessage + TaskCreate로 자체 조율). 서브커맨드로 --orchestrate(팀 집필), --sync-agents(템플릿 전파), --refresh(staleness), --factcheck, --link-posts(Tier 1 포스트 역링크), --deploy(빌드+배포+등록). 새 서베이 책을 시작·집필·유지보수할 때 반드시 이 스킬을 사용할 것."
argument-hint: "<제목 | URL> [--domain=... | --bootstrap | --register | --orchestrate | --sync-agents | --refresh | --factcheck | --link-posts | --deploy] [--phase=research|write|polish] [--chapters=1-3] [--max-parallel=N] [--visibility=group --group=snu]"
---

# /survey — 서베이 책 생애주기 허브

입력: $ARGUMENTS

이 스킬은 **두 가지 모드**(A: 부트스트랩 / B: 등록)와 **6가지 지속 운영 서브커맨드**로 서베이 책의 모든 단계를 관리한다. 본문은 모드 분기와 요약만 담고, 실제 단계별 세부는 `references/` 내 플레이북을 참조한다.

**집필은 `--orchestrate`가 기본**이다 — 7개 에이전트(`surveys/<slug>/.claude/agents/*.md`)가 `/harness` 규약의 팀 모드로 자율 병렬 수행한다. deep-researcher는 foundations(pre-2024)/frontier(2024+) 2명으로 분리돼 병렬 실행되며 `merge_research_shards.py`가 canonical papers.json 생성. 순차 Phase 실행이 아니라 의존성 그래프 기반 동시 진행·스트리밍·자체 조율이 표준. 세부는 `references/orchestration-playbook.md` 참조.

## Step 0. 모드 감지

```
if $ARGUMENTS 비었거나 --help        → 도움말 출력 후 종료
elif $ARGUMENTS가 URL 형태 (http/https)    → MODE B (등록)
elif --bootstrap 명시                → MODE A (부트스트랩) 강제
elif --register 명시                 → MODE B 강제
elif cwd가 terry-surveys 내부 AND $ARGUMENTS가 제목 문자열
                                     → MODE A (부트스트랩)
elif --orchestrate <slug>            → 멀티에이전트 팀 집필 (기본 집필 모드)
elif --sync-agents / --refresh / --factcheck / --link-posts / --deploy
                                     → 해당 서브커맨드 분기
else                                  → 명확한 의도 부족 — 사용자에게 모드 재확인
```

URL인지 판별은 정규식 `^https?://`로 충분. URL 형태 제목(매우 드문 엣지케이스)은 `--bootstrap` 플래그를 요구.

## MODE A — 부트스트랩 (새 책 시작)

**세부는 `references/bootstrap-playbook.md` 참조.** 핵심만:

1. 제목 → slug 도출, `surveys/<slug>/` 충돌 체크.
2. `python3 build.py --new <slug>` (공개 구조 스캐폴딩).
3. `mkdir .claude/agents/` + 템플릿 6개 복사 + placeholder 치환.
4. `survey.json` 제목·설명·날짜 초벌 채움.
5. `python3 build.py --index` + `--validate <slug>`.
6. (선택) Git 초기 커밋.
7. Next-steps 안내 — 에이전트 파이프라인 개시 방법.

`scripts/bootstrap.sh <slug> "<title_ko>" "<title_en>" "<domain>" [--dry-run]`이 위 1–5를 한 번에 실행한다.

### 예시
```
/survey "Robot Grasp Learning" --domain="learning-based dexterous grasping"
/survey "Vision-Language-Action 서베이" --slug=vla-agentic-robotics-v2
```

## MODE B — 등록 (갤러리 추가)

**세부는 `references/registration-playbook.md` 참조.** 핵심만:

1. URL에서 메타(title, description, toc) 추출 (WebFetch / README).
2. 메타 객체 구성 (toc는 ko ≤12자 / en ≤19자 per item).
3. `/image-gen`으로 커버(1:1) + OG(16:9) 이미지 생성 + **sharp로 cover.webp에서 thumb.webp(288×288) 파생**. 세 자산 모두 필수 — thumb은 홈페이지 Featured 카드 전용(누락 시 broken image). **Prompt 금지어**: "book cover/mockup/square book" — Gemini가 회색 배경 + 그림자 위에 책 illustration을 그려 카드가 풀블리드가 안 됨. 대신 "full-bleed, edge-to-edge, no book mockup, no frame, no shadow" 명시 (2026-04-28 사고 두 건 — registration-playbook Step 3 참조).
4. `projects/surveys/surveys.json`에 엔트리 추가 + `next_survey_number` 증가.
5. `npx tsc --noEmit && npm run build`.
6. terry-surveys 책이면 `/cite-post <slug>` 자동 호출 (역링크).
7. `git pull --rebase` 후 커밋·푸시.
8. **GHA `Deploy to Cloudflare Workers` 검증** — `gh run watch <id> --exit-status`. 실패 시 진단·수정·재push 또는 `gh workflow run deploy.yml`로 재트리거.
9. **라이브 노출 확인** — `curl -s https://www.terryum.ai/{en,ko}/surveys | grep <slug>`. 안 보이면 5–10분 대기 또는 Cloudflare Cache Purge.

**완료 보고 직전 필수**: Step 8+9는 skip 금지. push 자체가 deploy 성공을 의미하지 않는다 (2026-04-28 사고: surveys.json push가 CI 캐시 stale로 실패, 재트리거로 복구).

그룹 비공개 서베이는 `--visibility=group --group=<slug>`로 surveys.json 대신 Supabase `private_content`에 저장 (Git 커밋 없음).

### 예시
```
/survey https://survey-robot-hand-tactile-sensor.pages.dev
/survey https://survey-snu-tactile-hand.pages.dev --visibility=group --group=snu
```

## 지속 운영 서브커맨드

### `/survey --orchestrate <slug> [--phase=...] [--chapters=...] [--max-parallel=N]` — 기본 집필 모드

**세부는 `references/orchestration-playbook.md` 참조.**

`/harness` 규약의 팀 모드로 7개 에이전트를 기동하여 **자율 병렬 집필**. 순차 Phase 아님 — 의존성 그래프 기반 동시 진행·스트리밍이 기본.

**리더(오케스트레이터 = /survey 스킬 자체) 동작**:
1. `TeamCreate(name="survey-<slug>", members=[deep-researcher-foundations, deep-researcher-frontier, critical-analyst, book-writer, image-curator, fact-checker, qa-reviewer])` — 각 에이전트는 `surveys/<slug>/.claude/agents/<name>.md`를 system prompt로 로드, 모델 `opus`.
2. `TaskCreate`로 의존성 그래프 설정 (`addBlockedBy`로 표현):
   - deep-researcher-foundations + deep-researcher-frontier → 각자 `_research/papers_{role}.json` 샤드 (병렬 실행, peer grep으로 중복 회피)
   - **T-merge-research** (리더 직접 실행): `python3 .claude/skills/survey/scripts/merge_research_shards.py <slug>` → canonical `_research/papers.json` + `_merge_report.md`
   - critical-analyst (blockedBy: merge 부분 또는 샤드 60% 시점) → `_analysis/gaps.md`
   - book-writer × 챕터 수 (blockedBy: 해당 Part analysis) — 챕터 간 독립, **병렬 실행**
   - image-curator, fact-checker — 챕터 완료 이벤트에 **스트림 처리**
   - qa-reviewer — 진행 중 incremental QA + 최종 관문
3. 팀원들이 `SendMessage`로 자체 조율 (발견 공유·수정 요청·상충 토론). deep-researcher 2인은 경계년도 논문·중복 엔트리를 서로 넘겨주며 협업.
4. 리더는 `TaskList`로 진행 모니터링, 작업은 안 함(예외: merge 스크립트 실행). 완료 감지 시 `TeamDelete`.

**Phase 플래그**:
- `--phase=research`: 연구·분석만 (`_research/` + `_analysis/` 산출)
- `--phase=write`: 집필만 (research 전제, `book/` 산출)
- `--phase=polish`: 팩트체크·QA만 (draft 전제, 보고서 산출)
- 생략 시: 전체 파이프라인 자율 완주

**기타 플래그**:
- `--chapters=1-3`: 특정 챕터만 타겟 (부분 업데이트·리프레시).
- `--max-parallel=N`: 동시 진행 챕터 상한 (기본 4).
- 세션 분할 체크포인트: `_workspace/orchestration_state.json`에 상태 저장.

### `/survey --sync-agents [<slug> | --all] [--dry-run | --apply] [--retrofit]`

템플릿(`references/agent-template/`) → per-survey `.claude/agents/` 동기화.
- placeholder 치환 영역은 per-survey 값 보존, 공통 섹션만 업데이트.
- `--retrofit`: 아직 `.claude/agents/`가 없는 서베이에 최초 생성.
- 기본은 `--dry-run` (diff만), 실제 반영은 `--apply`.

구현: `scripts/sync_agents.py` 호출.

### `/survey --refresh <slug>`

```bash
python3 build.py --staleness <slug>
```
오래된 챕터 × 그 이후 신규 논문 수 스코어 출력 → 상위 챕터부터 `book-writer` / `fact-checker` 호출 권장.

### `/survey --factcheck <slug>`

`surveys/<slug>/.claude/agents/fact-checker.md`를 로드하여 Agent 호출. 모든 챕터에 대해 `_refs_extracted.json` + `_factcheck_report.md` 갱신. `book-write` · `fact-check` 글로벌 스킬과 연동.

**선행 단계 — mechanical baseline:**

fact-checker를 호출하기 전에 `_refs_extracted.json`의 mechanical 필드를 일괄 채워두는 게 표준이다 (idempotent, fact-checker가 만진 verification 필드는 보존).

```bash
python3 build.py --refresh-refs <slug>
```

이로써 fact-checker는 ID 채우기 잡일에서 해방되고 `verification_status` / `factcheck_notes` / `scholar_url` enrich와 본문 정정 제안에 집중할 수 있다.

**`_research/papers.json` 부재 시 backfill:**

서베이가 deep-researcher 패스를 거치지 않아 `_research/papers.json`이 없으면, candidate pool / impact 분석 / Tier 1 매칭이 메타 빈 껍데기가 된다. 다음으로 best-effort 골격을 만들어둔다 (bibtex master + 챕터 ref 라인에서 도출, `provenance: "bibtex_backfill"` 태그). 이후 `/survey --orchestrate`의 deep-researcher가 method_summary·limitations·tags 등을 enrich한다.

```bash
python3 build.py --backfill-research <slug>
```

`--force`는 기존 `bibtex_backfill` 엔트리만 새로 만들고, deep-researcher가 채운 풍부 엔트리(method_summary 등)는 항상 보존된다.

### `/survey --link-posts <slug>`

`/link-post-to-surveys <slug>` 프록시. Tier 1(arXiv/DOI/Nature 정확 매칭) 링크만 자동 삽입. Tier 2는 수동 승인 흐름.

### `/survey --deploy <slug>`

```bash
python3 build.py <slug>                                 # 빌드
bash surveys/<slug>/scripts/push.sh "deploy message"    # Cloudflare Pages (책 사이트)

# Surveys candidate pool 재계산 — terry-papers/knowledge-index.json의
# candidate_index 섹션을 갱신해 /paper-search next 모드 신선도 유지.
# OPENAI_API_KEY가 환경에 있으면 새 candidate에 임베딩도 함께 생성.
node /Users/terrytaewoongum/Codes/personal/terryum-ai/scripts/sync-survey-candidates.mjs --with-embeddings
```
배포 후 MODE B로 자동 진입해 `surveys.json` 업데이트 (사용자 확인 후). MODE B는 Step 8+9에서 GHA 검증 + 라이브 노출 확인을 **반드시** 수행한다 — 책 사이트 배포 성공만으로는 홈페이지 갤러리 노출을 보장하지 않는다.

## Common Pitfalls (과거 사고에서 학습한 강제 규칙)

새 서베이를 만들거나 집필할 때 반드시 지켜야 할 규칙. 각각 `build.py --validate`가 자동 검사한다.

### P1. Figure alt 텍스트에 `[Author, Year]` 대괄호 금지

**규칙**: `![caption](url)`의 caption(=alt) 안에는 대괄호 인용이 없어야 한다. 출처는 `Author et al. Year` 또는 `Author Year` 형식으로 대괄호 없이 기입.

**이유**: build_site.py의 citation linkifier가 `[Kajita et al., 2003]`을 `<sup><a>[1]</a></sup>` HTML로 치환 → alt 속성의 `"`가 linkifier 출력 내부에서 조기에 닫히면서 `loading="lazy"`, `onerror=...`, `style="cursor:zoom-in">` 등 img 태그 속성이 figcaption에 visible text로 누출 (2026-04 humanoid-revolution 사고).

**함정의 반대 규칙**: 본문(narrative) 인용은 `[Author et al., Year]` 대괄호가 **필수**. 즉 위치에 따라 규칙이 정반대.

### P2. Figure 수 하한 = 챕터당 3개 (플랫폼/회사 챕터는 4–8 + 실제 사진 ≥ 2)

**규칙**: 모든 챕터 ≥ 3 figure. 플랫폼/회사/하드웨어 챕터는 4–8, 그중 실제 제품 사진(press kit · GitHub README · 하드웨어 arXiv) ≥ 2개 필수.

**이유**: 이전 "≤ 2 AI 보조/ch" 하드캡이 history/theory/company 챕터에서 figure 빈약을 낳아 0.56/ch까지 떨어짐 (2026-04 humanoid-revolution 사전사고).

**해결**: 티어 쿼터 (theory 3–5, method 3–6, platform 4–8 + ≥2 photos, history/ecosystem 3–5). canonical은 `references/agent-template/image-curator.md` 참조.

### P3. Figure 소스 3-way 병용

**규칙**: 세 계열을 함께 쓴다 — (a) 논문 원본 figure 크롭, (b) 공식 플랫폼/제품 사진 (press kit / GitHub / 하드웨어 arXiv, fair use), (c) Gemini 생성 개념도. 단일 소스로만 채우지 말 것.

**이유**: 단일 소스 정책은 챕터 유형에 따라 비효율 — 논문 figure는 이론/산업 분석 챕터에서 희소하고, 플랫폼 사진은 회사 챕터에서만 합리적, Gemini는 이론/전략 챕터의 1급 소스.

### P4. 매니페스트에 `source_type` + `license_basis` 필수

**규칙**: `_workspace/04_image_manifest.json`의 모든 항목에 `source_type` (paper_figure/platform_photo/gemini/seminar_pdf/blog) + `license_basis` 필수. 플랫폼 사진은 `source_url` · `fetch_date` · `sha256` 추가. Gemini는 `source_prompt` 추가.

**이유**: 저작권·fair use 추적성, 향후 이미지 재활용·교체 시 원본 복원.

### P5. 모든 figure는 opaque여야 한다 (투명 PNG/WebP 금지)

**규칙**: 챕터 figure·커버·OG 어떤 이미지든 디스크에 저장된 시점에 alpha 채널이 투명 픽셀을 가져서는 안 된다. 저장 직후 반드시 흰 배경으로 flatten.

**실행**:
```bash
python /Users/terrytaewoongum/Codes/personal/terryum-ai/scripts/flatten-transparent-figures.py \
  surveys/<slug>/assets/
# 공유 figure 디렉토리도 동일
python /Users/terrytaewoongum/Codes/personal/terryum-ai/scripts/flatten-transparent-figures.py \
  assets/figures/
```
- 스크립트는 opaque 파일은 자동 skip, RGBA/LA/palette tRNS 세 종류 모두 처리 (idempotent).
- `image-curator` 에이전트 체크리스트에도 동일 항목 존재 — 오케스트레이터는 배포 전(특히 `build_site.py` 호출 이전) 한 번 더 전수 실행할 것.

**이유**: 다크모드 사이트·PDF에서 투명 영역이 검정으로 비친다. R2 엣지는 `immutable` 1년 캐시라 배포 후 파일 교체로는 회복 불가 (2026-04 terryum.ai post #13 사고 — 투명 cover/og가 다크모드에서 로봇 사진 전체를 검정으로 묻어버림).

### P6. Reader-facing 콘텐츠에 monorepo-internal path 노출 금지

**규칙**: `book/{ko,en}/**.md`에 절대로 다음 경로·워크플로우 안내를 쓰지 말 것:
- `glossary/master_{ko,en}.md` (maintainer sync 워크플로우)
- `bibtex/references.bib` (마스터 bibtex 관리)
- `.claude/`, `_workspace/`, `shared/build_site.py` 등 레포 내부 경로
- "먼저 X를 grep해서 …" 식의 유지보수자 전용 지시문 (특히 blockquote `>` 형식)

**이유**: 독자는 이런 내부 구조를 몰라야 하고, 알 필요도 없다. 유지보수 노트는 `CLAUDE.md` / `glossary/README.md` / `_workspace/`에 둔다. 2026-04 humanoid-revolution 사고: `scaffold.py`가 glossary 템플릿에 `> **신규 용어 추가 시**: glossary/master_ko.md를 grep …` blockquote을 자동 삽입했고, 이게 공개 사이트에 그대로 렌더링됨. scaffold 수정 + 검증기가 이제 이 패턴을 warning으로 잡는다.

**검증**: `build.py --validate`가 위 경로들을 `book/**.md`에서 발견하면 warning 발생.

## Home Page Standards (index.html의 hero 구성)

각 서베이의 `docs/{ko,en}/index.html`은 `build_site.py`의 `build_toc_html()`이 `survey.json`에서 읽어 생성한다. 홈 hero 섹션의 표준 구성 (순서 고정):

1. **커버 이미지** (`cover_image` 필드) — `<h1>` 위에 배치. 필수.
2. **제목** (`short_title`) — 그래디언트 텍스트.
3. **부제** (`subtitle`) — 한 문장.
4. **부연설명** (`description`) — **짧게** (KO ≤ 90자, EN ≤ 140자 권장).
5. 날짜 + CTA 버튼.

### 커버 이미지 (`cover_image`)

- **필드**: `survey.json` 최상위 `cover_image` (경로는 `"../assets/cover.<ext>"`).
- **파일 위치**: `surveys/<slug>/assets/cover.{jpg,png,webp,svg}` (`assets/figures/` 아님 — flat `assets/` 루트).
- **해상도**: 16:9 landscape 권장 (2752×1536 또는 유사). 1:1 정사각도 허용 (CSS `aspect-ratio: 16/9; object-fit: cover`가 center-crop).
- **재사용**: MODE B 등록 시 생성된 `terryum-ai/public/images/projects/survey-<slug>-og.jpg` (16:9) 또는 `-cover.webp` (1:1)를 그대로 복사하는 것을 우선. 이미 있는 자산을 **새로 생성하지 말 것** (2026-04 humanoid-revolution 사고: 이미 좋은 OG가 있는데 Gemini로 새로 생성해 ₩210 낭비).
- **생성 폴백**: og가 없을 때만 `/image-gen` (cinematic hero banner, 16:9, 2K).
- **빌드 동작**: `build_site.py`가 `surveys/<slug>/assets/cover.*` → `docs/assets/cover.*`로 자동 복사. `index.html`은 `../assets/cover.<ext>`를 참조.
- **CSS**: `.hero-cover` (max 960px, 라운디드, soft shadow, 16:9 aspect-ratio).

### 부연설명 (`description`) 길이 제한

- **KO**: 약 40–90자 (한 줄 내외)
- **EN**: 약 80–140자
- 초과 시 `build.py --validate`가 warning. **챕터 전 목록을 나열하지 말 것** — 목차(`parts[].chapters[]`)가 이미 하단 Chapter Grid에 노출된다.
- 이상적 형식: "**핵심 질문 또는 범위 한 줄** — N Parts, M Chapters". 예:
  - ✅ `"에이전틱 루프가 물리 세계에서 작동하려면 무엇이 달라져야 하는가. — 4 Parts, 10 Chapters"` (59자)
  - ❌ `"2015–2026년 휴머노이드 로보틱스의 대격변을 정리한 서베이. 정통파 LIPM/ZMP/MPC 스택의 한계, QDD 액추에이터·GPU 병렬 시뮬·teacher-student RL·sim-to-real 네 기폭제, System 0/1/2 3-레이어 아키텍처와 VLA 통합, Boston Dynamics·Figure·Agility·Unitree·AgiBot 선두 기업 분석, 그리고 한국 제조피지컬AI 관점에서의 미래 확산 시나리오까지."` (243자 — 2026-04 사고 예시, 모든 챕터를 한 문단에 나열해버림)

### 부제 (`subtitle`)

- 책의 부제 — "XX에서 YY까지" / "XX의 YY" 형식으로 한 문장. 부연설명과 중복되지 않도록.

## 에러 핸들링 개요

- **입력 모호**: 모드를 단정하지 말고 사용자에게 재확인.
- **선행 조건 미충족**: 구체적 이유 (예: 누락된 파일 경로) + 해결 명령 함께 안내.
- **중간 실패**: 이미 만든 파일은 남긴다. 사용자에게 수동 정리 권장. 부분 진행 상태를 다음 실행에서 이어받지 않음 (안전 우선).
- **Cross-repo 조작**: terryum-ai 측 변경(surveys.json, public/images/)은 MODE B 시에만 실행. 그 외 스텝은 terry-surveys 로컬만 건드림.

## 참고 파일

- **MODE A 세부**: `references/bootstrap-playbook.md`
- **MODE B 세부**: `references/registration-playbook.md`
- **집필 오케스트레이션 세부 (기본 집필 모드)**: `references/orchestration-playbook.md`
- **전 생애주기 가이드**: `references/unified-survey-guide.md` (새 사람이 먼저 읽을 문서)
- **에이전트 템플릿**: `references/agent-template/README.md`
- **부트스트랩 스크립트**: `scripts/bootstrap.sh`
- **Sync 스크립트**: `scripts/sync_agents.py`
- **하네스 메타스킬 규약**: `~/.claude/skills/harness/SKILL.md` (TeamCreate/SendMessage/TaskCreate 패턴)
- **루트 Canonical Standard**: `/CLAUDE.md` § "서베이 생성 표준"
