# Compatibility pointer: survey v2 quality

This filename remains for older callers. For every new book or major refresh,
read `quality-and-release.md` and load
`survey_harness/config/quality_profiles.yaml`. The v2 scorecard is authoritative;
thresholds formerly written in this document must not be copied into prompts or
verifiers.

Use the compatibility verifier only as a CLI alias:

```bash
python3 .codex/skills/survey/scripts/verify_survey_outputs.py <slug> \
  --compare-baseline --scope full --require-ready
```
