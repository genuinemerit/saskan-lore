# Release 5: Retrieval and Answering

Status: **Pending R4**

## Objective

Given a natural-language question, retrieve the most relevant reviewed claims and chunks
from the database, then generate an answer grounded solely in that retrieved context.
Return the answer together with the supporting evidence. This is the first end-to-end
RAG path.

---

## Deliverables

- `saskan_lore/analyzer/retrieval.py` — keyword search over claims and chunks
- `saskan_lore/analyzer/answering.py` — format context, call model, return answer + evidence
- `saskan_lore/prompts/answer.txt` — answer prompt template (with context + question slots)
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

### Retrieval: keyword search (MVP)

Tokenize the query (lowercase, split on whitespace and punctuation), then search
`claims.claim_text` and `chunks.text` using SQL `LIKE` or SQLite FTS5.

Only `reviewed=True` claims are eligible. Results are ranked by match count (simple).
Return the top N results (default N=3, configurable).

Each result includes:

```txt
- claim_id (or chunk_id)
- claim_text (or chunk text)
- source_span
- truth_status
- document title
- chunk sequence number
```

```python
def retrieve(query: str, session: Session, top_n: int = 3) -> list[RetrievalHit]:
    tokens = tokenize(query)
    # build LIKE clauses for each token against claim_text
    # return top_n matches ordered by token hit count
    ...
```

### Retrieval: embedding path (scaffold only)

If embedding retrieval is added later:

- Embed claims at load time, store as JSON blob or in a separate `claim_embeddings` table.
- At query time: embed query, compute cosine similarity in numpy, return top N.
- This is a drop-in replacement for keyword search behind the same `retrieve()` interface.
- Do not implement in this release; the interface design should accommodate it.

### Answering

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

### Answer prompt template (`answer.txt`)

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
