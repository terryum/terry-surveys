# Unified Survey Guide — 부트스트랩부터 유지보수까지

terry-surveys 모노레포에서 서베이 책 한 편의 **전 생애주기**를 `/survey` 한 스킬로 관리하는 통합 가이드. 처음 접하는 사람이 이 문서 하나로 시작에서 배포·운영까지 따라갈 수 있도록 설계됐다.

## 한눈에 보기

```
새 책 시작                    ─── /survey "<제목>"
   │
   ▼
1. scaffold (build.py --new)
2. .claude/agents/ × 7 생성 (deep-researcher 템플릿은 foundations/frontier 2개로 expand) + placeholder 치환
3. 인덱스 + 검증
   │
   ▼
집필 (멀티에이전트 하네스 팀, 기본) ─── /survey --orchestrate <slug>
   TeamCreate(survey-<slug>, 7 agents)
   ├─ deep-researcher-foundations ─┐ 샤드 병렬 (pre-2024 기초)
   ├─ deep-researcher-frontier ────┤ 샤드 병렬 (2024+ 최전선)
   │   └── merge_research_shards.py → canonical papers.json
   ├─ critical-analyst ────────────┤ 의존성 그래프 + SendMessage 자체 조율
   ├─ book-writer ×16 ─────────────┤ (챕터별 병렬 집필)
   ├─ image-curator ───────────────┤ (챕터 완료 이벤트 스트리밍)
   ├─ fact-checker ────────────────┤ (챕터 완료 이벤트 스트리밍)
   └─ qa-reviewer ─────────────────┘ (incremental + 최종 관문)
   │
   ▼
빌드 + 배포 ─── /survey --deploy <slug>
   build.py <slug> → scripts/push.sh → Cloudflare Pages
   │
   ▼
홈페이지 갤러리 등록 ─── /survey <cloudflare-url>
   surveys.json 추가 + /cite-post 자동 역링크
   │
   ▼
지속 운영
   /survey --orchestrate <slug> --phase=polish  # 팩트체크·QA 재라운드
   /survey --refresh <slug>                     # staleness 체크
   /survey --factcheck <slug>                   # 수치·인용 재검증
   /survey --link-posts <slug>                  # 포스트 Tier 1 링크
   /survey --sync-agents <slug>                 # 템플릿 최신화 전파
```

## 아키텍처 3-레이어

| 레이어 | 위치 | 역할 |
|---|---|---|
| **공통 스킬** (Layer 1) | `terry-surveys/.claude/skills/` | 모든 서베이가 참조. book-write, deep-literature-research, fact-check, curate-paper-images 등 14개 실파일 + 몇몇 심링크 |
| **Canonical Agent 템플릿** (Layer 2) | `terry-surveys/.claude/skills/survey/references/agent-template/` | 에이전트 정의 6개 템플릿 파일(deep-researcher는 `{{RESEARCHER_ROLE}}` placeholder로 foundations/frontier 2인 생성)의 source of truth. 개선사항을 여기에 반영하면 새 책은 자동으로 최신을 받음 |
| **per-survey 에이전트** (Layer 3) | `surveys/<slug>/.claude/agents/` | 템플릿 복사본 + 도메인 컨텍스트 주입 (`{{DOMAIN}}`, `{{CHAPTERS}}`, `{{TERMS}}`) |

**원칙**: 에이전트 정의(역할)는 per-survey, 스킬(방법)은 모노레포 공통. 스킬은 **중복 생성하지 않는다.**

## Repo Ownership 원칙

- **원본은 주된 작업이 일어나는 repo에 둔다.**
- **terryum-ai는 모든 스킬의 심링크를 가진 허브.**

적용 결과:

| 스킬 | 원본 위치 | terryum-ai 측 |
|---|---|---|
| `/survey` | **terry-surveys** | 심링크 → terry-surveys |
| `/post`, `/project`, `/share`, `/paper-search`, `/defuddle` | terryum-ai | 해당 repo 자체 (원본) |

## MODE 자동 분기

`/survey`는 인자 · 위치로 모드를 자동 판별:

```
$ARGUMENTS 비었거나 --help          → 도움말
$ARGUMENTS 가 URL (http/https) 형태  → MODE B (등록)
cwd가 terry-surveys 내부 & 제목 문자열 → MODE A (부트스트랩)
--bootstrap / --register 명시        → 강제 모드 지정
--orchestrate <slug>                → 멀티에이전트 팀 집필 (기본 집필 모드)
```

- **MODE A 세부**: `bootstrap-playbook.md` 참조.
- **MODE B 세부**: `registration-playbook.md` 참조.
- **오케스트레이션 세부**: `orchestration-playbook.md` 참조.

## 지속 운영 서브커맨드

