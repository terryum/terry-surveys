# Codex harness adoption — 2026-09-18

This framework adapts ideas from [revfactory/codex-harness](https://github.com/revfactory/codex-harness/tree/79b82281d305c89181fbb216499d5f1e962c14ed)
(Apache-2.0). It keeps the existing survey/tutorial controllers as the execution
authority. It does not install a second controller or change personal model,
MCP, sandbox, or publication settings.

## What changed

| Upstream practice | Adaptation here |
| --- | --- |
| Explicit task/result packets | Survey packets include input selectors and SHA-256 fingerprints, decisions, dependencies, owned outputs, and completion checks. |
| One owner per shared artifact | Paired KO/EN chapter ownership; serialized ledger updates; separate chapter QA files and final book QA. |
| Freshness-aware resume | Both controllers revalidate input/output fingerprints; survey also validates role contracts. Previous run state is archived. |
| Producer/reviewer separation | QA identities cannot be production identities. Reviews bind current manuscript bytes and identify real passages. |
| Small bounded teams | Parent schedules at most three workers using available native tools. Role names do not imply tools or agents exist. |
| Native project discovery | `.agents/skills/{survey,tutorial}` point to canonical `.codex/skills/`; installed copies are synchronized and checked. |

See upstream [runtime guide](https://github.com/revfactory/codex-harness/blob/79b82281d305c89181fbb216499d5f1e962c14ed/skills/harness/references/runtime-guide.md),
[QA guide](https://github.com/revfactory/codex-harness/blob/79b82281d305c89181fbb216499d5f1e962c14ed/skills/harness/references/qa-agent-guide.md),
and [migration notes](https://github.com/revfactory/codex-harness/blob/79b82281d305c89181fbb216499d5f1e962c14ed/docs/migration.md).
Its Claude benchmarks are historical and do not establish Codex quality.

## Editorial behavior

The survey DAG now requires critical analysis, then an editorial contract,
evidence synthesis, individual chapter packets, and an accepted first chapter
before dispatching remaining writers. The first numbered chapter is the initial
representative; choose the outline with that checkpoint in mind.

Full/mini profiles retain approximately 4,000 rough words as guidance. Word
bands, table volume/count, title length, terminology ratios, and learning-outcome
formatting are diagnostic warnings. They do not create automatic writer repairs.
Synthesis is judged from current independent chapter reviews, not table density.
Every chapter must meet the synthesis floor. Source verification, claim anchors,
citations, provenance, assets, metadata synchronization, and release checks remain
mandatory.

A blocking editorial finding carries a stable ID, path/anchor, real excerpt,
problem, reader impact, expected result, and `add`, `cut`, `rewrite`, `reorder`,
or `evidence`. A low synthesis score without a diagnosis returns to QA. Repairs
record changed artifacts and before/after evidence; repeating a no-progress
repair requires a revised diagnosis. These checks establish traceability, not
proof that AI judgment matches the reader's preference.

The canonical role instructions distinguish a book's explanatory prose from its
internal execution machinery. Research tables, audit receipts, and execution
checklists remain useful working artifacts; their existence is not a reason to
insert them into every chapter.

## Compatibility and recovery

State 2.0 remains readable. `resume` archives it and constructs a 2.1 DAG with
unverified tasks pending; it does not rewrite manuscripts or fabricate missing
fingerprints/reviews. Existing 2.1 runs reuse unchanged work and reopen changed
consumers and descendants. `init --force` and `migrate --force` also archive the
replaced state. Old publication receipts remain history and cannot authorize a
newly changed manuscript.

```bash
python3 .codex/skills/survey/scripts/survey_harness.py resume <slug>
python3 .codex/skills/survey/scripts/survey_harness.py next <slug>
python3 .codex/skills/survey/scripts/survey_harness.py verify <slug>
```

Do not pass fake worker IDs or mark tasks complete merely because old files
exist. The controller can check identity bindings, but the parent must match IDs
to actual runtime spawn results.

## Skill and agent maintenance

```bash
python3 .codex/skills/survey/scripts/sync_installed.py --apply --archive-legacy
python3 .codex/skills/survey/scripts/sync_installed.py --check
python3 scripts/audit-codex-harness.py --root .agents/skills --agent-root .codex/agents
```

The installer preserves previous copies outside active discovery. The optional
archive removes only three superseded project orchestrators: `survey-lite`,
`research-book-orchestrator`, and `tactile-book-orchestrator`. Claude files remain
available for their own runtime. Four native role TOMLs now reference canonical
topic-neutral contracts; they no longer hard-code an earlier research project.
Start a new Codex thread to discover changed skill/agent definitions.

The audit also accepts an individual skill directory. Use it for `$paper` or
`$write` without migrating their domain logic into the survey DAG. Their existing
publication and Terry-authored-text preservation rules remain authoritative.
Across workflows, first reuse source ownership, input freshness, evidence-backed
completion, and independent checks where justified. Introduce additional agents
only when independent work warrants their coordination cost.

## Validation commands

```bash
python3 -m unittest discover -s survey_harness/tests -t . -q
python3 -m unittest discover -s tutorial_harness/tests -t . -q
git diff --check
```

Private editorial pilots and critique excerpts belong outside this public
framework. A chapter A/B test validates only those chapters under a fixed source
set; it is neither a full book run nor release evidence. Before adopting a pilot
into production, refresh claim anchors, independent QA, build evidence, and the
existing publication checks.
