# Survey source repositories

## Canonical topology

Keep reader access and GitHub source access independent:

- `survey.json.visibility` controls reader access (`public` or `group`).
- `terryum/terry-surveys` is the public framework repository. It contains only
  the skill, harness, schemas, scaffold, builders, and shared presentation code.
- `terryum/terry-surveys-contents` is the private canonical content repository.
  Every survey lives at `surveys/<slug>/`; shared assets, bibliography data,
  glossary masters, and maintenance records live there too.

Do not create a standalone GitHub repository for a new survey. Adding a survey
means adding one directory to `terry-surveys-contents/surveys/`. Public feedback
belongs in `terryum/terry-surveys` Issues; do not copy issue templates into each
private survey folder.

Locally, clone the two repositories as siblings and require
`bash scripts/setup-contents.sh --check` to pass. The public framework exposes
compatibility symlinks so existing `surveys/<slug>` and master-data paths keep
working.

## GitHub checks and mutations

Run `gh context` before repository creation, visibility changes, force pushes,
deletions, or other consequential GitHub mutations. Under this workspace require:

```text
context=personal
account=terryum
owner=terryum
```

Use the normal directory-routed `gh` command; never run `gh auth switch`.
Before a content commit or release, verify
`gh repo view terryum/terry-surveys-contents --json visibility,isPrivate`
reports `PRIVATE` and `isPrivate: true`. If it does not, stop before source
mutation or release.

Never add survey content, built survey docs, research workspaces, or private
master data to the public framework repository. Never make the contents
repository public unless the user explicitly reverses this policy.

The private contents Git repository is text-first. Do not commit per-survey
`assets/`, generated `docs/`, PDFs, audio, archives, or other heavyweight
binaries. Keep them locally, record hashes in `assets/manifest.json`, and sync
the asset directories to the private `terry-surveys-assets-private` R2 bucket
with `scripts/sync-content-assets.sh`. Pages deployment still builds from local
assets and uploads the generated site directly. A fresh clone must restore R2
assets before build, QA, or release.

Do not force-add gitignored `_workspace/` files or `_refs_extracted.json` merely
to satisfy release digest checks. They remain local derived score inputs. The
release digest binds their commit-eligible evidence through `_assets_log.md`,
`_factcheck_report.md`, `_analysis/claim_evidence.jsonl`, and the tracked
research corpus.

## Metadata and publication

New and migrated surveys use:

```json
{
  "github_repo": "terryum/terry-surveys-contents",
  "github_repo_visibility": "private"
}
```

The site builder hides private GitHub links. Public books are served through
Cloudflare Pages and the Terry gallery; group books retain their group access
path. Release evidence records the private `content_commit`, public
`framework_commit`, and `gallery_commit`. Legacy states using `survey_commit`
remain readable, but new releases must use the split names.

Historical standalone repositories may exist only as archival branches in the
private contents repository. They are not active push targets or sources of
truth.
