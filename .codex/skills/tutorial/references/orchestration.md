# Tutorial orchestration

## New tutorial

1. Verify the linked private contents workspace and repository privacy.
2. Scaffold and normalize one or more supplied inputs:

   ```bash
   python3 .codex/skills/tutorial/scripts/tutorial_harness.py scaffold <slug> --prompt "..."
   ```

   Use `--file` or `--chatgpt-url` instead when supplied. `--chatgpt-html` is a
   test/offline extraction aid. If a share link cannot be read, stop with a
   resumable input blocker; do not fabricate its content.
3. Initialize the full state, start the first task with the real worker ID, and
   repeatedly use `next`, `start`, and `complete`. After the curriculum architect
   finalizes `survey.json` and `_tutorial/roadmap.md`, run `sync-roadmap` so newly
   planned chapters enter the downstream DAG.
4. Keep no more than three workers active. A worker owns only its declared
   artifacts. The orchestrator owns repository gates, score, registry, deploy,
   and release receipts.
5. Run `score --write`. Fix every hard blocker, then deploy preview and record it
   with `release <slug> preview released ...`.

## Chapter update

Run `reopen <slug> --chapter N`. The DAG still begins with input normalization
and whole-roadmap review, but downstream lab/write/verify/QA tasks target only N.
The state stores digests of every other ready chapter and rejects silent edits.
Version changes or an explicit roadmap impact may justify a separate user-visible
reopen of affected chapters; never fold that expansion into the current run.

## Resume and feedback

`resume` reopens running, blocked, or artifact-invalid tasks. Terry's real-world
result enters through `feedback --chapter N --result ... --environment-json ...
--notes ...`; this appends `_tutorial/user_validation.jsonl` and starts a fresh
chapter run. Preserve failure evidence instead of rewriting it as success.

## Durable chapter format

Use the same sequence in both languages:

```markdown
### Step 1 — observable goal

**Action**: exact command or UI action

**Expected**: exact screen, file, or output fragment

**Recovery**: smallest safe diagnostic and retry path

**Validation**: checked
```

Korean uses `**행동**`, `**기대 결과**`, `**복구**`, and `**검증 상태**`.
The first Action appears within 200 rough words. Put policy, administration, long
theory, hardware selection, and alternatives after the first observable success;
only immediate safety warnings may precede it.
