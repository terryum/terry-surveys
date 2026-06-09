---
name: curate-paper-images
description: "논문 figure를 선별하여 책 챕터에 삽입하고, 논문 원문과 대조하여 내용을 보강하며, 필요시 OpenAI gpt-image-2로 보조 일러스트를 생성하는 스킬. '이미지 추가', '논문 사진', 'figure 삽입', '이미지 큐레이션', '논문 그림', '챕터에 그림 넣어줘', '이미지 보강', '시각 자료 추가' 요청 시 반드시 이 스킬을 사용할 것. 챕터가 텍스트만으로 구성되어 있고 시각적 보강이 필요할 때도 자동 트리거."
---

# Curate Paper Images — 논문 Figure 큐레이션 + 내용 보강 스킬

논문 figure를 선별하여 책 챕터에 배치하고, 논문 원문과 대조하여 내용을 보강하며, 필요시 OpenAI gpt-image-2로 보조 일러스트를 생성한다.

## 전제 조건

- 책 챕터(`book/ko/`, `book/en/`)가 이미 완성되어 있어야 한다
- 세미나 PDF가 `docs/revise-source/`에 존재해야 한다

## 이미지 소스 (챕터 유형별 우선순위)

세 계열을 챕터 유형에 맞게 병용한다. 단일 소스로만 채우지 말 것.

1. **논문 원본 figure**: arXiv PDF / 저널 PDF → 해당 figure 크롭. 메서드·결과 챕터의 **1급 소스**.
2. **플랫폼 / 제품 공식 사진**: 상용 휴머노이드·쿼드러패드·액추에이터·센서 플랫폼은 회사 press kit, GitHub README, 하드웨어 arXiv 논문에서 가져온다. 학술 리뷰 fair use 범위. **회사·플랫폼 챕터의 1급 소스**.
3. **세미나 PDF / 블로그 포스트**: `docs/revise-source/*.pdf`, `terryum-ai/posts/papers/{slug}/` — 이미 크롭되어 meta 첨부된 figure.
4. **OpenAI gpt-image-2 생성 개념도**: `/image-gen` 또는 `~/.claude/skills/image-gen/scripts/generate-image.py` — 이론·전략·생태계 챕터의 overview 스키마, 타임라인, 비교 다이어그램. 기본은 `--style survey-dark --ratio 16:9 --quality medium`; Terry가 결과물을 마음에 들지 않는다고 재생성을 지시할 때만 `--quality high` 또는 `--high`를 쓴다. **티어 쿼터 내에서 다수 생성 허용** (이전의 "챕터당 ≤ 2" 상한 폐기).
5. **웹 이미지 검색 (최후 수단)**: 위 네 경로에 없을 때만. 반드시 원 출처를 확인하고 라이선스 근거를 `_assets_log.md`에 기록.

Google Gemini / Imagen 계열 이미지 생성은 신규 survey figure 생성에서 비활성화한다. 과거 산출물의 provenance를 설명할 때만 Gemini 명칭을 남긴다.

## 7단계 워크플로우

### Step 1: Source 매핑 구축

각 챕터에서 인용된 논문과 이미지 소스를 매핑한다.

```
매핑 항목:
- paper_name: 논문 명칭
- slug_short: 축약명 (예: saycan, rt2, openvla, pi0)
- source_type: seminar_pdf | blog | arxiv | ai_generated
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

**논문별 선택 우선순위:**

| Priority | 대상 | 선택 조건 |
|----------|------|----------|
| 1 | Fig 1 (overview/teaser) | 거의 항상 선택 |
| 2 | Architecture/pipeline | 방법론을 상세히 다룰 때 |
| 3 | Results comparison | 정량 결과를 비교할 때 |

**챕터 유형별 쿼터** (canonical agent template `image-curator.md` 참조):

| 챕터 유형 | figure 수 | 소스 믹스 |
|---|---|---|
| Theory / Overview / Primer | 3–5 | gpt-image-2 스키마 중심 + 논문 figure 1–2개 |
| Method / Algorithm survey | 3–6 | 논문 figure 중심 + gpt-image-2 타임라인 1개 |
| Platform / Company / Hardware | 4–8 (**실제 사진 ≥ 2**) | 플랫폼 press + 하드웨어 arXiv + 회사 공개 다이어그램 |
| History / Ecosystem | 3–5 | 역사 사진 + gpt-image-2 스키마 + 논문 figure |

**하한**: 챕터당 ≥ 3 (예외는 `_assets_log.md`에 사유).
**논문당**: 핵심 논문 3개, 그 외 2개.

### Step 4: 이미지 크롭 + 리네이밍

**네이밍 규칙:**
- 논문 figure: `assets/figures/ch{NN}_{slug_short}_fig{N}.{ext}` (예: `ch04_pi0_fig2.jpeg`)
- gpt-image-2 생성: `assets/figures/ch{NN}_illust_{topic}.png` (예: `ch01_illust_agentic_loop.png`)

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
- gpt-image-2 생성 일러스트는 `출처:` 없이 내용 설명만 기재

**⚠ 치명적 함정 — alt 텍스트에 `[Author, Year]` 대괄호 인용 금지**
build_site.py의 citation linkifier가 markdown 이미지 alt 텍스트 안의 `[Author, Year]`도 `<sup><a>[N]</a></sup>` HTML로 바꾸면서 alt 속성의 closing `"`를 조기에 닫는다. 결과: `loading="lazy"`, `onerror=...`, `style="cursor:zoom-in"` 등 이미지 태그의 나머지 HTML 속성이 figcaption에 **visible text로 새어 나옴** (2026-04 humanoid-revolution 사고 — `[Kajita et al., 2003]`이 ch01.html의 figcaption에 `loading="lazy" onerror="..."` 유출).
- ❌ BAD: `![Figure 1.1: Diagram — source: [Kajita et al., 2003] Fig. 2](...)`
- ✅ GOOD: `![Figure 1.1: Diagram — source: Kajita et al. 2003 Fig. 2](...)`

