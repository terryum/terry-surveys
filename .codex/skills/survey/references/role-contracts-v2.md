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

After the research shards, deduplicate by DOI, arXiv ID, canonical title, then
write:

- `_research/source_ledger.jsonl`, one source per line using the bundled schema.
- `_analysis/claim_evidence.jsonl`, including every quantitative, comparative,
  dated, causal, and load-bearing claim.
- `_analysis/chapter_source_packets/chNN.json`, with thesis, section claims,
  primary sources, counterevidence, limitations, Terry links, and visual
  candidates.

## Deep researchers

Foundations owns conceptual origin, seminal methods, negative results, and
historical transitions. Frontier owns freshness-sensitive papers, benchmarks,
industry primary sources, datasets, and unresolved debates. Both record method,
experiment, quantitative result, limitation, evidence tier, verification,
chapter hints, and visual candidates. Do not fill quotas with near-duplicates,
press rewrites, or uncited metadata shells.

## Book writer/editor

Own both languages of assigned chapters. Write from the source packet, not from
paper abstracts. Each chapter must have a clear question and thesis, learning
outcomes, historical and frontier synthesis, tables where comparison helps,
limitations or disagreement, practical/manufacturing interpretation, and a
bridge to the next chapter. Preserve claim IDs adjacent to audited assertions
in both manuscripts, for example `<!-- claim:ch03-c07 -->`, so the fact checker
can connect prose to `_analysis/claim_evidence.jsonl`. Put the marker immediately
before substantive claim prose, exactly once per language. The fact checker
stores the controller-compatible normalized excerpt SHA-256 under
`manuscript_anchors.ko/en`. Avoid repeated chapter
skeletons and translation compression.

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
parity, and build integrity. Write `_quality/reviewer_scores.json` with 0–100
scores and evidence for every dimension, `_quality/build_validation.json`, and
an `_qa_report.md` ending in exactly `READY FOR RELEASE` or `BLOCKED: <reason>`.
No dimension score may be justified by counts alone.
Reject title sets that exceed the active profile's part/chapter length limits,
mix incompatible naming grammars across a numbered series, or drift between
`survey.json`, frontmatter, and visible chapter headings.
