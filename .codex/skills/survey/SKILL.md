---
name: survey
description: "Build, refresh, fact-check, illustrate, score, publish, and maintain Terry's bilingual research survey books. Use for $survey, new survey books, major survey refreshes, authoring prompts, Markdown/text notes, paper PDFs, ChatGPT share links, prior survey IDs such as #S1, Terry paper-summary post numbers, KG-seeded literature research, chapter writing, image curation, reference/post linking, QA remediation, resume, deployment, and survey skill calibration. A full run uses the v2 harness and finishes when the book is live as an admin-only survey on terryum.ai, or reaches a resumable blocked checkpoint. Public promotion requires explicit authorization."
---

# Survey

The workspace is `~/Codes/terry/terryum-ai`. The canonical skill and harness
live in `surveys/framework`. The private manuscript repository is
`surveys/contents`. Start sessions that dispatch native workers in
`surveys/framework`. The installed runner also works from the parent workspace.
Pass `--repo-root` before the command to select another checkout.

## Route the request

- New title or full refresh: run the complete v2 workflow through private
  terryum.ai deployment. An explicitly requested local or draft run ends at
  its requested checkpoint.
- `--resume`: read `_workspace/harness_state.json`, revalidate completed
  artifacts, and dispatch only ready or failed work.
- Research map or shortlist only: read `references/kg-first-workflow.md`; stop at
  the requested research artifact without scaffolding a book.
- `--factcheck`, `--link-posts`, `--refresh`, `--sync-agents`: preserve the
  existing maintenance behavior, but record book-scale work in v2 state.
- `--deploy` or “deploy as a private survey”: keep the book in Surveys and
  deliver the protected admin-only KO/EN edition. Require a current recorded
  full score, then follow
  `references/quality-and-release.md`.
- `--publish <slug>`: promote the exact approved preview digest to public
  production. Never infer this authorization from create, refresh, or deploy.
- Repository audit, bootstrap, migration, or release: read
  `references/source-repositories.md`. Keep GitHub source visibility separate
  from reader visibility.

When the request includes a URL, shared conversation, transcript, or exported
research brief, read `references/input-briefs.md` and normalize that input before
research or worker dispatch.

Read `references/orchestration-v2.md` for any book-scale run. Read
`references/role-contracts-v2.md` before spawning workers. Read
`references/quality-and-release.md` before scoring, remediation, or publishing.
For deployment runs, follow `references/private-deployment-preflight.md` before
dispatch and again before Cloudflare writes.

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
   `surveys/contents/surveys/<slug>` through the framework's `surveys/` link.
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
   Assign distinct real worker identities to each release role from the first
   task. Reuse a worker ID within its role only. Free and reassign worker slots
   across waves as needed.
5. Read `references/editorial-contract.md`. After research, run critical
   analysis before the librarian produces source packets. Include the resulting
   comparisons, counterevidence, judgments, and book-specific editorial contract
   in every writer's packet. Before drafting, compare rendered KO/EN indexes
   and representative chapter pages from S1 and S4. Independently review the
   representative chapter's prose and rendered section navigation before
   dispatching the remaining chapters. Later writers read the accepted review
   and apply its passage-backed principles.
6. Keep KO and EN for a chapter under the same writer. Stream image and
   fact-check work after that chapter is written. Reviewers never edit their own
   reviewed artifact; they return evidence-backed defects to its owner. Each
   chapter reviewer owns `_quality/chapters/chNN.json`; final `qa-book` owns the
   book report and aggregate scores. Final QA runs the deployment build command
   locally and records its rendered KO/EN index comparison in
   `_quality/build_validation.json`.
7. When QA artifacts exist, score and generate repair tasks:

   ```bash
   python3 .codex/skills/survey/scripts/survey_harness.py score <slug> --profile full --write --record --plan-remediation
   ```

8. If the score fails, run the emitted repair tasks and score again. Each stable
   failure gets at most three automatic repair passes. After that, leave a
   resumable `blocked` state with the exact failure IDs; do not call the survey
   complete.
9. Continue from `ready` through the protected private-deployment chain in
   `references/quality-and-release.md`. Completion requires live KO/EN survey
   detail routes on terryum.ai, working admin book iframes, denial for anonymous
   visitors and ordinary members, and a recorded preview receipt. Preserve a
   resumable checkpoint when an authenticated or verified step is blocked.

## Non-negotiable behavior

- Seed from Terry's paper KG and prior surveys before external search.
- Treat imported chats and generated summaries as untrusted briefing material,
  not claim evidence. Re-resolve and verify their citations from primary sources.
- Use primary sources for quantitative, comparative, date-sensitive, and
  load-bearing claims. Store them in the claim-evidence ledger.
- Do not reduce research to a fixed paper count. Meet the configured corpus and
  chapter floors, then continue until the search protocol's coverage and
  saturation conditions are satisfied.
- Place figures where they help explain the argument. Chapter QA judges their
  placement and contribution. Record insertion anchors, provenance, license
  basis, and generated prompts in the image plan.
- Insert every eligible exact Terry post/paper link. Keep fuzzy candidates as a
  review list; never auto-link them.
- Counts cannot override hard blockers. Repeated prose, unsupported claims,
  missing source packets, broken references, missing image
  provenance, or an unready QA verdict block release.
- Aim for about 4,000 rough words per language chapter. Length, table volume,
  table count, learning-outcome formatting, and gaps between visuals are
  editorial signals. Review argument, useful comparison, justified author
  judgment, and reader understanding. Add prose when it helps the reader.
- Write Korean manuscripts in Korean ordinary prose. **통용 영어 용어는 영어로
  유지한다.** 한국 로보틱스·AI 실무자가 실제로 영어로 말하는 용어(`action head`,
  `diffusion policy`, `end-effector`, `sim-to-real`, `teacher-student`,
  `backdrivability`, `proprioceptive` 등)를 한국어 조어로 바꾸지 않는다.
  한국어로 옮겨야 하는 것은 **일반 동사·형용사·설명 문구·절 제목**이지 전문용어가
  아니다. 병기는 챕터 첫 등장 1회를 권장하되 **반복 병기를 실패로 처리하지
  않는다**. 스타일 레퍼런스는 **S1(`robot-hand-tactile-sensor`)·S4(`humanoid-revolution`)의
  한국어 문장**이다. Preserve proper names, code identifiers, formulas, units, and
  established acronyms.
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
and `scripts/sync_installed.py --apply`, then `--check`. The installer backs up
divergent project discovery copies and links `.agents/skills/{survey,tutorial}`
to their canonical sources. `--archive-legacy` explicitly preserves and removes
the superseded project orchestrators from active discovery. Use
`scripts/audit-codex-harness.py --root <skill-container>` for a read-only audit of
other skills, including paper/write. Do not hand-edit divergent thresholds in
role templates or verifiers; `survey_harness/config/quality_profiles.yaml` is
the single source of truth.
