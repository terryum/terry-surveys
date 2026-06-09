# Orchestration Playbook — `/survey --orchestrate <slug>`

`/survey`의 **기본 집필 모드**. 서베이 한 편의 연구·집필·큐레이션·팩트체크·QA를 **에이전트 팀이 자체 조율하며 병렬로** 수행한다. 순차 Phase 1→2→3→… 아님. `/harness` 규약의 **에이전트 팀 패턴**을 따른다.

## 왜 팀 모드가 기본인가

에이전트 정의 파일(`surveys/<slug>/.claude/agents/*.md`)은 이미 **"팀 통신 프로토콜"** 섹션을 포함해 팀 모드용으로 설계되어 있다 (각 파일의 "## 팀 통신 프로토콜" 섹션 참조).

- **병렬성**: book-writer의 챕터별 집필은 서로 독립이므로 16개 챕터가 동시 진행 가능.
- **스트리밍**: image-curator·fact-checker는 book-writer가 챕터를 완성할 때마다 이어받음 — 전체 완료 대기 불필요.
- **자체 조율**: 발견·수정·누락을 SendMessage로 즉시 공유하여 긴 피드백 루프(세션 종료 후 재시작)를 없앰.
- **품질**: 팀원 간 상충 토론·보완이 단독 에이전트 순차 실행보다 우수.

순차 Phase 모델은 **진입점 부재 상태의 임시 우회**였다. `--orchestrate`가 이것을 대체한다.

## 실행

```
/survey --orchestrate <slug> [--phase=research|write|polish] [--chapters=1-3] [--max-parallel=N]
```

- **기본** (`--phase` 생략): 전체 팀 기동, 의존성 그래프에 따라 자율 진행.
- **`--phase=research`**: deep-researcher + critical-analyst만 기동. `_research/`·`_analysis/` 산출물까지 확보하고 멈춤.
- **`--phase=write`**: book-writer 중심 기동 (image-curator는 on-demand). 이미 research/analysis가 있을 때 집필만 돌리는 용도.
- **`--phase=polish`**: fact-checker + qa-reviewer만 기동. 본문이 완성된 후의 마무리 라운드.
- **`--chapters=1-3`**: 특정 챕터만. 부분 업데이트·리프레시에 사용.
- **`--max-parallel=N`**: 동시 진행 챕터 수 상한 (기본 4). GPU/API rate limit에 맞춰 조정.

## 팀 구성 (`TeamCreate`)

```
team_name: "survey-<slug>"
members (7):
  - deep-researcher-foundations  (model: opus)  # pre-2024 기초·방법론 계보
  - deep-researcher-frontier     (model: opus)  # 2024–현재 최전선·산업 발표
  - critical-analyst             (model: opus)
  - book-writer                  (model: opus)
  - image-curator                (model: opus)
  - fact-checker                 (model: opus)
  - qa-reviewer                  (model: opus, 타입: general-purpose)
leader: /survey 스킬 (오케스트레이터) — TaskCreate/TaskUpdate로 진행 추적, 완료 감지, 팀 정리
```

**deep-researcher 2인 분할 근거**: 단일 researcher가 전체 파이프라인의 병목. 2024년 발행 논문 수 폭증으로 전체 corpus의 60%가 최근 2년치 → 시간대로 분할하면 병렬화 가능. 자세한 역할 분담·중복 회피 프로토콜은 `agent-template/deep-researcher.md` 참조.

## 의존성 그래프 (`TaskCreate` with `addBlockedBy`)

