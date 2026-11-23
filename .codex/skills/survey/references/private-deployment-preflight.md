# Private survey deployment preflight

Run these checks before starting a full survey and repeat them in the execution
environment that will deploy it. A new book belongs in Surveys with
`visibility: private` and `preview_embed_url`. The homepage serves it through
the admin session and the private survey origin proxy. Use
[quality and release](quality-and-release.md) for the deployment itself.

## Cloudflare account and existing service token

1. Verify personal `terryum` GitHub routing and the private content repository.
   Confirm the Cloudflare account used by the existing homepage and Pages
   projects. Check access to the private R2 bucket and verify that the
   homepage's `Deploy to Cloudflare Workers` workflow is available.
2. Load the existing deployment settings through the site's
   `scripts/lib/env.mjs`. The preview provisioner consumes
   `CLOUDFLARE_ACCOUNT_ID` (or `CF_ACCOUNT_ID`), `CLOUDFLARE_API_TOKEN`,
   `ADMIN_EMAIL`, and `CF_ACCESS_SERVICE_TOKEN_ID`. The running Worker
   authenticates to the Pages origin using its existing encrypted
   `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`.
3. Resolve a missing `CF_ACCESS_SERVICE_TOKEN_ID` yourself with authenticated
   read-only GETs on the selected account. List
   `/accounts/{account_id}/access/service_tokens` and
   `/accounts/{account_id}/access/apps`. Inspect
   `/accounts/{account_id}/access/apps/{app_id}/policies` for the existing
   private survey origin. Follow pagination if present. Match the enabled,
   unexpired `terryum-ai-private-surveys` entry's `id` to the existing
   `non_identity` policy's `include[].service_token.token_id`. Use the token
   resource UUID for `CF_ACCESS_SERVICE_TOKEN_ID`. Ask the user for access only
   after a reachable Cloudflare API or the dashboard establishes which scope
   is missing. The account read scopes are `Access: Service Tokens Read` and
   `Access: Apps and Policies Read`; provisioning requires Pages write and
   `Access: Apps and Policies Write` in that account. The
   [Cloudflare permission reference](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)
   has the current names.
4. Load the verified UUID through the approved deployment environment. When
   `site/.env.local` is read-only, save only the UUID assignment as
   `export CF_ACCESS_SERVICE_TOKEN_ID=…` in the survey's ignored
   `_workspace/recovery/cloudflare-preview.env` with mode 600. Source that file
   before invoking the preview provisioner or book deploy script. Keep API
   credentials and Worker secrets in their existing stores and out of commands,
   tracked files, and receipts.

## Verify the actual deployment transport

From `site`, with the selected environment loaded, run:

```bash
curl -sS --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}\n' https://api.cloudflare.com/client/v4/
node scripts/provision-survey-preview-access.mjs --project=<slug>-preview --hostname=<slug>-preview.pages.dev --dry-run
wrangler whoami
```

The first command tests transport. An HTTP response such as 404 at that base
URL shows the API was reached. Report `ENOTFOUND` and TLS errors as transport
failures. Classify a 401/403 only after an authenticated request reaches the
correct account. A project lookup returning Cloudflare's project-not-found
response is expected before a first deployment.

If Node `fetch` fails while the direct shell `curl` command succeeds, use the
permitted direct `curl -sS` transport for the read-only inventory above. In a
managed session, calling curl as a child of Node can have a different network
profile. Feed authenticated curl configuration through a mode-600 FIFO under
a private temporary directory, with a separate writer that loads
`scripts/lib/env.mjs`. Pass the FIFO to `curl --config`, save responses in that
directory, and emit only status, relevant names, and whether the UUID matched.
Keep bearer credentials off the command line and remove the temporary
responses when finished.

For Node TLS trust errors, check the
[official Node enterprise network guidance](https://nodejs.org/learn/http/enterprise-network-configuration)
and the approved system or organizational CA configuration.
`NODE_USE_SYSTEM_CA=1 wrangler whoami` can verify Wrangler on a supported Node
version when the expected CA is in the OS trust store. Recheck the native
provisioner separately. If either command still fails, use a permitted
environment where both preflight commands pass. Report the failing command
and error if that environment is unavailable.

## Check task and release evidence

- Assign real worker IDs to one release role each from the first dispatch.
  A full run with automatic deployment rejects cross-role worker reuse when
  a task starts. The final release check also inspects earlier attempts in
  the run. Keep the framework guidance used for task fingerprints stable
  during the run.
- Run `survey_harness.py verify <slug>` from the framework before recording the
  release score. For stale inputs, run `resume` and review the reopened packets.
  Use valid existing evidence where it satisfies the current packet and record
  genuine rechecks. A successful standalone score file can precede a failed
  `--record`; check the command's exit status and the recorded digest.
- If the historical state assigned the same real worker to several required
  roles, preserve that history. A new, correctly assigned run may use the
  existing manuscript, claims, and sources as evidence. Archive the older
  state through the controller before replacing it. Complete reopened work
  with real role-specific workers before recording a fresh score.
- When a prerequisite remains blocked, record the latest verified stage and
  exact error with `publication <slug> preview blocked --reason ...`. Keep the
  private source commit and local score evidence available for resumption.
