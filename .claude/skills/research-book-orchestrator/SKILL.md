---
name: research-book-orchestrator
description: "LLM Planner → VLA → Agentic Robotics 서베이 책의 전체 제작 파이프라인을 조율하는 오케스트레이터. '책 만들어줘', '전체 빌드', '오케스트레이터 실행', '서베이 책 작성', 'build book' 요청 시 반드시 이 스킬을 사용할 것."
---

# Research Book Orchestrator

Agentic Robotics 서베이 책의 전체 제작을 조율한다. 4명의 에이전트를 Phase별로 팀 구성하여 서베이→분석→집필→팩트체크→통합 파이프라인을 실행한다.

## 실행 모드: 에이전트 팀

## 에이전트 구성

| 팀원 | 에이전트 파일 | 역할 | 스킬 | 주요 출력 |
|------|-------------|------|------|----------|
| researcher | deep-researcher | 논문 심층 서베이 | deep-literature-research | `_workspace/01_researcher_*.md` |
| analyst | critical-analyst | 간극 분석, 패러다임 전환 | critical-analysis | `_workspace/02_analyst_*.md` |
| writer | book-writer | 양국어 챕터 집필 | expert-book-write | `book/ko/`, `book/en/` |
| checker | fact-checker | 수치/인용 검증 | fact-check | `_workspace/03_factcheck_*.md` |

## 워크플로우

### Phase 0: 준비

1. 디렉토리 확인: `book/ko/`, `book/en/`, `_workspace/`, `assets/figures/` 존재 확인
2. 컨텍스트 로드:
   - `docs/robotics_vla_agentic_llm_papers.md` — 핵심 10개 논문
   - `docs/agentic_robotics_llm_vla_curated_papers_2023_2025.md` — 확장 큐레이션
   - `CLAUDE.md` — 프로젝트 설정, 챕터 구조, 작업 원칙

### Phase 1: 서베이 + 분석 (researcher + analyst 팀)

**팀 구성:**
```
TeamCreate(
  team_name: "research-team",
  members: [
    {
      name: "researcher",
      agent_type: "deep-researcher",
      model: "opus",
      prompt: "당신은 deep-researcher입니다. docs/ 폴더의 논문 목록을 읽고, deep-literature-research 스킬에 따라 7개 카테고리별 심층 서베이를 수행하세요. _workspace/01_researcher_*.md에 결과를 저장하세요. 서베이 중 흥미로운 발견이나 패러다임 전환을 발견하면 analyst에게 SendMessage로 공유하세요."
    },
    {
      name: "analyst",
      agent_type: "critical-analyst",
      model: "opus",
      prompt: "당신은 critical-analyst입니다. researcher의 서베이를 기다리는 동안, 프로젝트 docs/의 논문 목록과 CLAUDE.md를 읽고 Agentic Coding vs Robotics의 7대 차원 초기 분석을 시작하세요. researcher의 서베이 결과가 나오면 이를 반영하여 4개 분석 파일을 _workspace/02_analyst_*.md에 저장하세요."
    }
  ]
)
```

**작업 등록:**
```
TaskCreate(tasks: [
  { title: "LLM Planner 카테고리 서베이", assignee: "researcher" },
  { title: "Code as Policy 카테고리 서베이", assignee: "researcher" },
  { title: "VLA Models 카테고리 서베이", assignee: "researcher" },
  { title: "Hierarchical Planning 카테고리 서베이", assignee: "researcher" },
  { title: "Memory & Scene Graph 카테고리 서베이", assignee: "researcher" },
  { title: "Agentic Systems & Sim2Real 카테고리 서베이", assignee: "researcher" },
  { title: "연구 그룹 매핑 + 시간축 흐름", assignee: "researcher" },
  { title: "7대 차원 간극 분석 (초기)", assignee: "analyst" },
  { title: "패러다임 전환 타임라인", assignee: "analyst", depends_on: ["LLM Planner 카테고리 서베이"] },
  { title: "미해결 문제 식별", assignee: "analyst", depends_on: ["VLA Models 카테고리 서베이"] },
  { title: "논문 간 영향 관계 맵", assignee: "analyst", depends_on: ["연구 그룹 매핑 + 시간축 흐름"] }
])
```

**팀원 간 통신:**
- researcher → analyst: 서베이 중 발견한 패러다임 전환점이나 예상치 못한 gap
- analyst → researcher: 추가 조사가 필요한 영역 (예: "tactile feedback 관련 논문 더 필요")

