---
name: survey
description: "Survey 책 생애주기 전 단계를 관리한다. terry-surveys 모노레포에서 호출하면 MODE A(새 책 부트스트랩 = scaffold + .claude/agents/ 템플릿 복사 + 하네스 구성), 배포된 Cloudflare Pages URL을 주면 MODE B(홈페이지 Surveys 갤러리 등록 + /cite-post 자동 호출). **집필은 기본적으로 --orchestrate로 멀티에이전트 하네스 팀이 자율 병렬 수행** (deep-researcher·critical-analyst·book-writer·image-curator·fact-checker·qa-reviewer 6종, TeamCreate + SendMessage + TaskCreate로 자체 조율). 서브커맨드로 --orchestrate(팀 집필), --sync-agents(템플릿 전파), --refresh(staleness), --factcheck, --link-posts(Tier 1 포스트 역링크), --deploy(빌드+배포+등록). 새 서베이 책을 시작·집필·유지보수할 때 반드시 이 스킬을 사용할 것."
argument-hint: "<제목 | URL> [--domain=... | --bootstrap | --register | --orchestrate | --sync-agents | --refresh | --factcheck | --link-posts | --deploy] [--phase=research|write|polish] [--chapters=1-3] [--max-parallel=N] [--visibility=group --group=snu]"
---

# /survey — 서베이 책 생애주기 허브

입력: $ARGUMENTS

이 스킬은 **두 가지 모드**(A: 부트스트랩 / B: 등록)와 **6가지 지속 운영 서브커맨드**로 서베이 책의 모든 단계를 관리한다. 본문은 모드 분기와 요약만 담고, 실제 단계별 세부는 `references/` 내 플레이북을 참조한다.

**집필은 `--orchestrate`가 기본**이다 — 6개 에이전트(`surveys/<slug>/.claude/agents/*.md`)가 `/harness` 규약의 팀 모드로 자율 병렬 수행한다. 순차 Phase 실행이 아니라 의존성 그래프 기반 동시 진행·스트리밍·자체 조율이 표준. 세부는 `references/orchestration-playbook.md` 참조.

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
3. `/gemini-3-image-generation`으로 커버(1:1) + OG(16:9) 이미지 생성.
4. `projects/surveys/surveys.json`에 엔트리 추가 + `next_survey_number` 증가.
5. `npx tsc --noEmit && npm run build`.
6. terry-surveys 책이면 `/cite-post <slug>` 자동 호출 (역링크).
7. `git pull --rebase` 후 커밋·푸시.

그룹 비공개 서베이는 `--visibility=group --group=<slug>`로 surveys.json 대신 Supabase `private_content`에 저장 (Git 커밋 없음).

### 예시
```
/survey https://survey-robot-hand-tactile-sensor.pages.dev
/survey https://survey-snu-tactile-hand.pages.dev --visibility=group --group=snu
```

## 지속 운영 서브커맨드

### `/survey --orchestrate <slug> [--phase=...] [--chapters=...] [--max-parallel=N]` — 기본 집필 모드

**세부는 `references/orchestration-playbook.md` 참조.**

`/harness` 규약의 팀 모드로 6개 에이전트를 기동하여 **자율 병렬 집필**. 순차 Phase 아님 — 의존성 그래프 기반 동시 진행·스트리밍이 기본.

**리더(오케스트레이터 = /survey 스킬 자체) 동작**:
1. `TeamCreate(name="survey-<slug>", members=[deep-researcher, critical-analyst, book-writer, image-curator, fact-checker, qa-reviewer])` — 각 에이전트는 `surveys/<slug>/.claude/agents/<name>.md`를 system prompt로 로드, 모델 `opus`.
2. `TaskCreate`로 의존성 그래프 설정 (`addBlockedBy`로 표현):
   - deep-researcher → `_research/papers.json` (부분 산출도 하위 블록 해제)
   - critical-analyst (blockedBy: research 부분) → `_analysis/gaps.md`
   - book-writer × 챕터 수 (blockedBy: 해당 Part analysis) — 챕터 간 독립, **병렬 실행**
   - image-curator, fact-checker — 챕터 완료 이벤트에 **스트림 처리**
   - qa-reviewer — 진행 중 incremental QA + 최종 관문
3. 팀원들이 `SendMessage`로 자체 조율 (발견 공유·수정 요청·상충 토론).
4. 리더는 `TaskList`로 진행 모니터링, 작업은 안 함. 완료 감지 시 `TeamDelete`.

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

### `/survey --link-posts <slug>`

`/link-post-to-surveys <slug>` 프록시. Tier 1(arXiv/DOI/Nature 정확 매칭) 링크만 자동 삽입. Tier 2는 수동 승인 흐름.

### `/survey --deploy <slug>`

```bash
python3 build.py <slug>                                 # 빌드
bash surveys/<slug>/scripts/push.sh "deploy message"    # Cloudflare Pages
```
배포 후 MODE B로 자동 진입해 `surveys.json` 업데이트 (사용자 확인 후).

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
