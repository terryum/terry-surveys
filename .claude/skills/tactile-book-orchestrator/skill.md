---
name: tactile-book-orchestrator
description: "Tactile Sensing for Robot Hands 책 프로젝트의 전체 워크플로우를 조율하는 오케스트레이터. 문헌 조사 → 기존 자료 분석 → 책 집필 → 웹사이트 구축의 4단계 파이프라인을 에이전트 팀으로 실행한다. '책 만들어줘', '프로젝트 시작', '전체 실행', 'tactile book' 등의 요청이 있을 때 이 스킬을 사용할 것. 개별 Phase만 실행하는 것도 가능하다."
---

# Tactile Book Orchestrator

Tactile Sensing for Robot Hands 책 집필 + 웹사이트 구축 프로젝트를 조율한다.

## 실행 모드: 에이전트 팀 (Phase별 팀 재구성)

전체 프로젝트는 3개 Phase로 나뉘며, Phase별로 팀을 구성·해체한다. 이전 팀의 산출물은 `_workspace/`에 보존되어 다음 팀이 접근 가능하다.

## 에이전트 구성

| 에이전트 | 타입 | Phase | 스킬 | 출력 |
|---------|------|-------|------|------|
| researcher | general-purpose | A | literature-research | literature_map.json, literature_summary.md, industry_trends.md |
| content-analyst | general-purpose | A | content-extract | content_extraction.md, reference_papers.json, gap_analysis.md, toc_proposal.md |
| book-writer | general-purpose | B | book-write, ieee-paper-write | book/ko/, book/en/, paper/ (IEEE LaTeX) |
| illustrator | general-purpose | B | — | assets/figures/, figure_manifest.json |
| reference-checker | general-purpose | B | — | refcheck reports, journal_comparison.md |
| web-builder | general-purpose | C | web-build | docs/ (KO/EN 이중 언어 정적 사이트) |
| qa-reviewer | general-purpose | A,C | — | qa_report.md (Phase A, C) |

## 워크플로우

### Phase 0: 준비

1. 프로젝트 디렉토리에 `_workspace/` 및 `_workspace/00_input/` 생성
2. 사용자 입력 자료 경로를 `_workspace/00_input/sources.md`에 기록:

```markdown
# 입력 자료 목록

## 세미나 PDF
- /Users/terrytaewoongum/Downloads/260319_Seminar_SNU_Junsoo_Jihwan_TactileHand_Maipulation.pdf
- /Users/terrytaewoongum/Downloads/260323_Seminar_SNU_Taejoon_DataGlove_Sensors.pdf
- /Users/terrytaewoongum/Downloads/260323_Seminar_SNU_Inchul_Hand_Gripper_Machanism.pdf

## 홈페이지 포스트
- https://terry.artlab.ai/en/posts?tab=papers
- https://github.com/terryum/terry-artlab-homepage/tree/main/posts/papers
```

3. `book/` 및 `docs/` 디렉토리 생성

### Phase A: 연구 (Research)

**팀 구성:**

```
TeamCreate(
  team_name: "research-team",
  members: [
    {
      name: "researcher",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 researcher 에이전트입니다. .claude/agents/researcher.md를 읽고 역할과 원칙을 따르세요. .claude/skills/literature-research/skill.md의 워크플로우에 따라 문헌 조사를 수행하세요. 산출물은 _workspace/에 저장하세요."
    },
    {
      name: "content-analyst",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 content-analyst 에이전트입니다. .claude/agents/content-analyst.md를 읽고 역할과 원칙을 따르세요. .claude/skills/content-extract/skill.md의 워크플로우에 따라 기존 자료를 분석하세요. 산출물은 _workspace/에 저장하세요."
    },
    {
      name: "qa-a",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 qa-reviewer 에이전트입니다. .claude/agents/qa-reviewer.md를 읽고 역할과 원칙을 따르세요. Phase A(연구) 산출물의 품질을 검증하세요. researcher와 content-analyst의 작업이 완료되면 검증을 시작하세요."
    }
  ]
)
```

**작업 등록:**

```
TaskCreate(tasks: [
  { title: "문헌 조사 실행", description: "7개 카테고리 논문 검색 및 구조화", assignee: "researcher" },
  { title: "세미나 PDF 분석", description: "3개 PDF에서 콘텐츠 추출", assignee: "content-analyst" },
  { title: "홈페이지 포스트 분석", description: "논문 요약 포스트에서 콘텐츠 추출", assignee: "content-analyst" },
  { title: "참조 논문 교차 전달", description: "content-analyst가 추출한 참조 논문을 researcher에게 전달", assignee: "content-analyst", depends_on: ["세미나 PDF 분석"] },
  { title: "갭 분석", description: "기존 자료 커버리지 분석", assignee: "content-analyst", depends_on: ["홈페이지 포스트 분석"] },
  { title: "Phase A QA", description: "연구 산출물 품질 검증", assignee: "qa-a", depends_on: ["문헌 조사 실행", "갭 분석"] }
])
```

