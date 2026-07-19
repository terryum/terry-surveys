# Survey workflow compatibility pointer

The retired seven-agent TeamCreate workflow is not authoritative for new books.
Use `orchestration-v2.md`, `role-contracts-v2.md`, and
`quality-and-release.md`. The persistent `survey_harness` controller, not a
pinned model or chat-team topology, owns dependencies, retries, scoring, resume,
and release state.

Legacy surveys may be imported with `survey_harness.py migrate`; a major refresh
must then satisfy the current full profile before publication.
