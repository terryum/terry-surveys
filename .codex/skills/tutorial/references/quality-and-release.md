# Tutorial quality and release

## Hard gates

`tutorial_harness score` rejects: first action after 200 rough words; first
observable success over ten minutes; a core action without Expected and Recovery;
missing KO/EN parity; missing official chapter sources; broken links; missing
verification evidence; or claims such as “tested/검증 완료” while a relevant check
is `reader_test_required`. The latter status is valid and preferred for heavy,
privileged, hardware, and reader-environment work.

## Preview sequence

1. Update the asset manifest and pass local build/validation/score.
2. Run `gh context`; require `personal / terryum`. Verify
   `terryum/terry-surveys-contents` is private.
3. Stage only the tutorial's text/evidence files in the contents repository,
   commit, and push. Do not commit assets, generated docs, or unrelated dirt.
4. Provision `<slug>-preview.pages.dev` and its Access application before upload
   with `terryum-ai/scripts/provision-survey-preview-access.mjs`. The operation is
   idempotent and preserves the configured admin and service-token policies.
5. Build from the recorded content/framework commits and upload to the preview
   Pages project.
6. Register/update the gallery item privately with `preview_embed_url`, cover
   assets, full TOC status, content type, and tutorial number. Commit/push only
   those gallery files and require the deployment workflow to succeed.
7. Verify anonymous denial, ordinary-member denial, and admin KO/EN iframe
   success. Receipts contain status and hashes, never cookies, Access credentials,
   raw headers, or tokens.
8. Record `_quality/releases/preview.json`. If Access permission or any access
   assertion fails, record `release ... preview blocked --reason ...`.

## Production promotion

Only `$tutorial --publish <slug>` authorizes production. Re-score and require the
current digest to equal the approved preview digest. Deploy that exact snapshot
to `<slug>.pages.dev`, set the registry production `embed_url`, switch reader
visibility to public, and retain `preview_embed_url` for admins. Record
`_quality/releases/production.json`.

After publication, edits go only to preview until the next explicit publish.
Public WIP exposes ready chapters and locked planned cards; production must never
receive a newly ready chapter before the next promotion.
