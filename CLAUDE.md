# terry-surveys — 통합 서베이 모노레포

양국어(KO/EN) 연구 서베이 책을 통합 관리하는 모노레포. Markdown → HTML 정적 사이트 생성, Cloudflare Pages 배포.

## 프로젝트 구조

```
terry-surveys/
├── build.py                  # CLI 엔트리포인트
├── shared/                   # 공유 빌드 인프라
│   ├── build_site.py         # 통합 Markdown→HTML 빌드 스크립트
│   ├── scaffold.py           # 새 서베이 스캐폴딩
│   ├── css/style.css         # 공유 스타일시트
│   └── js/                   # 공유 JS (header, footer, main, chapter)
├── bibtex/                   # 통합 BibTeX 마스터 + 인덱스 도구
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
python3 build.py --index           # BibTeX refs_index.json 재생성
```

---

# 서베이 생성 표준 (Canonical Standard)

모든 서베이는 아래 **공통 구조·파이프라인·포맷**을 따른다. 이 표준은 `shared/scaffold.py`가 자동 생성하는 템플릿과 `shared/build_site.py`가 기대하는 입력 스키마의 기준이기도 하다.

## 1. 정규 서베이 디렉토리 구조

```
surveys/<name>/
├── survey.json                       # 메타 (필수)
├── CLAUDE.md                         # 서베이-레벨 도메인 설명 + 에이전트 매핑
├── README.md                         # 공개 repo용 소개 (KO/EN 섹션 병기)
├── LICENSE                           # MIT (기본)
├── CONTRIBUTING.md                   # 기여 가이드
├── .gitignore                        # 로컬 overrides
├── .github/
│   └── ISSUE_TEMPLATE/               # 4종 템플릿 (content/translation/error/config)
├── book/
│   ├── ko/                           # ch01.md … chNN.md + glossary.md + toc.md
│   ├── en/                           # 동일 구조
│   └── references.bib                # 마스터 bibtex/references.bib의 subset
├── assets/figures/                   # flat 구조, chNN_<slug>_fig<N>.<ext>
├── scripts/
│   └── push.sh                       # Cloudflare Pages 외부 repo 동기화
├── docs/                             # 빌드 산출물 (git 커밋)
│   └── _redirects                    # Cloudflare Pages 리다이렉트
├── _refs_extracted.json              # 인용 추출 + scholar 링크 상태
└── _factcheck_report.md              # 팩트체크 감사 리포트
```

**금지 사항:**
- `assets/figures/ch01/`, `chNN/` 등 **서브폴더 금지** — 모두 flat.
- `paper/`, `build_pdf.*` 등 서베이-로컬 PDF/LaTeX 빌드 코드 금지 (별도 워크플로우에서 관리).
- 세미나 STT·번역·슬라이드 매칭 등 1회성 데이터 처리 스크립트는 `scripts/`에 커밋하지 않고 `_workspace/`(gitignore)에서 돌린다.

## 2. 정규 에이전트 파이프라인

서베이 1편 완성은 다음 순서로 진행한다. 각 단계는 **필수 산출물**을 남겨 다음 단계에 컨텍스트를 공급한다.

| 단계 | 에이전트 | 필수 산출물 |
|---|---|---|
| 1. 조사 | `deep-researcher` | `_research/<domain>_papers.json`, 연구 그룹·타임라인 매핑 |
| 2. 분석 | `critical-analyst` | gap·novelty 문서 (`_analysis/gaps.md`) |
| 3. 집필 | `book-writer` | `book/{ko,en}/chNN.md` (KO/EN 동시), `book/{ko,en}/glossary.md` |
| 4. 그림 | `image-curator` | `assets/figures/chNN_<slug>_fig<N>.<ext>` (논문 원본 크롭 우선) |
| 5. 팩트 | `fact-checker` | `_refs_extracted.json`, `_factcheck_report.md` |
| 6. 리뷰 | `qa-reviewer` | 커버리지·인용 포맷·교차참조 최종 체크 |

