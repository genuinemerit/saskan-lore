# R3 Extraction — Test Cases

Status: **Complete** — all 10 tests passing

---

## Scope

Unit tests for the R3 extraction pipeline: `inference.py` (mocked), `extractor.py`,
and `staging.py`.

All extraction tests mock `complete()` to return fixture JSON strings — no GGUF model
is loaded during the test run. The `llama_cpp` module is replaced in `sys.modules` by
the R3 conftest before any test module is imported.

Test module: `tests/unit/r3_extraction/test_r3_extraction.py`
R3 conftest: `tests/unit/r3_extraction/conftest.py`
Shared fixture: `tests/conftest.py::db_session`

---

## Test Cases

| ID | Test function | What it verifies | Status |
| --- | --- | --- | --- |
| TC-R3-01 | `test_extract_chunk_success` | Well-formed model response produces a staging file with correct top-level fields | Pass |
| TC-R3-02 | `test_extract_chunk_reviewed_always_false` | `reviewed=False` is injected at write time even if the model response includes `reviewed=True` | Pass |
| TC-R3-03 | `test_extract_chunk_invalid_json` | Non-JSON model response produces `_extraction_error.json`; no exception raised | Pass |
| TC-R3-04 | `test_extract_chunk_missing_fields` | Valid JSON missing required fields produces `_extraction_error.json`; no exception raised | Pass |
| TC-R3-05 | `test_extract_chunk_out_of_scope` | Chunk whose parent document has scope != 'varkaar' returns None; no file written | Pass |
| TC-R3-06 | `test_list_staging_excludes_errors` | `list_staging()` returns success files only; error files are excluded | Pass |
| TC-R3-07 | `test_list_errors_only` | `list_errors()` returns error files only; success files are excluded | Pass |
| TC-R3-08 | `test_validate_staging_valid` | `validate_staging()` returns an empty list for a well-formed staging record | Pass |
| TC-R3-09 | `test_validate_staging_invalid` | `validate_staging()` returns error strings for a record missing required claim fields | Pass |
| TC-R3-10 | `test_load_for_document` | `load_for_document()` returns only valid records matching the given document_id; invalid and mismatched files are excluded | Pass |

---

## Requirements Coverage

| Test | FR / NFR / ADR |
| --- | --- |
| TC-R3-01 | FR-003, FR-004 (entities and claims in staging output) |
| TC-R3-02 | NFR-004 (human review gate; reviewed=false until R4) |
| TC-R3-03 | FR-004 (malformed output preserved, not silently dropped) |
| TC-R3-04 | FR-004, NFR-003 (structural validation; missing fields rejected) |
| TC-R3-05 | ADR-006 (scope guard; only varkaar chunks extracted) |
| TC-R3-06 | NFR-003 (staging files inspectable and separable by status) |
| TC-R3-07 | NFR-003 (error files separately listable for review) |
| TC-R3-08 | NFR-003 (extract_schema.json validates correct staging records) |
| TC-R3-09 | NFR-003 (extract_schema.json rejects records violating traceability rules) |
| TC-R3-10 | FR-003, FR-004 (per-document staging retrieval for R4 load) |

---

## Run Results

| Date | Command | Result |
| --- | --- | --- |
| 2026-04-02 | `poetry run pytest tests/unit/r3_extraction/test_r3_extraction.py -v` | 10 passed in 0.14s |

---

## Notes

- `llama_cpp` is replaced in `sys.modules` in `conftest.py` before any test imports,
  so `inference.py` never attempts to load a real model file.
- `complete()` is patched per-test via `unittest.mock.patch` to return controlled
  fixture strings.
- `REVIEWED_DIR` is set to a `tmp_path` subdirectory via `monkeypatch` in each
  extraction test — no writes to the real `var/reviewed/` directory during tests.
- DB fixtures (Document, Chunk) are created in the shared in-memory `db_session`.
