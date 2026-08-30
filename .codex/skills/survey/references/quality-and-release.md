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
every dimension floor, and zero hard blockers. Reviewer scores supplement but
cannot replace deterministic evidence.

## Remediation

The controller groups stable failures by owner. A repair worker receives only
the failure IDs, current metric, threshold, and affected artifacts. It must
record the specific changes and evidence, complete its repair task, then the
orchestrator reruns the whole score. Never delete a failure from the scorecard or
weaken a threshold to make the run pass.

After three failed repair passes for the same failure ID, preserve all score
history and stop in resumable blocked state. A later `--resume` may succeed after
new sources, corrected assets, credentials, or user direction arrive.

## Publication chain

After state becomes `ready`, record release start:

```bash
python3 .codex/skills/survey/scripts/survey_harness.py release <slug> running
```

This records the pre-sync Terry KG SHA-256. The final verifier requires a
different post-sync KG hash plus current candidate IDs/backrefs, preventing an
old survey entry from masquerading as a refresh sync.

Then perform, in order:

1. Restore/verify local assets, then local survey build and validation.
2. Cloudflare Pages deploy and public survey URL check.
3. Exact Terry post/paper links and master reference index rebuild.
4. Cover/OG/thumb validation and `terryum-ai` gallery registration.
5. `terryum-ai` type-check/build, commit, push, and Workers workflow success.
6. Upload changed local assets to private R2 and refresh
   `assets/manifest.json`. Re-run the `source-repositories.md` gate, then commit
   and push text source plus the manifest to private `terry-surveys-contents`.
   Never commit `assets/` or generated `docs/`. Record that SHA as
   `content_commit`.
   Record the public skill/harness version used for scoring as
   `framework_commit`; this commit must contain no survey content.
7. Candidate/KG sync-back.
8. Live KO/EN list and detail checks, expected iframe source, and absence of an
   active not-found tree.

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