**팀원 간 통신:**
- content-analyst → researcher: 기존 자료에서 발견한 참조 논문 목록 전달 (SendMessage)
- researcher → content-analyst: 조사 중 사용자 기존 자료와 관련된 최신 논문 정보 공유
- qa-a: 양쪽 모두 완료 후 검증, FAIL 발견 시 리더에게 즉시 알림

**산출물:**

| 파일 | 생산자 |
|------|--------|
| `_workspace/01_researcher_literature_map.json` | researcher |
| `_workspace/01_researcher_literature_summary.md` | researcher |
| `_workspace/01_analyst_content_extraction.md` | content-analyst |
| `_workspace/01_analyst_reference_papers.json` | content-analyst |
| `_workspace/01_analyst_gap_analysis.md` | content-analyst |
| `_workspace/01_qa_report.md` | qa-a |

**Phase A 완료 기준:** qa-a 리포트에 FAIL이 0개이거나, 리더가 수정 지시 후 재검증 통과

**Phase A 종료:** TeamDelete → 다음 Phase 준비

---

### Phase B: 집필 (Writing)

**팀 구성: 4명** (writer + illustrator + reference-checker + ieee-validator 겸임)

```
TeamCreate(
  team_name: "writing-team",
  members: [
    {
      name: "book-writer",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 book-writer 에이전트입니다. .claude/agents/book-writer.md를 읽고 역할을 따르세요. .claude/skills/book-write/skill.md의 워크플로우에 따라 챕터별로 집필하세요. 각 챕터 완성 시 reference-checker에게 검증 요청하고, illustrator에게 Figure placeholder 목록을 전달하세요."
    },
    {
      name: "illustrator",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 book-illustrator 에이전트입니다. .claude/agents/book-illustrator.md를 읽고 역할을 따르세요. book-writer가 챕터를 완성할 때마다 Figure placeholder를 실제 시각 자료로 채우세요. 논문 인용 이미지는 반드시 캡션에 Source를 표시하세요."
    },
    {
      name: "reference-checker",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 reference-checker 에이전트입니다. .claude/agents/reference-checker.md를 읽고 역할을 따르세요. book-writer가 챕터를 완성할 때마다 Level 1(citation 정합성) + Level 2(사실 정확성) 검증을 수행하세요. IEEE paper 완성 시에는 Level 3(IEEE 형식) + Level 4(타겟 저널 비교)도 수행하세요."
    }
  ]
)
```

**작업 등록 — 챕터별 집필+검증+일러스트 사이클:**

```
TaskCreate(tasks: [
  { title: "목차 확정 (13챕터)", description: "01_analyst_toc_proposal.md 기반 최종 목차 KO/EN 작성", assignee: "book-writer" },

  // Part I: Foundations (Ch 1-3)
  { title: "Ch01 집필 (KO+EN)", description: "왜 촉각인가", assignee: "book-writer", depends_on: ["목차 확정"] },
  { title: "Ch01 검증", description: "citation 정합성 + 사실 정확성", assignee: "reference-checker", depends_on: ["Ch01 집필"] },
  { title: "Ch01 일러스트", description: "역사 타임라인 + 개념도", assignee: "illustrator", depends_on: ["Ch01 집필"] },
  { title: "Ch02 집필 (KO+EN)", description: "촉각 센서 기술", assignee: "book-writer", depends_on: ["Ch01 검증"] },
  { title: "Ch02 검증", assignee: "reference-checker", depends_on: ["Ch02 집필"] },
  { title: "Ch02 일러스트", assignee: "illustrator", depends_on: ["Ch02 집필"] },
  { title: "Ch03 집필 (KO+EN)", description: "촉각 데이터", assignee: "book-writer", depends_on: ["Ch02 검증"] },
  { title: "Ch03 검증", assignee: "reference-checker", depends_on: ["Ch03 집필"] },
  { title: "Ch03 일러스트", description: "Albini taxonomy 시각화", assignee: "illustrator", depends_on: ["Ch03 집필"] },

  // Part II: Hands (Ch 4-6) — Ch01 검증 통과 후 병렬 가능
  { title: "Ch04 집필 (KO+EN)", description: "로봇 핸드 설계", assignee: "book-writer", depends_on: ["Ch03 검증"] },
  { title: "Ch04 검증", assignee: "reference-checker", depends_on: ["Ch04 집필"] },
  { title: "Ch04 일러스트", assignee: "illustrator", depends_on: ["Ch04 집필"] },
  // ... Ch05~Ch13 동일 패턴 (챕터 순차, 검증+일러스트 병렬)

  // 통합 작업
  { title: "참고문헌 통합", description: "BibTeX + 용어집 KO/EN", assignee: "book-writer", depends_on: ["Ch13 검증"] },
  { title: "최종 정리", description: "book/ko/, book/en/ 저장", assignee: "book-writer", depends_on: ["참고문헌 통합"] },
  { title: "Figure manifest 확정", description: "전체 Figure 목록 최종 확인", assignee: "illustrator", depends_on: ["Ch13 일러스트"] },

  // IEEE Paper
  { title: "IEEE Survey Paper 집필", description: "IEEEtran.cls LaTeX. ieee-paper-write 스킬 따를 것", assignee: "book-writer", depends_on: ["최종 정리"] },
  { title: "IEEE Paper 검증 (Level 3+4)", description: "IEEE 형식 + 타겟 저널 비교", assignee: "reference-checker", depends_on: ["IEEE Survey Paper 집필"] },
  { title: "IEEE Paper 수정", description: "검증 FAIL 항목 수정", assignee: "book-writer", depends_on: ["IEEE Paper 검증"] }
])
```

