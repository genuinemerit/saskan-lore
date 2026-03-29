# Release 2: Source Ingestion and Chunking

Status: **Pending R1**

## Objective

Register source documents in the database and split them into chunks using the existing
`chunker.py`. By the end of this release, Varkaar source texts are loaded as documents
and chunks, ready for extraction.

---

## Deliverables

- `saskan_lore/loader/load_document.py` — register a source document (FR-001)
- `saskan_lore/loader/load_chunks.py` — run chunker on a document and persist chunks (FR-002)
- `saskan_lore/loader/ingest.py` — top-level entry point that chains registration + chunking
- CLI command wired via Typer (e.g., `poetry run saskan-lore ingest <path>`)
- Idempotence: re-running ingestion on a previously ingested document is safe

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| FR-001 | Document registration with stable ID, title, source path, scope, timestamp |
| FR-002 | Chunks ordered, linked to document, text stored verbatim |
| NFR-001 | Local only; source files read from `data/lore_texts/` |
| NFR-003 | Chunks stored with sequence for downstream traceability |
| NFR-005 | Simple implementation; no streaming or async needed |
| ADR-006 | Scope guard: only documents with `scope="varkaar"` are ingested in pre-pilot |
| Workflow Stage 1 | Source selection — document registered as candidate |
| Workflow Stage 2 | Chunking — reproducible, order-preserving |

---

## Design Notes

### Document registration

Check for an existing document by `source_path` before inserting. If found, return the
existing record without creating a duplicate.

```python
def register_document(session, title, source_path, scope="varkaar"):
    doc = session.query(Document).filter_by(source_path=source_path).first()
    if doc:
        return doc
    doc = Document(title=title, source_path=source_path, scope=scope)
    session.add(doc)
    session.commit()
    return doc
```

### Chunking and persistence

`chunker.py` exposes `chunk_text(text: str, ...) -> list[str]`. The loader wraps this:

```python
def load_chunks(session, document: Document, text: str):
    existing = session.query(Chunk).filter_by(document_id=document.id).count()
    if existing > 0:
        return  # already chunked; idempotent
    chunks = chunk_text(text)
    for i, chunk_text_val in enumerate(chunks):
        session.add(Chunk(document_id=document.id, sequence=i, text=chunk_text_val))
    session.commit()
```

### PDF text extraction

The source files are PDFs. A PDF-to-text step is needed before chunking. Use `pdfminer.six`
(already a reasonable dep) or `pypdf`. Extract as plain text, then pass to `chunk_text()`.
Approved normalization: collapse multiple whitespace, strip page headers/footers if
consistently identifiable. Do not alter the text content itself. See ADR-007.

### Ingest entry point

```txt
ingest.py:
  1. Extract text from PDF
  2. register_document()
  3. load_chunks()
  4. Log: "Ingested <title>: <N> chunks"
```

### CLI

Wire the `ingest` command in `pyproject.toml` under `[tool.poetry.scripts]` or as a Typer
app. Minimum interface:

```txt
saskan-lore ingest --path data/lore_texts/SaskanCanon-VarkaarCovenant.pdf
                   --title "Saskan Canon — Varkaar Covenant"
                   --scope varkaar
```

---

## Testability Considerations

- Test `register_document()` idempotence: calling twice with the same path returns the
  same record and does not insert a duplicate.
- Test `load_chunks()` idempotence: calling twice on the same document does not add chunks.
- Test that chunk sequence is monotonically increasing from 0.
- Test that chunk text matches the source (no silent modification).
- Use a small fixture text string instead of a real PDF for unit tests.

---

## Acceptance Criteria

- Running `ingest` on a Varkaar PDF registers the document and loads all chunks.
- Each chunk is linked to its parent `document_id` with a correct `sequence` value.
- Chunk text is stored verbatim (modulo approved normalization).
- Re-running `ingest` on the same file produces no duplicate records.
- A document with `scope != "varkaar"` is rejected with a clear error message.
