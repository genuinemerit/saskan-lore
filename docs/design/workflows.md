# Workflows

## Pipeline

```text
data/lore_texts/   →   analyzer/   →   prompts/   →   reviewed/   →   loader/   →   SQLite DB
  (source PDFs)      (chunker)      (LLM extract)   (human review)   (DB load)
```

Record state per artifact:

| State | Meaning |
| --- | --- |
| `raw` | original text passage |
| `extracted` | LLM output (untrusted) |
| `reviewed` | your corrected version (trusted) |
| `loaded` | persisted in DB |

---

## Stages

### Stage 1 — Source Selection

| | |
| --- | --- |
| **Input** | a lore passage or document in scope |
| **Output** | source registered as a document candidate |
| **Acceptance** | source is in scope; stable enough to extract from; has an identifier |

### Stage 2 — Chunking

| | |
| --- | --- |
| **Input** | one selected source document |
| **Output** | ordered chunks linked to document |
| **Acceptance** | chunk order preserved; boundaries reproducible; text unchanged except approved normalization |

### Stage 3 — Extraction

| | |
| --- | --- |
| **Input** | one chunk or small document section |
| **Output** | summary, entities, claims, source spans, claim type |
| **Acceptance** | no invented details; every claim has an evidence span; uncertain items marked accordingly |

### Stage 4 — Human Review

| | |
| --- | --- |
| **Input** | extracted draft records |
| **Output** | approved, corrected, or rejected records |
| **Acceptance** | all approved claims reviewed by you; no dubious claims silently loaded as trusted |

### Stage 5 — Load to DB

| | |
| --- | --- |
| **Input** | reviewed extraction records |
| **Output** | persisted documents, chunks, entities, claims, relationships |
| **Acceptance** | referential integrity holds; rerunning load is controlled and predictable |

### Stage 6 — Evaluation

| | |
| --- | --- |
| **Input** | stored evaluation questions |
| **Output** | retrieved evidence, generated answer, result record |
| **Acceptance** | answer includes supporting evidence; pass/fail recorded; notes allow failure analysis |

**Retrieval approach (MVP):** keyword search, or embedding + cosine similarity in Python. Return top 3 chunks with associated claims. No vector DB.