**산출물:**
- `_workspace/01_researcher_llm_planner.md`
- `_workspace/01_researcher_code_policy.md`
- `_workspace/01_researcher_vla.md`
- `_workspace/01_researcher_hierarchy.md`
- `_workspace/01_researcher_memory.md`
- `_workspace/01_researcher_agentic.md`
- `_workspace/01_researcher_groups.md`
- `_workspace/02_analyst_gap_analysis.md`
- `_workspace/02_analyst_paradigm_shifts.md`
- `_workspace/02_analyst_open_problems.md`
- `_workspace/02_analyst_paper_connections.md`

**Phase 1 완료 조건:** 모든 7+4개 파일이 생성됨.

**Phase 1 → Phase 2 전환:**
1. 모든 팀원에게 종료 요청 SendMessage
2. TeamDelete로 research-team 정리
3. `_workspace/` 산출물 보존

### Phase 2: 집필 + 팩트체크 (writer + checker 팀)

**팀 구성:**
```
TeamCreate(
  team_name: "writing-team",
  members: [
    {
      name: "writer",
      agent_type: "book-writer",
      model: "opus",
      prompt: "당신은 book-writer입니다. _workspace/01_researcher_*.md와 _workspace/02_analyst_*.md를 읽고, expert-book-write 스킬에 따라 10개 챕터를 Part 단위로 집필하세요. Part 완료 시 checker에게 SendMessage로 검증 요청하세요. book/ko/와 book/en/에 동시 저장하세요."
    },
    {
      name: "checker",
      agent_type: "fact-checker",
      model: "opus",
      prompt: "당신은 fact-checker입니다. writer가 집필하는 동안 핵심 논문의 주요 수치를 사전 검증하세요(_workspace/03_factcheck_pre_verification.md). writer가 Part를 완료하면 fact-check 스킬에 따라 해당 챕터들을 검증하고 결과를 SendMessage로 writer에게 전달하세요."
    }
  ]
)
```

**작업 등록:**
```
TaskCreate(tasks: [
  { title: "핵심 수치 사전 검증", assignee: "checker" },
  { title: "Part I 집필 (Ch 1-3)", assignee: "writer" },
  { title: "Part I 팩트체크", assignee: "checker", depends_on: ["Part I 집필 (Ch 1-3)"] },
  { title: "Part I 수정 반영", assignee: "writer", depends_on: ["Part I 팩트체크"] },
  { title: "Part II 집필 (Ch 4-6)", assignee: "writer", depends_on: ["Part I 수정 반영"] },
  { title: "Part II 팩트체크", assignee: "checker", depends_on: ["Part II 집필 (Ch 4-6)"] },
  { title: "Part II 수정 반영", assignee: "writer", depends_on: ["Part II 팩트체크"] },
  { title: "Part III 집필 (Ch 7-9)", assignee: "writer", depends_on: ["Part II 수정 반영"] },
  { title: "Part III 팩트체크", assignee: "checker", depends_on: ["Part III 집필 (Ch 7-9)"] },
  { title: "Part III 수정 반영", assignee: "writer", depends_on: ["Part III 팩트체크"] },
  { title: "Part IV 집필 (Ch 10)", assignee: "writer", depends_on: ["Part III 수정 반영"] },
  { title: "Part IV 팩트체크", assignee: "checker", depends_on: ["Part IV 집필 (Ch 10)"] },
  { title: "Part IV 수정 반영", assignee: "writer", depends_on: ["Part IV 팩트체크"] }
])
```

**집필-검증 루프:**
1. writer가 Part N 집필 → `book/ko/chXX.md`, `book/en/chXX.md` 저장
2. writer → checker SendMessage: "Part N 집필 완료, 검증 요청"
3. checker가 해당 챕터 검증 → `_workspace/03_factcheck_partN_chXX_YY.md` 저장
4. checker → writer SendMessage: 검증 결과 (critical issues, warnings)
5. writer가 수정 반영 → "수정 완료, 재검증 요청"
6. 재검증 → OK면 다음 Part로 진행

**산출물:**
- `book/ko/ch01.md` ~ `ch10.md`
- `book/en/ch01.md` ~ `ch10.md`
- `_workspace/03_factcheck_*.md` (6개 검증 보고서)

**Phase 2 완료 조건:** 20개 챕터 파일 + 검증 보고서 완료.

### Phase 2.5: 이미지 큐레이션 (단독 또는 리더 직접)

Phase 2 완료 후, image-curator 에이전트 또는 리더가 직접 수행:

