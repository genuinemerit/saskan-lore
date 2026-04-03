# Changelog

All notable changes are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.5.0] - 2026-04-03 — R5 Retrieval and Answering

### Added

- `saskan_lore/analyzer/retrieval.py` — `tokenize(query)`, `retrieve(query, session, top_n=3)`,
  `format_context(hits)`: FTS5 BM25 full-text search over approved claims; returns `RetrievalHit`
  list with `claim_id`, `claim_text`, `source_span`, `score`
- `saskan_lore/analyzer/answering.py` — `answer(question, session, top_n=3)`: retrieves hits,
  formats grounded context, calls `inference.complete()`, returns `AnswerResult` with answer and
  supporting claims
- `saskan_lore/analyzer/answer.txt` — grounded-answer prompt template; `{context}` + `{question}`
  placeholders; instructs model to cite only provided context
- `alembic/versions/c2d4a8f3e610_add_claims_fts.py` — Alembic migration: `claims_fts` FTS5
  content virtual table backed by `claims`; content synced via `load_reviewed.load_file()`
- `saskan-lore ask "<question>"` CLI command added to `loader/ingest.py`; inference import
  deferred to avoid model load on unrelated commands
- `docs/design/r5_retrieval/test_cases.md` — R5 test case register (TC-R5-01 through TC-R5-14)
- `docs/design/backlog.md` — BL-009 added (FTS5 manual re-sync utility)

### Changed

- `saskan_lore/data/schema/database_schema.py` renamed to `data_schema.py`; all import
  references updated across source, tests, and docs
- `saskan_lore/data/schema/data_schema.py` — `RetrievalHit` and `AnswerResult` frozen
  dataclasses added; `review_status` vocabulary (`pending` / `approved` / `rejected`)
  replaces prior `reviewed: bool` + `status: "rejected"` throughout staging structures
- `saskan_lore/data/schema/extract_schema.json` — updated to enforce `review_status='pending'`
  on extractor output (was `reviewed=false`); `truth_status` enum unchanged
- `saskan_lore/analyzer/extractor.py` — sets `review_status='pending'` at write time
- `saskan_lore/loader/review_staging.py` — sets `review_status='approved'` or `'rejected'`
- `saskan_lore/loader/load_reviewed.py` — reads `review_status`; triggers FTS5 content rebuild
  after each successful load commit
- `tests/conftest.py` — shared `db_session` fixture creates `claims_fts` FTS5 virtual table
  via raw SQL after `Base.metadata.create_all()`
- `docs/guides/user.md` — Stage 5 section added (`ask`, `retrieve`, `format_context`, `answer`);
  `review_status` vocabulary fixed throughout; broken relative links fixed; pipeline status updated
- `docs/guides/workflows.md` — retrieval approach updated to FTS5/BM25; test dirs listed
  explicitly
- `docs/guides/reference.md` — FTS5 entry expanded with BM25 explanation; Cosine Similarity
  entry added
- `README.md` — R4 and R5 status → Complete; description updated; `setenv.sh` usage fixed

### Tests

- `tests/unit/r5_retrieval/test_r5_retrieval.py` — 14 unit tests; all passing
  (TC-R5-01 through TC-R5-14); `llama_cpp` mocked via `sys.modules` in conftest
- `tests/unit/r3_extraction/test_r3_extraction.py` — updated for `review_status` vocabulary
- `tests/unit/r4_review_load/test_r4_review_load.py` — updated for `review_status` vocabulary
- Full suite: 54/54 passing

---

## [0.4.0] - 2026-04-03 — R4 Human Review and Load

### Added

- `saskan_lore/loader/review_staging.py` — `review_file()`: interactive per-claim
  review (approve / correct / reject / quit); writes back partial state on interrupt
  via try/finally; `reject_reason` stored as optional staging field; `print_summary()`
- `saskan_lore/loader/load_entities.py` — `load_entities()`: inserts Entity records
  from staging lists (places, characters, factions, key_events); returns name→id map;
  idempotent by `canonical_name`; `load_entity_aliases()`: stub, no-op for current
  staging format; ready for future alias data
- `saskan_lore/loader/load_relationships.py` — `load_relationships()`: inserts typed
  directed relationships; idempotent by `(source_id, target_id, relationship_type)`;
  no-op for current staging format (no relationship data); ready for future extension
- `saskan_lore/loader/load_reviewed.py` — `load_file()`: orchestrates full load
  sequence (entities → aliases → claims → claim-entity links → relationships); owns
  transaction commit; skip-and-log validation; `print_load_summary()`
- `saskan-lore review <staging-file>` CLI command added to `loader/ingest.py`
- `saskan-lore load <staging-file>` CLI command added to `loader/ingest.py`
- `docs/design/r4_review_load/test_cases.md` — R4 test case register
- `docs/design/backlog.md` — design backlog for deferred items, tech debt, and future
  design candidates (BL-001 through BL-008)

### Changed

