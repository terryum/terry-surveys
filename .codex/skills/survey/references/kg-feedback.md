# Survey KG Feedback

## Reading Map Buckets

- Confirmed anchors: existing `paper_list` nodes closest to the topic.
- Candidate pool: `candidate_index.candidates`, especially rich metadata and repeated survey backrefs.
- Gaps: `gap_index` entries that the survey can resolve or sharpen.
- Memos: `memo_index` entries that encode Terry-authored priorities.
- Typed paths: `knowledge_graph.edges` paths explaining why papers belong together.

## Feedback Actions

Emit actions in this shape:

```json
{
  "kg_feedback_actions": [
    {
      "action": "promote_candidate|add_relation|add_gap|update_candidate|sync_candidates",
      "target": "",
      "reason": "",
      "evidence": "",
      "requires_user_approval": true
    }
  ]
}
```

Every action that mutates repos or production systems requires explicit user approval or a direct user request.
