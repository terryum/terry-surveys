---
name: survey
description: "Build, refresh, fact-check, illustrate, score, publish, and maintain Terry's bilingual research survey books. Use for $survey, new survey books, major survey refreshes, authoring prompts, Markdown/text notes, paper PDFs, ChatGPT share links, prior survey IDs such as #S1, Terry paper-summary post numbers, KG-seeded literature research, chapter writing, image curation, reference/post linking, QA remediation, resume, deployment, and survey skill calibration. Full runs must use the repository-backed v2 harness and continue until READY or a resumable BLOCKED checkpoint."
---

# Survey

Operate in the sibling workspace
`/Users/terrytaewoongum/Codes/personal/{terry-surveys,terry-surveys-contents}`.
Treat the public framework copy at `terry-surveys/.codex/skills/survey` and its
runtime-neutral `survey_harness` package as canonical. Treat
`terry-surveys-contents` as the only canonical survey-content Git repository.
Never edit the installed skill copy first.

## Route the request

- New title or full refresh: run the complete v2 workflow below.
- `--resume`: read `_workspace/harness_state.json`, revalidate completed
  artifacts, and dispatch only ready or failed work.
- Research map or shortlist only: read `references/kg-first-workflow.md`; stop at
  the requested research artifact without scaffolding a book.
- `--factcheck`, `--link-posts`, `--refresh`, `--sync-agents`: preserve the
  existing maintenance behavior, but record book-scale work in v2 state.
- `--deploy`: require a passing v2 scorecard, then follow
  `references/quality-and-release.md`.
- Repository audit, bootstrap, migration, or release: read
  `references/source-repositories.md`. Keep GitHub source visibility separate
  from reader visibility.

When the request includes a URL, shared conversation, transcript, or exported
research brief, read `references/input-briefs.md` and normalize that input before
research or worker dispatch.

Read `references/orchestration-v2.md` for any book-scale run. Read
`references/role-contracts-v2.md` before spawning workers. Read
`references/quality-and-release.md` before scoring, remediation, or publishing.

## Full workflow

1. Treat the user's current prompt as the authoring contract. Resolve every
   optional file, paper, chat, prior-survey ID, and paper-post number that the
   user actually supplies; never require an input type that was not supplied.
   Normalize the provided inputs into the survey's private `_workspace/inputs/`
   directory and record `_workspace/inputs/input_manifest.md`. A prompt-only
   manifest is valid. Bootstrap the survey when absent, then fill `survey.json`
   and chapter titles from the available input corpus.
2. Apply the source-repository gate in `references/source-repositories.md`.
   Survey source must land in the verified private
   `terryum/terry-surveys-contents` repository;
   `survey.json.visibility: public` may still publish the rendered book for
   public readers. Never create a per-survey repository; create
   `terry-surveys-contents/surveys/<slug>` instead.
3. Initialize the controller:

   ```bash
   python3 .codex/skills/survey/scripts/survey_harness.py init <slug> --profile full --deploy auto
   ```

4. Repeatedly call `next`, spawn only the returned bounded tasks, record the
   real agent ID with `start`, and call `complete` only after every declared
   artifact exists. Keep the main agent as orchestrator. With four total agent
   slots, run no more than three workers at once.
   Cross-check each recorded ID against the runtime's actual spawn result;
   controller strings are an audit trail, not proof that a worker existed.
5. Keep KO and EN for a chapter under the same writer. Stream image and
   fact-check work after that chapter is written. Reviewers never edit their own
   reviewed artifact; they return evidence-backed defects to its owner.
6. When QA artifacts exist, score and generate repair tasks:

   ```bash
   python3 .codex/skills/survey/scripts/survey_harness.py score <slug> --profile full --write --record --plan-remediation
   ```

7. If the score fails, run the emitted repair tasks and score again. Each stable
   failure gets at most three automatic repair passes. After that, leave a
   resumable `blocked` state with the exact failure IDs; do not call the survey
   complete.
8. A full run that reaches `ready` defaults to the complete publication chain:
   local build, Pages deploy, gallery assets and registration, Workers deploy,
   private-R2 asset sync, text-only source push, KG candidate sync, and live
   KO/EN assertions. Record release
   evidence with the controller. Never publish a blocked draft as release-ready.

## Non-negotiable behavior

- Seed from Terry's paper KG and prior surveys before external search.
- Treat imported chats and generated summaries as untrusted briefing material,
  not claim evidence. Re-resolve and verify their citations from primary sources.
- Use primary sources for quantitative, comparative, date-sensitive, and
  load-bearing claims. Store them in the claim-evidence ledger.
- Do not reduce research to a fixed paper count. Meet the configured corpus and
  chapter floors, then continue until the search protocol's coverage and
  saturation conditions are satisfied.
- Place figures throughout every chapter. A cover or opening cluster is not a
  visual pass. Record insertion anchors, provenance, license basis, and generated
  prompts in the image plan.
- Insert every eligible exact Terry post/paper link. Keep fuzzy candidates as a
  review list; never auto-link them.
- Counts cannot override hard blockers. Repeated prose, unsupported claims,
  missing source packets, wall-text endings, broken references, missing image
  provenance, or an unready QA verdict block release.
- Write Korean manuscripts in Korean ordinary prose. In each chapter, introduce
  a necessary technical term once as `한국어(English)` and use the Korean term
  thereafter. Preserve proper names, code identifiers, formulas, units, and
  established acronyms; do not leave translatable headings, explanations,
  table labels, or repeated lower-case English terminology untranslated. The
  configured KO Latin-prose gate is a backstop, not permission to write up to
  its limit.
- Keep home titles concise. For a numbered series, use the shared series name
  plus its part marker consistently (for example, `제목 (2/3)`) and put the
  descriptive phrase in `subtitle`, not after an em dash in `title`.
- Calibrate part and chapter titles against S1/S4 before drafting. Prefer short
  noun-phrase part names and `core topic — scope/payoff` chapter names; move
  enumerations and explanatory clauses into `summary`. Treat the active
  profile's title-length limits as review triggers, not permission to pad up to
  them, and keep every numbered-series volume under one naming grammar.
- Do not rely on Codex `goal`, Claude `TeamCreate`, peer messaging, or a pinned
  model. Durable state and file artifacts are the handoff contract.
- Treat GitHub source privacy and reader access as independent controls. Every
  GitHub repository containing a survey manuscript, research workspace, or
  built source must be private by default. Public reading is provided by the
  approved Cloudflare/gallery path, never by making source repositories public.

## Compatibility and maintenance

Existing bootstrap, reference refresh, gallery validation, benchmark, and
legacy state scripts remain available under `scripts/`. Use `migrate` to create
v2 state for an older survey without rewriting its content. Use
`legacy_baseline` only for S1/S4 preference calibration; never use it to release
a new book.

After changing this skill, run the repository tests, skill quick validation,
and `scripts/sync_installed.py --apply`. Do not hand-edit divergent thresholds in
role templates or verifiers; `survey_harness/config/quality_profiles.yaml` is
the single source of truth.