```
T-research-foundations:  deep-researcher-foundations → _research/papers_foundations.json, groups_foundations.md, timeline_foundations.md
T-research-frontier:     deep-researcher-frontier    → _research/papers_frontier.json, groups_frontier.md, timeline_frontier.md
                                      ├─ 두 태스크 병렬. 상호 SendMessage로 경계·중복 조율
                                      └─ 각자 60% 완료 시 peer에 cross-coverage 요청

T-merge-research:        orchestrator (자동)         → _research/papers.json, groups.md, timeline.md, _merge_report.md
                           blockedBy: T-research-foundations, T-research-frontier (둘 다 완료)
                           **선행 검증 (필수, 머지 직전)**: 각 role(foundations, frontier)에 대해
                             papers_{role}.json + groups_{role}.md + timeline_{role}.md
                           3종 모두 존재 확인. 누락 발견 시 즉시 해당 researcher에게
                           SendMessage("missing <file> 작성 요청") 후 1회 재시도. 재실패 시 사용자 에스컬레이션.
                           **silent skip 금지**: 머지 스크립트의 missing-shard WARN을 stderr/stdout에서 캐치하여
                           T-task fail로 처리 (2026-04-29 사고 — frontier가 timeline_frontier.md를 생략했고
                           머지가 silent skip하면서 timeline.md가 foundations-only로 굳어짐).
                           실행: python3 .claude/skills/survey/scripts/merge_research_shards.py <slug>
                           샤드 자동 dedup + union (arxiv_id/doi/title 기반)

T-analysis:    critical-analyst    → _analysis/gaps.md, novelty_matrix.md, positioning.md
                 blockedBy: T-merge-research (부분 — 샤드 60% 시점의 중간 머지도 허용)
                 → deep-researcher-{foundations|frontier}에게 추가 조사 요청(SendMessage) 수시 발송
                 **완료 검증 (필수, T-write 차단 해제 직전)**: `ls _analysis/{gaps,novelty_matrix,positioning}.md`
                 3종 모두 존재 확인. 빠진 파일이 있으면 critical-analyst에 SendMessage("missing <file>") + 1회 재시도.
                 재실패 시 사용자 에스컬레이션 — 부분 완료로 다음 단계 넘기지 말 것.
                 (2026-04-29 사고: physical-ai-manufacturing의 _analysis/가 빈 채로 책 출판까지 흘러감)

T-write-ch<N>: book-writer         → book/{ko,en}/ch<N>.md (× 16)
                 blockedBy: T-analysis (해당 Part 관련 부분)
                 병렬 실행: 최대 --max-parallel 챕터 동시
                 완료 시 image-curator·fact-checker 에 SendMessage

T-image-ch<N>: image-curator       → assets/figures/ch<N>_*, 챕터 md의 <!-- IMAGE --> 치환
                 blockedBy: T-write-ch<N> (스트리밍 — placeholder 확정 시점부터)
                 **티어 쿼터 강제**: theory 3–5 · method 3–6 · platform 4–8 (+실제 사진 ≥ 2) · history 3–5
                 **alt 텍스트 대괄호 금지**: [Author, Year] → Author et al. Year 형식 (build.py validate가 거부)
                 **완료 검증 (필수)**: `_assets_log.md` 존재 + `grep -rn '<!-- IMAGE:' book/` 결과 0줄 +
                 챕터 N의 `assets/figures/chNN_*` 파일 ≥ 티어 quota 하한. 미충족 시 1회 재시도.

T-fact-ch<N>:  fact-checker        → _refs_extracted.json, _factcheck_report.md (챕터별 누적)
                 blockedBy: T-write-ch<N>
                 **완료 검증 (필수)**: 두 파일 모두 존재 + 해당 챕터 엔트리가 _refs_extracted.json에 누적됨.

T-qa:          qa-reviewer         → _qa_report.md, READY FOR RELEASE 플래그
                 blockedBy: 모든 T-write-*, T-fact-*, T-image-*
                 중간 감사(incremental QA)도 수행 — 챕터 3개 완료 시마다 스팟 체크
                 **완료 검증 (필수)**: `_qa_report.md` 존재 + 마지막 줄 "READY FOR RELEASE" 또는 "BLOCKED: <이유>".
                 부재 시 절대 배포 단계로 넘어가지 말 것 (2026-04-29 사고 패턴 — silent skip이 6 agent 모두에서 가능).
```

**핵심 속성**:
- deep-researcher 2인은 "완료" 없이도 부분 산출물을 지속 공급. 샤드 60% 시점에 중간 머지 실행 → critical-analyst가 조기 착수 가능.
- **중복 회피는 샤드 분리로**: 두 에이전트는 자기 샤드에만 쓰고, 쓰기 전 peer 샤드 grep 필수. 경계 논문은 `SendMessage`로 battery.
- book-writer의 챕터 간에는 순서 없음. 의존은 **해당 챕터의 Part-level analysis**만 — Part II가 준비되면 Ch4~7이 동시 출발.
- image-curator·fact-checker는 **스트림 워커**. 각 챕터 완료 이벤트를 받아 처리.
- qa-reviewer는 **incremental QA** — 끝에 한 번이 아니라 진행 중 지속.

## 통신 프로토콜 (`SendMessage`)

에이전트 정의 파일의 "팀 통신 프로토콜" 섹션 정의에 따라 자체 발송. 주요 패턴:

