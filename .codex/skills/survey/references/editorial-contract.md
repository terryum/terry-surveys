# Book-specific editorial contract

The `editorial-contract` task, owned by the book writer/editor, writes
`_analysis/editorial_contract.md` from the user's authoring request and
normalized input manifest before chapter source packets are finalized. Record
the audience, central question, intended explanation depth, exclusions, source
cutoff, bilingual terminology choices, and what a reader should understand or
decide afterward. Carry the same contract into initial writing and repairs.
Distinguish explanatory reading from any explicitly requested runnable tutorial
or protocol. Preserve the latter in a linked companion if appropriate; changing
the prose form must not discard a real requirement or weaken its conditions.

Before drafting the representative chapter, open the rendered Korean and
English indexes (`ko/index.html`, `en/index.html`) and a representative chapter
in each language from both S1 (`robot-hand-tactile-sensor`) and S4
(`humanoid-revolution`). If local rendered pages are absent, build the two books
locally. Record the pages and sections consulted, then specify the new book's
cover, introduction cards, reading link, table of contents, glossary and
bibliography, and where readers will find companion materials or appendices.
Record part, chapter, and section heading conventions, including section
numbering and the labels shown in chapter navigation. For a format difference
requested by the user, record the request and the route readers use to reach
the affected material.

Use short attributed examples from the reference chapters to explain how the
new book will move from a reader's problem to the concepts needed to understand
it, establish fair comparison conditions, and draw a judgment the evidence
supports. Record the source chapter and section for each example. Verify reused
factual claims against primary sources.

For Korean, retain terms practitioners normally say in English, such as
`action head`, `diffusion policy`, `end-effector`, and `sim-to-real`; use Korean
for ordinary explanation. Use natural particles and complete sentences that
name the actor, object, and conditions wherever the reader needs them. Avoid
stacking particles such as `의` and calques from English. Record choices relevant
to this book with an actual example sentence. Keep repeated parenthetical terms
when useful in context.

The critical analyst reads both research shards and identifies comparisons,
conditions under which results disagree, what each approach solved, and what
remains open. The librarian incorporates that analysis into each chapter's
thesis, claims, counterevidence, limitations, and visual candidates. A list of
papers without this reasoning is not a usable writer packet.

The first representative chapter tests the contract in prose and in rendered
pages. Its independent review cites actual KO/EN passages, checks whether
readers can follow the explanation and why author judgments are justified, and
checks that the visible section navigation leads to the corresponding headings
in each language. Record reusable examples of prose and section navigation for
later writers. Resolve concrete defects before other writers start. The
controller's representative chapter is the first chapter in the planned numeric
order.

Use roughly 4,000 words as a planning target. Shorter sufficient explanation may
pass; a long chapter may be appropriate with a clear reason. No numeric prose
floor, mandatory table, learning-outcome block, section count, or manufacturing
checkpoint substitutes for reader understanding. Facts, citations, figure
provenance, required process artifacts, and release checks remain mandatory.

This workflow adapts task packets, changed-input invalidation, and independent
producer/consumer QA from [revfactory/codex-harness](https://github.com/revfactory/codex-harness/tree/79b82281d305c89181fbb216499d5f1e962c14ed)
(Apache-2.0, Copyright 2025 robin). These are independently implemented workflow
ideas; no upstream source is vendored here. Keep the existing survey controller
instead of nesting another one.
