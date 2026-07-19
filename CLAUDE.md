# CLAUDE.md

## 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Mention unrelated dead code; don't delete it.
- Remove imports/variables your changes orphaned.

The test: every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → ensure tests pass before and after.

For multi-step tasks, state a brief plan with verifiable checks per step.

---

## terry-surveys — Bilingual Survey Framework

Public skill/build framework for bilingual (KO/EN) research-survey books.
Canonical content lives in the private sibling `terry-surveys-contents` repo.

### Structure
```
terry-surveys/
├── build.py                  # CLI entry point
├── shared/                   # build_site.py, scaffold.py, css, js
├── bibtex/                   # tools; master data links to private contents
├── glossary/                 # docs; master data links to private contents
├── surveys -> ../terry-surveys-contents/surveys
└── docs/SCHEMAS.md           # canonical schemas, citations, figures, KaTeX, BibTeX, glossary
```

Run `bash scripts/setup-contents.sh --check` before content work. New surveys
must be created under the linked `surveys/` directory and committed to
`terry-surveys-contents`, never to this public framework repository.
Binary assets remain local and are synchronized to private R2 with
`scripts/sync-content-assets.sh`; generated `docs/` output is never committed.

### Build commands
```
python3 build.py <name>                          # single-survey build
python3 build.py --all | --new <name>            # all / scaffold
python3 build.py --validate [<name>|--all]       # schema/citation/figure/subset
python3 build.py --index                         # rebuild bibtex/refs_index.json
python3 build.py --sync-bibtex <name>            # subset master bib → local
python3 build.py --sync-glossary <name>          # subset master glossary → local
python3 build.py --staleness [<name>|--all]      # age × new-paper score
python3 build.py --refresh-refs <name|--all>     # refresh _refs_extracted.json mechanically
python3 build.py --backfill-research <name|--all> # skeleton _research/papers.json
```

### Canonical survey v2 harness
`survey_harness/` owns the runtime-neutral task DAG, quality profiles, score history, remediation attempts, resume state, and release evidence. Claude and Codex are dispatch adapters: one orchestrator runs at most three workers, using KG mapper → source strategy → foundations/frontier research → evidence synthesis → paired KO/EN chapter writing → streamed image/factcheck → independent QA. Role contracts live in `.codex/skills/survey/references/role-contracts-v2.md`; mutable thresholds live only in `survey_harness/config/quality_profiles.yaml`.

### `/survey` is the entry point
Don't run `build.py --new` directly. Use:
- `/survey "<title>"` (inside this repo) — full research-to-release run by default
- `/survey --orchestrate <slug>` — resume/write/factcheck/QA with v2 state
- `/survey --sync-agents | --refresh | --factcheck | --link-posts | --deploy <slug>` — sub-commands
- `/survey <cf-url>` — register on homepage `surveys.json`

### Reference data flow
`book/<lang>/chNN.md` (inline cites) → `bibtex/references.bib` (master) → `_research/papers.json` (deep-researcher meta) → `_refs_extracted.json` (factcheck status) → `bibtex/refs_index.json` (cross-survey dedup) → `terry-papers/scripts/sync-survey-candidates.mjs` (candidate pool).

### Schemas + standards → `docs/SCHEMAS.md`
Chapter frontmatter, citation rules (incl. ⚠ figure-alt-text bracket exception), KaTeX, figure tier-quotas, `_refs_extracted.json` schema, `_factcheck_report.md` shape, `survey.json` fields, glossary + BibTeX management — all in `docs/SCHEMAS.md`. Read it before editing chapters or schemas.

### Shared code rule
Editing anything in `shared/` affects every survey. With the private contents
repo linked, run `python3 build.py --all` and confirm every survey still builds.

### Deploy: Cloudflare Pages direct upload (no Git provider)
```
cd surveys/<name>
bash scripts/push.sh "commit msg"
```
Pages project name = survey dir name. `docs/_redirects` survives builds. 25 MiB file limit — keep large source PDFs in `_revise-source/` (gitignored, push.sh excludes).

### Concurrency / boundaries
Other workspaces (`terryum-ai`, `terry-obsidian`, `terry-papers`) may integrate
with this framework and the private contents repo. Pull both siblings before a
survey run. Don't touch Supabase schema, RLS, or ACL/auth from here — those
changes happen in `terryum-ai`.