- `saskan_lore/data/schema/data_schema.py` — `ExtractionClaimRecord.statement`
  renamed to `claim_text` to align staging field names with DB column names
- `saskan_lore/data/schema/extract_schema.json` — `statement` renamed to `claim_text`
  in claim schema; description updated to clarify this schema covers extractor output
  only; post-review files validated by loader in code
- `saskan_lore/loader/ingest.py` — `review` and `load` commands added; module
  docstring updated
- `docs/design/pull_requests/` directory removed; all release design docs lifted to
  `docs/design/r*/` via `git mv`; `pr_000_index.md` renamed `design_000_index.md`;
  all internal path references updated across source, tests, docs, and memory
- `docs/design/design_000_index.md` — release statuses updated; cross-reference table
  corrected (workflows and glossary paths); backlog entry added
- `docs/design/r4_review_load/design.md` — status → In Progress; Progress checklist
  added; design notes for staging schema boundary and `reject_reason` added
- `README.md` — status table updated through R4; models and hardware section added;
  current version noted; lore texts copyright notice added; `setenv.sh` in setup steps

### Tests

- `tests/unit/r4_review_load/test_r4_review_load.py` — 10 unit tests; all passing
  (TC-R4-01 through TC-R4-10)
- `tests/unit/r3_extraction/test_r3_extraction.py` — updated for `claim_text` rename
- Full suite: 40/40 passing

---

## [0.3.0] - 2026-04-02 — R3 Extraction Pipeline

### Added

- `saskan_lore/analyzer/inference.py` — `complete()`: single public interface to local GGUF
  model via llama.cpp; model loaded once at module level; env validation at import time;
  `LOCAL_MODEL_PATH` and `LLAMA_N_GPU_LAYERS` read from environment
- `saskan_lore/analyzer/extractor.py` — `extract_chunk()`: ChatML prompt formatting, scope
  guard (ADR-006), JSON parse and structural validation, staging file write; malformed
  responses saved as `_extraction_error.json`; `reviewed=False` injected at write time
- `saskan_lore/analyzer/staging.py` — staging area read utilities: `list_staging()`,
  `list_errors()`, `load_staging()`, `validate_staging()`, `load_for_document()`
- `saskan_lore/data/schema/extract_schema.json` — JSON Schema (draft 2020-12) for staging
  file validation; enforces `reviewed=false`, non-empty `source_span`, `truth_status` enum
- `saskan-lore extract` CLI command added to `loader/ingest.py` Typer app; accepts
  `--chunk-id` or `--document-id`; inference import deferred to avoid model load on
  unrelated commands
- `scripts/poetry_activate.sh` — activation helper (moved from `saskan_lore/tools/`)
- `saskan_lore/utils/` — utility modules promoted from `saskan_lore/tools/utils/`
  (`file_io.py`, `match_semver.py`, `platform.py`, `shell.py`, `stamps.py`)
- `docs/architecture/decisions/adr_008.md` — multi-environment config and platform-aware
  model selection (Darwin: Metal/gpu_layers=-1; Linux: CPU/gpu_layers=0)
- `docs/design/r3_extraction/test_cases.md` — R3 test case register
- `docs/guides/reference.md` — MagicMock and monkeypatch (pytest) glossary entries added
- `docs/guides/workflows.md` — updated to reflect `var/` paths and R3 test structure

### Changed

- `saskan_lore/loader/ingest.py` — `add_completion=False` on Typer constructor (removes
  `--install-completion` / `--show-completion` from help output)
- `scripts/setenv.sh` — platform auto-detection sets `LOCAL_MODEL_PATH` and
  `LLAMA_N_GPU_LAYERS` after sourcing env file; model filenames configurable at top of script
- `saskan_lore/infra/config/env.example` — updated with platform-specific model config;
  OpenAI section retained as documentation only
- Root `data/` directory renamed to `var/` (runtime artifacts: DB, reviewed staging);
  `saskan_lore/data/` (package assets: models, schema, lore texts) unchanged
- `.gitignore` — `/data/reviewed/` entry updated to `/var/reviewed/`

### Removed

- `saskan_lore/tools/` — directory removed; utilities moved to `saskan_lore/utils/`
- `saskan_lore/tools/poetry_activate` — replaced by `scripts/poetry_activate.sh`

### Tests

- `tests/unit/r3_extraction/test_r3_extraction.py` — 10 unit tests; all passing
  (TC-R3-01 through TC-R3-10); `llama_cpp` mocked via `sys.modules` in conftest
- Full suite: 30/30 passing

---

## [0.2.0] - 2026-03-30 — R2 Ingestion Pipeline

### Added

- `saskan_lore/loader/register_lore_text.py` — `register_document()`: registers a lore
  source PDF in the database with scope guard, SHA-256 content hash, and dual idempotence
  check (source_path or content_hash)
- `saskan_lore/loader/load_chunks.py` — `load_chunks()`: splits plain text into chunks and
  persists them; count-based idempotence guard handles partial-failure recovery
