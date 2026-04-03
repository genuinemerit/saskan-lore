# User Guide

saskan-lore is a local, inspectable lore catalog for the fictional world of Saskantinon,
focused on the Covenant of Varkaar region. It processes PDF source documents through a
structured pipeline — chunking, LLM extraction, human review, and database load — so that
lore facts can be looked up, queried, and used to ground model-assisted ideation.

All LLM output is treated as untrusted until you review it. Nothing enters the database
without passing through a human review step.

For a full description of terms and concepts used throughout this guide, see the
[Glossary](reference.md). For acceptance criteria at each pipeline stage, see
[Workflows](workflows.md).

---

## Contents

- [The Pipeline at a Glance](#the-pipeline-at-a-glance)
- [Getting Started](#getting-started)
- [Stage 1–2: Ingesting Lore Documents](#stage-12-ingesting-lore-documents)
  - [ingest (CLI command)](#ingest-cli-command)
  - [register_document](#register_document)
  - [load_chunks](#load_chunks)
- [Stage 3: Extracting Claims](#stage-3-extracting-claims)
  - [extract (CLI command)](#extract-cli-command)
  - [extract_chunk](#extract_chunk)
  - [Staging utilities](#staging-utilities)
- [Stage 4: Reviewing and Loading Claims](#stage-4-reviewing-and-loading-claims)
  - [review (CLI command)](#review-cli-command)
  - [load (CLI command)](#load-cli-command)
  - [review_file](#review_file)
  - [load_file](#load_file)
  - [load_entities](#load_entities)
  - [load_entity_aliases](#load_entity_aliases)
  - [load_relationships](#load_relationships)
- [Stage 5: Retrieving and Answering](#stage-5-retrieving-and-answering)
  - [ask (CLI command)](#ask-cli-command)
  - [retrieve](#retrieve)
  - [format_context](#format_context)
  - [answer](#answer)
- [Database Administration](#database-administration)
  - [Inspecting the database](#inspecting-the-database)
  - [Deleting and recreating the database](#deleting-and-recreating-the-database)
  - [Alembic, SQLAlchemy, and direct SQL](#alembic-sqlalchemy-and-direct-sql)
  - [Known issues](#known-issues)

---

## The Pipeline at a Glance

```txt
data/lore_texts/  ->  analyzer/  ->  reviewed/  ->  loader/  ->  SQLite DB
  (source PDFs)      (chunk +       (human         (DB load)
                      extract)       review)
```

Each source document moves through six stages:

1. **Source Selection** — choose an in-scope PDF and register it as a Document.
2. **Chunking** — split the document into short, retrievable passages (Chunks).
3. **Extraction** — a local LLM reads each Chunk and identifies Claims, Entities, and
   relationships. Output is written to the `reviewed/` staging area, not directly to the DB.
4. **Human Review** — inspect and correct the LLM staging files before they become trusted data.
5. **Load to DB** — approved records are persisted to the SQLite database.
6. **Evaluation** — stored questions are answered using retrieved Chunks and Claims.

Stages 1–5 are complete. Stage 6 is planned.
See [Workflows](../design/workflows.md) for the full stage definitions and acceptance criteria.

---

## Getting Started

### Activate the environment

```bash
source scripts/poetry_activate.sh   # activates the Poetry venv
source scripts/setenv.sh local             # loads env variables from env.local
```

Run both from the repo root. Use `deactivate` to exit the venv. See the
[Poetry](../design/reference.md#poetry-virtual-environment) entry in the Glossary for
details on managing the virtual environment.

### Initialize the database

If the database file does not yet exist:

```bash
poetry run python -m saskan_lore.infra.db.init_db
```

This runs `alembic upgrade head`, creating `var/saskan_lore.db` with the full schema.
See [Database Administration](#database-administration) for how to reset or inspect the
database after it exists.

---

## Stage 1–2: Ingesting Lore Documents

The ingestion pipeline takes a PDF from `data/lore_texts/`, registers it as a Document,
splits its text into Chunks, and saves both to the database. All three steps can be run
together via the CLI (the most common path) or individually via the Python API.

---

### ingest (CLI command)

**Module:** `saskan_lore.loader.ingest`

Runs the full ingestion pipeline from the command line. Given a PDF file, it:

1. Extracts the plain text from the PDF.
2. Registers the document in the database (using `register_document`).
3. Splits the text into chunks and saves them (using `load_chunks`).
4. Reports how many chunks were stored.

Running the command a second time on the same file is safe — it reports that the document
is already ingested and makes no changes.

The command will refuse a file if its scope is not `varkaar`, if the file does not exist,
or if the PDF cannot be read. Errors are printed to stderr and the command exits with a
non-zero status code.

#### Options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--path` | yes | — | Path to the source PDF file |
| `--title` | yes | — | Human-readable title for the document |
| `--scope` | no | `varkaar` | Lore scope (only `varkaar` accepted in pilot) |

#### Examples

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

---

### register_document

**Module:** `saskan_lore.loader.register_lore_text`

Records a source lore text (a PDF file) in the database. It saves the file's title, path,
and a content fingerprint. It does not load the text content — it only notes that the file
exists and gives it an ID for later steps.

If the same file has already been registered (by path or by content), the function returns
the existing record instead of creating a duplicate.

The function will refuse a file if its `scope` is not `"varkaar"`. It will also refuse if
the file path does not exist on disk.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session (from `get_session()`) |
| `title` | `str` | yes | Human-readable name for the document |
| `source_path` | `str` | yes | Path to the source PDF file |
| `scope` | `str` | no | Lore scope; defaults to `"varkaar"` |

**Returns:** A `Document` record (new or existing).

#### Examples

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

### load_chunks

**Module:** `saskan_lore.loader.load_chunks`

Splits the plain text of a lore document into chunks and saves them to the database. Each
chunk is a short passage (one to two sentences by default). Chunks are numbered in order
starting from 0.

The function always processes the full document. If the chunks are already saved and
complete, it does nothing. If a previous run saved only some of the chunks (for example,
because it failed early), it clears the partial set and saves the full set again.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session (from `get_session()`) |
| `document` | `Document` | yes | Registered document record (from `register_document()`) |
| `text` | `str` | yes | Full plain text of the source document |

**Returns:** Number of chunks stored (`0` if the document was already fully chunked).

#### Examples

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

## Stage 3: Extracting Claims

The extraction step reads each Chunk from the database, sends it to a local language
model, and saves the results as a JSON file in the `var/reviewed/` staging area. The
model tries to find claims, entities, and other information in the text.

The output is not trusted yet. It must be reviewed by a human before anything is loaded
into the database. This happens in Stage 4 (planned).

Each chunk produces one of two files:

- `chunk_NNNN_extraction.json` — the model returned a usable result.
- `chunk_NNNN_extraction_error.json` — the model output could not be parsed. The raw
  response is saved so you can inspect it.

---

### extract (CLI command)

**Module:** `saskan_lore.loader.ingest`

Runs extraction from the command line. You can extract one chunk by its database ID,
or all chunks for a document at once.

The command loads the local GGUF model on startup. On the Dell laptop (CPU only) this
takes a few seconds. On the Mac M2 (Metal GPU) it is faster.

The command does not write to the database. It only writes JSON files to `var/reviewed/`.

#### Options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--chunk-id` | one of the two | — | Database ID of a single chunk to extract |
| `--document-id` | one of the two | — | Database ID of a document; extracts all its chunks |

You must provide exactly one of `--chunk-id` or `--document-id`, not both.

#### Examples

Extract one chunk by ID:

```bash
poetry run saskan-lore extract --chunk-id 1
#   chunk_0001: ok -> chunk_0001_extraction.json
# Done: 1 extracted, 0 errors, 0 skipped.
```

Extract all chunks for a document:

```bash
poetry run saskan-lore extract --document-id 1
#   chunk_0001: ok -> chunk_0001_extraction.json
#   chunk_0002: ok -> chunk_0002_extraction.json
#   chunk_0003: parse error -> chunk_0003_extraction_error.json
# Done: 2 extracted, 1 errors, 0 skipped.
```

If a chunk belongs to a document with the wrong scope, it is skipped:

```bash
#   chunk_0004: skipped (out of scope)
```

Show full option help:

```bash
poetry run saskan-lore extract --help
```

---

### extract_chunk

**Module:** `saskan_lore.analyzer.extractor`

The Python function behind the `extract` command. Call this directly if you want to
run extraction from a script instead of the command line.

It takes a Chunk record and its parent Document record. It calls the local model,
parses the response, and writes the staging file. It returns the path of the file
written, or `None` if the chunk was skipped.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `chunk` | `Chunk` | yes | ORM Chunk record from the database |
| `document` | `Document` | yes | Parent Document record (used for scope check) |

**Returns:** `Path` of the staging file written, or `None` if skipped.

#### Example

```python
from saskan_lore.analyzer.extractor import extract_chunk
from saskan_lore.data.models import Chunk, Document
from saskan_lore.infra.db.db import get_session

with get_session() as session:
    chunk = session.get(Chunk, 1)
    document = session.get(Document, chunk.document_id)

out = extract_chunk(chunk, document)
if out is None:
    print("Skipped — document is out of scope.")
elif "_error" in out.name:
    print(f"Parse error — see {out.name}")
else:
    print(f"Success — staging file at {out}")
```

---

### Staging utilities

**Module:** `saskan_lore.analyzer.staging`

These functions help you inspect and read the staging files in `var/reviewed/`. They
are useful for checking what has been extracted before moving to the review step.

#### list_staging

Returns the paths of all successful extraction files. Error files are not included.

```python
from pathlib import Path
from saskan_lore.analyzer.staging import list_staging

reviewed_dir = Path("var/reviewed")
files = list_staging(reviewed_dir)
for f in files:
    print(f.name)
# chunk_0001_extraction.json
# chunk_0002_extraction.json
```

#### list_errors

Returns the paths of all error files. Successful files are not included.

```python
from saskan_lore.analyzer.staging import list_errors

errors = list_errors(reviewed_dir)
for f in errors:
    print(f.name)
# chunk_0003_extraction_error.json
```

#### load_staging

Reads one staging file and returns its contents as a Python dictionary. No validation
is done — use `validate_staging` separately if you want to check the structure.

```python
from saskan_lore.analyzer.staging import load_staging

data = load_staging(Path("var/reviewed/chunk_0001_extraction.json"))
print(data["summary"])
print(len(data["claims"]), "claims found")
```

#### validate_staging

Checks a staging record against the extraction schema. Returns a list of error
messages. An empty list means the record is valid.

```python
from saskan_lore.analyzer.staging import load_staging, validate_staging

data = load_staging(Path("var/reviewed/chunk_0001_extraction.json"))
errors = validate_staging(data)
if errors:
    for e in errors:
        print("Validation error:", e)
else:
    print("Record is valid.")
```

#### load_for_document

Loads all valid staging records for one document at once. Invalid files and files from
other documents are skipped automatically. Useful for reviewing all extraction output
for a document before loading it into the database.

```python
from saskan_lore.analyzer.staging import load_for_document

records = load_for_document(reviewed_dir, "doc_001")
print(f"{len(records)} valid records found for doc_001")
for r in records:
    print(r["chunk_id"], "-", r["summary"])
```

---

## Stage 4: Reviewing and Loading Claims

After extraction, the staging files in `var/reviewed/` hold untrusted LLM output. Stage 4
is the human review step. You read each claim, decide whether to approve, correct, or
reject it, and then load the approved records into the database.

The `review` command helps you go through each claim one at a time. The `load` command
takes a reviewed file and writes the approved records to the database.

Nothing enters the database as trusted data unless `review_status='approved'` is set on the claim.

---

### review (CLI command)

**Module:** `saskan_lore.loader.ingest`

Opens a staging file and shows you each claim that has not been decided yet. For each
claim, it displays the claim text, the exact quote from the source that supports it
(`source_span`), and the truth status. You then choose what to do.

**Actions:**

| Key | Action | What happens |
| --- | --- | --- |
| `A` | Approve | Sets `review_status='approved'` on the claim |
| `C` | Correct | Leaves the claim unchanged; you edit the JSON file directly and run `review` again |
| `R` | Reject | Sets `review_status='rejected'`; you can add a short reason |
| `Q` | Quit | Stops early; all decisions made so far are saved |

If you stop early (Q or Ctrl-C), the file is saved with whatever decisions you made.
Claims already approved or rejected are skipped automatically on the next run.

#### Arguments

| Name | Required | Description |
| --- | --- | --- |
| `STAGING_FILE` | yes | Path to a staging JSON file in `var/reviewed/` |

#### Example

```bash
poetry run saskan-lore review var/reviewed/chunk_0001_extraction.json

# Reviewing: chunk_0001_extraction.json
#   3 claim(s) to review, 0 already decided.
#
# ── Claim 1/3 ─────────────────────���────────────────────
#   truth_status : fact
#   confidence   : high
#
#   claim_text   : The Covenant of Varkaar governed oath law.
#
#   source_span  : The Covenant governed the northern provinces.
#
# [A]pprove  [C]orrect  [R]eject  [Q]uit: A
```

After all claims are processed, a short summary is printed:

```text
── Review summary ──────────────────────────────────────
  Approved  : 2
  To correct: 0
  Rejected  : 1
  Skipped   : 0
```

---

### load (CLI command)

**Module:** `saskan_lore.loader.ingest`

Reads a reviewed staging file and loads the approved and rejected records into the
database. The full load runs in this order:

1. Entities (places, characters, factions, key events)
2. Entity aliases (reserved for future use)
3. Claims (approved and rejected)
4. Claim-entity links
5. Relationships (reserved for future use)

The command is safe to run more than once on the same file. It will not create
duplicate records.

Only claims with `review_status='approved'` are inserted as approved. Claims with
`review_status='rejected'` are also inserted, but marked as rejected in the database. This
keeps the full audit trail. Claims that are still pending are skipped.

#### Arguments

| Name | Required | Description |
| --- | --- | --- |
| `STAGING_FILE` | yes | Path to a reviewed staging JSON file in `var/reviewed/` |

#### Example

```bash
poetry run saskan-lore load var/reviewed/chunk_0001_extraction.json

# Loading: chunk_0001_extraction.json
#
# ── Load summary ────────────────────────────────────────
#   Entities loaded      : 3
#   Claims loaded        : 2
#   Claims skipped       : 0
#   Claims rejected      : 1
#   Claim-entity links   : 4
```

---

### review_file

**Module:** `saskan_lore.loader.review_staging`

The Python function behind the `review` command. Call this directly if you want to
run review from a script.

It loads the staging file, shows each pending claim, and writes the updated file back
to disk when finished. If you stop the process early, the file is still saved.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `path` | `Path` | yes | Path to the staging JSON file |

**Returns:** A dictionary with counts: `approved`, `corrected`, `rejected`, `skipped`.

#### Example

```python
from pathlib import Path
from saskan_lore.loader.review_staging import review_file, print_summary

path = Path("var/reviewed/chunk_0001_extraction.json")
counts = review_file(path)
print_summary(counts)
```

---

### load_file

**Module:** `saskan_lore.loader.load_reviewed`

The Python function behind the `load` command. It runs the full load sequence for one
staging file and commits everything in a single database transaction. If anything goes
wrong, no changes are saved.

The caller provides an open database session. Use `get_session()` to create one.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session (from `get_session()`) |
| `path` | `Path` | yes | Path to the reviewed staging JSON file |

**Returns:** A summary dictionary with keys: `entities_loaded`, `claims_loaded`,
`claims_skipped`, `claims_rejected`, `claim_entity_links`.

**Raises:** `ValueError` if `chunk_id` or `document_id` cannot be parsed, or if the
referenced chunk does not exist in the database.

#### Example

```python
from pathlib import Path
from saskan_lore.infra.db.db import get_session
from saskan_lore.loader.load_reviewed import load_file, print_load_summary

path = Path("var/reviewed/chunk_0001_extraction.json")

with get_session() as session:
    summary = load_file(session, path)

print_load_summary(summary)
```

---

### load_entities

**Module:** `saskan_lore.loader.load_entities`

Inserts entity records from the staging file's entity lists (`places`, `characters`,
`factions`, `key_events`). Each list maps to an entity type in the database.

| Staging list | Entity type in DB |
| --- | --- |
| `places` | `place` |
| `characters` | `person` |
| `factions` | `faction` |
| `key_events` | `event` |

If an entity with the same name already exists in the database, it is not inserted
again. The function just returns its existing ID. This makes it safe to call more
than once.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session |
| `staging_data` | `dict` | yes | Parsed staging JSON dictionary |

**Returns:** A dictionary mapping `canonical_name` to `entity_id` for all entities
in the file. This map is used by `load_file` to link claims to entities.

#### Example

```python
import json
from pathlib import Path
from saskan_lore.infra.db.db import get_session
from saskan_lore.loader.load_entities import load_entities

data = json.loads(Path("var/reviewed/chunk_0001_extraction.json").read_text())

with get_session() as session:
    entity_map = load_entities(session, data)
    session.commit()

print(entity_map)
# {'Northern Provinces': 1, 'High Arbiter': 2, 'Covenant of Varkaar': 3}
```

---

### load_entity_aliases

**Module:** `saskan_lore.loader.load_entities`

Inserts alternate names (aliases) for entities that already exist in the database.
Each alias is a pair of an entity ID and an alias string.

**Note:** The current staging format does not include alias data. This function is
ready for future use but does nothing when called with an empty list, which is the
current behaviour inside `load_file`.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session |
| `aliases` | `list[tuple[int, str]]` | yes | List of `(entity_id, alias_string)` pairs |

**Returns:** Number of alias records inserted.

#### Example

```python
from saskan_lore.loader.load_entities import load_entity_aliases

with get_session() as session:
    n = load_entity_aliases(session, [(3, "The Covenant"), (3, "Varkaar Covenant")])
    session.commit()
    print(f"{n} aliases inserted")
```

---

### load_relationships

**Module:** `saskan_lore.loader.load_relationships`

Inserts typed, directed relationships between two entities. Each relationship connects
a source entity to a target entity with a label such as `governs` or `allied_with`.

**Note:** The current staging format does not include relationship data. This function
is ready for future use but does nothing when called with an empty list, which is the
current behaviour inside `load_file`.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `session` | `Session` | yes | Open database session |
| `relationships` | `list[dict]` | yes | List of relationship dicts (see below) |
| `entity_map` | `dict[str, int]` | yes | Name-to-ID map from `load_entities()` |

Each relationship dict should have:

| Key | Required | Description |
| --- | --- | --- |
| `source` | yes | Canonical name of the source entity |
| `target` | yes | Canonical name of the target entity |
| `relationship_type` | yes | Label for the relationship, e.g. `governs` |
| `claim_id` | no | ID of a Claim record that supports this relationship |

If either entity name is not in `entity_map`, the relationship is skipped and a
warning is logged.

**Returns:** Number of relationship records inserted.

#### Example

```python
from saskan_lore.loader.load_relationships import load_relationships

relationships = [
    {
        "source": "Covenant of Varkaar",
        "target": "Northern Provinces",
        "relationship_type": "governs",
    }
]

with get_session() as session:
    n = load_relationships(session, relationships, entity_map)
    session.commit()
    print(f"{n} relationships inserted")
```

---

## Stage 5: Retrieving and Answering

After approved claims are in the database, you can ask questions in plain language.
The `ask` command searches the claims, builds a context block, and calls the local model
to produce a grounded answer. Every answer comes with a list of the claims that were used.

The model is told to answer only from the claims it is given. If none of the claims are
relevant, it says so — and the model is not called at all.

---

### ask (CLI command)

**Module:** `saskan_lore.loader.ingest`

Searches approved claims for a question, then calls the local model to produce an answer.
Returns the answer text and a numbered evidence list showing which claims were used.

If no approved claims match the question, the command prints a message and exits without
calling the model.

The command loads the local GGUF model on startup. This takes a few seconds on first run.

#### Arguments and options

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `QUESTION` | yes | — | Natural-language question (in quotes) |
| `--top-n` | no | `3` | Maximum number of claims to use as context |

#### Example

```bash
poetry run saskan-lore ask "What is the Covenant of Varkaar?"

# Answer: The Covenant of Varkaar is a legal framework that governed oath law
# in the northern provinces of Saskantinon.
#
# Evidence:
#   [1] claim_0091 (fact) — chunk_0042 — "Saskan Canon: Varkaar Covenant"
#       "...oath-breakers were put to death under Covenant law..."
#   [2] claim_0103 (fact) — chunk_0051 — "Saskan Canon: Varkaar Covenant"
#       "...the northern provinces were bound by the Covenant..."
```

If no claims match:

```bash
poetry run saskan-lore ask "What is the capital city of Gondor?"
# No relevant claims found for that question.
```

---

### retrieve

**Module:** `saskan_lore.analyzer.retrieval`

Searches approved, active claims using SQLite FTS5 full-text search. Returns a list of
`RetrievalHit` objects ordered by relevance (BM25 rank). Returns an empty list if
the query produces no tokens or no approved claims match.

Only claims with `review_status='approved'` and `is_active=True` are returned.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | `str` | yes | Natural-language query string |
| `session` | `Session` | yes | Open database session |
| `top_n` | `int` | no | Maximum number of results (default: 3) |

**Returns:** `list[RetrievalHit]` — each hit contains `claim_id`, `claim_text`,
`source_span`, `truth_status`, `document_title`, `chunk_sequence`, and `bm25_rank`.

#### Example

```python
from saskan_lore.analyzer.retrieval import retrieve
from saskan_lore.infra.db.db import get_session

with get_session() as session:
    hits = retrieve("oath law Covenant", session, top_n=3)
    for h in hits:
        print(h.claim_id, h.truth_status, h.claim_text[:60])
```

---

### format_context

**Module:** `saskan_lore.analyzer.retrieval`

Formats a list of `RetrievalHit` objects as a numbered context block for use in a model
prompt. Each entry shows the truth status, document title, chunk number, source span,
and full claim text. Returns an empty string if the list is empty.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `hits` | `list[RetrievalHit]` | yes | Retrieval results from `retrieve()` |

**Returns:** A formatted multi-line string, or `""` if `hits` is empty.

#### Example

```python
from saskan_lore.analyzer.retrieval import format_context, retrieve
from saskan_lore.infra.db.db import get_session

with get_session() as session:
    hits = retrieve("oath law", session)
    print(format_context(hits))
# [1] fact — Saskan Canon: Varkaar Covenant — chunk 42
#     Source: "oath-breakers were put to death under Covenant law"
#     The Covenant of Varkaar prescribed death for oath-breaking.
```

---

### answer

**Module:** `saskan_lore.analyzer.answering`

The Python function behind the `ask` command. Calls `retrieve()`, formats the context,
builds the prompt, and calls `inference.complete()`. Returns an `AnswerResult`.

If `retrieve()` returns no hits, returns `AnswerResult(answerable=False)` without calling
the model. If the model signals that it cannot answer, that response is preserved as-is.

#### Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `question` | `str` | yes | Free-text question |
| `session` | `Session` | yes | Open database session |
| `top_n` | `int` | no | Maximum claims to retrieve as context (default: 3) |

**Returns:** `AnswerResult` with fields: `answerable` (bool), `answer` (str or None),
`evidence` (list of claim IDs).

#### Example

```python
from saskan_lore.analyzer.answering import answer
from saskan_lore.infra.db.db import get_session

with get_session() as session:
    result = answer("What governed oath law in Varkaar?", session)

if result.answerable:
    print(result.answer)
    print("Evidence claim IDs:", result.evidence)
else:
    print("No relevant claims found.")
```

---

## Database Administration

### Inspecting the database

The `dba` module provides read-only reporting functions. Import it and call from a Python
session or script:

```python
from saskan_lore.infra.db import dba

dba.summary()                    # table names, row counts, DB file size
dba.row_counts()                 # row count per table
dba.inactive_counts()            # rows where is_active=False per table
dba.check_schema()               # compare live DB schema against ORM models
dba.table_info("chunks")         # column names and types for one table
dba.show_rows("documents", 10)   # show first N rows from a table
dba.alembic_version()            # current Alembic migration revision
dba.db_size()                    # database file size on disk
```

### Deleting and recreating the database

Use this when you want a clean slate — for example after a schema change in development,
or to reset test data.

> **Warning:** This permanently deletes all data in the database. There is no undo.

```bash
# 1. Delete the database file
rm var/saskan_lore.db

# 2. Recreate the schema by running all Alembic migrations from scratch
poetry run python -m saskan_lore.infra.db.init_db
```

After step 2, `var/saskan_lore.db` exists again with a fresh schema and no rows.
Re-ingest documents with `poetry run saskan-lore ingest ...`.

If you prefer to invoke Alembic directly, use the full venv path (see
[Known Issues](#known-issues)):

```bash
/home/dave/.cache/pypoetry/virtualenvs/saskan-lore-EY9omgOA-py3.12/bin/alembic upgrade head
```

### Alembic, SQLAlchemy, and direct SQL

There are three ways to interact with the database. They serve different purposes and should
not be mixed casually.

#### Alembic — schema changes

Use Alembic when you need to change the database schema: add a column, rename a table, add a
constraint. Alembic tracks every change as a numbered migration script. The database records
which migration it is at in the `alembic_version` table.

```bash
alembic upgrade head                                   # apply all pending migrations
alembic downgrade -1                                   # roll back one migration
alembic current                                        # check which revision the DB is at
alembic revision --autogenerate -m "add summary col"   # generate migration from model changes
alembic history                                        # list all revisions
```

Never use `Base.metadata.create_all()` in place of `alembic upgrade head`. `create_all()`
cannot update an existing schema — it only creates tables that do not yet exist.

See the [Alembic](../design/reference.md#alembic) entry in the Glossary for setup details,
key concepts, and best practices.

#### SQLAlchemy ORM — application data

Use SQLAlchemy when your Python code needs to read or write rows: query Chunks, insert
Claims, update Entity aliases. This is the normal path for all application logic.

```python
from saskan_lore.infra.db.db import get_session
from saskan_lore.data.models import Document, Chunk

# Query
with get_session() as session:
    docs = session.query(Document).filter_by(is_active=True).all()

# Insert
with get_session() as session:
    session.add(Chunk(document_id=1, text="The Covenant governed oath law..."))
    session.commit()
```

The `get_session()` context manager handles connection setup, the foreign-key pragma, and
cleanup. Always use it rather than creating engines directly in application code.

See the [SQLAlchemy and SQLite](../design/reference.md#sqlalchemy-and-sqlite) entry in the
Glossary for the declarative model pattern and session usage.

#### Direct SQL — inspection and one-off queries

Use direct SQL when you want to inspect the database outside of Python: verify a migration,
count rows, or debug a constraint. The SQLite CLI or a GUI tool works directly on
`var/saskan_lore.db`. Two good free options:

- [DB Browser for SQLite](https://sqlitebrowser.org) — lightweight, SQLite-specific viewer.
- [DBeaver Community Edition](https://dbeaver.io) — full-featured database IDE; supports
  SQLite, PostgreSQL, and many others. Useful if you ever migrate to Postgres.

```bash
sqlite3 var/saskan_lore.db

# Inside the sqlite3 shell:
.tables                         -- list all tables
.schema documents               -- show CREATE TABLE statement
SELECT count(*) FROM chunks;    -- count rows
SELECT * FROM alembic_version;  -- check current migration revision
.quit
```

Do not use direct SQL to insert, update, or delete rows in a database the application is
using. Direct SQL bypasses the ORM layer, which means `is_active` flags, timestamps, and
foreign key constraints may not be applied correctly. Reserve direct SQL for read-only
inspection.

### Known issues

`poetry run alembic` does not resolve correctly in this environment (the env points to
system Python). Use the full venv path instead:

```bash
/home/dave/.cache/pypoetry/virtualenvs/saskan-lore-EY9omgOA-py3.12/bin/alembic upgrade head
```

Or run via `init_db.py`, which wraps `alembic upgrade head` and is always correct:

```bash
poetry run python -m saskan_lore.infra.db.init_db
```
