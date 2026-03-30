# Project Status

Last updated: 2026-03-30

---

## What This Is

A disciplined, inspectable lore management system for the world of Saskantinon —
starting with the Covenant of Varkaar.

Pre-pilot. Local. Claim-based. Human-reviewed. No hallucinations tolerated.

---

## MVP Definition

Done when all of these are true:

- [ ] 20–30 lore documents ingested
- [ ] ~100–200 reviewed claims stored
- [ ] 10 evaluation questions answered using retrieval
- [ ] Every answer includes traceable supporting evidence

---

## Completed

The foundation is solid. Every decision documented, every constraint named.

- GitHub repo, scaffolding, package layout
- Design docs: `workflows.md`, `reference.md` (glossary)
- ADRs 001–007 — seven clean decisions, no ambiguity
- Functional requirements FR-001–008
- Non-functional requirements NFR-001–005
- Database design sketch: `data/schema/database_schema.py`
- Extraction prompts: `analyzer/extract_claims.txt`, `analyzer/structure_claims_metadata.txt`
- `analyzer/chunker.py` — sentence-aware, reproducible text chunker
- `analyzer/extractor.py` — OpenAI gpt-4o claim extraction and structuring
- Utility modules: `platform.py`, `stamps.py`, `file_io.py`, `shell.py`, `match_semver.py`

The structure is ready. The decisions are made. The chord progression is in place.

---

## Next

Time to play.

1. **Define and build the SQLite database** — SQLAlchemy declarative models, Alembic migrations, all tables from the schema
2. **Run the chunker** — produce chunks from Varkaar source texts, load into DB
3. **Wire up the extraction pipeline** — call the LLM with existing prompts, save extracted output to `reviewed/` staging
4. **Review and load** — first real pass through the human review gate
5. **Write evaluation questions** — 10 questions against Varkaar claims

---

## Known Issues

- Entity naming inconsistencies in source documents (flag during review, do not "fix" during extraction — see ADR-007)
- Timeline inconsistencies in source documents (same treatment)

---

## Scope Boundary

Covenant of Varkaar only until MVP graduation criteria are met. See ADR-006.

---

## Ideas for Future Attention

Items noted in early design discussions that are not yet formalized in any FR, NFR, ADR,
or release design. Not in scope for MVP — flagged here so they are not forgotten.

### Conflict and Contradiction Extraction

During extraction, flag claims that appear to contradict other claims already stored
for the same entity or event. This is more than truth-status labeling — it requires
comparison across chunks. No FR or ADR covers this yet. Candidate for R5 or a
post-MVP release.

### Terminology Consistency Checking

Regex-based scan for alternate spellings of entity names (e.g. "Varkaar" vs "Varkar").
`character_counter.py` is a stub that could anchor this work. No design doc or FR
covers it. Candidate for a utility script or a dedicated release.

### Entity Frequency and Co-occurrence Analysis

Count how often entities appear and how often they appear together. Useful for
identifying central characters and relationships before the graph layer exists.
Mentioned in early design notes; `character_counter.py` is the relevant stub.
No FR or design doc covers the intended scope.

### Timeline as an Explicit Data Element

Early design notes describe the timeline as the "backbone" of the lore. No schema
field, no FR, and no ADR addresses how timeline or era data should be stored,
queried, or presented. The `era` field on `ChunkRecord` is a placeholder —
it is a free-text label, not a structured temporal value. Worth revisiting
before the graph layer (R5) is designed.

### DuckDB as Optional Analytical Layer

Discussed at length in early design notes as a complement to SQLite for analytical
queries (aggregations, co-occurrence, frequency). No ADR or release design covers
when or how to introduce it. Candidate for an ADR when analytical needs become clear.

### LoRA / PEFT Fine-Tuning Path

Long-term Stage 3 vision: fine-tune a small model (Qwen 3B or similar) on reviewed
claims using LoRA/PEFT via MLX on Apple Silicon. ADR-001 defers this explicitly to
post-MVP. No design doc covers the training data format, evaluation criteria, or
toolchain. Should be designed before the corpus grows stale for this purpose.

### Long-Term Tool Vision: Two Assistants

Early design notes describe two distinct long-term tools:

- **Continuity assistant** — answers "is this consistent with established lore?"
  Used during active writing to catch contradictions.
- **Exploratory assistant** — answers "tell me about X" for worldbuilding research.

These are not the same product and may warrant separate design docs when the time comes.

### Saskan Console UI

Very long-term concept: a unified interface combining a search bar, entity cards,
a timeline view, a relationship graph, and a continuity checker. No design work has
been done. Not relevant until the retrieval layer is working and evaluated.
