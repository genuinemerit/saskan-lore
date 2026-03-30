# User Guide

How to call saskan-lore functions.

This guide covers the public functions available in the system. Each entry names the
function and its module, gives a plain description, and shows example calls.

## Contents

- [register_document](#register_document) — register a lore text in the database
- [load_chunks](#load_chunks) — split a lore text into chunks and save them
- [ingest (CLI)](#ingest-cli-command) — run the full ingestion pipeline from the command line

---

## register_document

**Module:** `saskan_lore.loader.register_lore_text`

**What it does:**

Records a source lore text (a PDF file) in the database. It saves the file's title,
path, and a content fingerprint. It does not load the text content — it only notes that
the file exists and gives it an ID for later steps.

If the same file has already been registered (by path or by content), the function
returns the existing record instead of creating a duplicate.

The function will refuse a file if its `scope` is not `"varkaar"`. It will also refuse
if the file path does not exist on disk.

**Arguments:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session (from `get_session()`) |
| `title` | `str` | yes | Human-readable name for the document |
| `source_path` | `str` | yes | Path to the source PDF file |
| `scope` | `str` | no | Lore scope; defaults to `"varkaar"` |

**Returns:** A `Document` record (new or existing).

**Examples:**

Register a file for the first time:

```python
from saskan_lore.infra.db.db import get_session
from saskan_lore.loader.register_lore_text import register_document

with get_session() as session:
    doc = register_document(
        session=session,
        title="Saskan Canon: Varkaar Covenant",
        source_path="data/lore_texts/SaskanCanon-VarkaarCovenant.pdf",
    )
    print(doc.id, doc.title)
```

Re-registering the same file is safe — returns the existing record:

```python
with get_session() as session:
    doc1 = register_document(session, "My Doc", "data/lore_texts/example.pdf")
    doc2 = register_document(session, "My Doc", "data/lore_texts/example.pdf")
    assert doc1.id == doc2.id  # same record, no duplicate
```

Wrong scope raises a clear error:

```python
with get_session() as session:
    register_document(
        session=session,
        title="Out of Scope Doc",
        source_path="data/lore_texts/example.pdf",
        scope="gondor",  # not allowed
    )
# Raises: ValueError: Scope 'gondor' is not allowed. Valid scopes: ['varkaar']
```

---

## load_chunks

**Module:** `saskan_lore.loader.load_chunks`

**What it does:**

Splits the plain text of a lore document into chunks and saves them to the database.
Each chunk is a short passage (one to two sentences by default). Chunks are numbered
in order starting from 0.

The function always processes the full document. If the chunks are already saved and
complete, it does nothing. If a previous run saved only some of the chunks (for example,
because it failed early), it clears the partial set and saves the full set again.

**Arguments:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session (from `get_session()`) |
| `document` | `Document` | yes | Registered document record (from `register_document()`) |
| `text` | `str` | yes | Full plain text of the source document |

**Returns:** Number of chunks stored (`0` if the document was already fully chunked).

**Examples:**

Load chunks for a registered document:

```python
from saskan_lore.infra.db.db import get_session
from saskan_lore.loader.load_chunks import load_chunks

with get_session() as session:
    n = load_chunks(session=session, document=doc, text=plain_text)
    print(f"Stored {n} chunks")
```

Calling again on a fully-chunked document is safe and does nothing:

```python
with get_session() as session:
    n = load_chunks(session=session, document=doc, text=plain_text)
    assert n == 0  # already complete; no changes made
```

---

## ingest (CLI command)

**Module:** `saskan_lore.loader.ingest`

**What it does:**

Runs the full ingestion pipeline from the command line. Given a PDF file, it:

1. Extracts the plain text from the PDF.
2. Registers the document in the database (using `register_document`).
3. Splits the text into chunks and saves them (using `load_chunks`).
4. Reports how many chunks were stored.

Running the command a second time on the same file is safe — it reports that the
document is already ingested and makes no changes.

The command will refuse a file if its scope is not `varkaar`, if the file does not
exist, or if the PDF cannot be read. Errors are printed to stderr and the command
exits with a non-zero status code.

**Options:**

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--path` | yes | — | Path to the source PDF file |
| `--title` | yes | — | Human-readable title for the document |
| `--scope` | no | `varkaar` | Lore scope (only `varkaar` accepted in pre-pilot) |

**Examples:**

Ingest a lore text for the first time:

```bash
poetry run saskan-lore ingest \
  --path data/lore_texts/SaskanCanon-VarkaarCovenant.pdf \
  --title "Saskan Canon: Varkaar Covenant"
# Ingesting: Saskan Canon: Varkaar Covenant
#   path:  data/lore_texts/SaskanCanon-VarkaarCovenant.pdf
#   scope: varkaar
# Ingested 'Saskan Canon: Varkaar Covenant': 142 chunks stored (document id=1)
```

Running again on the same file does nothing:

```bash
poetry run saskan-lore ingest \
  --path data/lore_texts/SaskanCanon-VarkaarCovenant.pdf \
  --title "Saskan Canon: Varkaar Covenant"
# Already ingested: 'Saskan Canon: Varkaar Covenant' (no changes made)
```

Show full option help:

```bash
poetry run saskan-lore --help
```
