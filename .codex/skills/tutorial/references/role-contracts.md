# Tutorial role contracts

## curriculum_architect

Own `_tutorial/roadmap.md`, chapter order, prerequisites, audience, final goal,
first success, and `survey.json` planned/ready state. A chapter-specific request
still reviews the entire roadmap but may change only the target chapter unless it
records a concrete version or prerequisite impact.

## source_version_researcher

Own `_tutorial/environment_matrix.json` and `_tutorial/source_ledger.jsonl`.
Prefer official vendor/project documentation. Record product, supported versions,
OS/runtime constraints, checked date, chapter numbers, URL, and exact scope.
Date-sensitive version facts require current verification.

## lab_builder

Own `labs/chNN/`, its `manifest.json`, and
`_tutorial/chapter_packets/chNN.json`. Keep examples small and reusable. Every
packet step has `action`, `expected`, `recovery`, and `validation`; first success
is designed for ten minutes or less. Never perform prohibited heavy/system/robot
actions on the reader's behalf.

## chapter_writer

Own both `book/ko/chNN.md` and `book/en/chNN.md` for one chapter. Write from the
packet and source ledger. Put a source link beside each version/API/install step
and a short Sources section at the end. Mark the chapter ready only after both
languages exist and match the packet.

## example_verifier

Own `_quality/example_verification/chNN.json`. Check official links, syntax, file
references, and only lightweight safe smoke tests available in the current
environment. Each check is `checked` or `reader_test_required`, with commands and
observations when checked. Never convert absence of an error into a tested claim.

## pedagogy_reviewer

Own `_quality/pedagogy/chNN.json`; never edit the reviewed manuscript. Use a real
agent identity different from the chapter writer. Review action latency, expected
output specificity, recovery usefulness, cognitive load, KO/EN parity, and the
transition to the next chapter. A pass requires `independent: true` and
`verdict: pass`.