- `saskan_lore/loader/ingest.py` — `saskan-lore ingest` Typer CLI command: PDF text
  extraction (pdfminer.six), whitespace normalisation, registration, chunking, and
  structured logging; clean error messages and non-zero exit on failure
- `pdfminer-six` runtime dependency added
- `[tool.poetry.scripts]` entry in `pyproject.toml`: `saskan-lore` CLI wired to
  `saskan_lore.loader.ingest:app`
- `docs/design/r2_ingestion/test_cases.md` — R2 test case register
- `docs/guides/user.md` — new user guide documenting public function call patterns
- `docs/design/reference.md` — Typer and pdfminer.six entries added

### Changed

- `docs/design/r2_ingestion/design.md` — finalised design decisions:
  pdfminer.six chosen, content_hash dual-check, range-selection rationale, CLI notes
- `.markdownlint.json` — MD013 line_length set to 100 (matching Python and editorconfig)

### Removed

- `saskan_lore/loader/load_metadata.py` — early stub replaced by the above modules

### Tests

- `tests/unit/r2_ingestion/test_r2_ingestion.py` — 10 unit tests; all passing
  (TC-R2-01 through TC-R2-10)
- Full suite: 20/20 passing

---

## [0.1.3] - 2026-03-30

### Changed

- `LICENSE` — added explicit carve-out for lore source documents in `data/lore_texts/`
- `saskan_lore/data/lore_texts/COPYRIGHT` — new All Rights Reserved notice covering the
  six SaskanCanon PDF source documents; excluded from the MIT license
- Repository visibility changed from private to public

---

## [0.1.2] - 2026-03-30

### Changed

- `pyproject.toml` — bumped black dev dependency from `^24.8` to `^26.3`; resolves
  Dependabot security alert (arbitrary file writes via unsanitized cache filename)

---

## [0.1.1] - 2026-03-30

### Removed

- `matplotlib` removed from the `analytics` extra dependency; eliminates transitive
  Pillow vulnerability flagged by Dependabot

---

## [0.1.0] - 2026-03-30 — R1 Database Layer

### Added

- `saskan_lore/data/models.py` — SQLAlchemy ORM models for all 9 tables with `TimestampMixin`
  (`is_active`, `created_at`, `updated_at`), indexes, unique constraints, and FK constraints
- `saskan_lore/infra/db/db.py` — engine singleton, `get_session()` context manager,
  SQLite FK pragma hook, `reset_engine()` for test fixtures
- `saskan_lore/infra/db/dba.py` — DB admin/reporting utilities: `summary()`, `row_counts()`,
  `inactive_counts()`, `check_schema()`, `table_info()`, `show_rows()`, `alembic_version()`,
  `db_size()`
- `saskan_lore/infra/db/init_db.py` — one-shot DB initialisation via `alembic upgrade head`
- `alembic/` — Alembic configuration, initial schema migration, and FK constraint migration
- `var/saskan_lore.db` — local SQLite DB (gitignored); created and validated in DBeaver
- `tests/conftest.py` — shared pytest fixture: in-memory SQLite, StaticPool, FK pragma ON
- `tests/unit/r1_database/test_r1_db.py` — 10 unit tests covering schema structure, column
  defaults, nullability, unique constraints, FK enforcement, and full insert chain
- `tests/fixtures/`, `tests/output/` — test data directories
- `scripts/commit.sh`, `scripts/release.sh` — git commit and release automation scripts
- `docs/design/r1_database/test_cases.md` — R1 test case register
- `.pre-commit-config.yaml` — pre-commit hooks: black (formatting) and ruff (linting)

### Changed

- `pyproject.toml` — added `ruff` dev dependency; added pytest markers (`unit`, `integration`);
  activated semantic versioning starting at `v0.1.0`
- `saskan_lore/analyzer/character_counter.py` — promoted bare stub code to a proper function
- `docs/design/workflows.md` — added Testing and Version Control sections

---

## [Pre-release] - 2026-03-30

### Added

- Repo structure and Python package scaffolding (`saskan-lore/saskan_lore/`)
- `pyproject.toml` — Poetry, Python 3.12, all dependencies declared
- Design docs: `workflows.md`, `reference.md`
- ADR-001 through ADR-007 — architecture decisions
- FR-001 through FR-008 — functional requirements
- NFR-001 through NFR-005 — non-functional requirements
- Release design docs: R0 through R6
- Database design sketch: `data/schema/database_schema.py`
- Prompt templates: `analyzer/extract_claims.txt`, `analyzer/structure_claims_metadata.txt`
- `analyzer/chunker.py` — sentence-aware, reproducible text chunker
- `analyzer/extractor.py` — LLM-based claim extraction and structuring
- Utility modules: `utils/platform.py`, `utils/stamps.py`,
  `utils/file_io.py`, `utils/shell.py`, `utils/match_semver.py`
- Six PDF lore source texts added to `data/lore_texts/`
