# Survey v2 role contracts

## KG mapper

Read Terry's `knowledge-index.json`, `candidate_index`, `gap_index`, rich paper
metadata, prior survey chapters, master BibTeX, and post index. Produce
`_research/kg_seed.json` and `_analysis/prior_survey_absorption.md`. Distinguish
confirmed anchors from extrapolation and record reusable figures and exact
post/paper links.

## Evidence librarian and source strategist

Write `_research/search_protocol.md` before web search. The protocol must include
query families, databases/venues, time bands, source tiers, inclusion/exclusion,
backward/forward snowballing, chapter coverage, disagreement targets, and a stop
rule. Stop only after all planned clusters are covered and two consecutive
query/snowball passes add less than 5% new eligible sources.

After the research shards and critical analysis, read
`_analysis/editorial_contract.md`, `gaps.md`, `novelty_matrix.md`, and
`positioning.md`. Deduplicate by DOI, arXiv ID, canonical title, then write:

- `_research/source_ledger.jsonl`, one source per line using the bundled schema.
- `_analysis/claim_evidence.jsonl`, including every quantitative, comparative,
  dated, causal, and load-bearing claim.
- `_analysis/chapter_source_packets/chNN.json`, with thesis, section claims,
  primary sources, counterevidence, limitations, Terry links, and visual
  candidates.

Include the relevant critical analysis and editorial contract in each source
packet, so writers consume reasoning and style decisions rather than just a
source inventory.

## Deep researchers

Foundations owns conceptual origin, seminal methods, negative results, and
historical transitions. Frontier owns freshness-sensitive papers, benchmarks,
industry primary sources, datasets, and unresolved debates. Both record method,
experiment, quantitative result, limitation, evidence tier, verification,
chapter hints, and visual candidates. Do not fill quotas with near-duplicates,
press rewrites, or uncited metadata shells.

## Critical analyst

Read the research shards and the user's authoring contract. Own
`_analysis/gaps.md`, `_analysis/novelty_matrix.md`,
and `_analysis/positioning.md`. Identify the
comparison axes that matter to this reader, experimental conditions behind
disagreements, what was solved, and what remains open. Link judgments to primary
sources and distinguish a demonstrated limitation from an unanswered question.
Do not invent gaps to meet a count. The librarian must consume these artifacts
before finalizing chapter packets.

## Book writer/editor

Own the separate `editorial-contract` task after critical analysis. Follow
`editorial-contract.md` to write `_analysis/editorial_contract.md` with actual
S1/S4 examples and book-specific terminology before evidence synthesis begins.

Own both languages of assigned chapters. Read the current editorial contract and
source packet. Each chapter must answer a clear question with explanation,
evidence, comparison where helpful, and a justified judgment of what is solved
or remains open. Teach the reader without imposing identical headings, tables,
or manufacturing checklists on every topic. Preserve claim IDs adjacent to audited assertions
in both manuscripts, for example `<!-- claim:ch03-c07 -->`, so the fact checker
can connect prose to `_analysis/claim_evidence.jsonl`. Put the marker immediately
before substantive claim prose, exactly once per language. The fact checker
stores the controller-compatible normalized excerpt SHA-256 under
`manuscript_anchors.ko/en`. Avoid repeated chapter
skeletons and translation compression.

Write for a reader, not an auditor. Use S1 (`robot-hand-tactile-sensor`) and S4
(`humanoid-revolution`) as the prose references; treat the recurring procedural,
audit-style apparatus documented in the historical S11–S14 critique as an
anti-pattern. Check the current files: later revisions may already fix it.
Apply these prose criteria:

- Keep each KO and EN chapter around 4,000 rough words when the material warrants
  it. Length bands are editorial warnings, not pass/fail prose quotas.
- Use tables only where comparison materially helps. Table count and text
  volume prompt review; they do not determine synthesis quality. Avoid audit checklists,
  role-responsibility tables, or "common confusion" tables.
- Carry the argument through paragraphs instead of atomizing it into checklist
  sections. Do not cap subsection counts: S1 remains readable with 23 headings;
  the defect is audit-item content, not the number of headings.
- State the author's judgment: explain what a method solved, what remains open,
  and why. S4's `판결 1 — QDD 액추에이터: 해결됨 (commodity)` is the reference
  form for an evidence-backed verdict.
- Address the reader rather than an auditor. Do not make contract, inheritance,
  ownership, permission, or "gate to close" language the default grammar of the
  narrative.

Before prose drafting, audit the complete KO/EN part and chapter title set
against S1/S4. Use concise noun phrases for parts and a shared `core topic —
scope/payoff` grammar for chapters. Put lists, method catalogs, and explanatory
clauses in chapter summaries, not headings. Keep `survey.json`, manuscript
frontmatter, and visible H1 headings exactly synchronized.

## Image curator

Use paper figures for empirical or architectural evidence, official photos for
platform/hardware reality, and generated diagrams only for synthesis that no
source figure expresses. Use the Codex `imagegen` skill for generated raster
assets. Populate `_workspace/image_plan.json` with insertion anchors,
provenance, license basis, source URL or prompt/provider/model, and insertion
status. Check both languages and distribute visuals into the latter half.

## Fact checker

Verify all high-risk claims against primary sources and update the claim ledger,
`_refs_extracted.json`, and `_factcheck_report.md`. Check number, unit,
population, date, benchmark setup, comparison baseline, causal wording, and
caption/prose agreement. `qualified` claims must carry the limiting caveat.
Recompute each KO/EN claim-anchor excerpt digest after corrections; a marker in
references, a duplicated marker, or a digest mismatch is not evidence.
Send corrections to the writer; do not merely label an incorrect statement.

## QA reviewer

Do not edit reviewed chapters. Inspect evidence coverage, argument and
originality, factual support, visual pedagogy and pacing, crosslinks, bilingual
parity, and build integrity. A chapter reviewer owns only
`_quality/chapters/chNN.json`, identifying chapter, current manuscript digest,
real reviewer ID, dimension scores, and structured defects. `qa-book` consumes
all current chapter reviews, checks repetition/contradictions/transitions across
chapters, and owns `_quality/reviewer_scores.json`,
`_quality/build_validation.json`, and `_qa_report.md`. The final report ends in
exactly `READY FOR RELEASE` or `BLOCKED: <reason>`.

Score synthesis from the argument, valid comparison, justified author judgment,
and reader understanding. Cite specific passages and supporting evidence; no
dimension may be justified by counts alone. Each chapter must meet the synthesis
dimension floor independently. Fewer table characters cannot raise this score.
Do not treat length, absence of a table, or learning-outcome format as a defect
without showing a concrete reader problem. Record long or inconsistent titles
for editorial review; metadata/frontmatter/visible-heading drift is a separate
correctness defect.

Every defect needs a stable ID, owner, location, excerpt, problem, reader impact,
expected result, and repair action (`add`, `cut`, `rewrite`, `reorder`, or
`evidence`). A vague low score returns to the reviewer for diagnosis,
not to the writer as an invitation to pad text. Recheck repaired passages under
a fresh manuscript digest. Stop after three failed repairs of the same stable
defect and preserve the evidence.
