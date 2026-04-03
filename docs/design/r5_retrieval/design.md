# Release 5: Retrieval and Answering

Status: **In Progress**

## Objective

Given a natural-language question, retrieve the most relevant reviewed claims and chunks
from the database, then generate an answer grounded solely in that retrieved context.
Return the answer together with the supporting evidence. This is the first end-to-end
RAG path.

---

## Deliverables

- `saskan_lore/analyzer/retrieval.py` — FTS5 search over claims; returns `RetrievalHit` list
- `saskan_lore/analyzer/answering.py` — format context, call model, return `AnswerResult`
- `saskan_lore/analyzer/answer.txt` — answer prompt template (with context + question slots)
- `saskan_lore/data/schema/data_schema.py` — `RetrievalHit` and `AnswerResult` dataclasses added here
- CLI command: `saskan-lore ask "<question>"`
- Embedding retrieval path: scaffolded but not required for MVP

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| FR-006 | Retrieve top N relevant chunks/claims for a query |
| FR-007 | Answer grounded in retrieved context; evidence returned with every answer |
| NFR-001 | Local-only: no external embedding API required for MVP |
| NFR-002 | Model called through `inference.complete()` from R3 — not inline |
| NFR-003 | Retrieval results include source references (document, chunk, claim ID) |
| ADR-001 | Local GGUF model for answering |
| ADR-007 | Answer prompt instructs model to use only supplied context |
| Glossary | RAG, retrieval |

---

## Design Notes

### Retrieval: FTS5 search (MVP)

Use SQLite FTS5 to search `claims.claim_text`. FTS5 requires a `claims_fts` content virtual
table, added via an Alembic migration. The virtual table mirrors `claims.id` and
`claims.claim_text` without duplicating data (a *content table* pointing to `claims`).

Only claims with `reviewed=True` in the DB are eligible (FTS query joined to `claims` table
to enforce this). Results are ranked by BM25 relevance (FTS5 built-in). Return the top N
results (default N=3, configurable).

Each result is a `RetrievalHit` (defined in `data_schema.py`) containing:

```txt
- claim_id
- claim_text
- source_span
- truth_status
- document title
- chunk sequence number
```

```python
def retrieve(query: str, session: Session, top_n: int = 3) -> list[RetrievalHit]:
    # query claims_fts virtual table using FTS5 MATCH syntax
    # join result rowids to claims table, filter reviewed=True
    # return top_n hits ordered by BM25 rank
    ...
```

### Retrieval: embedding path (deferred)

Tracked in backlog as BL-009. Do not implement in this release. The `retrieve()` interface
is designed to accommodate a future embedding-based replacement without callers needing
to change.

### Answering

`AnswerResult` is defined in `data_schema.py`.

```python
def answer(question: str, session: Session) -> AnswerResult:
    hits = retrieve(question, session)
    if not hits:
        return AnswerResult(answer=None, evidence=[], answerable=False)
    context = format_context(hits)   # numbered list of claim texts + source refs
    prompt = load_prompt("answer.txt").format(context=context, question=question)
    raw = inference.complete(prompt)
    return AnswerResult(answer=raw, evidence=[h.claim_id for h in hits], answerable=True)
```

### Answer prompt template (`saskan_lore/analyzer/answer.txt`)

Must include:

- Clear instruction to answer only from the supplied context.
- Instruction to say "I cannot answer from the available evidence" if context is insufficient.
- Placeholder slots: `{context}` and `{question}`.

Example structure:

```txt
You are answering questions about a fictional world using only the evidence provided below.
Do not use any knowledge outside this context. If the context does not contain enough
information to answer, say: "I cannot answer from the available evidence."

Context:
{context}

Question: {question}

Answer:
```

### Cannot-answer handling

If `retrieve()` returns no hits, return `answerable=False` without calling the model.
If the model returns a "cannot answer" signal in its response text, preserve that as the
answer rather than treating it as an error.

### CLI output

```txt
Answer: The Covenant of Varkaar prescribed death for oath-breaking.

Evidence:
  [1] claim_0091 (fact) — chunk_0042 — "Saskan Canon — Varkaar Covenant"
      "...oath-breakers were put to death under Covenant law..."
```

---

## Testability Considerations

- Test that `retrieve()` returns only `reviewed=True` claims.
- Test that a query with no matching tokens returns an empty list, not an error.
- Test that `answer()` with no retrieval hits returns `answerable=False` without calling
  the model (mock `inference.complete` to assert it is not called).
- Test that the evidence list in `AnswerResult` matches the claim IDs returned by `retrieve()`.
- Test `format_context()` independently: given a list of hits, verify the output format.
- Use a small fixture DB with a few known claims to test keyword match behavior.

---

## Acceptance Criteria

- Given a query that matches known claims, `retrieve()` returns those claims with source
  references.
- `answer()` calls the model only when retrieval returns at least one hit.
- Every answer includes a non-empty evidence list.
- A query with no matches returns `answerable=False` and no model call is made.
- The model is not called directly from `answering.py`; only `inference.complete()` is used.
- CLI output displays answer text and numbered evidence with claim ID, truth status,
  chunk reference, and source span.

---

## Progress

### Housekeeping

- [x] `database_schema.py` renamed to `data_schema.py`; all code and doc references updated
- [x] R5 design doc updated: prompt path (`analyzer/answer.txt`), FTS5 chosen, type locations
- [x] FTS5 entry added to `docs/guides/reference.md`
- [x] BL-009 (embedding retrieval path) added to `docs/design/backlog.md`
- [x] `reviewed`/`status` vocabulary replaced by `review_status` enum across all staging
  files, loader code (`extractor.py`, `review_staging.py`, `load_reviewed.py`, `ingest.py`),
  `extract_schema.json`, `data_schema.py`, and all R3/R4 tests; BL-002 resolved

### Implementation

- [x] Alembic migration: `claims_fts` FTS5 content virtual table backed by `claims`
- [x] `saskan_lore/data/schema/data_schema.py` — `RetrievalHit` and `AnswerResult` frozen dataclasses
- [x] `saskan_lore/analyzer/retrieval.py` — `tokenize()`, `retrieve()`, `format_context()`
- [x] `saskan_lore/analyzer/answering.py` — `answer()`
- [x] `saskan_lore/analyzer/answer.txt` — grounded-answer prompt template
- [x] `saskan-lore ask "<question>"` CLI command in `loader/ingest.py`
- [x] FTS5 index rebuild triggered by `load_reviewed.load_file()` after each successful load

### Testing

- [x] `docs/design/r5_retrieval/test_cases.md` — test case register
- [x] `tests/unit/r5_retrieval/test_r5_retrieval.py` — unit tests (TC-R5-01 through TC-R5-14)

### Post-testing

- [x] Review `docs/guides/user.md` — Stage 5 section added; review_status vocabulary updated
- [x] Review `docs/guides/workflows.md` — retrieval approach and test structure updated
- [x] Review `README.md` — status table, version, and description updated to R5 complete
