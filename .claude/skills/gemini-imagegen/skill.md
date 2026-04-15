---
name: gemini-imagegen
description: "Gemini API를 사용하여 고품질 이미지를 생성하는 스킬. 텍스트 프롬프트로 교육용 인포그래픽, 기술 다이어그램, 개념도 등을 생성한다. 이미지 생성, 삽화, 일러스트, 그림 요청 시 반드시 이 스킬을 사용할 것. <!-- IMAGE: --> 태그를 처리할 때도 이 스킬을 사용."
---

# Gemini Image Generation Skill

Google Gemini API의 이미지 생성 기능을 사용하여 고품질 시각 자료를 생성한다.

## 사전 요구사항

- `.env.local` 파일에 `GEMINI_API_KEY` 설정 필요
- Python 3.8+ (google-genai 패키지)

## 설치

첫 실행 전 아래 명령어로 의존성을 설치한다:
```bash
pip install google-genai Pillow
```

## 사용법

### 기본 이미지 생성

`scripts/generate_image.py` 스크립트를 Bash로 실행한다:

```bash
python3 .claude/skills/gemini-imagegen/scripts/generate_image.py \
  --prompt "기술적 다이어그램: GelSight 센서의 광학 원리" \
  --style "technical" \
  --output "assets/figures/ch02/fig_2_3_gelsight.png" \
  --size "1024x1024"
```

### 스타일 프리셋

| 스타일 | 설명 | 용도 |
|--------|------|------|
| `technical` | 깔끔한 기술 다이어그램, 흰 배경, 정확한 선 | 센서 구조도, 시스템 아키텍처 |
| `infographic` | 교육용 인포그래픽, 아이콘 + 화살표 | 비교 차트, 타임라인 |
| `conceptual` | 개념도, 추상적 시각화 | taxonomy, 흐름도 |
| `darkmode` | 다크 모드 호환, 밝은 선 + 어두운 배경 | 웹사이트용 |
| `academic` | 학술 논문 스타일, 단순하고 명확 | IEEE paper Figure |

### 스타일별 기본 프롬프트

```python
STYLE_PROMPTS = {
    "technical": "Clean technical diagram with precise lines, white background, labeled components, engineering drawing style. No text in non-English languages.",
    "infographic": "Educational infographic with icons, arrows, and visual hierarchy. Pastel color palette, clear layout, minimal text.",
    "conceptual": "Conceptual diagram showing relationships and flow. Abstract visualization with nodes and connections. Clean modern design.",
    "darkmode": "Technical illustration on dark background (#0a0a0f). Bright lines (#00D4AA, #3498DB, #9B59B6). Glowing edges, minimal style.",
    "academic": "Academic paper figure style. Simple, clear, black and white with minimal color accents. Publication-ready quality."
}
```

## 프롬프트 작성 원칙

1. **영어로 작성**: Gemini의 이미지 생성은 영어 프롬프트가 가장 정확
2. **텍스트 최소화**: AI 생성 이미지에서 텍스트(특히 한국어)는 깨지기 쉬움. 레이블은 후처리로 추가
3. **구체적 묘사**: "robot hand" 보다 "anthropomorphic 5-fingered robot hand with blue tactile sensors on fingertips, side view"
4. **구성 지시**: "left side shows X, right side shows Y, arrow connecting them"
5. **스타일 일관성**: 같은 챕터 내 이미지는 동일 스타일 프리셋 사용

## <!-- IMAGE: --> 태그 처리

book-writer가 삽입한 IMAGE 태그를 파싱하여 이미지를 생성한다:

```
<!-- IMAGE: [Figure 2.3: GelSight optical principle — citation, Yuan et al. 2017 Fig.2] -->
```

파싱 결과:
- figure_id: "fig_2_3"
- description: "GelSight optical principle"
- type: "citation" → 이 경우 원본 논문의 그림을 최대한 재현하되, 자체 생성 표시
- source: "Yuan et al. 2017 Fig.2"

**citation 타입**: 원본 논문의 그림을 참고하여 유사한 개념도를 자체 생성. 캡션에 "Inspired by [Source]" 또는 "Adapted from [Source]" 표시.
**original 타입**: 완전 자체 생성. 캡션에 출처 불필요.
**chart 타입**: 데이터 기반 차트. Matplotlib/SVG로 생성 권장.

## 에러 핸들링

- API Key 없음: `.env.local` 확인 안내 메시지 출력
- Rate limit: 30초 대기 후 재시도 (최대 3회)
- 생성 실패: 프롬프트 단순화 후 재시도
- 부적절 콘텐츠 필터: 프롬프트에서 문제 부분 제거 후 재시도

## 출력

- 이미지 파일: PNG 형식, 1024x1024 기본
- 메타데이터: 파일명, 프롬프트, 스타일, 생성 시각을 figure_manifest.json에 기록
