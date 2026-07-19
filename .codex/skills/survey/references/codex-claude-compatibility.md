# Codex and Claude adapter boundary

Both runtimes use the same repository controller, schemas, artifacts, scorecard,
remediation counters, and release state. Codex may use bounded subagents; Claude
may use team primitives. Neither may substitute chat status for file evidence,
pin a model in a shared role contract, lower a gate, or continue after exhausted
remediation as if the survey were complete.

When a runtime-specific worker API is unavailable, keep the controller state and
run the emitted packet in the main session. Do not silently replace a book-scale
run with a shallow single-agent draft.
