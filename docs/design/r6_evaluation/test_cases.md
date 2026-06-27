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

---

## System Acceptance Test (Linux — partial run)

**Date:** 2026-04-03 to 2026-04-04
**Platform:** Dell XPS 13, Ubuntu Linux, Intel i7-1165G7, 16GB RAM, CPU-only inference
**Model:** Qwen2.5-3B-Instruct-Q4_K_M.gguf, `gpu_layers=0`
**Reference:** `docs/design/r6_evaluation/system_test.md`
**Export:** `docs/design/r6_evaluation/eval_export_20260404_163644.json`

### Results summary

| Phase | Result |
| --- | --- |
| 1 — DB init | Pass |
| 2 — Ingest (1210 chunks) | Pass |
| 3 — Extraction (323/1210 chunks) | Pass — stopped after 12 hours; 0 errors |
| 4 — Human review (150 files) | Pass — 191 approved claims |
| 5 — Load | Pass — 191 claims, 205 entities, 179 links loaded |
| 6a — Load eval questions | Pass — 10 questions, idempotent |
| 6b — Run evaluation | Pass — 10 results written |
| 6c — Human grading | Pass — all 10 graded |
| 6d — Eval summary | 1/10 pass (10%) — below graduation threshold |
| 7 — Export and reset | Pass — results exported; DB wiped and reinitialized |

### Grading detail

| Question | Result ID | Grade | Failure type | Notes |
| --- | --- | --- | --- | --- |
| q_001 — How many provinces are full members? | 1 | fail | incomplete | No matching claims retrieved |
| q_002 — When did Eelan accept protection? | 2 | fail | incomplete | No matching claims retrieved |
| q_003 — How does the Covenant function? | 3 | fail | incomplete | No matching claims retrieved |
| q_004 — What is the role of the Varkaar Council? | 4 | fail | incomplete | No matching claims retrieved |
| q_005 — What is the Great Ring Road? | 5 | **pass** | — | Correct substance; verbose/repetitive |
| q_006 — What are the Articles of Borded? | 6 | fail | incomplete | Evidence retrieved but too thin to answer |
| q_007 — In what era did the Eelani-Futanik War occur? | 7 | fail | incomplete | No matching claims retrieved |
| q_008 — What are the Ring Runners? | 8 | fail | incomplete | No matching claims retrieved |
| q_009 — What is the Varkaar Union? | 9 | fail | incomplete | Evidence retrieved; model hedged correctly |
| q_010 — What is the Cann of Borded? | 10 | fail | hallucination | Model said "Cann of Byenung"; correct name is "Cann of Borded" |

### Bugs found during acceptance run

Seven patch items identified (BL-019, BL-021 through BL-028). All code bugs fixed in
`v0.6.1` working tree. See `docs/design/backlog.md` for full details.

### Graduation status

**Not yet declared.** 1/10 pass is expected given partial extraction (323/1210 chunks).
The 8 `incomplete` failures are a data coverage problem, not a pipeline defect. The
`hallucination` on q_010 is a genuine model quality issue worth tracking on the Mac run.

---

## System Acceptance Test (macOS — complete)

**Date:** 2026-04-04 to 2026-06-27 (extraction on 04-04; review/load/eval resumed 06-27
after a multi-month gap, in small batches)
**Platform:** MacBook, Apple Silicon, Metal GPU, gpu_layers=-1
**Model:** Qwen2.5-7B-Instruct-Q4_K_M.gguf
**Reference:** `docs/design/r6_evaluation/system_test.md`
**Export:** `docs/design/r6_evaluation/eval_export_20260627_204423.json`

### Results summary

| Phase | Result |
| --- | --- |
| 1 — DB init | Pass |
| 2 — Ingest (1210 chunks) | Pass — matches Linux chunk count exactly |
| 3 — Extraction (1206/1210 chunks) | Pass — 4 errors (0.33%); full run ~2h42m at ~8s/chunk |
| 4 — Human review (227 claims) | Pass — 218 approved, 9 rejected; past the 100–200 target |
| 5 — Load | Pass — claims=227, entities=800, claim_entities=260 |
| 6a — Load eval questions | Pass — 10 questions, idempotent |
| 6b — Run evaluation | Pass — run twice (see Fixes below); final run = 10 results |
| 6c — Human grading | Pass — all 10 graded |
| 6d — Eval summary | **1/10 pass (10%)** — below graduation threshold |
| 7 — Export and reset | Pass — results exported; DB wiped and reinitialized |

