---
name: curate-paper-images
description: "논문 figure를 선별하여 책 챕터에 삽입하고, 논문 원문과 대조하여 내용을 보강하며, 필요시 Gemini로 보조 일러스트를 생성하는 스킬. '이미지 추가', '논문 사진', 'figure 삽입', '이미지 큐레이션', '논문 그림', '챕터에 그림 넣어줘', '이미지 보강', '시각 자료 추가' 요청 시 반드시 이 스킬을 사용할 것. 챕터가 텍스트만으로 구성되어 있고 시각적 보강이 필요할 때도 자동 트리거."
---

# Curate Paper Images — 논문 Figure 큐레이션 + 내용 보강 스킬

논문 figure를 선별하여 책 챕터에 배치하고, 논문 원문과 대조하여 내용을 보강하며, 필요시 Gemini로 보조 일러스트를 생성한다.

## 전제 조건

- 책 챕터(`book/ko/`, `book/en/`)가 이미 완성되어 있어야 한다
- 세미나 PDF가 `docs/revise-source/`에 존재해야 한다

## 이미지 소스 (우선순위 순)

1. **세미나 PDF**: `docs/revise-source/(Modular Approach) Literature Review.pdf` — 크롭
2. **블로그 포스트**: `terryum-ai/posts/papers/{slug}/` — fig-{N}.{ext} + meta.json
3. **arXiv 논문 PDF**: 직접 다운로드 → figure 크롭
4. **Gemini 생성**: `/gemini-3-image-generation` 스킬 — 보조 일러스트 (챕터당 최대 2개)

## 7단계 워크플로우

### Step 1: Source 매핑 구축

각 챕터에서 인용된 논문과 이미지 소스를 매핑한다.

```
매핑 항목:
- paper_name: 논문 명칭
- slug_short: 축약명 (예: saycan, rt2, openvla, pi0)
- source_type: seminar_pdf | blog | arxiv | gemini
- source_location: PDF 페이지 | 블로그 슬러그 | arXiv URL
- figures_available: 사용 가능한 figure 번호 목록
```

세미나 PDF를 페이지별로 확인하여 어떤 논문의 어떤 figure가 몇 페이지에 있는지 기록한다. 블로그는 `meta.json`의 `figures[]` 배열을 확인한다.

### Step 2: 챕터 스캔

각 `book/ko/ch{NN}.md`를 읽고:
1. `### Paper Name` 형식의 전용 서브섹션이 있는 논문 식별
2. 해당 논문에 대한 토론 깊이 판단 (3+ 단락 = 주요 논문 → 이미지 대상)
3. 간략 언급(1-2문장)인 논문은 이미지 대상에서 제외
4. 이미 figure가 삽입된 논문은 건너뛴다

### Step 3: Figure 선별

각 주요 논문에 대해:

| Priority | 대상 | 선택 조건 |
|----------|------|----------|
| 1 | Fig 1 (overview/teaser) | 거의 항상 선택 |
| 2 | Architecture/pipeline | 방법론을 상세히 다룰 때 |
| 3 | Results comparison | 정량 결과를 비교할 때 |

- 논문당 최대 2개 (핵심 논문은 예외적으로 3개)
- 챕터당 2-4개 총합 (논문 figure + Gemini)

### Step 4: 이미지 크롭 + 리네이밍

**네이밍 규칙:**
- 논문 figure: `assets/figures/ch{NN}_{slug_short}_fig{N}.{ext}` (예: `ch04_pi0_fig2.jpeg`)
- Gemini 생성: `assets/figures/ch{NN}_illust_{topic}.png` (예: `ch01_illust_agentic_loop.png`)

**소스별 크롭 방법:**
- 세미나 PDF: 해당 페이지에서 figure 영역 크롭, PNG/JPG 저장
- 블로그: `terryum-ai/posts/papers/{slug}/fig-{N}.{ext}` 복사
- arXiv: 논문 PDF 다운로드 → figure 크롭 → 저장

### Step 5: 논문 원문과 내용 대조·보강

논문을 다운로드하거나 열었으면, **이미지만 크롭하고 끝내지 않는다.** 논문 원문의 핵심 내용과 챕터 서술을 비교하여 보강한다.

