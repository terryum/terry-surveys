---
name: ieee-paper-write
description: "IEEE Journal 형식의 LaTeX 기반 survey paper를 작성하는 스킬. IEEE Computer, AI, Robotics 관련 저널(T-RO, RA-L, T-ASE 등)에서 통용되는 IEEE 템플릿으로 tactile sensing for robot hands 분야의 종합 survey 논문을 집필한다. IEEE 논문, LaTeX survey paper, 학술 논문 작성이 필요할 때 이 스킬을 사용할 것."
---

# IEEE Paper Write Skill

문��� 조사 결과와 책 콘텐츠를 기반으로, IEEE Journal 형식의 LaTeX survey paper를 작성한다.

## 대상 저널 스타일

IEEE Transactions on Robotics (T-RO), IEEE Robotics and Automation Letters (RA-L), IEEE Transactions on Automation Science and Engineering (T-ASE) 등에서 사용하는 IEEE 2-column 형식.

## 워크플로우

### Step 1: LaTeX 프로젝트 구조 생성

```
paper/
├── main.tex                 # 메인 파일
├── IEEEtran.cls            # IEEE 템플릿 클래스 (다운로드)
├── IEEEtran.bst            # IEEE 참고문헌 스타일
├── references.bib           # BibTeX 참고문헌
├── sections/
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── tactile_sensors.tex
│   ├── robot_hand_design.tex
│   ├── data_representation.tex
│   ├── learning_methods.tex
│   ├── integrated_systems.tex
│   ├── discussion.tex
│   └── conclusion.tex
├── figures/                  # 그림 파일 (placeholder)
│   └── .gitkeep
└── Makefile                  # pdflatex 빌드용
```

### Step 2: 논문 구조 설계

IEEE survey paper의 전형적 구조를 따른다:

```latex
\documentclass[journal]{IEEEtran}

\title{Tactile Sensing for Dexterous Robot Manipulation: \\
A Comprehensive Survey}

\author{
  Terry Taewoong Um~\IEEEmembership{Member,~IEEE}
  \thanks{...affiliation...}
}

\begin{abstract}
% 150-250 words
\end{abstract}

\begin{IEEEkeywords}
Tactile sensing, dexterous manipulation, robot hand,
vision-language-action models, embodiment retargeting
\end{IEEEkeywords}

% I. Introduction
% II. Tactile Sensing Technologies
% III. Robot Hand Design and Mechanisms
% IV. Tactile Data Acquisition and Representation
% V. Learning-based Tactile Manipulation
% VI. Vision-Language-Action Models for Manipulation
% VII. Human Hand Data and Embodiment Retargeting
% VIII. Integrated Systems and Applications
% IX. Open Challenges and Future Directions
% X. Conclusion
```

### Step 3: 섹션별 집필

#### 집필 원칙

1. **학술적 어조**: 3인칭, 수동태 혼용, 객관적 서술
2. **인용 밀도**: 문단당 최소 2-3개 인용 (`\cite{key}`)
3. **비교표 필수**: 주요 방법론/기술 비교 테이블 (`\begin{table}`)
4. **분류 체계**: 각 섹션에서 다루는 기술을 taxonomy로 분류
5. **그림**: 각 섹션에 최소 1개 개념도/분류도 (`\begin{figure}`)
6. **분량**: 전체 20-30페이지 (IEEE 2-column 기준)

#### 섹션별 가이드

| 섹션 | 내용 | 예상 분량 |
|------|------|----------|
| Abstract | 전체 survey 요약, 주요 발견, 기여 | 200 words |
| I. Introduction | 동기, 기존 survey 대비 차별점, 논문 구성 | 2 pages |
| II. Tactile Sensing | 센서 유형 분류, 비교표, 최신 센서 | 3-4 pages |
| III. Robot Hand Design | 구동 방식, DOF, VSA, underactuated | 2-3 pages |
| IV. Data & Representation | 데이터셋, 표현 학습, sim-to-real | 2-3 pages |
| V. Learning-based Manipulation | RL, IL, contact-rich tasks | 3-4 pages |
| VI. VLA Models | foundation models, 멀티모달 정책 | 2-3 pages |
| VII. Human Data & Retargeting | data glove, teleoperation, transfer | 2-3 pages |
| VIII. Integrated Systems | 촉각-시각 융합, 실제 응용 | 2 pages |
| IX. Open Challenges | 미해결 문제, 미래 방향 | 1-2 pages |
| X. Conclusion | 핵심 요약, 전망 | 0.5 page |

### Step 4: 참고문헌 관리

`book/references.bib`를 기반으로 IEEE 스타일에 맞게 정리:

```bibtex
@article{yuan2017gelsight,
  author={Yuan, Wenzhen and Dong, Siyuan and Adelson, Edward H.},
  journal={IEEE Sensors Journal},
  title={GelSight: High-Resolution Robot Tactile Sensors for
         Estimating Geometry and Force},
  year={2017},
  volume={17},
  number={22},
  pages={7159-7167},
  doi={10.1109/JSEN.2017.2748146}
}
```

- 모든 `\cite{}`가 references.bib에 존재하는지 확인
- IEEE 약어 규칙 준수 (예: Transactions → Trans., Conference → Conf.)
- DOI 필드 필수

### Step 5: 비교표 생성

survey의 핵심 가치인 체계적 비교표를 반드시 포함:

| 표 | 내용 |
|----|------|
| Table I | Tactile sensor comparison (type, resolution, frequency, cost) |
| Table II | Dexterous hand comparison (DOF, actuation, weight, sensors) |
| Table III | Tactile datasets comparison (modality, size, tasks) |
| Table IV | Learning methods comparison (approach, input, task, performance) |
| Table V | VLA models comparison (architecture, modalities, benchmarks) |

### Step 6: 빌드 및 검증

```makefile
# Makefile
all:
	pdflatex main.tex
	bibtex main
	pdflatex main.tex
	pdflatex main.tex

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.pdf
```

## 입력

- `_workspace/01_researcher_literature_map.json` — 논문 DB
- `book/en/` — 영어 책 콘텐츠 (재활용 가능한 서술)
- `book/references.bib` — 통합 참고문헌

## 출력

- `paper/` — 전체 LaTeX 프로젝트
- `paper/main.pdf` — 컴파일된 PDF (pdflatex 설치 시)

## 품질 기준

- IEEE 형식 준수 (IEEEtran.cls)
- 참고문헌 50편 이상
- 비교표 최소 5개
- 모든 `\cite{}`와 `references.bib` 1:1 매칭
- Abstract 150-250 words
- 전체 20-30 pages (2-column)
