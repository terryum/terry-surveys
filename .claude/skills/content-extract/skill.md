---
name: content-extract
description: "사용자의 기존 자료(세미나 PDF, 홈페이지 논문 요약 포스트, GitHub md 파일)를 분석하여 책에 활용할 콘텐츠를 추출·구조화하는 스킬. PDF 파일이나 기존 포스트에서 핵심 내용을 추출하거나, 기존 자료와 새로운 문헌 간의 갭을 분석할 때 이 스킬을 사용할 것."
---

# Content Extract Skill

사용자가 보유한 세미나 PDF, 홈페이지 논문 요약, md 파일에서 책 집필에 필요한 콘텐츠를 추출하고 구조화한다.

## 대상 자료

### 세미나 PDF (3건)

| 파일 | 주제 | 예상 챕터 매핑 |
|------|------|--------------|
| `260319_Seminar_SNU_Junsoo_Jihwan_TactileHand_Maipulation.pdf` | Tactile hand + manipulation | Ch 2, 4, 7 |
| `260323_Seminar_SNU_Taejoon_DataGlove_Sensors.pdf` | Data glove + sensors | Ch 2, 5 |
| `260323_Seminar_SNU_Inchul_Hand_Gripper_Machanism.pdf` | Hand/gripper mechanism | Ch 3, 10 |

### 홈페이지 논문 포스트

- **웹 URL**: `https://terry.artlab.ai/en/posts?tab=papers`
- **GitHub 원본**: `https://github.com/terryum/terry-artlab-homepage/tree/main/posts/papers`
- GitHub raw URL로 md 파일 직접 접근 가능

## 워크플로우

### Step 1: PDF 분석

각 PDF에 대해:

1. Read 도구로 PDF 내용 읽기 (페이지 범위 지정)
2. 슬라이드/섹션 단위로 구조 파악
3. 핵심 내용 추출:
   - 다루는 기술/개념 목록
   - 언급된 논문/연구 (저자, 제목, 연도)
   - 핵심 그림/다이어그램의 설명
   - 사용자의 독창적 분석/비교/의견
4. 챕터 매핑 태그 부여

### Step 2: 홈페이지 포스트 분석

1. GitHub repo에서 papers 디렉토리의 md 파일 목록 조회
2. 각 md 파일의 내용을 WebFetch로 읽기 (raw URL 사용)
3. 포스트별 핵심 추출:
   - 요약 대상 논문의 메타데이터
   - 사용자가 강조한 핵심 기여/인사이트
   - 관련 분야 태그
4. 챕터 매핑 태그 부여

### Step 3: 갭 분석

기존 자료가 다루는 영역과 책의 목표 범위를 비교:

```
책의 목표 범위 (12 챕터)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
■■■■ 기존 자료 커버        (강점)
░░░░ 부분적 커버            (보충 필요)
     미커버                 (새로 작성 필요)
```

각 챕터별로:
- **강점**: 기존 자료에서 충분한 콘텐츠가 있는 영역
- **보충 필요**: 기존 자료가 있으나 깊이 부족 — researcher에게 추가 조사 요청
- **새로 작성**: 기존 자료 없음 — literature map에서 콘텐츠 구성

### Step 4: 참조 논문 목록 추출

기존 자료에서 언급된 모든 논문을 구조화하여 researcher에게 전달:

```json
{
  "referenced_papers": [
    {
      "title": "string",
      "authors": "string (자료에 기재된 형태 그대로)",
      "year": 2024,
      "source_material": "string (어느 자료에서 발견)",
      "context": "string (어떤 맥락에서 언급)"
    }
  ]
}
```

### Step 5: 산출물 저장

- `_workspace/01_analyst_content_extraction.md`
- `_workspace/01_analyst_reference_papers.json`
- `_workspace/01_analyst_gap_analysis.md`

## 품질 기준

- PDF당 최소 10개 이상의 핵심 개념/기술 추출
- 참조 논문 누락률 10% 이하 (PDF에 명시된 논문 기준)
- 갭 분석은 12개 챕터 모두에 대해 수행
