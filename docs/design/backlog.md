# Design Backlog

A running list of deferred design decisions, technical debt, potential refactors,
and future feature candidates identified during development. Items here are not
requirements — they are candidates for future releases, each requiring its own
design and requirements work before implementation.

Add items here when something notable is deferred during a release rather than
letting it get lost in commit messages or conversation history.

---

## Items

| ID | Category | Summary | Origin |
| --- | --- | --- | --- |
| BL-001 | Debt | `load_entity_aliases()` and `load_relationships()` are no-ops — the current staging format (`ExtractionRecord`) has no `relationships` or alias fields. Both functions are wired and idempotent but called with empty lists. Requires staging format extension, extraction prompt update, and design work. | R4 |
| BL-002 | Refactor | `reviewed` / `status` vocabulary is inconsistent across staging and DB. Staging uses `reviewed: bool` (True/False) plus an optional `status: "rejected"` field. The DB uses only `status` (`pending`, `approved`, `rejected`). Consider aligning to a single controlled vocabulary throughout the pipeline. | R4 |
| BL-003 | Design | Fuzzy entity matching (e.g. Levenshtein distance) to handle dialect spelling variants across lore texts. Needs threshold design, alias resolution strategy, ambiguity handling, and at minimum one ADR and one FR before implementation. | R4 |
| BL-004 | Debt | `_load_claim_entities()` in `load_reviewed.py` uses case-insensitive substring matching to link claims to entities. This is a heuristic — it can miss mentions and produce false positives. The `ClaimEntity.role` field is always NULL because the staging format provides no role data. A proper solution requires either NLP-based mention detection or explicit entity mention data in the staging format. | R4 |
| BL-005 | Debt | Entity type conflict is not detected. If an entity (e.g. "Varkaar") already exists in the DB with `entity_type="faction"` but a new staging file lists it under `places`, the loader silently returns the existing record with no warning. Consider logging a type mismatch or adding a review step. | R4 |
| BL-006 | Design | `reject_reason` is a staging-only field — it is logged at load time but not written to any DB column. If rejection audit history is valuable for analysis (e.g. tracking hallucination patterns), consider adding a `reject_reason` column to the `claims` table. Requires a schema migration. | R4 |
| BL-007 | Design | `extract_schema.json` covers extractor output only (`reviewed=false`). Post-review staging files (with `reviewed=true`, `status`, `reject_reason`) are not schema-validated. Consider whether a second JSON Schema for reviewed staging files would add value as documentation or for tooling. | R4 |
| BL-008 | Design | The extraction prompt and staging format do not currently produce relationship data or entity aliases. When this is addressed, `ExtractionRecord` in `database_schema.py`, `extract_schema.json`, the extraction prompt, and both loader stubs will all need coordinated updates. Worth designing as a single cohesive change rather than piecemeal. | R4 |

---

## Categories

| Label | Meaning |
| --- | --- |
| Design | Needs ADR and/or FR before implementation |
| Refactor | Code improvement with no new functionality |
| Enhancement | Small improvement, minimal design needed |
| Debt | Currently a stub, approximation, or known limitation |