| 커맨드 | 용도 | 재사용 도구 |
|---|---|---|
| `/survey --orchestrate <slug>` | **기본 집필 모드** — 멀티에이전트 팀 자율 병렬 집필 | `TeamCreate` + 6 agent md + `orchestration-playbook.md` |
| `/survey --sync-agents <slug>` | 템플릿 업데이트를 per-survey에 전파 | `scripts/sync_agents.py` (3-way diff, placeholder 보존) |
| `/survey --refresh <slug>` | 오래된 챕터 리프레시 우선순위화 | `python3 build.py --staleness <slug>` |
| `/survey --factcheck <slug>` | 모든 챕터 팩트체커 재실행 | `.claude/skills/fact-check` + fact-checker 에이전트 |
| `/survey --link-posts <slug>` | Tier 1 포스트 링크 재적용 | `/link-post-to-surveys` 프록시 |
| `/survey --deploy <slug>` | 빌드 + Cloudflare 배포 + 자동 등록 | `build.py <slug>` → `scripts/push.sh` → MODE B 자동 진입 |

## 인덱스 · 포스트 연동

- **서베이 ref → 포스트 링크 자동화**: 각 챕터 `## 참고문헌`의 ref 라인이 arXiv/DOI/Nature ID를 포함하면, `bibtex/refs_index.json`에 자동 편입되어 `/link-post-to-surveys`가 Tier 1 정확 매칭을 수행.
- **포스트 추가 후 자동 역링크**: `/post` 실행 마지막 단계에서 `build.py --impact <post-slug>`를 돌려 해당 논문을 인용한 서베이 챕터를 찾고, Tier 1 매칭에 `[#NN](post-url)` 삽입.
- **수동 트리거**: `/survey --link-posts <slug>`로 특정 서베이에 대해 전수 재적용 가능.

## Staleness & Refresh

```bash
python3 build.py --staleness --all
```
- 각 챕터의 `(age × new-paper-count)` 스코어로 오래된 챕터 + 그 이후 추가된 신규 논문 수를 정렬.
- 상위 챕터부터 `book-writer` / `fact-checker` 호출로 업데이트.
- `/survey --refresh <slug>`가 이 리포트를 보여주고 다음 행동 제안.

## 에이전트 팀 실행 가이드 — `/survey --orchestrate`가 기본

서베이 집필의 **기본 진입점은 `/survey --orchestrate <slug>`**다. `/harness` 규약에 따라 7개 에이전트(deep-researcher 2인 + 5인)가 자율 팀으로 동작한다.

### 핵심 원칙 (순차 Phase 아님)

- 팀원 간 `SendMessage`로 직접 통신
- `TaskCreate`로 의존성 그래프 공유 (addBlockedBy)
- 리더는 `/survey` 스킬 자체 — 모니터링 + T-merge-research 스크립트 실행만
- **deep-researcher 2인 병렬** (foundations + frontier 시간대 분할, 샤드→머지로 중복 회피)
- book-writer의 챕터 간 **병렬**, image-curator·fact-checker는 **스트리밍**, qa-reviewer는 **incremental**

### 호출

```bash
# 전체 팀 기동 (연구·집필·이미지·팩트체크·QA 자율 완주)
/survey --orchestrate humanoid-revolution

# 연구·분석만
/survey --orchestrate humanoid-revolution --phase=research

# 집필만 (research 산출물 전제)
/survey --orchestrate humanoid-revolution --phase=write

# 팩트체크·QA 라운드만
/survey --orchestrate humanoid-revolution --phase=polish

# 특정 챕터만
/survey --orchestrate humanoid-revolution --chapters=1-3

# 병렬 상한 조정 (API rate 이슈 시)
/survey --orchestrate humanoid-revolution --max-parallel=2
```

### 수동 개별 호출 (일반적이지 않음 — 오케스트레이션이 실패할 때만)

```
Agent(
  subagent_type="general-purpose",
  model="opus",
  prompt="surveys/<slug>/.claude/agents/deep-researcher.md 의 역할·원칙·입출력 프로토콜을 따라
         작업을 수행. 도메인: ..., 챕터: ..."
)
```

세부 팀 구성·의존성 그래프·에러 대응은 `orchestration-playbook.md` 참조.

## 트러블슈팅

| 증상 | 확인 사항 |
|---|---|
| `/survey`가 동작 안 함 | `terry-surveys/.claude/skills/survey/SKILL.md` 존재 확인. 심링크가 깨졌으면 `ls -la`로 확인하고 `bootstrap-playbook.md`의 "선행 조건" 검토 |
| 에이전트가 placeholder(`{{...}}`) 그대로 읽음 | `/survey --sync-agents <slug>` 실행. survey.json이 잘 채워져 있는지 확인 |
| `/link-post-to-surveys`가 Tier 1 매칭 0 | refs에 arXiv/DOI ID 누락. fact-checker 재실행으로 `_refs_extracted.json` 갱신 후 `build.py --index` |
| 홈페이지에 서베이가 안 보임 | `projects/surveys/surveys.json`의 엔트리 확인, `npm run build` 통과 여부, Cloudflare Pages 배포 상태 |
| 템플릿 업데이트가 다른 책에 전파 안 됨 | 자동 전파는 **새 책만**. 기존 책은 `/survey --sync-agents <slug>` 명시 실행 필요 |

## 참고 파일

- **부트스트랩 세부**: `bootstrap-playbook.md`
- **등록 세부**: `registration-playbook.md`
- **에이전트 템플릿**: `agent-template/README.md`
- **루트 Canonical Standard**: `/CLAUDE.md` § "서베이 생성 표준"
- **하네스 레슨**: `~/.claude/skills/harness/references/book-creation-playbook.md`
