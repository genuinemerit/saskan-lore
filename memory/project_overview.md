---
name: saskan-lore project overview
description: Purpose, architecture, file inventory, ADRs, FRs, and current status of the saskan-lore project
type: project
---

**saskan-lore** is a pre-pilot worldbuilding lore management tool for a fictional world called Saskantinon, focused on the Covenant of Varkaar region. Explicitly a learning/throwaway project by Phoenix Quinn (MIT License, 2026). GitHub: genuinemerit/saskan-lore.

## Goal
Build a clean, inspectable lore catalog supporting: (A) lookup, (B) entity relationships, (C) exploratory queries, (D) model-assisted ideation.

## Pipeline
PDF lore docs → chunker → LLM extraction → human review → SQLite DB
(data/lore_texts/)  (analyzer/) (prompts/)     (reviewed/)    (loader/)

LLM output is treated as untrusted until human-reviewed.

## Package layout
- Root: `saskan-lore/` (git repo root)
- Python package: `saskan-lore/saskan-lore/` (inner dir with `__init__.py`)
- Key subdirs: `analyzer/`, `data/schema/`, `data/lore_texts/`, `loader/`, `prompts/`, `tools/utils/`
- Docs: `docs/architecture/decisions/`, `docs/architecture/requirements/functional/`, `docs/design/`
- Memory (local copy): `memory/`

## Key files
- `saskan-lore/analyzer/chunker.py` — sentence-aware text chunker (uses `_is_sentence_end`, `chunk_text`)
- `saskan-lore/analyzer/character_counter.py` — snippet: Counter-based character mention counting
- `saskan-lore/analyzer/evaluate_result.py` — snippet: `record_result()` inserts into eval_results table
- `saskan-lore/loader/load_metadata.py` — snippet: `insert_doc()` inserts into documents table
- `saskan-lore/prompts/extract_claims.txt` — LLM prompt: extract 3–5 factual claims with source quotes
- `saskan-lore/prompts/structure_chunks_metadata.txt` — LLM prompt: convert chunk to schema
- `saskan-lore/prompts/structure_claims_metadata.txt` — LLM prompt: convert claims to schema
- `saskan-lore/data/schema/extract_schema.json` — schema: title, summary, region, places, characters, factions, era, canon_level, truth_status, key_events, claims[]
- `saskan-lore/data/schema/testing_schema.json` — schema: question, expected_answer, model_answer, pass_fail, failure_type{wrong fact, hallucination, incomplete, style}
- `saskan-lore/data/schema/source_span.json` — example source span record with statement, source_span, document_id, chunk_id
- `saskan-lore/data/schema/database_schema.py` — design sketch (not SQLAlchemy): documents, chunks, entities, entity_aliases, claims, claim_entities, eval_questions, eval_results, relationships tables
- `saskan-lore/data/lore_texts/` — six PDF source docs: VarkaarCovenant, SettanLands, OuterLands, FatunikDominion, HighWeir, KahilaLands
- `saskan-lore/tools/utils/platform.py`, `stamps.py` — utility snippets
- `docs/architecture/decisions/adr_000.md` — ADR-001 through ADR-007 (written)
- `docs/architecture/requirements/functional/functional_000.md` — FR-001 through FR-010 (written)
- `docs/design/reference.md` — glossary: Document / Chunk / Claim / Testable / RAG / ADR
- `docs/design/workflows.md` — pipeline stage diagram + Poetry usage notes
- `STATUS.md` — current project state and next steps
- `pyproject.toml` — Poetry config, Python 3.12, deps: SQLAlchemy, openai, rich, typer, jsonschema, etc.

## Architecture Decision Records (written)
- ADR-001: No training in pre-pilot (retrieval only, local GGUF model via llama.cpp, 3B class)
- ADR-002: SQLite as system of record
- ADR-003: Claims as first-class records (drive retrieval & eval; summaries are secondary)
- ADR-004: Truth-status awareness (fact / belief / interpretation / rumor)
- ADR-005: Relationships modeled early in schema
- ADR-006: Scope limited to Covenant of Varkaar until eval criteria met
- ADR-007: No lore expansion during extraction (structural enrichment only, never narrative)

## Functional Requirements (written, FR-001–010)
Covers: source ingestion, chunk storage, entity catalog, claim extraction, claim classification, relationship storage, retrieval, grounded answering, evaluation set, evaluation results.

## Design choices
- Claim-based extraction: lore stored as discrete, source-quoted, traceable claims
- Human review loop before DB load
- Eval-driven: testing schema with failure categories (wrong fact, hallucination, incomplete, style)
- Retrieval: keyword search or embedding + cosine in Python; no vector DB yet
- MVP: 20–30 documents, ~100–200 reviewed claims, 10 eval questions (Varkaar only)

## Current status (as of 2026-03-29)
**Completed:** GitHub repo, scaffolding, design docs, schemas, prompts, ADRs (7), FRs (10), chunker.py
**In progress:** Specifying NFRs
**Next steps:** Create chunks from lore text; define and build out SQLite DB

## Known issues
- No SQLite DB yet (planned next)
- No LLM orchestration code (prompts exist, nothing calls them)
- `character_counter.py`, `evaluate_result.py`, `load_metadata.py` are code snippets, not complete modules
- `database_schema.py` is a design sketch, not runnable SQLAlchemy
- Entity naming inconsistencies in source docs
- Timeline inconsistencies in source docs
- NFR not yet written

**Why:** Learning exercise to build disciplined, inspectable lore representation before scaling up.
**How to apply:** Frame suggestions around the pipeline stages and claim-based data model. Prioritize Varkaar Covenant scope for MVP.
