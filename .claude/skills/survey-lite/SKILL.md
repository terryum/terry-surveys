---
name: survey-lite
description: "토큰 효율 최적화 버전의 서베이 집필 오케스트레이션. 검색·검증·큐레이션 에이전트에 Sonnet을 사용하고 챕터별 fresh sub-agent로 컨텍스트 누적을 방지한다. /survey와 동일한 결과물 구조를 목표로 하되 비용 40-60% 절감. 전제: 서베이가 이미 /survey 또는 build.py --new로 스캐폴딩되어 있어야 한다. '/survey-lite', 'lite 버전 서베이', '토큰 절약 서베이', '가벼운 서베이' 요청 시 사용."
argument-hint: "<slug> [--phase=research|write|polish] [--chapters=N-M] [--max-parallel=N]"
---

# /survey-lite — 토큰 최적화 서베이 오케스트레이션

입력: $ARGUMENTS

/survey와 동일한 파이프라인을 더 효율적으로 실행한다.  
**수정하지 않는 것**: /survey, 기존 에이전트 파일들.  
**달라지는 것**: (1) 에이전트별 모델 선택, (2) 챕터별 fresh sub-agent로 컨텍스트 누적 방지.

## Step 0. 파싱 및 전제 확인

```
slug          = $ARGUMENTS의 첫 번째 단어 (예: vla-agentic-robotics)
phase         = --phase=xxx 값 (미지정 시 전체)
chapters_range = --chapters=N-M (미지정 시 전체)
max_parallel  = --max-parallel=N (기본 4)
```

**전제 확인**:
```bash
ls surveys/<slug>/survey.json          # 없으면 /survey "<제목>" 먼저 실행 안내
ls surveys/<slug>/.claude/agents/      # 없으면 bootstrap 필요
```

**⚠ Visibility 가드 (필수 — 2026-04-29 leak 사고 후 추가):**
부트스트랩이 잘못돼서 group-private 콘텐츠가 PUBLIC repo에 들어가 있는 경우 lite 흐름이 추가 leak을 가속하지 않도록 abort:
```bash
visibility=$(python3 -c "import json; print(json.load(open('surveys/<slug>/survey.json')).get('visibility','public'))")
if [ "$visibility" = "group" ] && [ ! -L "surveys/<slug>" ]; then
  echo "ABORT: visibility=group이지만 surveys/<slug>가 심링크가 아님 — terry-private으로 이전 필요"
  echo "  /survey 스킬의 부트스트랩 fix 또는 link-private.sh 실행"
  exit 1
fi
```

survey.json을 읽어 domain, 챕터 목록, parts 구조를 파악한다.

---

## 모델 티어 — 왜 이 분류인가

| 에이전트 | /survey | /survey-lite | 이유 |
|---|---|---|---|
| deep-researcher-**foundations** | opus | **opus** | 방법론 계보 추적, 기술 연결 이해 — 추론 품질 직결 |
| deep-researcher-**frontier** | opus | **sonnet** | 광역 스캔(80–100편) — 검색·추출 위주, 합성은 critical-analyst가 담당 |
| critical-analyst | opus | **opus** | 전략적 gap 분석, novelty 평가 — 핵심 판단 |
| book-writer | opus | **opus** | 양국어 서사 집필 — 정확성·문학성 동시 요구 |
| image-curator | opus | **sonnet** | figure 수집·캡션·네이밍 — tier quota 규칙이 명시적 |
| fact-checker | opus | **sonnet** | 인용 ID 검증, 수치 대조 — 비교·조회 위주 (mechanical baseline은 이미 build.py) |
| qa-reviewer | opus | **opus** | 품질 관문 — 다른 에이전트 오류의 최종 방어선 |

**결과**: Opus 4개 + Sonnet 3개.

---

## 컨텍스트 관리 원칙 (lite의 핵심 차별점)

### 문제: 단일 에이전트 세션의 컨텍스트 누적

단일 book-writer 세션이 10챕터를 순서대로 쓰면, 챕터 8부터 이전 7챕터 전문 + papers.json 전체(~150편)가 Opus 컨텍스트에 쌓인다. 이미 완료된 챕터는 "참고"가 아닌 "비용"이다.

### 해결: 챕터별 fresh sub-agent + papers 슬라이싱

1. **챕터별 fresh sub-agent**: 오케스트레이터가 챕터 N마다 독립적인 book-writer sub-agent를 기동. 각 서브에이전트는 타 챕터 내용을 모른다.
2. **Chapter-scoped papers**: papers.json 전체 대신 해당 챕터 관련 논문만 (`chapter_hint`에 N 포함) 전달.

**절감 규모**: 전체 papers.json(~40K 토큰) → 챕터별 ~20편(~5K 토큰). 10챕터 서베이 기준 Opus 입력 토큰 ~70% 절감.

---