| 발신 → 수신 | 메시지 예 |
|---|---|
| deep-researcher-foundations → deep-researcher-frontier | "Noticed 2024 arxiv paper in your territory: He et al. ASAP 2025. Not adding to my shard — please include and link back to Hwangbo 2019 lineage." |
| deep-researcher-frontier → deep-researcher-foundations | "Your wensing2017 entry: please add chapter_hint [Ch4, Ch11] and tags [industrial-revival]. Figure / Unitree reuse this architecture." |
| book-writer → image-curator | "Ch 7 sim-to-real 섹션에 ASAP delta action 다이어그램 placeholder 심었음. He et al. 2025 figure 4 크롭 권장" |
| book-writer → fact-checker | "Ch 5 Radosavovic 2023 success-rate 숫자 86% 기재했는데 Science 논문 원문 Table 2 확인 부탁" |
| critical-analyst → deep-researcher-foundations | "KAIST HUBO 후속 계보 커버리지 부족 — 2023 이전 서울대 ME RCV 랩 논문 조사 요청" |
| critical-analyst → deep-researcher-frontier | "2025년 Agility Motor Cortex 백서 원문 확보 필요" |
| fact-checker → book-writer | "Ch 12 Figure Helix 02 파라미터 10M → 원문엔 8M. 수정 권고" |
| qa-reviewer → all | "Ch 3 교차 참조 깨짐 — (Chapter 7) 언급했지만 Ch 7 제목 변경됨. book-writer 확인" |

## 리더(오케스트레이터) 책임

`/survey --orchestrate` 호출 시 `/survey` 스킬 자체가 리더가 된다:

1. **TeamCreate**: `survey-<slug>` 팀 생성, 7개 에이전트 로드 (`surveys/<slug>/.claude/agents/*.md`). deep-researcher는 `deep-researcher-foundations.md`와 `deep-researcher-frontier.md` 두 파일.
2. **TaskCreate**: 위 의존성 그래프를 `addBlockedBy`로 표현. T-merge-research는 자동 task (에이전트 owner 없음; 리더 본인이 실행).
3. **컨텍스트 주입**: 각 에이전트에 `_research/seed.md`, `survey.json`, 루트 `CLAUDE.md` + 본인 role 식별(`RESEARCHER_ROLE=foundations` or `frontier`)을 초기 컨텍스트로 제공.
4. **모니터링**: TaskList로 진행률 추적. 리더는 **작업하지 않고 조율만** 한다. 단 예외: T-merge-research는 리더가 직접 실행하며, **머지 직전에 6종 출력 존재 검증** (각 role의 papers/groups/timeline.md). 누락 발견 시 머지 진행 금지 — 해당 researcher에 재작업 요청. 머지 후 stderr에 `WARN: missing` 또는 stdout에 `WARNING: N missing shard md files`가 있으면 동일하게 fail로 처리.
5. **에러 대응**:
   - 에이전트 1회 실패 → 재시도 1회
   - 재실패 → 해당 산출물 플래그 후 팀은 진행 (결과 없이 보고서에 누락 명시)
   - 상충 결과(예: deep-researcher와 fact-checker가 동일 논문에 다른 arXiv ID) → 삭제 금지, 두 주장 병기
   - 머지 스크립트 실패(중복 arxiv_id 충돌) → `_merge_report.md`에 충돌 기록 후 리더가 수동 dedup 결정 또는 qa-reviewer에 에스컬레이션
6. **종료 감지**: qa-reviewer가 "READY FOR RELEASE" 플래그 + 모든 T-task `completed` → `TeamDelete`로 팀 정리.
7. **출력 요약**: 사용자에게 완성 요약 (챕터 × 2언어, ref 수, figure 수, 커버리지 %, 남은 이슈, 샤드별 기여도).

## 세션 분할 전략

대형 서베이(16챕터)는 한 세션에서 완주 못 할 수 있다. 리더는 다음 체크포인트를 존중:

- **Checkpoint A** (약 30% 완료): _research/ + _analysis/ + book-writer가 Part I 완료.
- **Checkpoint B** (약 60% 완료): book-writer가 Part III까지 + fact-checker 일부.
- **Checkpoint C** (약 90% 완료): 모든 챕터 초안 + fact-checker 90%+.
- **Checkpoint D** (출시 가능): qa-reviewer 승인.

체크포인트마다 현재 상태를 `_workspace/orchestration_state.json`에 저장. 다음 세션이 `/survey --orchestrate <slug> --resume`으로 이어받음 (구현 TODO).

## Phase 플래그 상세

### `--phase=research`

