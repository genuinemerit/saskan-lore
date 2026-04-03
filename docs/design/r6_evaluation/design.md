# Release 6: Evaluation

Status: **In Progress**

## Objective

Validate the full pipeline end-to-end against real Varkaar lore data and confirm MVP
graduation criteria are met. R6 has two distinct tracks running in sequence:

1. **Code track** — evaluation infrastructure: load questions, run the pipeline against
   them, grade results, summarise, and export.
2. **Acceptance track** — live run of the entire pipeline from ingest to eval-summary
   using real Varkaar PDFs, followed by graduation and system reset.

R6 ends with two tagged releases: `v0.6.0` (code complete) and `v1.0.0` (graduated,
reset, MVP complete).

---

## Deliverables

### Code

- `alembic/versions/<id>_add_eval_question_id.py` — adds `question_id` string column
  (unique, not null) to `eval_questions`
- `saskan_lore/data/schema/data_schema.py` — `EvalQuestionRecord` and `EvalResultRecord`
  frozen dataclasses added
- `saskan_lore/data/schema/testing_schema.json` — JSON Schema validating
  `varkaar_questions.json` input format
- `saskan_lore/data/eval/varkaar_questions.json` — 10 Varkaar evaluation questions
  (written by human; committed asset)
- `saskan_lore/loader/load_eval_questions.py` — `load_eval_questions(session, path)`:
  reads JSON, inserts `EvalQuestion` records; idempotent by `question_id`
- `saskan_lore/analyzer/evaluate.py` — `run_evaluation(session)` and `eval_summary(session)`
- Five CLI commands added to `loader/ingest.py` Typer app:
  - `saskan-lore load-eval-questions` — loads `varkaar_questions.json` into DB
  - `saskan-lore evaluate` — runs all Varkaar questions, writes `EvalResult` records
  - `saskan-lore grade <result-id> pass|fail [--type TYPE] [--notes TEXT]`
  - `saskan-lore eval-summary` — prints pass rate and failure breakdown
  - `saskan-lore export-eval [output-path]` — exports all results to JSON

### Tests

- `tests/unit/r6_evaluation/test_r6_evaluation.py` — unit tests (TC-R6-01 onward)
- `tests/integration/test_r6_integration.py` — full pipeline integration test using
  committed synthetic fixture (no GGUF model; inference mocked)

### Docs

- `docs/design/r6_evaluation/system_test.md` — system acceptance test plan and checklist

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| FR-008 | Eval question storage, per-run result recording, failure analysis |
| ADR-006 | Graduation criteria: 10 questions answered, evidence included, 7/10 pass |
| NFR-003 | Results include retrieved evidence (claim IDs) per answer |
| Workflow Stage 6 | Evaluation: retrieve evidence, generate answer, record result |
| `data/schema/testing_schema.json` | Validates `varkaar_questions.json` input |

---

## Design Notes

### Schema addition: `question_id` string column

`EvalQuestion` gains a `question_id` string column (e.g. `"q_001"`) with a unique
constraint. This provides a stable human-readable identifier independent of the integer
PK. Added via Alembic migration. The `varkaar_questions.json` loader uses `question_id`
for idempotence.

### Evaluation question format (`varkaar_questions.json`)

```json
[
  {
    "question_id": "q_001",
    "question_text": "What punishment did the Covenant prescribe for oath-breaking?",
    "expected_answer": "Death, under Covenant law.",
    "scope": "varkaar"
  }
]
```

File location: `saskan_lore/data/eval/varkaar_questions.json` (committed package asset).
Written by the human worldbuilder based on direct knowledge of lore texts — not derived
from model extraction. Scope always `"varkaar"` for this release.

Write 10 questions covering a range of entity types, relationship types, and truth
statuses. Include at least one question where the expected answer is a `belief` or
`interpretation`, not only `fact`, to confirm truth-status filtering does not
over-restrict retrieval.

`testing_schema.json` validates this format before loading.

### `testing_schema.json`

JSON Schema (draft 2020-12) validating `varkaar_questions.json`. Enforces: array of
objects; each object has `question_id` (non-empty string), `question_text` (non-empty
string), `expected_answer` (non-empty string), `scope` (enum: `"varkaar"`); no
additional properties. Schema location: `saskan_lore/data/schema/testing_schema.json`.