## 오케스트레이션 플로우

### Phase 1 — Research

foundations(Opus)와 frontier(Sonnet)을 **병렬** 기동. 각 에이전트는 `surveys/<slug>/.claude/agents/deep-researcher-foundations.md` / `deep-researcher-frontier.md`를 따른다.

```
병렬 기동 (run_in_background=True):
  Agent(
    subagent_type="deep-researcher-foundations",
    model="opus",
    prompt="surveys/<slug>/.claude/agents/deep-researcher-foundations.md의 역할과 프로토콜을 읽고
            해당 서베이의 foundations 조사를 수행하라. slug: <slug>"
  )
  Agent(
    subagent_type="deep-researcher-frontier",
    model="sonnet",   ← lite: sonnet
    prompt="surveys/<slug>/.claude/agents/deep-researcher-frontier.md의 역할과 프로토콜을 읽고
            해당 서베이의 frontier 조사를 수행하라. slug: <slug>"
  )

둘 완료 후 검증 + merge:
  # ⚠ 필수 검증 — 머지 직전. 각 deep-researcher가 약속한 3종 출력이 모두 존재하는지 확인.
  # Sonnet 다운그레이드된 frontier가 timeline_*.md 같은 보조 출력을 누락할 가능성 있음.
  # 누락 시 머지 스크립트가 silent skip 후 timeline.md/groups.md가 한쪽 샤드만 반영된 상태로 굳어짐 (2026-04-29 사고).
  for role in (foundations, frontier):
      assert exists(f"surveys/<slug>/_research/papers_{role}.json")
      assert exists(f"surveys/<slug>/_research/groups_{role}.md")
      assert exists(f"surveys/<slug>/_research/timeline_{role}.md")
  # 누락 발견 시: 해당 researcher 에이전트에 SendMessage("missing <file> — 작성 요청") 후 1회 재시도.
  # 재시도 후에도 누락이면 사용자에 에스컬레이션. 절대 그냥 머지로 넘어가지 말 것.

  Bash("python3 .claude/skills/survey/scripts/merge_research_shards.py <slug>")
  # 머지 스크립트 stderr에 "WARN: missing ..." 또는 stdout에 "WARNING: N missing shard md files"
  # 출력이 있으면 위 검증이 누락한 것 — 즉시 중단하고 사용자에 보고.
```

> **참고**: `subagent_type`이 per-survey 에이전트 파일을 찾지 못하면, `general-purpose` 타입을 쓰되 prompt 앞부분에 해당 에이전트 파일의 전체 내용을 인용(Read 후 임베드)한다.

### Phase 2 — Analysis

```
Agent(
  subagent_type="critical-analyst",
  model="opus",
  prompt="surveys/<slug>/_research/papers.json와 merge_report를 기반으로
          gap 분석, novelty 평가, positioning.md를 작성하라. slug: <slug>"
)
```

### Phase 3 — Write (챕터별 fresh sub-agent)

각 챕터 N에 대해 순차 또는 최대 `max_parallel`개 병렬:

**Step 3a. Chapter-scoped papers 생성** (챕터별, 기동 직전):

⚠ **출력 위치 주의**: `_research/`가 아니라 `_workspace/`에 쓴다. `_research/papers_*.json`은 deep-researcher 샤드 컨벤션이고 merge 스크립트의 auto-discovery 대상이다. 챕터 뷰를 거기 두면 다음 머지 실행 시 샤드로 오인되어 dedup 통계가 망가진다 (2026-04-29 사고).

```bash
mkdir -p surveys/<slug>/_workspace
python3 -c "
import json, sys, os
slug, n = sys.argv[1], sys.argv[2]
papers = json.load(open(f'surveys/{slug}/_research/papers.json'))
ch = [p for p in papers if n in str(p.get('chapter_hint', ''))]
out = f'surveys/{slug}/_workspace/papers_ch{n}.json'
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(ch, open(out,'w'), ensure_ascii=False, indent=2)
print(f'Ch{n}: {len(ch)} papers → {out}')
" <slug> <N>
```

**Step 3b. Fresh book-writer 기동**:
```
Agent(
  subagent_type="book-writer",
  model="opus",      ← book-writer는 opus 유지
  prompt="""
surveys/<slug>/.claude/agents/book-writer.md의 역할과 포맷 규칙을 따라 챕터 N을 집필하라.

입력 파일 (이것만 읽을 것 — 다른 챕터 파일·전체 papers.json 로드 금지):
  - surveys/<slug>/_workspace/papers_ch<N>.json   ← 해당 챕터 논문만
  - surveys/<slug>/_analysis/gaps.md의 "Chapter N" 관련 섹션만
  - surveys/<slug>/survey.json의 parts[].chapters[N] outline

출력:
  - surveys/<slug>/book/ko/ch<NN>.md
  - surveys/<slug>/book/en/ch<NN>.md
"""
)
```

