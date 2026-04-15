---
name: fact-check
description: "서베이 책의 수치, 인용, 주장을 교차 검증하는 스킬. 논문 원문 대조, 성능 수치 확인, 인용 일관성 검증. '팩트체크', '수치 확인', 'verify', 'fact check' 요청 시 사용."
---

# Fact Check

서베이 책 원고의 정확성을 검증한다.

## 검증 우선순위

### Critical (반드시 원문 확인)
- 성능 수치 (success rate, accuracy %)
- 데이터셋 규모 (N demonstrations, M hours)
- 비용 비교 ($X vs $Y)
- "N배 향상", "최초" 등의 주장

### Important (WebSearch로 교차 확인)
- 방법론 설명의 정확성
- 실험 조건 (baseline, task 수, embodiment)
- 연도와 저자 정보

### Normal (논리적 일관성)
- 인과 관계 서술의 타당성
- 챕터 간 서술 일관성
- 교차참조 정합성

## 검증 절차

### Step 1: 사전 검증 (writer 대기 중)
writer가 집필하는 동안 핵심 논문의 주요 수치를 미리 WebSearch로 확인한다:
- pi0의 dexterous task 성능
- OpenVLA vs RT-2 비교 수치
- DROID 데이터셋 규모
- Diffusion Policy의 baseline 대비 향상률

### Step 2: 챕터별 검증
writer가 파트를 완료하면 해당 챕터들을 검증한다:
1. 모든 `[Author et al., Year]` 인용을 추출
2. 참고문헌 리스트와 대조
3. **참고문헌의 논문 제목을 WebSearch로 원본 대조** (제목 hallucination 검출 — 가장 흔한 오류)
4. Critical 수치를 원문과 비교
5. 맥락 없는 수치에 경고 표시

### Step 3: 보고서 작성

```markdown
# Fact Check Report: Ch N-M

## Critical Issues (반드시 수정)
- **[Ch N, Ref X] 제목 불일치**: "Joint Motion Manifold for Cross-Embodiment Retargeting" → 실제 제목: "Learning to Transfer Human Hand Skills for Robot Manipulations" (arXiv:2501.04169)
  - 수정 제안: 실제 제목으로 교체, arXiv ID 추가
- **[Ch N, Section X]**: "pi0 achieves 95% success" → 원문 Table 2: 전체 평균 87%, 특정 task만 95%
  - 수정 제안: "pi0는 특정 dexterous task에서 95%, 전체 평균 87%의 성공률을 달성했다"

## Warnings (맥락 보강 권장)
- **[Ch N, Section Y]**: "3배 향상"은 단일 baseline(random) 대비. 기존 SOTA 대비 1.4배.

## Verified OK
- Ch N: 핵심 수치 X개 검증 완료, 인용 Y개 확인

## Missing Citations
- [Author et al., Year]가 참고문헌에 없음
```

## 주의 사항
- %p(percentage point)와 %(percent) 구분 필수
- 단일 task vs 전체 평균 구분 필수
- PR 자료 수치와 논문 수치 구분 — 논문만 사용
- R2, RMSE 등 정밀 수치는 반올림하지 않음
- 수치 인용 시 맥락 포함: 어떤 task, 몇 개 trial, 어떤 baseline

## 출력
`_workspace/03_factcheck_*.md`에 챕터 그룹별 보고서 저장:
- `03_factcheck_pre_verification.md` — 사전 검증 결과
- `03_factcheck_part1_ch01_03.md`
- `03_factcheck_part2_ch04_06.md`
- `03_factcheck_part3_ch07_09.md`
- `03_factcheck_part4_ch10.md`
- `03_factcheck_summary.md` — 전체 요약
