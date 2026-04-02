---
name: saskan-lore project overview
description: Purpose, architecture, file inventory, ADRs, FRs, and current status of the saskan-lore project
type: project
---

# saskan-lore Project Overview

Pre-pilot worldbuilding lore management tool for the fictional world of Saskantinon,
focused on the Covenant of Varkaar region. A learning/throwaway project by Phoenix Quinn
(MIT License, 2026). GitHub: genuinemerit/saskan-lore.

## Goal

Build a clean, inspectable lore catalog supporting: (A) lookup, (B) entity relationships,
(C) exploratory queries, (D) model-assisted ideation.

## Pipeline

```text
data/lore_texts/ → analyzer/ → prompts/ → reviewed/ → loader/ → SQLite DB
(source PDFs)     (chunker)   (LLM ext.) (human rev.) (DB load)
```

LLM output is treated as untrusted until human-reviewed.

## Package Layout

- Root: `saskan-lore/` (git repo root)
- Python package: `saskan_lore/` (with `__init__.py`)
- Key subdirs: `analyzer/`, `data/`, `loader/`, `infra/`, `tools/`
- Docs: `docs/architecture/decisions/`, `docs/architecture/requirements/`, `docs/guides/`
- Memory (local copy): `memory/`

## Key Files

- `saskan_lore/analyzer/chunker.py` — sentence-aware text chunker
- `saskan_lore/analyzer/extractor.py` — OpenAI gpt-4o claim extraction and structuring
- `saskan_lore/loader/ingest.py` — top-level CLI: extract PDF, register, chunk
- `saskan_lore/loader/register_lore_text.py` — document registration
- `saskan_lore/loader/load_chunks.py` — chunk persistence
- `saskan_lore/infra/db/db.py` — SQLAlchemy session management
- `saskan_lore/infra/db/init_db.py` — Alembic upgrade head
- `saskan_lore/infra/config/env.example` — env var template (gitignored: `env.local`)
- `alembic/versions/` — two migrations: initial schema + add foreign keys
- `docs/guides/reference.md` — glossary
- `docs/guides/workflows.md` — pipeline stage diagram + tooling notes
- `STATUS.md` — current project state and next steps
- `pyproject.toml` — Poetry config, Python 3.12

## Architecture Decision Records

- ADR-001: No training in pre-pilot (retrieval only, local GGUF via llama.cpp)
- ADR-002: SQLite as system of record
- ADR-003: Claims as first-class records
- ADR-004: Truth-status awareness (fact / belief / interpretation / rumor)
- ADR-005: Relationships modeled from the start
- ADR-006: Scope limited to Covenant of Varkaar until eval criteria met
- ADR-007: No lore expansion during extraction
- ADR-008: Multi-environment configuration and platform-aware model selection

## Functional Requirements (FR-001–010)

Covers: source ingestion, chunk storage, entity catalog, claim extraction, claim
classification, relationship storage, retrieval, grounded answering, evaluation set,
evaluation results.

## Design Choices

- Claim-based extraction: lore stored as discrete, source-quoted, traceable claims
- Human review loop before DB load
- Eval-driven: testing schema with failure categories
- Retrieval: keyword search or embedding + cosine; no vector DB yet
- MVP: 20–30 documents, ~100–200 reviewed claims, 10 eval questions (Varkaar only)

## Workstation Setup (ADR-008)

Two machines in active use:

- **Dell Linux laptop** (Ubuntu) — primary dev/test workstation, CPU-only inference
- **Apple M2 Pro Mac** (music studio) — target runtime, Metal GPU inference

Model files stored at `~/models/` on each machine (never in Dropbox / project dir).

| Machine | Model               | Quant  | `LLAMA_N_GPU_LAYERS` |
| ------- | ------------------- | ------ | -------------------- |
| M2 Pro  | Qwen2.5-7B-Instruct | Q4_K_M | -1 (all to Metal)    |
| Dell    | Qwen2.5-3B-Instruct | Q4_K_M | 0 (CPU only)         |

`env.local` (gitignored) is the authoritative per-machine config.
No platform detection logic in application code.

## Current Status (as of 2026-04-02)

**Completed:** GitHub repo, scaffolding, ADRs (8), NFRs (5), FRs (10+),
SQLite DB + Alembic migrations, full R2 ingestion pipeline (`ingest` CLI). Version: v0.2.1.

**In progress:** R3 — LLM extraction. Environment setup underway on both machines.

### R3 environment setup

| Machine | llama-cpp-python | Model | Status |
| --- | --- | --- | --- |
| Apple M2 Pro (macOS) | Installed via Poetry | Qwen2.5-7B-Instruct-Q4_K_M | Installed, verified ✓ |
| Dell laptop (Linux) | Installed via Poetry | Qwen2.5-?B-Instruct-Q4_K_M | Verify model size/name |

### Changes made this session (2026-04-02)

- ADR-008 created: multi-environment config and platform-aware model selection
- NFR-001 updated: references two-workstation setup and ADR-008
- `env.example` updated: documents `LOCAL_MODEL_PATH` / `LLAMA_N_GPU_LAYERS`,
  notes these are auto-set by `setenv.sh`
- `scripts/setenv.sh` updated: detects platform via `uname -s` after sourcing env
  file; sets `LOCAL_MODEL_PATH` and `LLAMA_N_GPU_LAYERS` automatically.
  Model filenames live in `_MAC_MODEL` / `_LINUX_MODEL` vars at top of script.
  Verified working on Mac (Darwin → 7B model, gpu_layers=-1).
- `docs/guides/reference.md` reorganized alphabetically with TOC
- `docs/design/pull_requests/r3_extraction/design.md` updated: status → In Progress,
  environment setup progress table added, changes logged

**Next steps (Linux session):**

1. Verify Linux model filename and size (`ls ~/models/`) — update `_LINUX_MODEL`
   in `scripts/setenv.sh` if needed
2. Smoke-test `source scripts/setenv.sh` on Linux
3. Build `saskan_lore/analyzer/inference.py` — single `complete()` function
   wrapping llama-cpp-python, reads `LOCAL_MODEL_PATH` and `LLAMA_N_GPU_LAYERS`
   from environment

## Known Issues

- Entity naming inconsistencies in source docs
- Timeline inconsistencies in source docs

**Why:** Learning exercise to build disciplined, inspectable lore representation before
scaling up.

**How to apply:** Frame suggestions around the pipeline stages and claim-based data model.
Prioritize Varkaar Covenant scope for MVP. Mac is target runtime; Linux is dev/test.
