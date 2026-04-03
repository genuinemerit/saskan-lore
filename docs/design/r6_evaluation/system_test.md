# R6 System Acceptance Test Plan

## Purpose

This document is the step-by-step checklist for the R6 system acceptance test. It covers
the full pipeline from a fresh database to a completed, human-graded evaluation. It is
intended to be followed after `v0.6.0` is tagged — any defects found here become `v0.6.x`
patches before graduation is declared.

Use `docs/guides/user.md` as the reference for all commands and function signatures.

---

## Prerequisites

- `v0.6.0` tagged and pushed.
- `var/saskan_lore.db` does not exist (fresh start) or has been wiped (see Phase 7).
- `var/reviewed/` is empty or does not exist.
- Environment variables loaded (`env.local`).
- GGUF model file present at `LOCAL_MODEL_PATH` (required for extract and ask/evaluate).

---

## Scope note

ADR-006 graduation criteria list "20–30 documents ingested." With the pilot scoped
strictly to `varkaar`, there is one eligible source document
(`SaskanCanon-VarkaarCovenant.pdf`). The operative graduation metric is **claim count**:
100–200 approved claims in the DB. Evaluate graduation against that target, not document
count.

---

## Phase 1 — Environment and database setup

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 1.1 | `source scripts/poetry_activate.sh` | Venv activated; prompt changes | ☐ |
| 1.2 | `source scripts/setenv.sh local` | `Environment loaded` message; `LOCAL_MODEL_PATH` and `LLAMA_N_GPU_LAYERS` set | ☐ |
| 1.3 | Confirm `var/saskan_lore.db` does not exist | `ls var/` shows no `.db` file | ☐ |
| 1.4 | `poetry run python -m saskan_lore.infra.db.init_db` | DB created; no errors | ☐ |
| 1.5 | Inspect DB schema: `dba.summary()` from Python shell | All expected tables present including `eval_questions`, `eval_results`, `claims_fts` | ☐ |
| 1.6 | `dba.alembic_version()` | Reports revision `e7f3a2c91d40` (latest) | ☐ |

---

## Phase 2 — Ingest

Source document: `saskan_lore/data/lore_texts/SaskanCanon-VarkaarCovenant.pdf`

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 2.1 | `poetry run saskan-lore ingest --path saskan_lore/data/lore_texts/SaskanCanon-VarkaarCovenant.pdf --title "Saskan Canon: Varkaar Covenant"` | Reports N chunks stored; no errors | ☐ |
| 2.2 | Run the same command again | Reports already ingested; no changes made | ☐ |
| 2.3 | `dba.row_counts()` | `documents=1`, `chunks=N` (record actual N) | ☐ |

Record actual chunk count: ______

---

## Phase 3 — Extraction

Extract all chunks for the ingested document. Document ID is `1` after a fresh ingest.

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 3.1 | `poetry run saskan-lore extract --document-id 1` | Runs all chunks; reports extracted/errors/skipped counts | ☐ |
| 3.2 | Inspect `var/reviewed/` | Contains one `_extraction.json` per successfully extracted chunk; any parse failures are `_extraction_error.json` | ☐ |
| 3.3 | Note error count; if > 5% of chunks, investigate before proceeding | Error rate acceptable | ☐ |

Record: extracted ______ / errors ______ / skipped ______

**If error files exist:** open a sample, read the raw model response, determine whether the
issue is a prompt problem, model quality issue, or chunk content (e.g. front matter, tables).
Document findings. Errors do not block proceeding — they are simply not reviewed or loaded.

---

## Phase 4 — Human review

Review each staging file in `var/reviewed/`. For each claim, choose Approve, Correct,
Reject, or Quit (to resume later). See `user.md` Stage 4 for key bindings and behaviour.

**Target: 100–200 approved claims.** If the document produces fewer than 100 usable claims,
review all of them. If it produces more, review until the target is reached.

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 4.1 | `poetry run saskan-lore review var/reviewed/<chunk_file>.json` (repeat for each file) | Each file reviewed; `review_status` set on all claims | ☐ |
| 4.2 | Review can be interrupted and resumed — confirm partial saves work correctly | Re-running skips already-decided claims | ☐ |
| 4.3 | After all files reviewed: count `approved` claims across all staging files | Count is in the 100–200 range | ☐ |

Record approved claim count across all staged files: ______

**Review discipline:**

- Approve a claim only if the `source_span` quote from the PDF directly supports `claim_text`.
- Reject if the model invented or misquoted content.
- Correct (C) + re-review if the claim is right in substance but poorly phrased — edit the
  JSON directly then run `review` again on that file.

---

## Phase 5 — Load

Load each reviewed staging file into the database. Only approved and rejected claims are
written; pending claims are skipped.

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 5.1 | `poetry run saskan-lore load var/reviewed/<chunk_file>.json` (repeat for each reviewed file) | Each file loads without errors; summary printed | ☐ |
| 5.2 | Run the same `load` command again on one file | Reports no duplicates; idempotent | ☐ |
| 5.3 | `dba.row_counts()` | `claims` row count matches expected approved + rejected total; `entities` populated | ☐ |
| 5.4 | Spot-check FTS5 index: `poetry run saskan-lore ask "Covenant of Varkaar"` | Returns an answer with at least one evidence claim | ☐ |