### `EvalQuestionRecord` and `EvalResultRecord` dataclasses

Defined in `saskan_lore/data/schema/data_schema.py` alongside existing staging and
query result types. Used in the loader and evaluator for typed intermediate values.

### Evaluation loop

```python
def run_evaluation(session: Session) -> list[EvalResult]:
    questions = session.query(EvalQuestion).filter_by(scope="varkaar").all()
    results = []
    for q in questions:
        result = answer(q.question_text, session)
        record = EvalResult(
            question_id=q.id,
            model_answer=result.answer or "",
            retrieved_evidence=json.dumps([h.claim_id for h in result.hits]),
            pass_fail=None,       # set by human via `saskan-lore grade`
            failure_type=None,
            notes=None,
            run_at=datetime.utcnow(),
        )
        session.add(record)
    session.commit()
    return results
```

### Grading

```txt
saskan-lore grade <result-id> pass
saskan-lore grade <result-id> fail --type hallucination --notes "Invented a council name"
```

Valid `--type` values: `wrong_fact`, `hallucination`, `incomplete`, `style`.
`pass_fail` and `failure_type` are `None` after the automated run; grading sets them.
Grading is one result at a time; run `eval-summary` after all 10 are graded.

### Summary report

```txt
Evaluation summary — Varkaar domain
Run: 2026-04-03 14:22

Total questions:  10
Pass:              7  (70%)
Fail:              3

Failures by type:
  wrong_fact:     1
  hallucination:  1
  incomplete:     1
```

### Export

`saskan-lore export-eval [output-path]` writes all `EvalResult` records (joined to
`EvalQuestion`) to a JSON file. Default path: `var/eval_export_<timestamp>.json`.
Export is the final step before the system reset.

### Failure types

| Type | Meaning |
| --- | --- |
| `wrong_fact` | Answer states something factually incorrect |
| `hallucination` | Answer introduces content not in retrieved context |
| `incomplete` | Answer is correct but missing important detail |
| `style` | Answer is factually correct but poorly phrased |

Automated grading (exact match or embedding similarity) is a future improvement — not
implemented in this release.

### MVP graduation check

From ADR-006: the pilot is complete when all of the following are true:

- 20–30 documents ingested
- ~100–200 reviewed claims stored
- 10 evaluation questions defined and answered using retrieval
- Every answer includes supporting evidence
- At least 7/10 questions pass human review

The `eval-summary` output is the graduation artifact.

---

## Integration Test

A full pipeline integration test runs in `tests/integration/test_r6_integration.py`
using a small committed synthetic fixture text (not a Varkaar PDF). Inference is mocked
throughout — the integration test validates pipeline wiring and data flow, not model
quality.

**Part A** — ingest to load:

1. Register a synthetic document
2. Load chunks from synthetic text
3. Extract (mocked inference returns a controlled staging JSON)
4. Programmatically approve all claims (bypass interactive review)
5. Load reviewed staging into DB; verify claims in DB and FTS5 index

**Part B** — retrieve to evaluate:

1. Load a small set of synthetic eval questions
2. Retrieve against a known query; verify hits
3. Answer (mocked inference); verify `AnswerResult`
4. Run `run_evaluation()`; verify one `EvalResult` per question, `pass_fail=None`
5. Grade one result; verify `pass_fail` and `failure_type` set correctly
6. Run `eval_summary()`; verify counts

Integration test does not require `LOCAL_MODEL_PATH` or `LLAMA_N_GPU_LAYERS`.

---

## System Acceptance Test

Documented in `docs/design/r6_evaluation/system_test.md`. Uses `docs/guides/user.md`
as the workflow guide and `system_test.md` as the step-by-step checklist. Covers:

1. Fresh DB init (`alembic upgrade head`)
2. Ingest all Varkaar PDFs (`saskan-lore ingest`)
3. Extract all chunks (`saskan-lore extract`)
4. Review all staging files (`saskan-lore review`)
5. Load all reviewed staging (`saskan-lore load`)
6. Verify claim count (~100–200 approved)
7. Load eval questions (`saskan-lore load-eval-questions`)
8. Run evaluation (`saskan-lore evaluate`)
9. Grade all 10 results (`saskan-lore grade`)
10. Print summary (`saskan-lore eval-summary`) — target 7/10 pass

