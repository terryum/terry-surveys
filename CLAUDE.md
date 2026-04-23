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
python3 build.py <survey-name>             # 단일 서베이 빌드
python3 build.py --all                     # 전체 빌드
python3 build.py --new <name>              # 새 서베이 스캐폴딩
python3 build.py --list                    # 서베이 목록
python3 build.py --index                   # BibTeX refs_index.json 재생성
python3 build.py --validate [name|--all]   # 스키마·인용·figure·subset 검증
python3 build.py --sync-bibtex <name>      # 마스터 기준으로 로컬 .bib 재생성
python3 build.py --sync-glossary <name>    # 마스터 기준으로 로컬 glossary 재생성
python3 build.py --staleness [name|--all]  # 챕터별 오래된 순위 리포트
```

**마스터 한 번 고치면 모든 서베이가 맞춰지는 흐름:**
1. `bibtex/references.bib` 또는 `glossary/master_{ko,en}.md` 마스터 수정
2. `python3 build.py --sync-bibtex <each-survey>` / `--sync-glossary <each-survey>` 실행
3. `python3 build.py --validate --all` 통과 확인 → `--all` 빌드 후 배포

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

- **네이밍 (서베이 로컬)**: `chNN_<sourceSlug>_fig<N>.<ext>` (flat 폴더). 예: `ch03_gelsight_fig1.png`.
- **경로 (서베이 로컬)**: 챕터 안에서 `../../assets/figures/파일명`.
- **네이밍 (공유 레지스트리)**: `<sourceSlug>_fig<N>.<ext>` (chapter 접두사 제거). 예: `gelsight_fig1.png`.
- **경로 (공유 레지스트리)**: 챕터 안에서 `../../../../assets/figures/파일명` — 모노레포 루트 `assets/figures/`에 존재.
- **정책**: **논문 원본 figure 우선**. image-curator가 원본 PDF·arXiv에서 크롭하여 출처 caption 명기.
- **공유 승격 규칙**: 2개 이상 서베이가 같은 논문 figure를 인용하면 즉시 루트 `assets/figures/`로 승격(chapter 접두사 제거) + `assets/registry.json`에 등록. 1개 서베이만 쓰는 figure는 서베이 로컬 유지.
- **빌드**: `shared/build_site.py`가 서베이 로컬을 먼저 `docs/assets/figures/`로 복사한 뒤 루트 공유 figure를 오버레이한다. 같은 파일명 충돌 시 루트가 우선(공유 canonical). 챕터 md의 경로는 자동 재매핑된다.
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
- `parts[].chapters[]`: 챕터 구조 (번호, 제목, 요약, `last_updated` per chapter)
- `highlights`: TOC 하이라이트 카드
- `acknowledgment`: 감사의 글
- `features`: 기능 플래그 — **기본값**
  - `glossary: true` (기본 on, 독자 진입장벽 완화)
  - `pdf: false` (전용 PDF 빌드 스킬 부재 시 off)
  - `paper: false` (IEEE paper 별도 워크플로우로 관리)
- `dates.first_published`, `dates.last_updated` (서베이 전체)

### 챕터 `last_updated` 업데이트 정책 (에이전트 필수)

각 챕터의 `last_updated`는 두 군데에 유지한다:
1. `book/{ko,en}/chNN.md` frontmatter — 챕터 본문 수정 시
2. `surveys/<name>/survey.json` → `parts[].chapters[].last_updated` — 같은 날짜

**에이전트 책임**: `book-writer`와 `fact-checker`가 챕터를 수정한 직후 반드시 두 군데 모두 오늘 날짜로 갱신해야 한다. `build.py --staleness`가 이 필드를 기준으로 "가장 오래된 챕터 × 그 이후 추가된 신규 논문 수" 리포트를 생성한다.

## 5. 배포

Cloudflare Pages **direct upload** (wrangler). 외부 GitHub repo 없이 monorepo에서 바로 업로드:

```bash
cd surveys/<name>
bash scripts/push.sh "커밋 메시지"
```

`scripts/push.sh`는 `docs/`를 임시 디렉토리에 rsync(`revise-source/` 제외) → `npx wrangler pages deploy`로 직접 업로드. Cloudflare Pages 프로젝트는 `Git Provider: No`로 설정된 상태(외부 repo 감시 X).

- 프로젝트명은 survey 디렉토리명과 동일 (예: `survey-robot-hand-tactile-sensor`).
- 리다이렉트: `docs/_redirects`에 정의 (빌드 스크립트가 덮어쓰지 않음).
- `.wrangler/`는 로컬 캐시 — `.gitignore` 등록 필수.
- **Pages 파일 크기 한도 25 MiB**. 대용량 PDF/영상 등 source material은 `docs/` 밖 `_revise-source/`에 두고 gitignore + push.sh에서 제외.

## 6. 하네스 부트스트랩 — `/survey`가 정규 진입점

새 서베이를 시작할 때는 **`python3 build.py --new <name>`을 직접 부르지 말고 `/survey "<책 제목>"`을 호출한다**. `/survey`는 scaffold + per-survey `.claude/agents/` 템플릿 복사 + placeholder 치환 + 인덱스 등록을 한 번에 수행한다.

### 2-모드 + 6-서브커맨드

| 호출 | 모드 | 동작 |
|---|---|---|
| `/survey "<제목>"` (terry-surveys 내부) | MODE A | 새 책 부트스트랩 |
| `/survey <cloudflare-url>` | MODE B | 홈페이지 Surveys 갤러리 등록 + `/cite-post` 자동 호출 |
| **`/survey --orchestrate <slug>`** | **서브 (기본 집필)** | **멀티에이전트 팀(6종) 자율 병렬 집필** — `TeamCreate` + `SendMessage` + `TaskCreate`. 순차 Phase 아님 |
| `/survey --sync-agents <slug>` | 서브 | 템플릿 → per-survey `.claude/agents/` 동기화 (placeholder 보존) |
| `/survey --refresh <slug>` | 서브 | `build.py --staleness` 기반 리프레시 우선순위 |
| `/survey --factcheck <slug>` | 서브 | fact-checker 에이전트 일괄 호출 |
| `/survey --link-posts <slug>` | 서브 | `/link-post-to-surveys` 프록시 (Tier 1) |
| `/survey --deploy <slug>` | 서브 | 빌드 + Cloudflare 배포 + MODE B 자동 진입 |

### 집필은 오케스트레이션이 기본

**`/survey --orchestrate <slug>`가 집필의 정규 진입점**이다. 이 스킬이 리더 역할을 하며 `surveys/<slug>/.claude/agents/*.md`에 정의된 6개 에이전트(deep-researcher · critical-analyst · book-writer · image-curator · fact-checker · qa-reviewer)를 `TeamCreate`로 기동하고, 의존성 그래프로 병렬·스트리밍·자체 조율을 수행한다. 단독 에이전트를 순차 호출하는 방식은 **오케스트레이션이 실패할 때의 예외 경로**로만 사용한다. `--phase=research|write|polish`로 단계별 제한 가능. 세부는 `.claude/skills/survey/references/orchestration-playbook.md` 참조.

### Repo Ownership 원칙

- **원본은 주된 작업이 일어나는 repo에 둔다.** `/survey` 원본은 terry-surveys (`.claude/skills/survey/`), terryum-ai 측은 심링크로 허브 성질 유지.
- 다른 심링크 스킬(`/post`, `/project`, `/share`, `/paper-search`, `/defuddle`)은 현재 구조 유지 (terryum-ai 원본).

### Canonical Agent 템플릿

- 위치: `.claude/skills/survey/references/agent-template/`
- 6종: `deep-researcher.md`, `critical-analyst.md`, `book-writer.md`, `image-curator.md`, `fact-checker.md`, `qa-reviewer.md`
- Placeholder: `{{SURVEY_SLUG}}`, `{{DOMAIN}}`, `{{CHAPTERS}}`, `{{TERMS}}`, `{{SURVEY_DIR}}` — `/survey` 부트스트랩 시 per-survey 값으로 치환되고 공통 섹션은 sync로 전파.
- 템플릿 수정은 한 곳(`agent-template/`)에서만. 새 책은 자동으로 최신을 복사, 기존 책은 `--sync-agents`로 선택적 전파.

### 상세 문서 포인터

- 부트스트랩 세부: `.claude/skills/survey/references/bootstrap-playbook.md`
- 등록 세부: `.claude/skills/survey/references/registration-playbook.md`
- 전 생애주기 통합 가이드: `.claude/skills/survey/references/unified-survey-guide.md`

---

# Paper 입수 파이프라인 — 홈페이지 → 서베이 업데이트

`terryum-ai`에 새 논문 포스트가 추가되면 다음 흐름으로 서베이에 반영한다:

1. **인덱스 갱신**: `python3 build.py --index` (서베이 refs 역인덱스 재생성)
2. **Impact 분석**: `python3 build.py --impact <post-slug>`
   - **Tier 1 (exact ID match)**: 이미 해당 논문을 citing 중인 서베이/챕터 리스트 → `[#NN]` 포스트 링크 자동 삽입 대상. 마스터 bibtex를 경유해 DOI↔arXiv cross-reference가 양방향 bridge된다.
   - **Tier 2 (keyword match)**: 포스트 tags/subfields/key_concepts와 챕터 summary·title의 word overlap 점수 top-K. 자동 삽입 금지 — "리프레시 후보"로 사용자 승인 받은 뒤에만 챕터 편집.
3. **Staleness 우선순위화**: `python3 build.py --staleness --all`가 챕터별 `(age × new-paper-count)` 스코어를 내준다. 상위 챕터부터 book-writer / fact-checker 호출.
4. **Tier 1 자동 링크**: `/link-post-to-surveys <slug>` 스킬이 `--impact` Tier 1 결과만 추려서 각 위치의 ref 라인에 `[#NN](post-url)` 삽입 + 재빌드 + 배포.
5. **챕터 last_updated 갱신**: 챕터 md frontmatter + `survey.json` 양쪽을 오늘 날짜로 업데이트 (에이전트 필수 책임).

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
