# Survey schemas & standards

Reference doc for surveys in `terry-surveys`. The root `CLAUDE.md` only points here; this file is the canonical source for chapter formats, citations, figures, refs, glossary, and BibTeX.

## Chapter frontmatter

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

## Citations

### Inline patterns (4)
1. **Standard inline**: `[Author et al., Year]` — **brackets required** (build-script regex). Build replaces with `<sup><a class="cite-link" href="#chN-ref-M">[M]</a></sup>`.
2. **Inline as subject**: `Author et al. [Year]은…` (e.g., `Albini et al. [2025]은…`). Same linkifier output.
3. **Cross-reference**: EN `(Chapter N)`, KO natural (`N장`, `N.M절`, "2장에서는…"). Multi-chapter: `(Chapter 2, Chapter 3)`. With name: `TacGlove (Chapter 7)`. **No arrows or abbreviations** (`→Ch.2`, `(Ch3)`, `→2장` forbidden). Validator passes both EN and KO forms.
4. **`et al.` rule**: 3+ authors → first author + `et al.`. 1–2 authors: list all.

### ⚠ Figure alt-text exception — NO brackets
Inside a figure caption (`![caption](url)`), do **not** use `[Author, Year]` brackets. The `build_site.py` citation linkifier injects `<sup><a>[N]</a></sup>` HTML into the alt attribute, which closes the alt `"` early and leaks `loading="lazy"`, `onerror=`, `style=` into the figcaption (2026-04 humanoid-revolution incident). Use plain `Author et al. Year` for figure sources. `build.py --validate` rejects bracketed alt text automatically.

### Reference patterns (4)
1. **Chapter-bottom heading**: `## 참고문헌` (KO) / `## References` (EN), required at end of every chapter.
2. **List format**: numbered list, `1. Author (Year). [Title](url). *Venue*.` — **markdown link mandatory** on every entry (P7 in `/survey` SKILL.md). `build_site.py:build_references_list_html` converts `[text](url)` → `<a target="_blank" rel="noopener">`; entries without a link render as un-clickable plain text. Validator rejects unlinked entries.
3. **Auto-anchored**: build emits `<li id="chN-ref-M">` per entry — inline cite `<sup><a href="#chN-ref-M">[M]</a></sup>` resolves here.
4. **Global references page** (separate from chapter refs): `book/references.bib` → `docs/{lang}/references.html` standalone page. Chapter inline cites do **not** link here; they link to the chapter-bottom list anchor.

### Click behavior (build_site.py-injected)
Inline cite click → smooth scroll to `#chN-ref-M` → 3-second highlight → `↩` backlink button at the end of the entry returns to the original cite location.

### Validator gates (`build.py --validate`)
- Rejects bracketed citation in figure alt text (regression guard for 2026-04 incident).
- Rejects arrow/abbrev cross-refs (`→Ch.N`, `→N장`, `(ChN)`).
- Enforces ≥50% bibtex_key coverage and ≥30% arxiv/doi coverage in `_refs_extracted.json`.
- Warns when `_research/papers.json` is missing or 100% `provenance: bibtex_backfill` (deep-researcher needed).
- **Rejects reference list entries without a markdown `[text](url)` link** (P7 — guards against 2026-05-05 claude-to-codex incident where 12 chapters shipped with text-only refs).

## Sidebar TOC (chapter pages)

`## 섹션` headings → `<nav class="sidebar-nav">` with dot navigation. Scroll-spy via `IntersectionObserver` highlights the current section as the reader scrolls.

## Bilingual system (KO/EN)

- **Separate directory model**: `book/ko/` and `book/en/` are completely independent markdown files (no in-file lang switch). Builds emit `docs/ko/` and `docs/en/` as separate static sites.
- **Root dispatcher**: `docs/index.html` redirects via `navigator.language` + `localStorage` (sticky preference).
- **Fonts**: KO = Noto Sans KR; EN = Inter + Noto Sans KR fallback. CSS toggles via `body.lang-ko` / `body.lang-en`.
- **Build pass**: `build_site.py` runs ko and en passes; UI strings are language-conditional (if-branches in the template).
- **Per-page lang switch**: not provided in chapter pages; only the root flag-card switcher.

## Figures

### Naming + paths
- **Survey-local**: `assets/figures/chNN_<sourceSlug>_fig<N>.<ext>` (flat, no subfolders). Path in chapter: `../../assets/figures/<filename>`.
- **Shared registry** (monorepo `assets/figures/`): `<sourceSlug>_fig<N>.<ext>` (chapter prefix removed). Path: `../../../../assets/figures/<filename>`.
- A figure cited by ≥2 surveys is promoted to the shared registry + recorded in `assets/registry.json`. `build_site.py` overlays shared on top of survey-local; same filename → shared wins.

