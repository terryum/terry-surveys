---
name: deep-literature-research
description: "로보틱스/VLA/LLM 기반 에이전틱 로보틱스 논문의 심층 서베이를 수행하는 스킬. 논문 서베이, 인용 분석, 연구 그룹 매핑, 시간축 흐름 추적을 포함. '논문 조사', '서베이', '논문 분석', 'paper survey' 요청 시 사용."
---

# Deep Literature Research

LLM as Planner → VLA → Code as Policy → Agentic Robotics 연구 흐름의 논문을 심층 서베이한다.

## 서베이 전략

### Step 1: 기존 논문 목록 로드
`docs/robotics_vla_agentic_llm_papers.md`와 `docs/agentic_robotics_llm_vla_curated_papers_2023_2025.md`를 읽어 핵심 논문과 카테고리를 파악한다.

### Step 2: 카테고리별 서베이

| 카테고리 | 핵심 질문 | 핵심 논문 |
|---------|----------|----------|
| LLM as Planner | LLM이 로봇 계획에 어떻게 사용되기 시작했는가? | LLM as Planners (2022), SayCan (2022), SayPlan (2023) |
| Code as Policy | 코드가 왜 자연어보다 나은 로봇 제어 인터페이스인가? | CaP (2022), Code-as-Symbolic-Planner (2025), CaP-X (2026) |
| VLA Models | VLM을 어떻게 로봇 action으로 직접 연결하는가? | PaLM-E, RT-2, OpenVLA, pi0, GR00T N1 |
| Hierarchical Planning | 고수준 계획과 저수준 제어를 어떻게 연결하는가? | AutoTAMP, RT-H, Hi Robot, HAMSTER |
| Memory & Scene Graph | 로봇이 장기 작업을 수행하려면 무엇을 기억해야 하는가? | KARMA, Embodied-RAG, RoboEXP, VeriGraph |
| Agentic & Sim2Real | 폐루프 에이전틱 시스템은 어떻게 작동하는가? | REFLECT, BUMBLE, AutoRT, PragmaBot, SIMPLER |

### Step 3: 각 논문 분석 형식

```markdown
### [Paper Name] ([Year])
- **arXiv**: https://arxiv.org/abs/XXXX.XXXXX
- **핵심 Contribution**: 1-2문장
- **방법론**: 핵심 접근법 요약
- **주요 결과**: 수치 포함 (정확한 테이블/그래프 출처 명시)
- **한계점**: 저자가 인정한 + 분석에서 드러나는
- **영향**: 이 논문이 후속 연구에 미친 영향
- **Agentic Coding 대비**: 이 접근이 디지털 에이전트에서 어떻게 대응되는지
```

### Step 4: 연구 그룹 매핑
각 그룹이 어떤 흐름을 주도하는지 파악한다:
- Google DeepMind: SayCan, PaLM-E, RT-2, AutoRT
- Stanford: Code as Policies, SayPlan
- Berkeley: DROID, OpenVLA, Octo
- Physical Intelligence: pi0, pi0.5
- NVIDIA: GR00T N1

### Step 5: 시간축 흐름
2022-2026 연도별 주요 전환점과 그 의미를 정리한다.

## WebSearch 전략
- `site:arxiv.org {paper name}` — 논문 원문 확인
- `{paper name} citation count` — 인용 영향력
- `{research group} robotics 2024 2025` — 최신 동향

## 출력
카테고리별 7개 파일을 `_workspace/01_researcher_*.md`에 저장한다.
