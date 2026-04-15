---
name: book-write
description: "Tactile Sensing for Robot Hands 책의 챕터를 집필하는 스킬. 문헌 조사와 기존 자료 분석 결과를 바탕으로 12개 챕터의 마크다운 원고를 생성한다. 책 목차 설계, 챕터 집필, 참고문헌 통합, 교차 참조 생성 등 책 콘텐츠 작성의 모든 단계를 수행한다. 책을 쓰거나, 챕터를 작성하거나, 목차를 설계할 때 이 스킬을 사용할 것."
---

# Book Write Skill

문헌 조사 결과와 기존 자료를 바탕으로 "Tactile Sensing for Robot Hands" 책 원고를 집필한다.

## 워크플로우

### Step 1: 목차 확정

입력 자료(`literature_map.json`, `content_extraction.md`, `gap_analysis.md`)를 종합하여 최종 목차를 확정한다.

**목차 설계 원칙:**
- Part 구분은 독자의 학습 흐름 기준 (기초 → 데이터 → 학습 → 응용)
- 각 챕터는 독립적으로도 읽을 수 있되, 순차 독서 시 자연스러운 흐름
- 챕터당 15~25페이지 분량 (마크다운 기준 약 800~1500줄)

**목차 파일**: `_workspace/02_writer_toc.md`

```markdown
# Tactile Sensing for Robot Hands — 목차

## Part I: Foundations
### Chapter 1: 왜 촉각인가
- 1.1 로봇 조작의 현재와 한계
- 1.2 촉각의 역할: 사람 vs 로봇
- 1.3 이 책의 구성과 로드맵
...
```

### Step 2: 챕터별 집필

각 챕터를 아래 구조로 집필:

#### 챕터 구조 템플릿

```markdown
---
chapter: N
title: "[한국어 제목]"
subtitle: "[영어 부제]"
part: "Part X: [파트명]"
---

# Chapter N: [제목]

> **요약**: [2-3문장으로 이 챕터에서 다루는 내용]

## N.1 [첫 번째 섹션]

[본문 — 개념 소개부터 시작]

> **핵심 연구**: Author et al. (Year). "[논문 제목]". *venue*.
> [1-2문장 핵심 기여 설명]

[본문 계속]

[📊 Figure N.1: {그림 설명} — Source: {출처}]

### N.1.1 [하위 섹션]

[기술적 상세]

$$수식이 필요한 경우 LaTeX$$

## N.2 [두 번째 섹션]
...

## N.X 최신 동향 (Recent Advances)

[2024~2026년 최신 연구 동향]

## N.Y 요약 및 전망

[챕터 핵심 정리 + 다음 챕터와의 연결]

## 참고문헌

[이 챕터에서 인용한 논문 목록 — APA 형식]
```

#### 집필 원칙

1. **이중 언어 집필**: 한국어 버전(`ch{NN}_ko.md`)과 영어 버전(`ch{NN}_en.md`)을 각각 작성. 단순 번역이 아닌 각 언어에 자연스러운 서술. 한국어 버전에서는 기술 용어 영어 병기: "촉각 센서(tactile sensor)"
2. **집필 메타데이터**: 각 챕터 frontmatter에 `date`, `last_updated`, `sources` 필드 필수 포함
3. **인용 밀도**: 섹션당 최소 3개 이상의 논문 인용
4. **그림 밀도**: 섹션당 최소 1개 이상의 Figure 위치 표시
5. **비교표 활용**: 기술/방법론 비교 시 테이블 사용
6. **코드 예시**: 필요한 경우 Python 의사코드 포함 (실행 가능할 필요 없음)
7. **학습 목표**: 각 챕터 시작에 "이 챕터를 읽고 나면..." 포함
8. **Reference List 필수**: 각 챕터 말미에 APA 형식의 전체 참고문헌 목록. 인용 키(`[Author et al., Year]`)와 참고문헌 항목이 1:1 ��칭

### Step 3: 참고문헌 통합

모든 챕터의 인용을 수집하여 통합 BibTeX 파일 생성:

**파일**: `_workspace/02_writer_references.bib`

```bibtex
@article{author2024title,
  title={Paper Title},
  author={Last, First and Last2, First2},
  journal={Journal Name},
  year={2024},
  doi={10.xxxx/xxxxx}
}
```

### Step 4: 교차 참조 및 용어집

- 챕터 간 교차 참조: `(→ Chapter N.M 참조)` 형태
- 용어집: `_workspace/02_writer_glossary.md` — 첫 등장 챕터 표시

### Step 5: 최종 정리

`book/` 디렉토리에 정리된 최종본 저장:
- `book/ko/toc.md`, `book/ko/ch01.md` ~ `book/ko/ch12.md`, `book/ko/glossary.md`
- `book/en/toc.md`, `book/en/ch01.md` ~ `book/en/ch12.md`, `book/en/glossary.md`
- `book/references.bib` (통합, 언어 무관)

## 품질 기준

- 챕터당 인용 논문 최소 15편
- literature_map.json의 논문 중 80% 이상이 본문에 인용
- 모든 Figure에 출처 표시
- 챕터 간 교차 참조 최소 2개/챕터
- 한국어/영어 버전의 챕터 구조(섹션 수, Figure 번호)가 동일
- 모든 챕터에 date, last_updated, sources frontmatter 존재
- 각 챕터 말미 참고문헌과 본문 인용이 1:1 매칭