본문(narrative text)의 `[Author, Year]` 인용은 대괄호 유지 가능 — linkifier가 태그 경계 바깥에서 안전하게 처리한다. 규칙은 **이미지 alt 텍스트에만** 적용.

### Step 7: OpenAI gpt-image-2 개념도 · 비교 다이어그램 생성

이론/전략/생태계 챕터는 논문 figure로 커버되지 않는 시각 자료가 챕터 본문을 이해하는 데 핵심이다. OpenAI gpt-image-2로 다음 유형을 **적극** 생성한다. 신규 생성 기본 명령은 `python3 ~/.claude/skills/image-gen/scripts/generate-image.py "<prompt>" --style survey-dark --ratio 16:9 --quality medium -o assets/figures/chNN_<slug>_figN.png` 이다:

**생성 권장 유형:**
- **Overview schematic**: 3-레이어 아키텍처 · Sim-to-Real 3전략처럼 여러 논문을 아우르는 구조도.
- **Comparison diagram**: 4-axis differentiation · ZMP vs RL vs Hybrid 컨트롤러 비교.
- **Timeline**: 학습 알고리즘 계보 · 플랫폼 발표 시계열.
- **Ecosystem map**: 한국 4-actor · 중국 2-actor · 미국 3-actor 생태계도.
- **Concept illustration**: LIPM 위상도 · domain randomization 샘플 공간.

티어 쿼터 내에서 필요한 만큼 생성한다 (이전의 "챕터당 ≤ 2개" 상한 **폐기**). 네이밍: `ch{NN}_illust_{topic}.png`.

**단, 플랫폼/회사 챕터 주의**: AI 생성 개념도만으로 회사 챕터를 채우지 말 것. 해당 챕터는 **실제 제품 사진 ≥ 2개를 선확보**한 후 gpt-image-2 다이어그램을 추가.

## 산출물

1. `assets/figures/ch{NN}_*.{ext}` — 논문 figure + gpt-image-2 일러스트
2. `book/ko/ch*.md` — 이미지 마크다운 + 내용 보강된 한글 챕터
3. `book/en/ch*.md` — 이미지 마크다운 + 내용 보강된 영문 챕터
4. `_workspace/04_image_manifest.json` — 매니페스트 (3-way source 추적):

```json
{
  "total_images": 75,
  "paper_figures": 22,
  "platform_photos": 22,
  "ai_generated": 22,
  "existing_kept": 9,
  "chapters": {
    "ch11": [
      {
        "figure_id": "Figure 11.1",
        "source_type": "platform_photo",
        "source_url": "https://bostondynamics.com/atlas/press-kit/...",
        "fetch_date": "2026-04-24",
        "sha256": "ab12cd34...",
        "license_basis": "BD press kit; fair use for academic review",
        "file": "ch11_atlas_electric_hero.jpg",
        "caption_ko": "...",
        "caption_en": "..."
      },
      {
        "figure_id": "Figure 11.2",
        "source_type": "paper_figure",
        "source_paper": "kuindersma2016optimization",
        "source_location": "arXiv:1507.02148 Fig. 3",
        "file": "ch11_kuindersma2016_fig3.png",
        "license_basis": "academic fair use",
        "caption_ko": "...",
        "caption_en": "...",
        "content_reinforced": true
      },
      {
        "figure_id": "Figure 11.3",
        "source_type": "ai_generated",
        "source_prompt": "Hybrid MPC+RL control stack diagram, dark cinematic survey style, 16:9",
        "provider": "openai",
        "model": "gpt-image-2",
        "quality": "medium",
        "file": "ch11_illust_hybrid_stack.png",
        "license_basis": "internally generated (OpenAI gpt-image-2, medium, via image-gen skill)",
        "caption_ko": "...",
        "caption_en": "..."
      }
    ]
  }
}
```

Key schema fields:
- `source_type`: `paper_figure` | `platform_photo` | `ai_generated` | `seminar_pdf` | `blog`
- `license_basis` **필수** (모든 항목).
- 플랫폼 사진은 `source_url` · `fetch_date` · `sha256` 필수.
- AI 생성 이미지는 `source_prompt` · `provider` · `model` · `quality` 필수.

## 주의사항

- **3-way 소스 병용**: 챕터 유형별 티어 쿼터 (agent-template `image-curator.md` 참조)로 소스 믹스 결정. gpt-image-2 개념도는 이론·생태계 챕터의 **1급 소스**.
- **플랫폼 사진은 회사 챕터의 필수 성분**: Ch급 회사 분석 챕터는 실제 제품 사진 ≥ 2개 없이 AI 생성 스키마만으로 채우지 말 것.
- **경로 규칙**: `../../assets/figures/`로 시작해야 build_site.py가 올바르게 변환
- **블록 이미지**: 한 줄에 `![...](...)`만 있으면 build_site.py가 `<figure>` 태그로 변환
- **다크모드**: 논문 figure는 단일 버전 — `onerror` fallback이 원본 표시
- **파일 형식**: .png, .jpg, .jpeg 모두 지원 — 확장자 확인 필수
- **내용 보강**: 이미지만 넣고 끝내지 않는다 — 논문을 열었으면 내용도 대조한다