### Source policy (3-way)
- (a) Paper original figure crop
- (b) Official platform / product photo (press kit, GitHub README, hardware arXiv) — fair use for academic review
- (c) Gemini-generated concept art

### Tier quota (≥3 per chapter)
| Chapter type | Quota | Source mix |
|---|---|---|
| Theory / Overview / Primer | 3–5 | Gemini-leaning |
| Method / Algorithm survey | 3–6 | Paper figure–leaning |
| Platform / Company / Hardware | 4–8 | **≥2 real product photos required** |
| History / Ecosystem | 3–5 | Mixed |

The previous "≤2 Gemini per chapter" hard cap is **retired** (caused theory-chapter figure starvation in 2026-04 humanoid-revolution incident). Generate as many as the tier quota allows; for platform/company chapters, secure ≥2 real photos before any Gemini.

### Captions
- Paper: `출처: Author et al. Year, Fig. N` (KO) / `Source: Author et al. Year, Fig. N` (EN). No brackets.
- Platform photo: `source: <company> press kit / <URL>, fair use for academic review`
- Gemini: `illustration by author (Gemini assisted)`

### Manifest
`_workspace/04_image_manifest.json` — `source_type` (paper_figure / platform_photo / gemini) + `license_basis` required. Platform photos add `source_url`, `fetch_date`, `sha256`. Gemini adds `source_prompt`.

### Image markdown tag
```markdown
![Figure N.M: caption](../../assets/figures/chNN_<slug>_figN.png)
```
Must be on its own line with blank lines before/after. `build_site.py` converts to a `<figure>` block.

## References (BibTeX)

- **Master-first**: new citations go to `bibtex/references.bib` first, then copied to `surveys/<slug>/book/references.bib`. The build only reads survey-local.
- **Key naming**: `{firstauthorlastname}{year}{keyword}` (lowercase). Examples: `zhao2025ftac`, `zhang2025soft`, `almeida2025roleoftouch`. Conflict resolution: see `bibtex/README.md`.
- **Reuse first**: `grep -i "<title-keyword>\|<arxiv-id>" bibtex/references.bib` before writing a new entry.
- **Sister-survey consistency**: if another survey uses a key for the same paper, reuse it.
- **After `build.py --new <name>`**: grep master before any citation; populate `survey.json` placeholders.

## `_refs_extracted.json`

```json
{
  "chapter": 3,
  "num": 12,
  "lang": "ko",
  "text": "Author et al., Year, ...",
  "bibtex_key": "...",
  "arxiv_id": "2412.14482",
  "doi": null,
  "nature_id": null,
  "scholar_url": "https://scholar.google.com/...",
  "scholar_status": "ok",
  "verification_status": "verified",
  "factcheck_notes": "...",
  "primary_verified": true
}
```

`build.py --refresh-refs` keeps mechanical fields fresh (`ch/num/lang/text/bibtex_key/arxiv_id/doi/nature_id`) without touching `verification_status`/`factcheck_notes`/`scholar_url` (idempotent). `--validate` enforces ≥50% bibtex_key coverage and ≥30% arxiv/doi coverage.

## `_factcheck_report.md`

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

## Reference metadata data flow

```
chNN.md (inline cites + ## 참고문헌)
   │
   └─[1] book-writer writes inline + ref-line
   ▼
bibtex/references.bib  (master)
   │
   └─[2] deep-researcher enriches _research/papers.json (method_summary, limitations, tags, chapter_hint, group)
   ▼
_research/papers.json  (canonical meta — required)
   │
   └─[3] fact-checker fills verification_status, factcheck_notes, scholar_url
   ▼
_refs_extracted.json  (Tier-1 ID matching source)
   │
   └─[4] build.py --index → bibtex/refs_index.json (cross-survey dedup)
   ▼
bibtex/refs_index.json
   │
   └─[5] terry-papers/scripts/sync-survey-candidates.mjs → candidate pool
```

| Field | Source | Filled by |
|---|---|---|
| bibtex_key, arxiv_id, doi, nature_id, venue, url, authors | master bib match | Mechanical (`build.py --refresh-refs`) |
| chapter_hint | ref-line position | Mechanical |
| method_summary, experiments, quantitative_results, limitations, group, tags | paper PDF read | deep-researcher |
| verification_status, factcheck_notes, primary_verified | source comparison | fact-checker |
| scholar_url, scholar_status | URL check | fact-checker |

`provenance: "bibtex_backfill"` entries in `_research/papers.json` are skeleton-only — deep-researcher must enrich and update provenance to `"deep_researcher"`.