Any pipeline defects found during the acceptance run are fixed as `v0.6.x` patches
before declaring graduation.

---

## Testability Considerations

- Test that `run_evaluation()` creates one `EvalResult` per `EvalQuestion` (scope filter).
- Test that each result has `pass_fail=None` after automated run.
- Test that `retrieved_evidence` is a valid JSON string (even if empty list).
- Test `eval_summary()`: given known pass/fail values, verify counts and percentages.
- Test `grade()`: verify `pass_fail`, `failure_type`, and `notes` are written correctly.
- Test that `failure_type` is rejected if not one of the four allowed values.
- Test `load_eval_questions()` idempotence: loading the same JSON twice inserts each
  question only once (keyed on `question_id`).
- Test `testing_schema.json` validation: a malformed question object is rejected.

---

## Acceptance Criteria

- `question_id` string column exists on `eval_questions` with unique constraint.
- 10 Varkaar evaluation questions loaded into DB from `varkaar_questions.json`.
- `saskan-lore evaluate` produces one `EvalResult` per question with model answer and
  retrieved evidence.
- `saskan-lore grade` sets `pass_fail`, `failure_type`, and `notes` on a result.
- `saskan-lore eval-summary` prints pass rate and failure type breakdown.
- `saskan-lore export-eval` writes all graded results to JSON.
- Integration test passes with mocked inference (no GGUF model required).
- System acceptance test: 7/10 questions pass human grading against real Varkaar data.

---

## Versioning

- `v0.6.0` — code complete: all deliverables above committed, unit tests and integration
  test passing. Tagged before the system acceptance run begins.
- `v0.6.x` — patches applied for defects discovered during acceptance run.
- `v1.0.0` — graduation: acceptance run complete, 7/10 pass confirmed, eval results
  exported, `var/` wiped and DB reinitialized, system in pristine state.

---

## Release Sequence

### Phase 1 — Design ✓

- [x] Sequence agreed; design.md updated
- [x] `question_id` Alembic migration (`e7f3a2c91d40`)
- [x] `EvalQuestionInput`, `EvalQuestionRecord`, `EvalResultRecord` in `data_schema.py`
- [x] `testing_schema.json` created
- [x] `docs/design/r6_evaluation/system_test.md` written
- [x] `saskan_lore/data/eval/varkaar_questions.json` — 10 questions (written by Phoenix)
- [x] "pre-pilot" → "pilot" refactor across all docs and code
- [x] BL-018 added: configurable scope tags

### Phase 2 — Code ✓

- [x] `EvalQuestion` ORM model updated (`question_id` column)
- [x] `saskan_lore/loader/load_eval_questions.py`
- [x] `saskan_lore/analyzer/evaluate.py`
- [x] Five CLI commands in `loader/ingest.py`:
  `load-eval-questions`, `evaluate`, `grade`, `eval-summary`, `export-eval`

### Phase 3 — Unit tests ✓

- [x] `tests/unit/r6_evaluation/test_r6_evaluation.py` — 15 tests (TC-R6-01 through TC-R6-15)
- [x] `docs/design/r6_evaluation/test_cases.md` — test case register
- [x] Full suite: 77/77 passing

### Phase 4 — Integration test ✓

- [x] `tests/fixtures/synthetic_lore.txt` — synthetic fixture text
- [x] `tests/integration/conftest.py` — llama_cpp mock
- [x] `tests/integration/test_r6_integration.py` — 8 tests (Parts A and B)

### Phase 5 — Release v0.6.0

- [ ] CHANGELOG, commit, push, tag `v0.6.0`

### Phase 6 — System acceptance test

- [ ] Follow `system_test.md` against real Varkaar PDFs
- [ ] Apply `v0.6.x` patches as needed

### Phase 7 — Graduation and v1.0.0

- [ ] `saskan-lore export-eval` → save outside `var/`
- [ ] Wipe `var/saskan_lore.db` and `var/reviewed/`
- [ ] `alembic upgrade head` — reinitialize DB
- [ ] CHANGELOG, commit, push, tag `v1.0.0`
