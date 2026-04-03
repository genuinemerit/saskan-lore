# R6 Test Cases

## Unit Tests

**File:** `tests/unit/r6_evaluation/test_r6_evaluation.py`

15 tests. All pass.

| ID | Function | Description |
| --- | --- | --- |
| TC-R6-01 | `load_eval_questions` | Loads all entries from a valid JSON file; DB count matches |
| TC-R6-02 | `load_eval_questions` | Idempotent: second load skips all entries, inserts none |
| TC-R6-03 | `load_eval_questions` | `question_id` is the idempotence key; same ID from two loads is skipped |
| TC-R6-04 | `load_eval_questions` | Raises `ValueError` when file fails `testing_schema.json` validation |
| TC-R6-05 | `run_evaluation` | Creates exactly one `EvalResult` per active question |
| TC-R6-06 | `run_evaluation` | `pass_fail` and `failure_type` are `None` on all new results |
| TC-R6-07 | `run_evaluation` | `retrieved_evidence` is a valid JSON-encoded list on every result |
| TC-R6-08 | `run_evaluation` | Returns `[]` and writes no records when no questions exist |
| TC-R6-09 | `grade_result` | Sets `pass_fail`, `failure_type`, and `notes` correctly on a result |
| TC-R6-10 | `grade_result` | Raises `ValueError` when `pass_fail` is not `"pass"` or `"fail"` |
| TC-R6-11 | `grade_result` | Raises `ValueError` for an unrecognised `failure_type` value |
| TC-R6-12 | `grade_result` | Raises `ValueError` when `result_id` does not exist |
| TC-R6-13 | `eval_summary` | Returns correct `passed`, `failed`, `ungraded`, and `failures` counts |
| TC-R6-14 | `eval_summary` | Ungraded results increment `ungraded`, not `passed` or `failed` |
| TC-R6-15 | `export_results` | Writes a valid JSON file with one entry per result, joined to question |

---

## Integration Tests

**File:** `tests/integration/test_r6_integration.py`

**Fixture:** `tests/fixtures/synthetic_lore.txt` — 5-sentence synthetic text used as a
stand-in for a real lore PDF.

**Mocks:** `inference.complete()` (returns a controlled staging JSON with IDs parsed from
the prompt string); `answering.answer()` (returns a fixed `AnswerResult`). No GGUF model
required. All DB operations, file I/O, and FTS5 indexing run against real code.

8 tests across two parts. All pass.

### Part A — Ingest to load

| ID | Test | Description |
| --- | --- | --- |
| TC-R6-INT-A1 | `test_a1_register_and_chunk` | `register_document()` and `load_chunks()` populate `documents` and `chunks` tables |
| TC-R6-INT-A2 | `test_a2_extract_writes_staging_files` | `extract_chunk()` with mocked inference writes one staging file per chunk, no error files |
| TC-R6-INT-A3 | `test_a3_load_approved_claims_into_db` | After approving staging files, `load_file()` inserts approved claims into the DB |
| TC-R6-INT-A4 | `test_a4_fts5_index_populated_after_load` | FTS5 index contains the loaded claims; keyword query returns results |

### Part B — Questions, evaluate, grade, summary, export

| ID | Test | Description |
| --- | --- | --- |
| TC-R6-INT-B1 | `test_b1_load_eval_questions` | `load_eval_questions()` inserts questions and is idempotent on a second call |
| TC-R6-INT-B2 | `test_b2_run_evaluation_creates_results` | `run_evaluation()` creates one `EvalResult` per question with `pass_fail=None` and correct `retrieved_evidence` |
| TC-R6-INT-B3 | `test_b3_grade_and_summary` | `grade_result()` and `eval_summary()` return correct pass/fail/failure counts end-to-end |
| TC-R6-INT-B4 | `test_b4_export_produces_valid_json` | `export_results()` writes all results joined to questions with correct field values |