## Math (KaTeX)
- Inline: `$...$` → `<span class="math-inline">`
- Block: `$$...$$` (one-line, complete) → `<div class="math-block">`
- `$` followed by a digit is treated as a price (skipped).
- Use `katex.render()` explicitly. Don't use `auto-render.min.js`.

## Chapter page navigation
`<nav class="chapter-nav">` at chapter HTML bottom shows **prev · index · next** only (placeholders for first/last). No glossary/refs/appendix links in chapter nav — those enter via the TOC index "Appendix" cards. `shared/build_site.py::build_chapter_html` is the single source of truth.

## `survey.json`

- `id`, `github_repo`: identifiers
- `title`, `short_title`, `subtitle`, `description`: bilingual
- **`cover_image`**: hero banner. Usually `"../assets/cover.jpg"`. File at `surveys/<slug>/assets/cover.{jpg,png,webp,svg}` (flat root, not under `figures/`). 16:9 recommended. Reuse `terryum-ai/public/images/projects/survey-<slug>-og.jpg` if it exists. `build_site.py` copies to `docs/assets/cover.*` and places above `<h1>`.
- `parts[].chapters[]`: structure (number, title, summary, per-chapter `last_updated`)
- `highlights`: TOC highlight cards
- `acknowledgment`
- `features`: defaults
  - `glossary: true` (default on, eases reader entry)
  - `pdf: false` (no canonical PDF skill yet)
  - `paper: false` (IEEE paper is a separate workflow)
- `dates.first_published`, `dates.last_updated`

### `description` length

KO 40–90 chars, EN 80–140 chars. One-line hook + `"— N Parts, M Chapters"`. Don't list chapters or companies in description (Chapter Grid already does that). 2026-04 humanoid-revolution incident: description ballooned to 243 KO / 444 EN chars.

✅ `"에이전틱 루프가 물리 세계에서 작동하려면 무엇이 달라져야 하는가. — 4 Parts, 10 Chapters"`
❌ `"2015-2026 휴머노이드 로보틱스의 대격변 ... 정통파 스택 ... 네 기폭제 ..."`

### `last_updated` policy (mandatory for agents)

Two places must stay in sync:
1. `book/{ko,en}/chNN.md` frontmatter — when chapter body changes
2. `surveys/<name>/survey.json` → `parts[].chapters[].last_updated` — same date

`book-writer` and `fact-checker` must update both immediately after editing a chapter. `build.py --staleness` ranks chapters by `(age × new-paper-count)`.

## Glossary management

`glossary/master_ko.md` / `master_en.md` are the master. Each survey's `book/<lang>/glossary.md` is a subset.

Workflow:
1. **grep master**: `grep -i "^- \*\*<term>" glossary/master_ko.md`
2. **Reuse if present**: copy the master line to survey's `book/<lang>/glossary.md`, append `(Ch N)` chapter ref.
3. **Add to master if absent**: add canonical definition to both `master_ko.md` and `master_en.md`, then copy to survey.
4. **Sister-survey consistency**: if another survey already uses the term, reuse the master definition.

Details: `glossary/README.md`.

## Mechanical refresh + agent enrichment

**Mechanical (forced for every survey):**
- `build.py --refresh-refs <slug>`: refresh `_refs_extracted.json` mechanical fields from chapter md + master bib. Idempotent.
- `build.py --backfill-research <slug>`: skeleton `_research/papers.json` if missing. Tags entries with `provenance: "bibtex_backfill"`.

**Agent (via `/survey --orchestrate`):**
- deep-researcher enriches `bibtex_backfill` entries (fills `method_summary`, etc.; updates provenance).
- fact-checker fills `verification_status`/`factcheck_notes`/`scholar_url`.

**Validation** (`build.py --validate <slug>`):
- `_research/papers.json` exists (warn + command hint if missing)
- `method_summary` coverage (100% bibtex_backfill → deep-researcher needed)
- `_refs_extracted.json` bibtex_key coverage ≥50%
- `_refs_extracted.json` arxiv/doi coverage ≥30%

## Paper-input pipeline (homepage → survey update)

When `terryum-ai` adds a new paper post:
1. **Index**: `python3 build.py --index`
2. **Impact**: `python3 build.py --impact <post-slug>`
   - **Tier 1 (exact ID match)**: surveys/chapters citing that paper → auto-insert `[#NN]` post link via DOI↔arXiv bridging in master bib.
   - **Tier 2 (keyword match)**: word-overlap top-K. **Don't** auto-insert — surface as refresh candidates for user approval.
3. **Staleness**: `build.py --staleness --all` → top chapters get book-writer/fact-checker.
4. **Tier-1 auto-link**: `/link-post-to-surveys <slug>` inserts `[#NN](post-url)` into ref lines + rebuild + deploy.
5. **`last_updated`**: chapter md frontmatter + `survey.json` both bumped.
