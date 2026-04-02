# Release 6: Evaluation

Status: **Pending R5**

## Objective

Load a set of evaluation questions with expected answers, run each question through the
retrieval + answering pipeline, record results, and produce a summary report. This is the
MVP graduation check: the system is done when it answers 10 Varkaar questions correctly
using retrieval.

---

## Deliverables

- `saskan_lore/loader/load_eval_questions.py` — insert evaluation questions and expected answers
- `saskan_lore/analyzer/evaluate.py` — run an evaluation pass, record results per question
- `data/eval/varkaar_questions.json` — the 10 evaluation questions for the Varkaar domain
- CLI command: `saskan-lore evaluate` (runs all questions, records results)
- CLI command: `saskan-lore eval-summary` (prints pass rate and failure breakdown)

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| FR-008 | Eval question storage, per-run result recording, failure analysis |
| ADR-006 | Graduation criteria: 10 questions answered, evidence included |
| NFR-003 | Results include retrieved evidence (claim IDs) per answer |
| Workflow Stage 6 | Evaluation: retrieve evidence, generate answer, record result |
| `data/schema/testing_schema.json` | Result schema: question, expected, model answer, pass/fail, failure type |

---

## Design Notes

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

Write 10 questions that are directly answerable from loaded Varkaar claims. Questions
should cover a range of entity types, relationship types, and truth statuses. Include at
least one question where the expected answer is a `belief` or `interpretation`, not only
`fact`, to test that truth-status filtering does not over-restrict retrieval.

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
            pass_fail=None,          # set by human review
            failure_type=None,
            notes=None,
            run_at=datetime.utcnow(),
        )
        session.add(record)
    session.commit()
    return results
```

### Grading (MVP: manual)

In the pre-pilot, pass/fail is set by the human reviewer, not automatically. After
`evaluate` runs, the reviewer reads each `model_answer`, compares to `expected_answer`,
and updates `pass_fail` and `failure_type` directly in the DB or via a simple CLI helper.

Failure types (from `testing_schema.json`):

| Type | Meaning |
| --- | --- |
| `wrong_fact` | Answer states something factually incorrect |
| `hallucination` | Answer introduces content not in retrieved context |
| `incomplete` | Answer is correct but missing important detail |
| `style` | Answer is factually correct but poorly phrased |

Automated grading (e.g., exact match or embedding similarity against expected answer)
is a future improvement — do not implement in this release.

### Summary report

```txt
Evaluation summary — Varkaar domain
Run: 2026-04-01 14:22

Total questions:  10
Pass:              7  (70%)
Fail:              3

Failures by type:
  wrong_fact:     1
  hallucination:  1
  incomplete:     1
```

Produce this from a simple query against `eval_results` joined to `eval_questions`.

### MVP graduation check

From ADR-006 and STATUS.md: the pre-pilot is complete when all of the following are true:

- 20–30 documents ingested
- ~100–200 reviewed claims loaded
- 10 evaluation questions defined and answered using retrieval
- Every answer includes supporting evidence

The evaluation summary report is the artifact that confirms graduation.

---

## Testability Considerations

- Test that `run_evaluation()` creates one `EvalResult` record per question.
- Test that each result includes a non-empty `retrieved_evidence` field (even if empty list).
- Test that `pass_fail` is `None` after an automated run (requires human grading).
- Test the summary query: given known pass/fail values, verify the counts are correct.
- Test that failure_type is validated as one of the four allowed values when set.

---

## Acceptance Criteria

- 10 evaluation questions loaded for the Varkaar domain.
- Running `saskan-lore evaluate` produces one `EvalResult` record per question.
- Each result includes the model answer and the list of claim IDs used as evidence.
- `eval-summary` prints pass rate and failure type breakdown.
- After human grading, the system demonstrates at least passing quality on the majority
  of questions (target: 7/10 pass) to meet MVP graduation criteria.
