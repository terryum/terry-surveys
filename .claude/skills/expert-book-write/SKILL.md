---
name: expert-book-write
description: "한국어/영어 이중언어 서베이 책의 챕터를 집필하는 스킬. 연구 흐름을 서사적으로 풀어내며 agentic coding과의 대비를 유지한다. '챕터 집필', '책 쓰기', 'write chapter' 요청 시 사용."
---

# Expert Book Write

LLM Planner → VLA → Code as Policy → Agentic Robotics 서베이 책의 챕터를 집필한다.

## 집필 순서

Part 단위로 집필 → 팩트체크 → 수정 → 다음 Part 진행:

1. **Part I** (Ch 1-3): 기초 — LLM이 로봇을 만나다
2. **Part II** (Ch 4-6): VLA 혁명
3. **Part III** (Ch 7-9): 에이전틱 로보틱스를 향하여
4. **Part IV** (Ch 10): 근본적 차이 — 종합

## 챕터별 핵심 메시지

| Ch | 핵심 질문 | Agentic Coding 대비 포인트 |
|----|----------|-------------------------|
| 1 | 왜 로봇에도 agentic loop이 필요한가? | Coding의 code→execute→error→fix 루프 소개 |
| 2 | LLM이 로봇 계획을 어떻게 바꿨나? | Tool description vs affordance의 차이 |
| 3 | 코드가 왜 자연어보다 나은 제어 인터페이스인가? | Code interpreter vs robot code execution의 차이 |
| 4 | VLM을 어떻게 직접 action으로 연결하는가? | End-to-end vs modular의 트레이드오프 |
| 5 | 고수준과 저수준을 어떻게 연결하는가? | IDE의 auto-complete vs 연속 제어 |
| 6 | 저수준 제어의 최전선은 어디인가? | Deterministic execution vs stochastic policy |
| 7 | 로봇은 무엇을 기억해야 하는가? | File system/context vs spatial memory |
| 8 | 폐루프 에이전틱 시스템은 어떻게 작동하는가? | CI/CD loop vs physical trial loop |
| 9 | Sim-to-Real gap을 어떻게 좁히는가? | Staging environment vs simulation |
| 10 | 디지털 에이전트와 물리 에이전트의 근본적 차이 | 7대 차원 종합 분석 |

## 챕터 구조 템플릿

```markdown
---
chapter: N
title: "한글 제목"
subtitle: "English Subtitle"
part: "Part X: 파트명"
date: "2026-04-08"
last_updated: "2026-04-08"
---

## 요약

[3-5문장. 이 챕터의 핵심 메시지와 agentic coding과의 연결점]

## N.1 도입

[왜 이 주제가 연구 흐름에서 중요한 전환점이었는지. 선행 챕터와의 연결.]

## N.2 ~ N.M 본문

[논문 기반 서술. 각 서브섹션은 하나의 핵심 아이디어나 논문 그룹을 다룸.]
[수치 인용: [Author et al., Year], 구체적 수치 포함]

## N.M+1 Agentic Coding과의 대비

[이 챕터의 주제를 agentic coding의 대응 개념과 비교]
[단순 비교표가 아닌 "왜 이 차이가 근본적인가"를 설명]

## N.M+2 미해결 문제와 전망

[현재 접근법의 한계, 열린 질문, 향후 연구 방향]

## 참고문헌

1. Author et al., "Title," arXiv:XXXX.XXXXX, Year.
```

## 인용 규칙

- 본문: `[Author et al., Year]` — 빌드 시 자동 변환됨
- 교차참조: `(→ Chapter N)` — 빌드 시 링크 변환됨
- 저자 3명 이상: 첫 저자 + et al.
- 참고문헌에 arXiv 링크 필수
- `et al.`의 마침표 뒤 쉼표: `[Author et al., Year]`

## 이중언어 집필

- `book/ko/chNN.md`와 `book/en/chNN.md`를 동시에 작성
- 번역이 아닌 각 언어에 자연스러운 문장으로 집필
- 한국어: 경어체, 영어: Academic but accessible
- 수식, 테이블, 인용은 양쪽 동일

## 입력

- `_workspace/01_researcher_*.md` — 서베이 결과
- `_workspace/02_analyst_*.md` — 분석 결과
- `docs/` — 원본 논문 목록
