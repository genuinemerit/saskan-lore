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
| BL-002 | ~~Refactor~~ **Resolved (R5-prep)** | ~~`reviewed` / `status` vocabulary is inconsistent across staging and DB.~~ Resolved: `reviewed: bool` and staging-only `status: "rejected"` replaced by a single `review_status` enum (`pending`, `approved`, `rejected`) across all staging files, loader code, schema, and tests. DB `claims.status` vocabulary is unchanged and now matches exactly. | R4 |
| BL-003 | Design | Fuzzy entity matching (e.g. Levenshtein distance) to handle dialect spelling variants across lore texts. Needs threshold design, alias resolution strategy, ambiguity handling, and at minimum one ADR and one FR before implementation. | R4 |
| BL-004 | Debt | `_load_claim_entities()` in `load_reviewed.py` uses case-insensitive substring matching to link claims to entities. This is a heuristic — it can miss mentions and produce false positives. The `ClaimEntity.role` field is always NULL because the staging format provides no role data. A proper solution requires either NLP-based mention detection or explicit entity mention data in the staging format. | R4 |
| BL-005 | Debt | Entity type conflict is not detected. If an entity (e.g. "Varkaar") already exists in the DB with `entity_type="faction"` but a new staging file lists it under `places`, the loader silently returns the existing record with no warning. Consider logging a type mismatch or adding a review step. | R4 |
| BL-006 | Design | `reject_reason` is a staging-only field — it is logged at load time but not written to any DB column. If rejection audit history is valuable for analysis (e.g. tracking hallucination patterns), consider adding a `reject_reason` column to the `claims` table. Requires a schema migration. | R4 |
| BL-007 | Design | `extract_schema.json` covers extractor output only (`reviewed=false`). Post-review staging files (with `reviewed=true`, `status`, `reject_reason`) are not schema-validated. Consider whether a second JSON Schema for reviewed staging files would add value as documentation or for tooling. | R4 |
| BL-008 | Design | The extraction prompt and staging format do not currently produce relationship data or entity aliases. When this is addressed, `ExtractionRecord` in `data_schema.py`, `extract_schema.json`, the extraction prompt, and both loader stubs will all need coordinated updates. Worth designing as a single cohesive change rather than piecemeal. | R4 |
| BL-009 | Design | Embedding-based retrieval as an alternative to FTS5 keyword search. At load time, embed each claim using a local embedding model and store vectors as JSON blobs or in a `claim_embeddings` table. At query time, embed the query and compute cosine similarity (numpy) against stored vectors, returning top N by score. This is a drop-in replacement behind the existing `retrieve()` interface. Requires: embedding model selection (ADR), storage format decision, and similarity threshold design. Do not implement until FTS5 path is validated on real lore data. | R5 |
| BL-010 | Design | Conflict and contradiction extraction: during or after loading, flag claims that appear to contradict other claims already stored for the same entity or event. Distinct from `truth_status` labeling — requires cross-chunk comparison. No FR or ADR covers this. Candidate for a post-R6 release. | STATUS |
| BL-011 | Enhancement | Terminology consistency checking: regex-based scan for alternate spellings of entity names (e.g. "Varkaar" vs "Varkar"). `saskan_lore/analyzer/character_counter.py` is a stub that could anchor this work. No FR or design doc defines the intended scope. | STATUS |
| BL-012 | Enhancement | Entity frequency and co-occurrence analysis: count how often entities appear and how often they appear together. Useful for identifying central characters before the graph layer exists. `character_counter.py` is the relevant stub. No FR or design doc covers this. | STATUS |
| BL-013 | Design | Timeline as an explicit data element: the `era` field on `ChunkRecord` is free-text, not a structured temporal value. No schema field, FR, or ADR addresses how timeline or era data should be stored, queried, or presented. Worth designing before any graph or relationship layer is built. | STATUS |
| BL-014 | Design | DuckDB as optional analytical layer: complement to SQLite for aggregation, co-occurrence, and frequency queries. No ADR or release design covers when or how to introduce it. Candidate for an ADR when analytical needs become clear. | STATUS |
| BL-015 | Design | LoRA / PEFT fine-tuning path: fine-tune a small model (Qwen 3B or similar) on reviewed claims using LoRA/PEFT via MLX on Apple Silicon. ADR-001 defers this to post-MVP. No design doc covers training data format, evaluation criteria, or toolchain. Should be designed before the reviewed corpus grows too large to curate manually. | STATUS |
| BL-016 | Design | Two-assistant tool vision: (1) continuity assistant — "is this consistent with established lore?" used during active writing; (2) exploratory assistant — "tell me about X" for worldbuilding research. These are distinct products and may warrant separate design docs when retrieval is evaluated and stable. | STATUS |
| BL-017 | Design | Saskan console UI: long-term concept for a unified interface combining search, entity cards, timeline view, relationship graph, and continuity checker. Not relevant until retrieval is evaluated. No design work has been done. | STATUS |

---

## Categories

| Label | Meaning |
| --- | --- |
| Design | Needs ADR and/or FR before implementation |
| Refactor | Code improvement with no new functionality |
| Enhancement | Small improvement, minimal design needed |
| Debt | Currently a stub, approximation, or known limitation |
