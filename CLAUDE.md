# terry-surveys — 통합 서베이 모노레포

양국어(KO/EN) 연구 서베이 책을 통합 관리하는 모노레포. Markdown → HTML 정적 사이트 생성, Vercel 배포.

## 프로젝트 구조

```
terry-surveys/
├── build.py                  # CLI 엔트리포인트
├── shared/                   # 공유 빌드 인프라
│   ├── build_site.py         # 통합 Markdown→HTML 빌드 스크립트
│   ├── scaffold.py           # 새 서베이 스캐폴딩
│   ├── css/style.css         # 공유 스타일시트
│   └── js/                   # 공유 JS (header, footer, main, chapter)
└── surveys/                  # 개별 서베이 프로젝트
    ├── vla-agentic-robotics/
    ├── robot-hand-tactile-sensor/
    └── snu-tactile-hand/
```

## 빌드 명령어

```bash
python3 build.py <survey-name>     # 단일 서베이 빌드
python3 build.py --all             # 전체 빌드
python3 build.py --new <name>      # 새 서베이 스캐폴딩
python3 build.py --list            # 서베이 목록
```

## 서베이별 설정: `survey.json`

각 서베이는 `surveys/<name>/survey.json`에서 메타데이터를 관리:
- `id`, `github_repo`: 식별자
- `title`, `short_title`, `subtitle`, `description`: 양국어 제목/설명
- `parts[].chapters[]`: 챕터 구조 (번호, 제목, 요약)
- `highlights`: TOC 페이지의 하이라이트 카드
- `acknowledgment`: 감사의 글
- `features`: glossary, pdf, paper 등 기능 플래그
- `dates`: 출판일, 최종수정일

## 공유 코드 수정 규칙

`shared/` 내 파일을 수정하면 **모든 서베이에 영향**. 수정 후 반드시:
```bash
python3 build.py --all
```

## 통합 BibTeX 관리

`bibtex/references.bib`는 **모든 서베이가 공유하는 단일 source of truth**. 각 서베이의 `surveys/<name>/book/references.bib`는 이 마스터의 subset으로 유지한다 (빌드 스크립트는 로컬 파일만 읽음).

### 신규 논문 인용 시 4단계 워크플로우 (필수)

1. **grep 먼저**: `grep -i "<title-keyword>\|<arxiv-id>" bibtex/references.bib`
2. **있으면 재사용**: 마스터 키를 서베이 로컬 `.bib`에 복사
3. **없으면 마스터에 먼저**: 엔트리를 마스터에 추가한 후 서베이 로컬에도 복사
4. **자매 서베이 일관성**: 다른 서베이가 이미 쓰는 키가 있으면 반드시 동일 키 사용

### 신규 서베이 생성 체크리스트

`python3 build.py --new <name>` 실행 후에도 **반드시**:
- [ ] 첫 인용을 추가하기 전에 `bibtex/references.bib` grep으로 기존 키 확인
- [ ] 기존 논문은 마스터 키를 그대로 재사용 (중복 키 금지)
- [ ] 신규 엔트리는 마스터에 먼저 추가하고 서베이 로컬로 복사

### 키 네이밍 규약

`{firstauthorlastname}{year}{keyword}` (소문자). 예: `zhang2025soft`, `almeida2025roleoftouch`. 자세한 규약과 충돌 해결은 `bibtex/README.md` 참조.

## 서베이별 콘텐츠 구조

```
surveys/<name>/
├── survey.json           # 메타데이터 (필수)
├── vercel.json           # Vercel 배포 설정
├── book/ko/              # 한국어 챕터 (ch01.md ~ chNN.md)
├── book/en/              # 영문 챕터
├── book/references.bib   # BibTeX 참고문헌
├── assets/figures/       # 이미지
├── docs/                 # 빌드 출력 (git 커밋)
└── CLAUDE.md             # 서베이별 컨텍스트
```

## 배포

각 서베이는 독립적인 Vercel 프로젝트로 배포:
1. `python3 build.py <name>` 으로 로컬 빌드
2. `docs/`가 자동 생성됨
3. git commit & push → Vercel 자동 배포

## 챕터 작성 규칙

### 프론트매터
```yaml
---
chapter: N
title: "제목"
part: "Part X: 파트명"
date: "YYYY-MM-DD"
last_updated: "YYYY-MM-DD"
---
```

### 인용
- 인라인: `[Author et al., Year]` → 빌드 시 `<sup>[N]</sup>` 자동 변환
- 챕터 하단 `## 참고문헌` 섹션에 번호 리스트 필수
- 교차참조: `(Chapter N)` → 자동 링크 변환

### 이미지
- 경로: `../../assets/figures/파일명`
- 형식: `![Figure N.M: caption](../../assets/figures/...)`

### 수학
- 인라인: `$...$`, 블록: `$$...$$`
- KaTeX 렌더링 (CDN)

## 하네스 에이전트

| 에이전트 | 역할 |
|---------|------|
| deep-researcher | 논문 심층 서베이, 연구 그룹 매핑 |
| critical-analyst | gap 분석, novelty 평가, 차별화 전략 |
| book-writer | 양국어 챕터 집필 |
| fact-checker | 수치/인용 교차 검증 |
| image-curator | 논문 figure 선별·배치 |
| researcher | 문헌 조사 |
| reference-checker | 레퍼런스 정확성 검증 |
| qa-reviewer | 전체 품질 리뷰 |