## 3. 표준 산출물 포맷

### 챕터 frontmatter (YAML)

```yaml
---
chapter: N
title: "제목"
subtitle: "부제 (선택)"
part: "Part X: 파트명"
date: "YYYY-MM-DD"
last_updated: "YYYY-MM-DD"
---
```

### 인용

- **인라인**: `[Author et al., Year]` — 괄호 필수 (빌드 스크립트 정규식 매칭용). 빌드 시 `<sup>[N]</sup>`으로 자동 변환.
- **교차참조**: `(Chapter N)` — 화살표·약어 금지.
- **챕터 하단 참고문헌**: `## 참고문헌` (KO) / `## References` (EN) 섹션 필수, 번호 리스트.

### Figure

- **네이밍**: `chNN_<sourceSlug>_fig<N>.<ext>` (flat 폴더). 예: `ch03_gelsight_fig1.png`.
- **경로**: 챕터 안에서 `../../assets/figures/파일명`.
- **정책**: **논문 원본 figure 우선**. image-curator가 원본 PDF·arXiv에서 크롭하여 출처 caption 명기.
- **AI 보조 일러스트**: Gemini 등 ≤ 2/챕터 한도. 도메인별 필요 시 각 서베이 CLAUDE.md에서 축소 조정.

### References (`book/references.bib`)

- **키 네이밍**: `{firstauthorlastname}{year}{keyword}` (소문자). 예: `zhao2025ftac`, `zhang2025soft`.
- **마스터 먼저**: 신규 인용 시 `bibtex/references.bib` 마스터에 먼저 추가 → 서베이 로컬로 복사. 자세한 규약은 아래 "통합 BibTeX 관리" 참조.

### `_refs_extracted.json` 스키마

각 인용 엔트리는 아래 키를 포함한다:

```json
{
  "chapter": 3,
  "num": 12,
  "lang": "ko",
  "text": "Author et al., Year, ...",
  "arxiv_id": "2412.14482",
  "doi": null,
  "scholar_url": "https://scholar.google.com/...",
  "scholar_status": "ok"
}
```

### `_factcheck_report.md` 섹션

```
## Summary
- 총 처리 refs: N
- Scholar 링크 추가: N
- 수정된 arXiv ID: N

## 수정사항
- chN ref M: (변경 내용)

## 미해결
- chN ref M: (원인)

## Scholar 링크 상태
- ok: N / missing: N / broken: N
```

### 수학

- 인라인: `$...$`, 블록: `$$...$$`. KaTeX(CDN) 렌더링.

### 이미지 태그 (마크다운)

```markdown
![Figure N.M: caption](../../assets/figures/chNN_<slug>_figN.png)
```

## 4. `survey.json` 필드 규약

- `id`, `github_repo`: 식별자
- `title`, `short_title`, `subtitle`, `description`: 양국어 제목/설명
- `parts[].chapters[]`: 챕터 구조 (번호, 제목, 요약)
- `highlights`: TOC 하이라이트 카드
- `acknowledgment`: 감사의 글
- `features`: 기능 플래그 — **기본값**
  - `glossary: true` (기본 on, 독자 진입장벽 완화)
  - `pdf: false` (전용 PDF 빌드 스킬 부재 시 off)
  - `paper: false` (IEEE paper 별도 워크플로우로 관리)
- `dates.first_published`, `dates.last_updated`

## 5. 배포

Cloudflare Pages로 배포. 기본 경로는 외부 GitHub repo 동기화:

```bash
cd surveys/<name>
bash scripts/push.sh "커밋 메시지"
```

`scripts/push.sh`는 `REPO_URL`에 명시된 외부 GitHub repo를 임시 디렉토리에 clone → `book/`, `docs/`, `assets/`를 rsync → 커밋/푸시. Cloudflare Pages가 외부 repo 변경을 감지해 자동 재배포.

