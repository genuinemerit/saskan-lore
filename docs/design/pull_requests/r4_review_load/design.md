# Release 4: Human Review and Load

Status: **Pending R3**

## Objective

Provide a workflow and tooling for reviewing staged extraction output, then loading
approved records into the database. This is the human review gate that separates
untrusted LLM output from trusted DB content. No unreviewed claim enters the DB as trusted.

---

## Deliverables

- `saskan_lore/loader/review_staging.py` — CLI helper to present staging files for review
  (display claims, prompt for approve / correct / reject per claim)
- `saskan_lore/loader/load_reviewed.py` — validate and insert approved records from staging
- `saskan_lore/loader/load_entities.py` — insert entities and aliases (must run before claims)
- `saskan_lore/loader/load_relationships.py` — insert relationships (must run after entities)
- Documented load order and idempotence strategy
- CLI commands: `saskan-lore review <staging-file>`, `saskan-lore load <staging-file>`

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| FR-003 | Entity catalog populated with canonical names, types, aliases |
| FR-004 | Reviewed claims inserted with all required fields |
| FR-005 | Relationships inserted after both referenced entities exist |
| NFR-003 | Every loaded claim has chunk_id, document_id, source_span |
| NFR-004 | Human review gate: `reviewed=true` required to load as trusted |
| ADR-003 | Claims as first-class; summaries not loaded |
| ADR-007 | Reviewer is the control point for catching any invented content |
| Workflow Stage 4 | Human review: approve, correct, or reject records |
| Workflow Stage 5 | Load to DB: referential integrity, idempotent re-runs |

---

## Design Notes

### Review workflow

The reviewer opens a staging file (or uses the CLI helper) and for each claim:

1. Reads the `claim_text` and `source_span` side by side.
2. Verifies the source span actually appears in the source chunk.
3. Confirms or corrects `truth_status`.
4. Sets `reviewed: true` to approve, or `status: "rejected"` to reject.
5. Saves the updated staging file.

The CLI helper (`review_staging.py`) automates the display; the edit can be done in the
terminal or directly in the JSON file. Keep this simple — a rich terminal UI is not
required. See NFR-005.

### Validation before load

Before inserting any record, validate:

```txt
Claim:
  - claim_text:   non-empty string
  - source_span:  non-empty string
  - truth_status: one of {fact, belief, interpretation, rumor}
  - reviewed:     must be True
  - chunk_id:     must reference an existing chunk

Entity:
  - canonical_name: non-empty string
  - entity_type:    one of {person, place, faction, artifact, era, other}

Relationship:
  - source_entity_id: must exist in entities table
  - target_entity_id: must exist in entities table
  - relationship_type: non-empty string
```

Any record failing validation is skipped and logged, not silently dropped or raised as
a fatal error. A summary of skipped records is printed after the load run.

### Load order

```txt
1. load_entities()        — no FK dependencies
2. load_entity_aliases()  — depends on entities
3. load_claims()          — depends on chunks, documents
4. load_claim_entities()  — depends on claims, entities
5. load_relationships()   — depends on entities
```

`load_reviewed.py` orchestrates this order for a given staging file.

### Idempotence

Before inserting a claim, check for an existing record by `(chunk_id, claim_text)`.
If found, skip. Do not update existing records silently — log a warning instead.
For entities, check by `canonical_name`. For relationships, check by
`(source_entity_id, target_entity_id, relationship_type)`.

### Rejected claims

Insert with `status="rejected"`, `reviewed=False`. Do not delete. This preserves the
audit trail and allows the reviewer to revisit a rejected claim later.

---

## Testability Considerations

- Test that a claim with `reviewed=False` is rejected by the loader.
- Test that a claim missing `source_span` fails validation and is skipped.
- Test that `load_relationships()` raises or skips when a referenced entity does not exist.
- Test idempotence: loading the same staging file twice produces no duplicate records.
- Test that rejected claims are inserted with `status="rejected"`, not silently dropped.
- Test the load order: claims cannot be loaded before their parent chunks exist.

---

## Acceptance Criteria

- Only claims with `reviewed=True` are inserted into the claims table.
- All loaded claims have non-empty `claim_text`, `source_span`, valid `truth_status`,
  and valid `chunk_id` and `document_id` references.
- Rejected claims are stored in the DB with `status="rejected"`.
- Re-running `load` on the same staging file produces no duplicate records.
- Relationships are only inserted when both referenced entities already exist.
- A post-load summary is printed: N claims loaded, N skipped, N rejected.
