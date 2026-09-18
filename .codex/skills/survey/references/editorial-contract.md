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

Read relevant passages from S1 (`robot-hand-tactile-sensor`) and S4
(`humanoid-revolution`) and include short, attributed examples with their source
chapter/section and why they suit this book. Choose examples of causal
explanation, comparison, and evidence-backed judgment, rather than copying a
chapter scaffold. Prior survey prose calibrates style; its primary sources must
still support any reused factual claim.

For Korean, retain terms practitioners normally say in English, such as
`action head`, `diffusion policy`, `end-effector`, and `sim-to-real`; use Korean
for ordinary explanation. The contract records choices relevant to this book,
including an actual example sentence. Do not force literal Korean coinages or
penalize repeated parenthetical terms automatically.

The critical analyst reads both research shards and identifies comparisons,
conditions under which results disagree, what each approach solved, and what
remains open. The librarian incorporates that analysis into each chapter's
thesis, claims, counterevidence, limitations, and visual candidates. A list of
papers without this reasoning is not a usable writer packet.

The first representative chapter tests the contract in prose. Its independent
review checks whether readers can follow the explanation and whether author
judgments are justified. Resolve concrete defects before other writers start;
retain what worked as evidence for later writers. The controller's representative
chapter is the first chapter in the planned numeric order. This review does not
require user approval.

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