대안: 모노레포에서 직접 `npx wrangler pages deploy docs` 실행.

- 리다이렉트: `docs/_redirects`에 정의 (빌드 스크립트가 덮어쓰지 않음).
- `.wrangler/`는 로컬 캐시 — `.gitignore` 등록 필수.

---

# 통합 Glossary 관리

`glossary/master_ko.md` / `glossary/master_en.md`는 **모든 서베이가 공유하는 용어집 마스터**. 각 서베이의 `book/<lang>/glossary.md`는 이 마스터의 subset으로 유지한다. BibTeX 마스터와 동일한 철학: "같은 용어는 어느 책에서 봐도 동일 정의".

## 워크플로우 (필수)

1. **마스터 grep**: `grep -i "^- \*\*<term>" glossary/master_ko.md`
2. **있으면 정의 재사용**: 마스터 엔트리 한 줄을 서베이 `book/<lang>/glossary.md`에 복사 → `(Ch N)` 챕터 참조만 뒤에 부기.
3. **없으면 마스터에 먼저**: `master_ko.md`와 `master_en.md` 양쪽에 canonical 정의를 추가한 후 서베이에 복사.
4. **자매 서베이 일관성**: 다른 서베이가 이미 쓰는 용어는 반드시 동일 정의(마스터 기준)를 사용.

상세는 `glossary/README.md` 참조.

---

# 통합 BibTeX 관리

`bibtex/references.bib`는 **모든 서베이가 공유하는 단일 source of truth**. 각 서베이의 `surveys/<name>/book/references.bib`는 이 마스터의 subset으로 유지한다 (빌드 스크립트는 로컬 파일만 읽음).

## 신규 논문 인용 시 4단계 워크플로우 (필수)

1. **grep 먼저**: `grep -i "<title-keyword>\|<arxiv-id>" bibtex/references.bib`
2. **있으면 재사용**: 마스터 키를 서베이 로컬 `.bib`에 복사
3. **없으면 마스터에 먼저**: 엔트리를 마스터에 추가한 후 서베이 로컬에도 복사
4. **자매 서베이 일관성**: 다른 서베이가 이미 쓰는 키가 있으면 반드시 동일 키 사용

## 신규 서베이 생성 체크리스트

`python3 build.py --new <name>` 실행 후에도 **반드시**:
- [ ] 첫 인용을 추가하기 전에 `bibtex/references.bib` grep으로 기존 키 확인
- [ ] 기존 논문은 마스터 키를 그대로 재사용 (중복 키 금지)
- [ ] 신규 엔트리는 마스터에 먼저 추가하고 서베이 로컬로 복사
- [ ] `survey.json`의 도메인별 정보(제목·파트·챕터) 채우기 (스캐폴드는 placeholder 삽입)

## 키 네이밍 규약

`{firstauthorlastname}{year}{keyword}` (소문자). 예: `zhang2025soft`, `almeida2025roleoftouch`. 자세한 규약과 충돌 해결은 `bibtex/README.md` 참조.

---

# 공유 코드 수정 규칙

`shared/` 내 파일을 수정하면 **모든 서베이에 영향**. 수정 후 반드시:
```bash
python3 build.py --all
```

---

# 하네스 에이전트 참조

| 에이전트 | 역할 |
|---------|------|
| deep-researcher | 논문 심층 서베이, 연구 그룹 매핑 |
| critical-analyst | gap 분석, novelty 평가, 차별화 전략 |
| book-writer | 양국어 챕터 집필 |
| image-curator | 논문 figure 선별·배치 (AI 보조 ≤ 2/챕터) |
| fact-checker | 수치/인용 교차 검증 |
| qa-reviewer | 전체 품질 리뷰 |
| researcher | 문헌 1차 조사 |
| reference-checker | 레퍼런스 포맷 정확성 검증 |
