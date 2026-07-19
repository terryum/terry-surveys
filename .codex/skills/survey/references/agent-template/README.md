# Canonical Agent Template

이 디렉토리는 **모든 서베이가 공유하는 에이전트 정의의 source of truth**다. 새 서베이를 부트스트랩할 때 `/survey "<title>"`이 이 파일들을 `surveys/<slug>/.claude/agents/`로 복사하고, placeholder를 해당 책의 도메인 컨텍스트로 치환한다.

## 왜 템플릿인가

- **에이전트 역할 = 공통, 도메인 = 고유**: v2 controller의 KG → source strategy → parallel research → evidence synthesis → bilingual writing → image/factcheck → independent QA 흐름은 모든 책이 공유한다.
- **한 곳에서 발전**: 팀이 집필 중 발견한 개선 사항(새 에러 케이스, 새 팀 통신 패턴)을 이 템플릿에 반영하면, 다음 새 책은 자동으로 최신 버전을 복사해간다.
- **기존 책 sync는 선택**: `/survey --sync-agents <slug>` 호출 시에만 기존 책의 `.claude/agents/`와 diff를 보여주고 사용자 승인 후 동기화.

## 포함 파일

| 파일 | 역할 |
|---|---|
| `kg-mapper.md` | Terry KG · 기존 서베이 · exact link seed |
| `deep-researcher.md` | foundations/frontier 연구 샤드 템플릿 |
| `evidence-librarian.md` | 검색 프로토콜 · dedup · source/claim/chapter packet |
| `book-writer.md` | 양국어 챕터 병행 집필 |
| `image-curator.md` | 논문 원본 figure 우선 큐레이션 |
| `fact-checker.md` | 인용 · 수치 · ID 정규화 |
| `qa-reviewer.md` | 경계면 교차 검증 · 출시 관문 |

## Placeholder 문법

템플릿 파일 곳곳에 아래 placeholder가 있다. `/survey`의 부트스트랩 단계에서 사용자 입력 또는 `survey.json` 읽기로 치환된다.

| Placeholder | 치환 예시 | 출처 |
|---|---|---|
| `{{DOMAIN}}` | `robotic tactile sensing for dexterous hands` | 사용자 입력 또는 `survey.json.description` |
| `{{CHAPTERS}}` | `Ch1: Taxonomy, Ch2: Sensors, Ch3: Manipulation, ...` | `survey.json.parts[].chapters[]`에서 자동 생성 |
| `{{TERMS}}` | `GelSight, TactoSense, tactile retargeting` | 사용자 입력 또는 `glossary.md`에서 top-K |
| `{{SURVEY_SLUG}}` | `robot-hand-tactile-sensor` | kebab-case slug |
| `{{SURVEY_DIR}}` | `surveys/robot-hand-tactile-sensor` | 모노레포 루트 기준 |
| `{{RESEARCHER_ROLE}}` | `foundations` 또는 `frontier` | split researcher 생성 시 AGENT_SPECS |

Placeholder가 포함된 영역은 **사용자 치환 가능 영역** — `/survey --sync-agents`가 3-way diff 시 이 영역은 per-survey 값 보존, 나머지 공통 영역만 템플릿 기준으로 업데이트.

## 발전 규약

### 템플릿 수정 시

1. 이 디렉토리의 해당 파일(`*.md`) 수정.
2. 변경 의도를 이 README 하단의 "변경 이력" 섹션에 추가 (한 줄).
3. **새 책은 자동으로 최신을 복사**하므로 별도 조치 불필요.
4. **기존 책에 반영하려면**: `/survey --sync-agents --all --dry-run` 으로 diff 확인 후 `--apply`로 적용.

### placeholder 추가 시

1. 이 README의 "Placeholder 문법" 표에 추가.
2. `/survey` 스킬의 `scripts/bootstrap.sh`와 `scripts/sync_agents.py`에 치환 로직 추가.
3. 기존 템플릿 파일에서 해당 placeholder를 사용.

### 새 에이전트 추가 시

1. 이 디렉토리에 `<name>.md` 추가 (다른 에이전트와 동일 구조: 역할 · 원칙 · 입출력 · 에러 · 팀통신 · 체크리스트).
2. 루트 `CLAUDE.md` "서베이 생성 표준" § "정규 에이전트 파이프라인"에 해당 에이전트 추가.
3. 이 README 표에 추가.

## 참고

- 에이전트 정의 구조·팀 통신 프로토콜 표준: `~/.claude/skills/harness/references/agent-design-patterns.md`
- 서베이 책 생성 레슨: `~/.claude/skills/harness/references/book-creation-playbook.md`
- 포맷 불변 규칙: 루트 `/CLAUDE.md` § "서베이 생성 표준"

## 변경 이력

- 2026-06-18: full survey anti-skeleton, baseline parity, referenced-figure, WIP deploy blocker 게이트를 book-writer/image-curator/qa-reviewer 템플릿에 반영.
- 2026-04-23: 초기 템플릿 6종 생성 (deep-researcher, critical-analyst, book-writer, image-curator, fact-checker, qa-reviewer).
- 2026-06-18: exhaustive depth and process gates strengthened; mutable thresholds moved to `survey_harness/config/quality_profiles.yaml`.
- 2026-07-14: KG mapper와 evidence librarian을 추가하고 신규 생성 스펙을 v2 8-role controller에 맞춤.
