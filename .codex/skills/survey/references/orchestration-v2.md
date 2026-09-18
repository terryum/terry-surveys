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
4. `critical-analysis` reads both shards and produces grounded comparisons,
   disagreements, solved/open problems, and book positioning. Then the
   book writer/editor's `editorial-contract` task fixes audience, explanation
   depth, terminology, and S1/S4 examples.
5. Evidence synthesis consumes that analysis, merges shards, and produces the
   source ledger and claim ledger. Separate librarian `packet-chNN` tasks then
   produce each chapter source packet, so revising one packet invalidates its
   consumers without rerunning unrelated research.
6. Write and review the representative chapter first. Once its editorial defects
   are resolved, remaining writers run in bounded parallel. One writer owns KO
   and EN for the same chapter.
7. Image and fact-check tasks stream behind each written chapter. QA waits for
   both and stays independent of the producer.
   Each chapter QA writes only `_quality/chapters/chNN.json`; `qa-book` then
   checks cross-chapter repetition, contradiction, progression, and integration.
8. Scoring groups failures by owner. Repairs carry location, excerpt, problem,
   reader impact, expected result, and an action: add, delete, rewrite, reorder,
   or strengthen evidence. Report the actual correction and verification, not
   merely a changed metric. A score deficit alone is not a writer instruction.

The four-slot Codex environment means one orchestrator plus at most three active
workers. Prefer waves of three bounded workers to a large nominal team. File
artifacts are authoritative; chat messages are hints only.

## Resume and migration

Use `resume` after interruption. It resets abandoned `running` tasks and
revalidates completed work against input, instruction, decision, and output
fingerprints. Changed inputs invalidate their consumers and downstream tasks;
unrelated valid work, attempts, score history, and release evidence remain.
Refresh packets before redispatch instead of reusing stale worker prompts.
Track shared ledgers by chapter records, so one chapter's correction does not
invalidate unrelated chapters. A permitted downstream edit must be recorded as
such rather than mistaken for an external change.

```bash
python3 .codex/skills/survey/scripts/survey_harness.py resume <slug>
python3 .codex/skills/survey/scripts/survey_harness.py verify <slug>
```

For an older survey with `_workspace/orchestration_state.json`, use `migrate`.
Preserve the earlier state before upgrading to 2.1. Existing 2.0 state remains
readable, but old completion without fingerprints or independent QA evidence
does not establish current completion. Missing or unverifiable evidence remains
pending. Never rewrite the manuscripts merely to migrate controller state.

## Packet and ownership contract

Every emitted packet identifies the goal, settled decisions, required guidance,
input artifacts and fingerprints, owned outputs, dependencies, and completion
checks. Workers read the packet and its referenced contracts before writing.
Do not treat an artifact as consumed because it merely exists: the downstream
packet must identify it and the produced work must reflect its relevant content.
Shared metadata/ledgers have an explicit owner; chapter workers propose changes
or edit only assigned records. Do not let concurrent writers overwrite the
whole `survey.json` or a shared QA report.

## Failure policy

- A worker failure becomes `block <task> --reason ...`; never mark it complete.
- Retry transient worker/tool failure once with the same packet. Content-quality
  failures go through scored remediation instead.
- Each stable score failure receives at most three repair passes. Exhaustion
  produces a resumable blocked checkpoint, not a partial release.
- Credentials, network, deployment, or external repository failures use the
  separate release state so content readiness is preserved.