1. **논문 figure 크롭**: 세미나 PDF + 블로그 포스트 + arXiv 논문에서 figure 선별·크롭
2. **이미지 배치**: `assets/figures/` 에 저장, KO/EN 챕터에 마크다운 삽입
3. **내용 보강**: 논문 원문과 챕터 내용을 대조하여 누락/부족한 부분 보강
4. **보조 일러스트**: 논문 figure로 커버되지 않는 개념 설명 → `/image-gen` (챕터당 0-2개)

**산출물:**
- `assets/figures/ch{NN}_*.{ext}` — 논문 figure + Gemini 일러스트
- `_workspace/04_image_manifest.json` — 이미지 매니페스트

**Phase 2.5 완료 조건:** 이미지 매니페스트 생성 + 각 챕터에 2-4개 figure 삽입.

### Phase 3: 통합 (리더 직접)

Phase 2 팀 정리 후, 리더가 직접 수행:

1. **toc.md 생성**: `book/ko/toc.md`, `book/en/toc.md`
   ```markdown
   ---
   title: "목차"
   ---
   ## Part I: 기초 — LLM이 로봇을 만나다
   1. [서론 — Agentic Coding에서 Agentic Robotics로](ch01.html)
   ...
   ```

2. **references.bib 생성**: 전체 챕터에서 인용된 논문을 통합 BibTeX로 정리

3. **일관성 최종 확인**:
   - 교차참조(→ Chapter N) 번호 정합성
   - 인용 형식 통일
   - KO/EN 간 챕터 구조 일치
   - Part/챕터 번호 연속성

4. **결과 요약 보고서**: `_workspace/04_integration_report.md`

### Phase 4: 정리

1. 팀원들에게 종료 요청 SendMessage
2. TeamDelete로 writing-team 정리
3. `_workspace/` 보존 (사후 검증·감사 추적용)
4. 사용자에게 결과 보고:
   - 생성된 파일 목록
   - 팩트체크 요약 (critical issues 해결 여부)
   - 다음 단계: `python build_site.py` → `docs/` 생성 → 배포

## 데이터 흐름

```
[논문 목록 docs/]
       ↓
Phase 1: [researcher] ←→ [analyst]
       ↓                    ↓
  01_researcher_*.md   02_analyst_*.md
       ↓                    ↓
       └─────── Read ───────┘
                 ↓
Phase 2: [writer] ←→ [checker]
       ↓                    ↓
  book/ko/, book/en/   03_factcheck_*.md
       ↓
Phase 2.5: [image-curator] (단독)
       ↓
  assets/figures/*.{ext}  ← 논문 figure 크롭 + Gemini 일러스트
  book/ko/, book/en/      ← 이미지 삽입 + 내용 보강
  04_image_manifest.json
       ↓
Phase 3: [리더: 통합]
       ↓
  toc.md, references.bib
       ↓
  build_site.py → docs/
```

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| researcher 서베이 일부 실패 | 완료된 카테고리로 진행, 누락 카테고리 보고서에 명시 |
| analyst가 researcher 대기 중 막힘 | docs/ 기반 초기 분석 선행 |
| writer 품질 부족 | checker의 피드백 반영 후 재집필 (최대 2회) |
| checker 원문 접근 불가 | 해당 수치 "미확인" 표기 |
| 팀원 1명 중단 | 리더가 해당 역할 직접 수행 |
| Phase 간 팀 재구성 실패 | 이전 팀 종료 재시도 후 새 팀 생성 |

## 테스트 시나리오

### 정상 흐름
1. Phase 0: 디렉토리 확인, 논문 목록 로드
2. Phase 1: researcher 7개 + analyst 4개 = 11개 파일 생성
3. Phase 2: 4 Parts × (집필→검증→수정) = 20 챕터 + 6 검증 보고서
4. Phase 2.5: image-curator가 9개 챕터에 20-30개 figure 삽입 + 내용 보강 + 매니페스트 생성
5. Phase 3: toc.md × 2, references.bib, 통합 보고서
6. Phase 4: 팀 정리, 결과 보고
7. 예상: `book/ko/ch01-10.md`, `book/en/ch01-10.md`, `assets/figures/`, `_workspace/` 전체

### 에러 흐름
1. Phase 1에서 researcher의 "Agentic Systems" 카테고리 서베이 실패
2. analyst가 해당 영역을 docs/ 기반으로 보완 분석
3. Phase 2에서 writer가 Ch 8 (Agentic Systems) 집필 시 데이터 부족 표시
4. checker가 해당 챕터를 "제한적 검증"으로 처리
5. 최종 보고서에 "Ch 8: Agentic Systems 서베이 데이터 일부 미수집" 명시