```
팀원: deep-researcher-foundations, deep-researcher-frontier, critical-analyst
산출:
  - _research/papers_foundations.json + papers_frontier.json (샤드)
  - _research/papers.json (머지 canonical)
  - groups_{role}.md → groups.md / timeline_{role}.md → timeline.md
  - _analysis/gaps.md · novelty_matrix.md · positioning.md
리더 종료 조건: papers.json에 최소 60편 (샤드 합산) + gaps.md 5개 항목 + positioning.md 완성 + _merge_report.md에 dedup 통계
```

### `--phase=write`

```
팀원: book-writer, image-curator, (fact-checker는 on-demand)
전제: _research/·_analysis/ 가 이미 존재. 없으면 에러.
산출: book/{ko,en}/ch*.md 전체 (또는 --chapters로 제한)
리더 종료 조건: 지정 챕터 모두 초안 완료 + placeholder 잔존 0
```

### `--phase=polish`

```
팀원: fact-checker, qa-reviewer, (book-writer는 수정 수신만)
전제: 초안이 모두 있음.
산출: _refs_extracted.json · _factcheck_report.md · _qa_report.md · READY FOR RELEASE 플래그
리더 종료 조건: qa-reviewer가 승인 신호
```

## 팀 크기·병렬성 튜닝

| `--max-parallel` | 용도 | 주의 |
|---|---|---|
| 1 | 디버깅·관찰 | 매우 느림, 1시간+ |
| 2~3 | API rate 제한이 빡빡할 때 | 기본 추천의 절반 속도 |
| **4** (기본) | 일반 사용 | 챕터 4개 동시 집필, 리뷰·이미지 스트리밍 병행 |
| 6~8 | 고성능·풍부한 API quota | 책 1권 30~60분 완주 가능 |

모델은 전부 `opus`로 통일. Haiku로 다운그레이드 금지 (루트 harness 규약).

## 에러 복구

| 증상 | 대응 |
|---|---|
| deep-researcher-{role}가 arXiv API timeout | 해당 논문 `status: incomplete`로 기록, 팀 진행. qa-reviewer가 나중에 재검증 플래그 |
| deep-researcher 2인 중 한 쪽만 완료 신호 | 리더가 5분 대기 후 병행 진행. 미완 샤드는 부분 머지 후 flag `partial_merge: true` 기록, qa-reviewer가 커버리지 재감사 |
| 머지 스크립트가 arxiv_id 충돌 감지 | `_merge_report.md`에 충돌 기록. 양쪽 method_summary 다르면 longer 본 채택 + 다른 본을 `method_summary_alt` 필드에 보존 |
| 경계년도 논문 중복 진입 (peer grep 실패) | 머지 스크립트가 dedup. owner 필드를 먼저 entry한 쪽으로 정규화 |
| book-writer가 같은 챕터 두 번 편집 | TaskCreate의 챕터별 단일 owner 원칙으로 방지. 충돌 시 파일 mtime 기반 최신본 채택 + diff 기록 |
| image-curator가 논문 PDF 접근 불가 | `<!-- IMAGE: 대체 일러스트 요청 -->` 로 변환, OpenAI gpt-image-2 medium fallback (`--style survey-dark --ratio 16:9`; 챕터당 상한 없음) |
| fact-checker가 수치 불일치 발견 | book-writer에 SendMessage로 정정 제안. 10초 무응답 시 보수적으로 "approximately" 완화 표현으로 수정 후 로그 |
| qa-reviewer가 CRITICAL 이슈 발견 | 해당 담당 에이전트에 재작업 요청. 3회 실패 시 사용자 개입 요청 |

## 호출 예

```bash
# 전체 팀 기동 (집필 시작)
/survey --orchestrate humanoid-revolution

# 연구·분석만
/survey --orchestrate humanoid-revolution --phase=research

# 특정 Part만 집필 (이미 research 완료 상태)
/survey --orchestrate humanoid-revolution --phase=write --chapters=1-3

# 마무리 라운드
/survey --orchestrate humanoid-revolution --phase=polish
```

## 참조

- **에이전트 정의 템플릿**: `agent-template/*.md` — 각 에이전트의 팀 통신 프로토콜 섹션
- **/harness 규약**: `~/.claude/skills/harness/SKILL.md` — TeamCreate/SendMessage/TaskCreate 패턴
- **루트 CLAUDE.md § 정규 에이전트 파이프라인**: 에이전트 역할·산출물 정의
- **bootstrap-playbook.md**: 부트스트랩 단계 (이 오케스트레이션 이전)
- **unified-survey-guide.md**: 전 생애주기 조망
