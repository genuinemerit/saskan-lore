# Release 2: Source Ingestion and Chunking

Status: **Ready**

## Objective

Register source documents in the database and split them into chunks using the existing
`chunker.py`. By the end of this release, Varkaar source texts are loaded as documents
and chunks, ready for extraction.

---

## Deliverables

- `saskan_lore/loader/register_lore_text.py` — register a source document (FR-001)
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

Check for an existing document by `source_path` **or** `content_hash` before inserting.
If either matches, return the existing record without creating a duplicate. This guards
against both re-ingestion of the same path and re-ingestion of a renamed copy of the
same file.

`content_hash` is a SHA-256 of the raw PDF bytes, computed via `get_sha256()` from
`saskan_lore/tools/utils/shell.py` before calling `register_document`.

```python
def register_document(session, title, source_path, content_hash, scope="varkaar"):
    doc = (
        session.query(Document)
        .filter(
            (Document.source_path == source_path)
            | (Document.content_hash == content_hash)
        )
        .first()
    )
    if doc:
        return doc
    doc = Document(
        title=title,
        source_path=source_path,
        content_hash=content_hash,
        scope=scope,
    )
    session.add(doc)
    session.commit()
    return doc
```

### Chunking and persistence

`chunker.py` exposes `chunk_text(text: str, ...) -> list[str]`. The loader wraps this:

```python
def load_chunks(session, document: Document, text: str):
    chunks = chunk_text(text)
    existing = session.query(Chunk).filter_by(document_id=document.id).count()
    if existing == len(chunks):
        return  # complete set already stored; idempotent
    # Missing or incomplete — delete any partial set and re-load all chunks.
    session.query(Chunk).filter_by(document_id=document.id).delete()
    for i, chunk_text_val in enumerate(chunks):
        session.add(Chunk(document_id=document.id, sequence=i, text=chunk_text_val))
    session.commit()
```

The idempotence guard compares the stored count against the expected total. A simple
`existing > 0` check would leave a partially-written set permanently stuck if ingestion
failed mid-way. Comparing to `len(chunks)` allows safe re-runs after partial failures
without manual DB cleanup, while still being a no-op when the document is fully chunked.

All chunks for a document are always loaded in a single call — full document, sequence
starting at 0. Range selection (e.g. "chunks 5–20 only") belongs at the extraction layer
(R3), not here. Chunking is cheap; extraction is the expensive, human-gated step where
batching makes sense.

### PDF text extraction

The source files are PDFs. A PDF-to-text step is needed before chunking. **Chosen
library: `pdfminer.six`** — add to `pyproject.toml` dependencies. Extract as plain text
via `pdfminer.high_level.extract_text()`, then pass to `chunk_text()`. Approved
normalization: collapse multiple whitespace, strip page headers/footers if consistently
identifiable. Do not alter the text content itself. See ADR-007.

### Ingest entry point

```txt
ingest.py:
  1. Extract text from PDF
  2. register_document()
  3. load_chunks()
  4. Log: "Ingested <title>: <N> chunks"
```

### CLI

Wire the `ingest` command using **Typer** (see `docs/design/reference.md`). Add a
`[tool.poetry.scripts]` entry in `pyproject.toml` pointing to the Typer app entry point.
Minimum interface:

```txt
saskan-lore ingest --path data/lore_texts/SaskanCanon-VarkaarCovenant.pdf
                   --title "Saskan Canon: Varkaar Covenant"
                   --scope varkaar
```

If CLI scaffolding grows beyond a single command, break into a separate sub-feature
(R2.1_cli) and keep ingestion logic in R2.2_ingestion.

---

## Testability Considerations

- Test `register_document()` idempotence: calling twice with the same path returns the
  same record and does not insert a duplicate.
- Test `load_chunks()` idempotence: calling twice on a fully-chunked document does not add
  or replace chunks.
- Test `load_chunks()` partial-failure recovery: if fewer chunks than expected are present,
  a second call replaces them with the complete set.
- Test that chunk sequence is monotonically increasing from 0.
- Test that chunk text matches the source (no silent modification).
- Use a small fixture text string instead of a real PDF for unit tests.

---

## Progress

### Implementation

- [x] `saskan_lore/loader/register_lore_text.py` — `register_document()`: scope guard, file
  existence check, SHA-256 content hash, dual idempotence check (source_path or
  content_hash), insert on first call, return existing on repeat
- [x] `saskan_lore/loader/load_metadata.py` — deleted (dead stub from early design)
- [x] `saskan_lore/loader/load_chunks.py` — `load_chunks()`: full-document chunking,
  count-based idempotence guard, partial-failure recovery; returns chunk count stored
- [x] `saskan_lore/loader/ingest.py` — `ingest` Typer command: PDF extraction (pdfminer.six),
  whitespace normalization, `register_document()`, `load_chunks()`, structured logging;
  clean error messages and non-zero exit on failure; no-op message when already ingested
- [x] `pyproject.toml` — `[tool.poetry.scripts]` entry: `saskan-lore = "saskan_lore.loader.ingest:app"`

### Testing

- [x] `tests/unit/r2_ingestion/test_r2_ingestion.py` — 10/10 passing (TC-R2-01 through TC-R2-10)

### Notes

- `get_sha256()` in `shell.py` hashes a `str` (encodes to UTF-8 internally). For raw PDF
  bytes, `hashlib.sha256(path.read_bytes()).hexdigest()` is used directly in
  `load_document.py` — no change to `shell.py` needed.

---

## Acceptance Criteria

- Running `ingest` on a Varkaar PDF registers the document and loads all chunks.
- Each chunk is linked to its parent `document_id` with a correct `sequence` value.
- Chunk text is stored verbatim (modulo approved normalization).
- Re-running `ingest` on the same file produces no duplicate records.
- A document with `scope != "varkaar"` is rejected with a clear error message.
