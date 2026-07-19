# Survey v2 orchestration

## Controller loop

The Python controller persists coordination; Codex dispatches workers. Run every
command from the terry-surveys root.

```bash
python3 .codex/skills/survey/scripts/survey_harness.py init <slug> --profile full --deploy auto
python3 .codex/skills/survey/scripts/survey_harness.py next <slug>
python3 .codex/skills/survey/scripts/survey_harness.py start <slug> <task-id> --agent-id <real-id>
python3 .codex/skills/survey/scripts/survey_harness.py complete <slug> <task-id>
python3 .codex/skills/survey/scripts/survey_harness.py status <slug>
```

Do not invent tasks outside the emitted packets. If a task discovers work for a
different role, save the evidence in its declared artifact and tell the
orchestrator. The orchestrator creates or routes a repair task; workers do not
silently edit another role's owned files.

## Waves and dependencies

1. `kg-seed` maps KG nodes, prior surveys, exact Terry links, and known gaps.
2. `source-strategy` defines query families, source venues, inclusion/exclusion,
   citation snowballing, and saturation. External search starts only afterward.
3. Foundations and frontier research run in parallel. Each uses canonical IDs
   and writes its own shard.
4. Evidence synthesis merges shards and produces the source ledger, claim
   ledger, and every chapter source packet.
5. Chapter writers run in bounded parallel. One writer owns KO and EN for the
   same chapter.
6. Image and fact-check tasks stream behind each written chapter. QA waits for
   both and stays independent of the producer.
7. Scoring groups failures by owner. Repair tasks change the smallest affected
   artifact set and report the before/after metric.

The four-slot Codex environment means one orchestrator plus at most three active
workers. Prefer waves of three bounded workers to a large nominal team. File
artifacts are authoritative; chat messages are hints only.

## Resume and migration

Use `resume` after interruption. It resets abandoned `running` tasks to
`pending` while preserving completed artifacts, attempts, score history, and
release evidence.

```bash
python3 .codex/skills/survey/scripts/survey_harness.py resume <slug>
python3 .codex/skills/survey/scripts/survey_harness.py verify <slug>
```

For an older survey with `_workspace/orchestration_state.json`, use `migrate`.
Only tasks whose legacy gate passed and whose new declared artifacts exist are
marked complete. Missing v2 evidence remains pending.

## Failure policy

- A worker failure becomes `block <task> --reason ...`; never mark it complete.
- Retry transient worker/tool failure once with the same packet. Content-quality
  failures go through scored remediation instead.
- Each stable score failure receives at most three repair passes. Exhaustion
  produces a resumable blocked checkpoint, not a partial release.
- Credentials, network, deployment, or external repository failures use the
  separate release state so content readiness is preserved.