**챕터별 사이클:**
```
book-writer: Ch N 집필 (KO+EN)
    ├── → reference-checker: citation + 사실 검증
    │       └── FAIL → book-writer 수정 → 재검증
    ├── → illustrator: Figure 생성 (논문 인용 + 원본 다이어그램)
    │       └── → reference-checker: Figure 인용 출처 확인
    └── PASS → 다음 챕터
```

**IEEE Paper 검증 특별 절차:**
1. reference-checker가 Level 3 (IEEE 형식) 검증
2. reference-checker가 Level 4 수행: **타겟 저널(T-RO, RA-L 등)의 최근 survey 2-3편을 WebFetch로 가져와** 섹션 구조, 참고문헌 수, 비교표, Figure 밀도, 페이지 수를 비교
3. 비교 결과를 리더에게 보고 → 사용자 확인

**산출물:**

| 파일 | 생산자 |
|------|--------|
| `_workspace/02_writer_toc_ko.md` / `_workspace/02_writer_toc_en.md` | book-writer |
| `_workspace/02_writer_ch{01-13}_ko.md` / `_workspace/02_writer_ch{01-13}_en.md` | book-writer |
| `_workspace/02_writer_references.bib` | book-writer |
| `_workspace/02_writer_glossary_ko.md` / `_workspace/02_writer_glossary_en.md` | book-writer |
| `_workspace/02_refcheck_ch{01-13}_report.md` | reference-checker |
| `_workspace/02_illustrator_figure_manifest.json` | illustrator |
| `assets/figures/ch{01-13}/` | illustrator |
| `book/ko/` (한국어 최종본) | book-writer |
| `book/en/` (영어 최종본) | book-writer |
| `book/references.bib` (통합 참고문헌) | book-writer |
| `paper/` (IEEE LaTeX survey paper) | book-writer |
| `_workspace/02_refcheck_ieee_report.md` | reference-checker |
| `_workspace/02_refcheck_journal_comparison.md` | reference-checker |

**Phase B 종료:** TeamDelete → 다음 Phase 준비

---

### Phase C: 웹 구축 (Web Build)

**팀 구성:**

```
TeamCreate(
  team_name: "web-team",
  members: [
    {
      name: "web-builder",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 web-builder 에이전트입니다. .claude/agents/web-builder.md를 읽고 역할을 따르세요. .claude/skills/web-build/skill.md의 워크플로우에 따라 정적 사이트를 구축하세요. book/ 디렉토리의 마크다운을 입력으로 사용하세요."
    },
    {
      name: "qa-c",
      agent_type: "general-purpose",
      model: "opus",
      prompt: "당신은 qa-reviewer 에이전트입니다. .claude/agents/qa-reviewer.md를 읽고 Phase C(웹) 검증을 수행하세요. 링크 유효성, 콘텐츠 누락, 반응형 CSS를 중점 검증하세요."
    }
  ]
)
```

**작업 등록:**

