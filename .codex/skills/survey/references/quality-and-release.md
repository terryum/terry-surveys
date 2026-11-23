# Quality, remediation, and release

## Single source of truth

Read `survey_harness/config/quality_profiles.yaml`; do not restate mutable
thresholds elsewhere. `full` is the only release profile. `mini` is for
non-deploying forward tests. `legacy_baseline` calibrates S1/S4 content without
requiring new process artifacts and can never authorize publication.

Run:

```bash
python3 .codex/skills/survey/scripts/survey_harness.py score <slug> --profile full --write --record --plan-remediation
```

The scorecard combines evidence, synthesis, accuracy, visuals, links, bilingual
quality, and release integrity. Release requires the configured total score,
every dimension floor, and zero hard blockers. Synthesis is an evidence-backed
editorial judgment, including a separate passing judgment for each chapter;
table volume cannot stand in for it. Deterministic evidence still verifies
claims, citations, provenance, artifacts, fingerprints, and release integrity.
Word bands, table count and volume, learning-outcome formatting, and visual
spacing produce editorial warnings. Figure coverage and provenance contribute
to the automatic visual score. Chapter reviewers judge whether visual placement
helps readers follow the explanation.

## Remediation

The controller groups stable failures by owner. A repair worker receives the
current editorial contract and refreshed input packet, stable failure IDs,
affected artifact, location, excerpt, problem, reader impact, expected result,
and action (`add`, `cut`, `rewrite`, `reorder`, `evidence`).
Concrete blockers go to the writer first. A low synthesis score alone returns
the chapter to QA for a diagnosis. The writer records `failure_ids`, `before`,
`after`, `changed_artifacts`, and `evidence` in the repair report. The controller
checks the claimed changes against the raw manuscript fingerprints from before
and after the edit. Chapter QA rechecks every original finding ID against the
revised passages. The controller preserves the accepted reviews and repair
checks as evidence across resumes.

Chapter QA writes `_quality/chapters/chNN.json` independently and never
overwrites the global review. Final `qa-book` checks the current chapter
digests, real reviewer identities, cross-chapter argument, and integration.
Old QA artifacts remain as history but cannot certify a changed manuscript.

For build evidence, run the local build command that produces the deployment
artifact. Use `python3 build.py <slug>` for the shared build or the command
specified by the book's deployment workflow for a custom build. Run structural
validation as a separate check. Inspect both rendered indexes on desktop and
mobile, compare their layout and links with the rendered S1/S4 indexes and the
book's editorial contract, and verify companion routes and chapter navigation.
Record the command, working directory, and exit code in
`_quality/build_validation.json`. Under `checks.rendered_indexes`, record the
S1/S4 pages consulted, both viewport sizes, and separate `ko` and `en` results
with each rendered page path and observations for the cover, introduction,
reading button, table of contents, glossary, bibliography, and companion
routes. Include discrepancies and their resolution or approved rationale.
Set top-level `passed` only after these checks and the existing build checks
pass.

At the profile's retry limit for the same failure ID, preserve all score
history and stop in resumable blocked state. A later `--resume` may succeed after
new sources, corrected assets, credentials, or user direction arrive.

## Private terryum.ai deployment (default)

Run the [private deployment preflight](private-deployment-preflight.md)
before dispatching a full run and repeat the transport checks before
provisioning. `ready` means editorial QA passed. The user's private edition
is delivered when the protected KO/EN detail routes work on terryum.ai and
the preview receipt has been recorded. An explicitly scoped local or draft
run can end before deployment.

After state becomes `ready` and the current full score is recorded, record
release start:

```bash
python3 .codex/skills/survey/scripts/survey_harness.py release <slug> running
```

This records the pre-sync Terry KG SHA-256. The final verifier requires a
different post-sync KG hash plus current candidate IDs/backrefs, preventing an
old survey entry from masquerading as a refresh sync.

Then perform, in order:

1. Restore/verify local assets, then local survey build and validation.
2. Create/verify `<slug>-preview` Pages and provision its Access application
   with the approved admin identity and existing private-survey service
   token. Confirm coverage for the preview hostname and any deployment
   alias that can serve the uploaded artifact. Upload the manuscript only
   after protection is verified, then test the origin anonymously.
