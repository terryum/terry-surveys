# KG-First Survey Workflow

Always seed survey work from Terry's paper KG before web search.

## Inputs

- `/Users/terrytaewoongum/Codes/personal/terry-papers/knowledge-index.json`
- Confirmed `paper_list` nodes near the topic.
- `candidate_index.candidates`, with rich metadata preferred over skeleton-only
  candidates.
- `gap_index`, `memo_index`, and typed edge neighborhoods.
- Existing survey `_research/papers.json` and `bibtex/refs_index.json` when the
  task refreshes an existing survey.

## Workflow

1. Identify confirmed anchors and typed paths explaining why they belong.
2. Pull direct neighbors, candidate pool entries, gaps, and Terry-authored memos.
3. Classify sources into foundations, direct neighbors, gap fillers, frontier
   candidates, high-citation/seminal candidates, and freshness targets.
4. Mark metadata quality:
   - `rich`: method/limitations/results/source IDs are present.
   - `skeleton`: title/URL/year only or backfilled metadata.
5. Map chapters to papers and candidates before starting any drafting.
6. Search externally only for missing coverage, freshness, or source
   verification.

## Outputs

- KG-seeded reading map.
- Candidate shortlist with `rich`/`skeleton` labels.
- Chapter-to-paper mapping.
- Unresolved gaps and fact-check targets.
- KG feedback actions per `kg-feedback.md`.
