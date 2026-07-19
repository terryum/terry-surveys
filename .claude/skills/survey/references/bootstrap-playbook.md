# MODE A — Bootstrap compatibility guide

The runtime-neutral canonical guide is
`.codex/skills/survey/references/bootstrap-playbook.md`. Claude must follow that
guide and the shared `survey_harness`; this file only records adapter-specific
entry points.

## Required workspace

```bash
cd /Users/terrytaewoongum/Codes/personal/terry-surveys
bash scripts/setup-contents.sh --check
gh repo view terryum/terry-surveys-contents --json visibility,isPrivate
```

The contents repository must be private. `terry-surveys` is a public framework
repository and must never receive manuscripts, built survey docs, research
artifacts, or content master data.

## Bootstrap

```bash
bash .claude/skills/survey/scripts/bootstrap.sh \
  <slug> "<title_ko>" "<title_en>" "<domain>" \
  [--visibility=group --group=<group>]
```

The wrapper delegates to the canonical Codex bootstrap script. It creates
`surveys/<slug>` through the tracked symlink, so files land at
`../terry-surveys-contents/surveys/<slug>`. Both public-reader and group-reader
surveys use that same private source repository. Do not move group content to
`terry-private`, add per-slug ignore rules, or create a standalone repository.

After filling the chapter plan, run agent sync, index rebuild, validation, and
the v2 controller. Commit source changes from `../terry-surveys-contents`.
Public feedback is handled by `terryum/terry-surveys` Issues.