```
TaskCreate(tasks: [
  { title: "사이트 구조 생성", description: "docs/ 디렉토리 + CSS/JS 기본 파일", assignee: "web-builder" },
  { title: "랜딩 페이지 구현", description: "index.html(언어 선택) + ko/index.html + en/index.html", assignee: "web-builder", depends_on: ["사이트 구조 생성"] },
  { title: "챕터 페이지 생성 (KO/EN)", description: "ko/ch01~12.html + en/ch01~12.html, 언어 전환 토글 포함", assignee: "web-builder", depends_on: ["사이트 구조 생성"] },
  { title: "참고문헌/용어집 페이지 (KO/EN)", description: "ko/en 각각 references.html, glossary.html. 챕터별 필터, 메타데이터 표시", assignee: "web-builder", depends_on: ["사이트 구조 생성"] },
  { title: "스타일링 완성", description: "다크 모드, glassmorphism, 반응형", assignee: "web-builder", depends_on: ["랜딩 페이지 구현"] },
  { title: "애니메이션 적용", description: "파티클 배경, GSAP 스크롤 애니메이션", assignee: "web-builder", depends_on: ["스타일링 완성"] },
  { title: "Phase C QA", description: "전체 사이트 검증", assignee: "qa-c", depends_on: ["애니메이션 적용", "챕터 페이지 생성", "참고문헌/용어집 페이지"] }
])
```

**산출물:**

| 파일 | 생산자 |
|------|--------|
| `docs/` (KO/EN 이중 언어 정적 사이트) | web-builder |
| `_workspace/03_qa_report.md` | qa-c |

**Phase C 종료:** TeamDelete → 사용자에게 최종 결과 보고

---

### Phase D: 최종 보고

1. 모든 `_workspace/` 보존 (감사 추적용)
2. 사용자에게 결과 요약:
   - 총 수집 논문 수, 카테고리별 분포
   - 책 총 분량 (챕터 수, 대략적 페이지 수)
   - 웹사이트 로컬 확인 방법: `cd docs && python3 -m http.server 8000`
   - GitHub Pages 배포 방법 안내
3. 보충/수정이 필요한 영역 목록 (QA 리포트 기반)

## 데이터 흐름 요약

```
Phase 0          Phase A              Phase B             Phase C
─────────        ─────────            ─────────           ─────────
sources.md  →  literature_map.json  → toc.md          → docs/index.html
               literature_summary.md  ch01~12.md        docs/ch01~12.html
               content_extraction.md  references.bib    docs/references.html
               reference_papers.json  glossary.md       docs/glossary.html
               gap_analysis.md                          docs/css/
                                                        docs/js/
                       ↕                    ↕                   ↕
                  01_qa_report          02_qa_report       03_qa_report
```

## 에러 핸들링

| 에러 유형 | 전략 |
|----------|------|
| PDF 읽기 실패 | poppler 설치 확인, 실패 시 파일명만 기록하고 진행 |
| 웹 검색 결과 부족 | 키워드 변형 3회 재시도, 그래도 부족하면 해당 카테고리 부족 보고 |
| 챕터 집필 중 논문 데이터 부족 | "[보충 필요]" 태그 삽입, QA에서 감지 |
| HTML 변환 오류 | 해당 섹션 원본 텍스트 삽입 + 경고 |
| 팀원 무응답/장시간 지연 | 리더가 SendMessage로 상태 확인, 필요시 작업 재할당 |
| 상충 데이터 | 삭제하지 않고 출처 병기 |

## 개별 Phase 실행

전체가 아닌 특정 Phase만 실행할 수도 있다:
- "Phase A만 실행" → 연구 팀만 구성·실행
- "Phase B만 실행" → `_workspace/01_*` 파일이 있는지 확인 후 집필 팀 구성
- "Phase C만 실행" → `book/` 디렉토리가 있는지 확인 후 웹 팀 구성

## 테스트 시나리오

### 정상 흐름
1. Phase 0: `_workspace/` 생성, sources.md 작성
2. Phase A: research-team 구성, 4명 병렬 작업, QA 통과
3. Phase B: writing-team 구성, 12챕터 순차 집필, Part별 QA 통과
4. Phase C: web-team 구성, 14개 HTML 생성, QA 통과
5. Phase D: 결과 요약 + 배포 안내

### 에러 흐름 — PDF 읽기 실패
1. Phase A에서 content-analyst가 PDF 읽기 실패
2. content-analyst가 리더에게 알림
3. 리더가 사용자에게 poppler 설치 요청 또는 PDF 내용 수동 입력 안내
4. 설치 후 재시도 또는 PDF 없이 진행 (문헌 조사만으로 book 구성)

### 에러 흐름 — QA FAIL
1. Phase B에서 qa-b가 Ch 3의 인용 불일치 발견
2. qa-b → book-writer: 구체적 수정 지시 (파일:라인, 누락 인용 목록)
3. book-writer 수정 후 qa-b 재검증
4. PASS 후 다음 Part 진행
