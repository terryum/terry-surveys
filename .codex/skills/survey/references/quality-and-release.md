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
Word bands, table count/volume, and learning-outcome formatting produce editorial
warnings rather than prose blockers. A warning requires review, not automatic
padding, deletion, or another boilerplate section.

## Remediation

The controller groups stable failures by owner. A repair worker receives the
current editorial contract and refreshed input packet, stable failure IDs,
affected artifact, location, excerpt, problem, reader impact, expected result,
and action (`add`, `cut`, `rewrite`, `reorder`, `evidence`).
Metrics can accompany a diagnosis; a low synthesis score alone cannot dispatch
a prose repair. Ask the reviewer to diagnose it instead. The owner must
record the specific changes and evidence, complete its repair task, then the
orchestrator reruns the whole score. Never delete a failure from the scorecard or
weaken a threshold to make the run pass.

Chapter QA writes `_quality/chapters/chNN.json` independently and never
overwrites the global review. Final `qa-book` checks the current chapter
digests, real reviewer identities, cross-chapter argument, and integration.
Old QA artifacts remain as history but cannot certify a changed manuscript.

After three failed repair passes for the same failure ID, preserve all score
history and stop in resumable blocked state. A later `--resume` may succeed after
new sources, corrected assets, credentials, or user direction arrive.

## Preview chain (default)

After state becomes `ready`, record release start:

```bash
python3 .codex/skills/survey/scripts/survey_harness.py release <slug> running
```

This records the pre-sync Terry KG SHA-256. The final verifier requires a
different post-sync KG hash plus current candidate IDs/backrefs, preventing an
old survey entry from masquerading as a refresh sync.

Then perform, in order:

1. Restore/verify local assets, then local survey build and validation.
2. Create/verify `<slug>-preview` Pages, provision its Cloudflare Access
   application and existing admin/service-token policies, then upload and check
   the protected preview. Never upload first and add Access later.
3. Exact Terry post/paper links and master reference index rebuild.
4. Cover/OG/thumb validation and private `terryum-ai` gallery registration using
   `preview_embed_url`. Preserve an existing public `embed_url` during refresh.
5. `terryum-ai` type-check/build, commit, push, and Workers workflow success.
6. Upload changed local assets to private R2 and refresh
   `assets/manifest.json`. Re-run the `source-repositories.md` gate, then commit
   and push text source plus the manifest to private `terry-surveys-contents`.
   Never commit `assets/` or generated `docs/`. Record that SHA as
   `content_commit`.
   Record the public skill/harness version used for scoring as
   `framework_commit`; this commit must contain no survey content.
7. Candidate/KG sync-back.
8. Live checks: anonymous and ordinary member denial, admin KO/EN preview iframe
   success, expected iframe source, and absence of an active not-found tree.

Record a preview receipt under `_quality/releases/`. Access API permission or
protection-check failure is `deploy_blocked`: preserve the source commits and do
not report the run complete.

Use `survey_harness.py publication <slug> preview released --artifact ...` only
after the access checks have actually passed. Record failures with
`publication <slug> preview blocked --reason ...`.

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