Record: claims in DB ______ (approved) ______ (rejected), entities ______

---

## Phase 6 — Evaluation

### 6a — Load evaluation questions

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 6.1 | `poetry run saskan-lore load-eval-questions` | Reports 10 questions loaded; no errors | ☐ |
| 6.2 | Run the same command again | Reports questions already loaded; no duplicates | ☐ |
| 6.3 | `dba.row_counts()` | `eval_questions=10` | ☐ |

### 6b — Run evaluation

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 6.4 | `poetry run saskan-lore evaluate` | Runs all 10 questions; writes 10 `EvalResult` records; prints result IDs and answers | ☐ |
| 6.5 | `dba.row_counts()` | `eval_results=10` | ☐ |
| 6.6 | Inspect each model answer against `expected_answer` in `varkaar_questions.json` | Record tentative pass/fail for each | ☐ |

### 6c — Human grading

For each of the 10 results, run the grade command. Use `dba.show_rows("eval_results", 10)`
or `saskan-lore eval-summary` to see result IDs.

```bash
poetry run saskan-lore grade <result-id> pass
poetry run saskan-lore grade <result-id> fail --type <wrong_fact|hallucination|incomplete|style> --notes "<note>"
```

| # | Question | Result ID | Grade | Failure type | Pass |
| --- | --- | --- | --- | --- | --- |
| 6.7 | q_001 — How many provinces are full members? | | | | ☐ |
| 6.8 | q_002 — When did Eelan accept protection? | | | | ☐ |
| 6.9 | q_003 — How does the Covenant function? | | | | ☐ |
| 6.10 | q_004 — What is the role of the Varkaar Council? | | | | ☐ |
| 6.11 | q_005 — What is the Great Ring Road? | | | | ☐ |
| 6.12 | q_006 — What are the Articles of Borded? | | | | ☐ |
| 6.13 | q_007 — In what era did the Eelani-Futanik War occur? | | | | ☐ |
| 6.14 | q_008 — What are the Ring Runners? | | | | ☐ |
| 6.15 | q_009 — What is the Varkaar Union? | | | | ☐ |
| 6.16 | q_010 — What is the Cann of Borded? | | | | ☐ |

### 6d — Summary

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 6.17 | `poetry run saskan-lore eval-summary` | Prints pass count, fail count, and failure type breakdown | ☐ |
| 6.18 | Pass count ≥ 7/10 | Graduation threshold met | ☐ |

**If pass count < 7:** investigate failures. If systemic (retrieval not finding relevant
claims, model hallucinating despite context), open a `v0.6.x` patch issue. Re-run
`saskan-lore evaluate` after the fix — new `EvalResult` records are created; previous
results are preserved.

---

## Phase 7 — Export and reset (graduation)

Only proceed to this phase after 6.18 passes (≥ 7/10 questions graded pass).

| # | Step | Expected result | Pass |
| --- | --- | --- | --- |
| 7.1 | `poetry run saskan-lore export-eval` | Writes `var/eval_export_<timestamp>.json` | ☐ |
| 7.2 | Copy `var/eval_export_<timestamp>.json` to a permanent location outside `var/` (e.g. `docs/design/r6_evaluation/`) | File saved and readable | ☐ |
| 7.3 | `rm -r var/reviewed/` | Staging files removed | ☐ |
| 7.4 | `rm var/saskan_lore.db` | DB file removed | ☐ |
| 7.5 | `poetry run python -m saskan_lore.infra.db.init_db` | Fresh DB created; all migrations applied | ☐ |
| 7.6 | `dba.row_counts()` | All tables present; all counts = 0 | ☐ |
| 7.7 | CHANGELOG updated with v1.0.0 entry | — | ☐ |
| 7.8 | `bash scripts/release.sh minor "MVP graduation — v1.0.0"` | Tagged and pushed | ☐ |

---

## Graduation checklist

All of the following must be true before declaring v1.0.0:

- [ ] 1 Varkaar source document ingested (`SaskanCanon-VarkaarCovenant.pdf`)
- [ ] 100–200 approved claims in the DB before reset
- [ ] 10 evaluation questions loaded and answered
- [ ] Every answer included retrieved evidence (non-empty `retrieved_evidence` field)
- [ ] ≥ 7/10 questions graded **pass** by the human reviewer
- [ ] Eval results exported and saved outside `var/`
- [ ] `var/` wiped and DB reinitialized to pristine state
- [ ] `v1.0.0` tagged and pushed

---

## Failure analysis reference

| Type | Meaning | Likely cause |
| --- | --- | --- |
| `wrong_fact` | Answer states something factually incorrect | Model ignored context; retrieval returned wrong claims |
| `hallucination` | Answer introduces content not in retrieved context | Model used parametric knowledge despite prompt instruction |
| `incomplete` | Answer is correct but missing important detail | `top_n` too low; relevant claims not retrieved |
| `style` | Answer is factually correct but poorly phrased | Model phrasing issue; not a pipeline defect |
