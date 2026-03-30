# R2 Ingestion — Test Cases

Status: **Complete** — all 10 tests passing

---

## Scope

Unit tests for the R2 ingestion layer: document registration
(`register_lore_text.py`) and chunk persistence (`load_chunks.py`).

All tests use an in-memory SQLite engine with FK pragma enabled.
Test module: `tests/unit/r2_ingestion/test_r2_ingestion.py`
Shared fixture: `tests/conftest.py::db_session`

---

## Test Cases

| ID | Test function | What it verifies | Status |
| --- | --- | --- | --- |
| TC-R2-01 | `test_register_document_inserts` | New document inserted with correct title, path, scope, and 64-char content_hash | Pass |
| TC-R2-02 | `test_register_document_idempotent_by_path` | Same source_path on second call returns existing record; count stays at 1 | Pass |
| TC-R2-03 | `test_register_document_idempotent_by_hash` | Different path, same file content returns existing record (content_hash match) | Pass |
| TC-R2-04 | `test_register_document_invalid_scope` | Scope outside allowed set raises `ValueError` | Pass |
| TC-R2-05 | `test_register_document_missing_file` | Non-existent source_path raises `FileNotFoundError` | Pass |
| TC-R2-06 | `test_load_chunks_sequence` | Chunks stored with monotonically increasing sequence starting at 0 | Pass |
| TC-R2-07 | `test_load_chunks_text_verbatim` | Stored chunk texts match `chunk_text()` output exactly | Pass |
| TC-R2-08 | `test_load_chunks_idempotent` | Second call on fully-chunked document returns 0 and does not add chunks | Pass |
| TC-R2-09 | `test_load_chunks_partial_recovery` | Partial chunk set is deleted and replaced with complete set on re-run | Pass |
| TC-R2-10 | `test_load_chunks_return_value` | Return value equals number of chunks stored, matching `chunk_text()` count | Pass |

---

## Requirements Coverage

| Test | FR / NFR / ADR |
| --- | --- |
| TC-R2-01 | FR-001 (document registration fields) |
| TC-R2-02 | FR-001 (idempotent registration by path) |
| TC-R2-03 | FR-001 (idempotent registration by content) |
| TC-R2-04 | ADR-006 (scope guard) |
| TC-R2-05 | NFR-001 (local files only; path must exist) |
| TC-R2-06 | FR-002, NFR-003 (chunks ordered, sequence for traceability) |
| TC-R2-07 | FR-002 (chunk text stored verbatim) |
| TC-R2-08 | FR-002 (idempotent chunking) |
| TC-R2-09 | FR-002, NFR-005 (partial-failure recovery without manual intervention) |
| TC-R2-10 | FR-002 (chunk count correctness) |

---

## Run Results

| Date | Command | Result |
| --- | --- | --- |
| 2026-03-30 | `poetry run pytest tests/unit/r2_ingestion/test_r2_ingestion.py -v` | 10 passed in 0.14s |

---

## Notes

- `register_document` reads raw PDF bytes from disk to compute the content hash.
  Tests use `tmp_path` (pytest built-in) to create small fake source files — no real
  PDFs needed at unit test level.
- `load_chunks` receives plain text directly; no PDF extraction in these tests.
- TC-R2-03 relies on two fixture files with identical byte content but different paths.
- TC-R2-09 simulates partial failure by inserting one chunk directly, bypassing
  `load_chunks`, then verifying that a subsequent `load_chunks` call replaces it.