**대조 항목:**
1. **핵심 수치**: 논문의 주요 실험 결과(성공률, 개선 폭 등)가 챕터에 정확히 반영되었는지
2. **방법론 핵심**: 논문의 핵심 기여(새로운 아키텍처, 학습 방법 등)가 충분히 설명되었는지
3. **한계/미해결 문제**: 논문이 명시한 limitation이 챕터에 언급되었는지
4. **다른 논문과의 비교**: 논문이 직접 비교한 baseline 결과가 챕터에 반영되었는지

**보강 원칙:**
- 소규모 보강 (1-2문장, 수치 추가/수정): 직접 수행
- 대규모 보강 (새 서브섹션, 서술 구조 변경): book-writer에게 요청
- KO/EN 동시 보강 필수
- 기존 문체와 톤을 유지한다

### Step 6: 마크다운 삽입

각 선별된 figure를 KO/EN 챕터에 동시 삽입한다.

**삽입 위치**: 해당 논문 서브섹션(`### Paper Name`)의 첫 단락 직후
- 표(table)가 첫 단락 직후에 있으면 표 뒤에 삽입
- 전후에 빈 줄 필수 (블록 이미지 인식)

**KO 형식:**
```markdown
![Figure {ch}.{seq}: {caption_ko}. 출처: {author} ({year}), Fig. {orig_num}](../../assets/figures/ch{NN}_{slug_short}_fig{N}.{ext})
```

**EN 형식:**
```markdown
![Figure {ch}.{seq}: {caption_en}. Source: {author} ({year}), Fig. {orig_num}](../../assets/figures/ch{NN}_{slug_short}_fig{N}.{ext})
```

Figure 번호는 챕터 내 순차 번호: Figure 2.1, 2.2, 2.3, ...

**Caption 처리:**
- 출처 attribution 필수: `출처: Author (Year), Fig. N`
- 캡션이 길면 1-2문장으로 요약
- Gemini 생성 일러스트는 `출처:` 없이 내용 설명만 기재

### Step 7: Gemini 보조 일러스트 판단 + 생성

Step 6 완료 후, 각 챕터를 재검토하여:

1. 논문 figure로 커버되지 않는 개념적 설명이 필요한 곳 식별
   - 복잡한 비교/대비 다이어그램 (예: Agentic Coding vs Robotics 루프)
   - 시간축 흐름도 (예: LLM Planner → CaP → VLA 진화)
   - 시스템 통합 개념도 (여러 논문을 아우르는)
2. `/gemini-3-image-generation` 스킬로 생성
3. 챕터당 최대 2개
4. 네이밍: `ch{NN}_illust_{topic}.png`

## 산출물

1. `assets/figures/ch{NN}_*.{ext}` — 논문 figure + Gemini 일러스트
2. `book/ko/ch*.md` — 이미지 마크다운 + 내용 보강된 한글 챕터
3. `book/en/ch*.md` — 이미지 마크다운 + 내용 보강된 영문 챕터
4. `_workspace/04_image_manifest.json` — 매니페스트:

```json
{
  "total_images": 25,
  "paper_figures": 20,
  "gemini_illustrations": 5,
  "chapters": {
    "ch02": [
      {
        "figure_id": "Figure 2.1",
        "source_paper": "SayCan",
        "source_type": "seminar_pdf",
        "source_page": 15,
        "file": "ch02_saycan_fig1.png",
        "caption_ko": "...",
        "caption_en": "...",
        "content_reinforced": true
      }
    ]
  }
}
```

## 주의사항

- **논문 figure 우선**: Gemini 생성은 논문 figure가 부족할 때의 보조 수단
- **경로 규칙**: `../../assets/figures/`로 시작해야 build_site.py가 올바르게 변환
- **블록 이미지**: 한 줄에 `![...](...)`만 있으면 build_site.py가 `<figure>` 태그로 변환
- **다크모드**: 논문 figure는 단일 버전 — `onerror` fallback이 원본 표시
- **파일 형식**: .png, .jpg, .jpeg 모두 지원 — 확장자 확인 필수
- **내용 보강**: 이미지만 넣고 끝내지 않는다 — 논문을 열었으면 내용도 대조한다
