---
name: literature-research
description: "Tactile sensing, robot hand, dexterous manipulation 분야의 학술 문헌을 체계적으로 조사하는 스킬. seminal paper(최근 5년), survey/review/tutorial(최근 3년)을 검색하고, 카테고리별로 분류하여 구조화된 논문 데이터베이스와 요약을 생성한다. 로봇 촉각 센서, 로봇 핸드, manipulation, VLA, embodiment retargeting 관련 논문 조사가 필요할 때 반드시 이 스킬을 사용할 것."
---

# Literature Research Skill

Tactile sensing & robot hand manipulation 분야의 문헌을 체계적으로 조사하여 구조화된 데이터베이스를 생성한다.

## 워크플로우

### Step 1: 카테고리별 검색 전략 수립

각 카테고리에 대해 검색 쿼리를 구성한다. 검색 소스는 아래 우선순위로 사용:

1. **Google Scholar** — 인용수 확인, 정렬 기준
2. **Semantic Scholar API** — 구조화된 메타데이터
3. **arXiv** — 최신 프리프린트 (특히 2025~2026)
4. **IEEE Xplore / ACM DL** — 학회 논문
5. **직접 연구 그룹 페이지** — 핵심 연구실의 최신 출판물

### Step 2: 카테고리별 검색 실행

7개 카테고리를 순회하며 검색:

| # | 카테고리 | 검색 쿼리 예시 | 목표 논문 수 |
|---|---------|---------------|------------|
| 1 | Tactile Sensing Hardware | "tactile sensor" "robot" survey OR review 2023..2026 | 8~12 |
| 2 | Tactile Data & Representation | "tactile representation learning" OR "tactile dataset" | 6~10 |
| 3 | Robot Hand Design | "dexterous hand" OR "anthropomorphic hand" design survey | 8~12 |
| 4 | Tactile Manipulation | "in-hand manipulation" "tactile" OR "contact-rich" | 8~12 |
| 5 | Learning for Manipulation | "vision language action" robot OR "VLA" manipulation | 8~12 |
| 6 | Human Hand Data | "data glove" OR "hand teleoperation" OR "embodiment retargeting" | 6~10 |
| 7 | Integrated Systems | "tactile visual fusion" OR "multimodal manipulation" foundation model | 6~10 |

### Step 3: 필터링 및 우선순위

각 검색 결과에서:
1. **Seminal papers (5년)**: 인용수 상위 또는 핵심 연구 그룹 소속
2. **Survey/Review (3년)**: "survey", "review", "tutorial", "overview" 키워드
3. **핵심 연구 그룹 가중**: MIT CSAIL, Stanford (Jeannette Bohg, Karen Liu, Fei-Fei Li), CMU (Jessica Hodgins, Abhinav Gupta), UC Berkeley (Pieter Abbeel, Jitendra Malik), ETH Zurich, Google DeepMind, Meta FAIR, NVIDIA, 서울대, KAIST
4. **핵심 인물 가중**: Roberto Calandra, Edward Adelson (GelSight), Sergey Levine, Chelsea Finn, Lerrel Pinto, Shuran Song

### Step 4: 구조화 및 저장

검색된 논문을 JSON 형태로 구조화하고, 카테고리별 마크다운 요약을 작성한다.

**JSON 저장**: `_workspace/01_researcher_literature_map.json`
**요약 저장**: `_workspace/01_researcher_literature_summary.md`

### Step 5: 교차 검증

- 동일 논문이 여러 카테고리에 해당하면 primary/secondary 카테고리 표시
- 인용수는 최소 2개 소스에서 교차 확인
- survey 논문이 참조하는 핵심 논문 중 목록에 누락된 것 추가

## 핵심 키워드 사전

검색 시 활용할 동의어/관련어:

```
tactile sensor → tactile sensing, touch sensor, contact sensor, pressure sensor array
GelSight → gel-based sensor, vision-based tactile, optical tactile
robot hand → dexterous hand, robotic gripper, anthropomorphic hand, end-effector
manipulation → grasping, in-hand manipulation, contact-rich manipulation
VLA → vision-language-action, multimodal policy, foundation model robot
retargeting → embodiment transfer, cross-embodiment, hand pose retargeting
underactuated → compliant mechanism, adaptive gripper, variable stiffness
VSA → variable stiffness actuator, series elastic actuator, impedance control
```

## 품질 기준

- 카테고리당 최소 5편, 전체 최소 50편
- seminal:survey 비율 약 3:1
- 2024~2026년 논문 비율 50% 이상
- 모든 논문에 DOI 또는 arXiv URL 포함