### Grading detail (final, post-fix)

| Question | Result ID | Grade | Failure type | Notes |
| --- | --- | --- | --- | --- |
| q_001 — How many provinces are full members? | 11 | fail | incomplete | No matching claims retrieved |
| q_002 — When did Eelan accept protection? | 12 | fail | incomplete | Evidence confirms acceptance but not timing |
| q_003 — How does the Covenant function? | 13 | **pass** | — | Near-exact match after FTS5 stemming fix |
| q_004 — What is the role of the Varkaar Council? | 14 | fail | incomplete | No matching claims retrieved |
| q_005 — What is the Great Ring Road? | 15 | fail | incomplete | Evidence too thin |
| q_006 — What are the Articles of Borded? | 16 | fail | style | Evidence retrieved; answer loops/repeats (BL-029) |
| q_007 — In what era did the Eelani-Futanik War occur? | 17 | fail | incomplete | No matching claims retrieved |
| q_008 — What are the Ring Runners? | 18 | fail | incomplete | No matching claims retrieved |
| q_009 — What is the Varkaar Union? | 19 | fail | incomplete | Evidence too thin |
| q_010 — What is the Cann of Borded? | 20 | fail | incomplete | Evidence too thin |

### Fixes applied during macOS run (v0.6.2)

- `tabulate` added as runtime dependency to `pyproject.toml` — was missing; present on Linux
  only as a transitive dependency
- `nltk` and `pandas` removed from `pyproject.toml`/`poetry.lock` — both unused in code;
  `nltk` had an open high-severity Dependabot alert with no patched version available
- Four Dependabot dependency bumps applied directly: cryptography, idna, mako, pytest
  (pytest constraint relaxed `^8.3` → `>=8.3,<10.0`)
- `scripts/row_counts.py` — refactored with aligned column output
- `scripts/row_rounts.py` — deleted (typo duplicate of `row_counts.py`)
- `scripts/db_summary.py`, `scripts/show_eval_results.py` — new scripts
- `scripts/load_reviewed.sh` — pre-filters to files with ≥1 approved/rejected claim before
  invoking the loader; quiets log noise via `LOG_LEVEL=WARNING`
- **BL-032**: `claims_fts` FTS5 tokenizer had no stemming, causing exact-token AND matches
  to fail on simple inflection differences (e.g. "function" vs "functions"). Confirmed two
  questions (q_002, q_003) had zero evidence purely from this, despite an exact-match
  approved claim existing for each. Fixed via migration `0e99af659a1b` (porter stemmer);
  `evaluate()` was re-run after this fix, producing a second, corrected set of results.
- **BL-031**: `eval_summary()` and `export_results()` counted every `EvalResult` ever
  written with no "latest per question" filter, so re-running `evaluate()` after the
  BL-032 fix doubled the apparent question count. Fixed to consider only the latest
  result per question. `export-eval`'s default output path was also hardcoded to a
  relative `var/` path that landed inside the Dropbox-synced repo, bypassing the
  `SASKAN_VAR_DIR` scheme from BL-023 — fixed to read `SASKAN_VAR_DIR`.
- **BL-029** (found, not fixed): repetitive/looping model output on longer answers
  (q_006) — `inference.complete()` has no `repeat_penalty` or `stop` sequence override,
  and uses a raw completion prompt against an instruct-tuned model. Logged for a future
  iteration.
- **BL-030** (found, not fixed): sequential review order (chunk_0001 forward, stopping at
  the claim-count target) systematically under-covers later-document topics relative to
  the hand-written eval question set. The dominant cause of the low pass rate on both
  platforms. Logged for a future iteration.

### Graduation status

**Not pursued.** 1/10 pass on macOS, same numeric result as the Linux run, despite fixing
two real retrieval bugs (BL-031, BL-032) along the way. The remaining shortfall is BL-030
(review-sampling coverage), not a pipeline defect. Rather than chase 7/10 by reviewing
more of the corpus under the current architecture, the project concludes this
experimental cycle at `v0.6.2` ("MVP experiment completion") — a deliberate decision, with
a number of validated lessons to carry into a possible next iteration (see
`docs/design/r6_evaluation/design.md` Status, and the backlog).