3. Exact Terry post/paper links and master reference index rebuild.
4. Validate cover, OG, and thumbnail. Register a new book with
   `visibility: private` and `preview_embed_url` in the terryum.ai survey
   registry. Keep the public `embed_url` unset for a new book. Preserve an
   existing public `embed_url` during refresh.
5. Type-check and build the homepage, then push the scoped registry change
   and verify the existing GitHub Actions `Deploy to Cloudflare Workers`
   run succeeded for that commit. This is the same homepage delivery path
   used by `$paper`; the Pages and Access setup is specific to the survey
   book origin.
6. Upload changed local assets to private R2 and refresh
   `assets/manifest.json`. Re-run the `source-repositories.md` gate, then commit
   and push text source plus the manifest to private `terry-surveys-contents`.
   Never commit `assets/` or generated `docs/`. Record that SHA as
   `content_commit`.
   Record the public skill/harness version used for scoring as
   `framework_commit`; this commit must contain no survey content.
7. Candidate/KG sync-back.
8. Verify anonymous and ordinary member denial on the gallery and detail
   routes. Verify that admins can load the KO and EN detail routes and the
   books inside their iframes, using the expected private proxy origin. Check
   the deployed revision and absence of an active not-found tree.

After those checks, record a preview receipt under `_quality/releases/`:

```bash
python3 .codex/skills/survey/scripts/survey_harness.py publication <slug> preview released \
  --artifact content_commit=<private-content-sha> --artifact framework_commit=<framework-sha> \
  --artifact gallery_commit=<site-sha> --artifact workflow_id=<workers-run-id> \
  --artifact pages_url=https://<slug>-preview.pages.dev \
  --artifact anonymous=denied --artifact member=denied \
  --artifact admin_ko=passed --artifact admin_en=passed
```

Report both private terryum.ai detail URLs and the workflow result. If a step
is blocked, record its exact error with
`publication <slug> preview blocked --reason ...` and preserve prior evidence.

## Production promotion

Only `/survey --publish <slug>` authorizes production. Re-score, require the
current digest to match the approved preview receipt, deploy that exact snapshot
to `<slug>.pages.dev`, set the registry `embed_url` public, and retain
`preview_embed_url` for the admin preview route. Later edits update preview only
until the next explicit publish.
Record the promotion with `publication <slug> production released`; the command
refuses a digest different from `_quality/releases/preview.json`.

Private surveys keep their detail iframe behind the admin identity session and
the `private-surveys.terryum.ai` proxy. For them, release verification runs the
gallery's production visibility/access probe instead of expecting an iframe in
anonymous HTML. The probe checks anonymous and member denial, admin KO/EN
iframes, protected proxy responses, caching/robots headers, and unknown-route
404 behavior without writing session cookies or Service Token values to the
receipt.

Record URLs, all three commit SHAs, workflow ID, asset validation, and live
assertions as release artifacts. The `released` command independently checks
the private content, public framework, and gallery commits on fetched remote
branches, the GitHub workflow conclusion/head SHA, exact KO/EN
detail routes and iframe `src` documents, current KG backrefs/IDs, and all three
live URLs, then writes a hashed `_quality/release_receipt.json`. On success:

KG coverage is compared with canonical IDs rebuilt from the current
`bibtex/refs_index.json` using the same arXiv → DOI/Nature → BibTeX → normalized
title precedence as `sync-survey-candidates.mjs`.

```bash
python3 .codex/skills/survey/scripts/survey_harness.py release <slug> released \
  --artifact pages_url=<url> --artifact content_commit=<private-content-sha> \
  --artifact framework_commit=<public-framework-sha> \
  --artifact gallery_commit=<sha> --artifact workflow_id=<id> \
  --artifact live_ko_url=https://terryum.ai/ko/surveys/<slug> \
  --artifact live_en_url=https://terryum.ai/en/surveys/<slug> \
  --artifact asset_validation=passed --artifact workers_status=success \
  --artifact source_push=passed --artifact kg_sync=passed \
  --artifact live_ko=passed --artifact live_en=passed \
  --artifact iframe_check=passed --artifact not_found_check=passed
```

On external failure, use `release <slug> blocked --reason ...`. Do not change the
quality score or claim that deployment succeeded.

States created before the split remain verifiable with legacy
`survey_commit`. New `split-v1` states require `content_commit` and
`framework_commit`; do not write new legacy evidence.