### Phase 4 — Images (챕터별 Sonnet)

```
Agent(
  subagent_type="image-curator",
  model="sonnet",    ← lite: sonnet
  prompt="챕터 <N> figure 큐레이션.
          입력: surveys/<slug>/book/ko/ch<NN>.md + surveys/<slug>/_workspace/papers_ch<N>.json
          surveys/<slug>/.claude/agents/image-curator.md 규칙 준수"
)
```

### Phase 5 — Fact-check (챕터별 Sonnet)

먼저 mechanical baseline 자동 생성:
```bash
python3 build.py --refresh-refs <slug>
```

각 챕터별 fresh Sonnet sub-agent:
```
Agent(
  subagent_type="fact-checker",
  model="sonnet",    ← lite: sonnet
  prompt="챕터 <N> fact-check.
          입력: surveys/<slug>/book/ko/ch<NN>.md + surveys/<slug>/_workspace/papers_ch<N>.json + bibtex/references.bib
          출력: _refs_extracted.json 해당 챕터 엔트리 갱신 + _factcheck_report.md 섹션 추가
          surveys/<slug>/.claude/agents/fact-checker.md 역할 참조"
)
```

### Phase 6 — QA

```
Agent(
  subagent_type="qa-reviewer",
  model="opus",
  prompt="surveys/<slug>/.claude/agents/qa-reviewer.md 역할로 전체 서베이 품질 검증.
          입력: book/ko + book/en 전체 챕터, _refs_extracted.json, _factcheck_report.md"
)
```

---

## Phase 플래그 분기

| 플래그 | 실행 Phase | 전제 |
|---|---|---|
| `--phase=research` | Phase 1 + 2 | survey.json 존재 |
| `--phase=write` | Phase 3 | papers.json + gaps.md 존재 |
| `--phase=polish` | Phase 4 + 5 + 6 | book/*/ch*.md 완성 |
| (미지정) | Phase 1–6 전체 | survey.json 존재 |
| `--chapters=N-M` | Phase 3-5에서 N~M번만 | papers.json 존재 |

---

## /survey vs /survey-lite 선택 가이드

```
연구 계보가 복잡하고 논문 간 미묘한 연결이 중요한 도메인   → /survey
빠른 초안 작성 후 품질 검토 예정                          → /survey-lite
비용보다 품질이 절대 우선인 중요 프로젝트                  → /survey
넓은 커버리지가 중요하고 개별 논문 깊이는 부차적            → /survey-lite
처음 사용해보거나 lite 품질 검증 중                        → /survey-lite로 시작
```

---

## 완료 체크리스트

- [ ] survey.json + .claude/agents/ 존재 확인
- [ ] **Phase 1 종료 시 6종 출력 검증**: `papers_{foundations,frontier}.json` + `groups_{foundations,frontier}.md` + `timeline_{foundations,frontier}.md` 모두 존재 (Sonnet downgrade로 보조 출력 누락 위험 — 2026-04-29 사고)
- [ ] **머지 스크립트 stderr/stdout에 WARN 없음** (있으면 누락 샤드 — 즉시 중단)
- [ ] `_merge_report.md`의 `foundations entries / frontier entries` 둘 다 0이 아님
- [ ] `_research/papers.json` 존재 (없으면 Phase 1부터)
- [ ] 각 챕터 기동 전 `_workspace/papers_ch<N>.json` 생성 확인 (← `_research/`가 아님)
- [ ] frontier sub-agent: `model="sonnet"` 명시
- [ ] fact-checker sub-agent: `model="sonnet"` 명시
- [ ] image-curator sub-agent: `model="sonnet"` 명시
- [ ] 단일 book-writer 세션에 여러 챕터 넣지 않음 (fresh per-chapter 원칙)
- [ ] 결과물: book/{ko,en}/ch*.md × N, _refs_extracted.json, _factcheck_report.md
- [ ] `python3 build.py --validate <slug>` 통과

## 다음 단계 (집필 완료 후)

`/survey-lite`은 집필까지만 책임진다. **배포·갤러리 등록은 `/survey`로 이어가야 사용자 task가 완결**된다:

```bash
# 1) 책 사이트 배포 + 갤러리 등록까지 한번에
/survey --deploy <slug>

# 또는 수동으로
python3 build.py <slug>
bash surveys/<slug>/scripts/push.sh "release: <slug>"
/survey https://survey-<slug>.pages.dev    # MODE B (홈페이지 갤러리 등록)
```

**중요**: MODE B는 surveys.json 푸시 후 GHA `Deploy to Cloudflare Workers` success 검증 + 라이브 노출 확인까지 마쳐야 "완료". push 자체가 deploy 성공을 의미하지 않는다 (2026-04-28 사고 — `references/registration-playbook.md` Step 7+8 참조).
