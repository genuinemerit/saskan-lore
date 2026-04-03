# Glossary

Terms, acronyms, and concepts used in this project.

## Contents

- [3B Class Model](#3b-class-model)
- [ADR (Architecture Decision Record)](#adr-architecture-decision-record)
- [Alembic](#alembic)
- [Chunk](#chunk)
- [Claim](#claim)
- [Cosine Similarity](#cosine-similarity)
- [Document](#document)
- [FTS5 (SQLite Full-Text Search)](#fts5-sqlite-full-text-search)
- [GGUF](#gguf)
- [Llama 3](#llama-3)
- [LLM (Large Language Model)](#llm-large-language-model)
- [M2 Mac vs. Dell Linux Laptop (Local Inference)](#m2-mac-vs-dell-linux-laptop-local-inference)
- [MagicMock](#magicmock)
- [Mako Templates](#mako-templates)
- [monkeypatch (pytest)](#monkeypatch-pytest)
- [pdfminer.six](#pdfminersix)
- [Poetry (Virtual Environment)](#poetry-virtual-environment)
- [Qwen](#qwen)
- [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
- [SQLAlchemy and SQLite](#sqlalchemy-and-sqlite)
- [Testable (Claim)](#testable-claim)
- [Type Annotations](#type-annotations)
- [Typer](#typer)

---

## 3B Class Model

A language model with approximately 3 billion parameters. Small enough to run on consumer
hardware without a dedicated GPU, large enough for structured extraction tasks such as claim
identification and metadata labeling.

---

## ADR (Architecture Decision Record)

A short, dated document capturing a design decision, its context, options considered, and
consequences. One ADR per decision, stored in `docs/architecture/decisions/`.

Example: ADR-002 — Use SQLite as the system of record.

---

## Alembic

[Alembic](https://alembic.sqlalchemy.org/) is the migration tool for SQLAlchemy. It tracks
every schema change as a numbered migration script, so the database can be brought to any
past or future version reliably.

**Why use it instead of `Base.metadata.create_all()`?**

`create_all()` builds the schema once but cannot update it later. Alembic keeps a migration
history, so adding a column, renaming a table, or changing a constraint is a safe, reversible
operation — even on a database that already contains data.

**Key concepts:**

| Term | Meaning |
| --- | --- |
| revision | a single migration script with an `upgrade()` and `downgrade()` function |
| head | the latest revision |
| `alembic_version` | a table Alembic writes to the DB to track the current revision |

**Setup (run once from the project root):**

```bash
alembic init alembic          # create alembic/ directory and alembic.ini
```

In `alembic/env.py`, import your `Base` and set:

```python
from saskan_lore.data.models import Base
target_metadata = Base.metadata
```

Point `alembic.ini` (or `alembic/env.py`) at `DATABASE_URL` from the environment.

**Common commands:**

```bash
alembic revision --autogenerate -m "initial schema"  # generate migration from models
alembic upgrade head          # apply all pending migrations
alembic downgrade -1          # roll back one revision
alembic history               # list all revisions
alembic current               # show which revision the DB is at
```

**Best practices:**

- Always generate migrations via `--autogenerate`, then review before applying.
- Never edit a migration already applied to a shared or production database.
- Commit `alembic/versions/` to version control — the migration history is part of the project.
- Use `alembic upgrade head` in `init_db.py`; never call `create_all()` in production code.

In this project: `saskan_lore/infra/db/init_db.py` runs `alembic upgrade head` to initialize
or update the database. See also: `r1_database/design.md`.

---

## Chunk

A retrievable slice of a Document, stored in the database. Typically one to two sentences.
Chunks are the unit of retrieval.

Example: "The Covenant of Varkaar governed oath law in the northern provinces during the
Ashen Era."

---

## Cosine Similarity

A way to measure how similar two vectors are. The result is a number between -1 and 1.
A result close to 1 means the vectors point in almost the same direction — the texts are
similar in meaning. A result close to 0 means they are unrelated.

In a retrieval-augmented system, text is converted to a numerical vector (an *embedding*)
by a model. A query is also converted to a vector. Cosine similarity is then used to find
the stored vectors that are closest to the query vector — these are the most relevant
passages.

This is the main alternative to keyword search (FTS5). Keyword search finds passages that
share the same words as the query. Cosine similarity finds passages that share the same
*meaning*, even if they use different words.

**In this project:** the MVP uses [FTS5](#fts5-sqlite-full-text-search) keyword search
because it requires no embedding model and no vector storage. Embedding-based retrieval
using cosine similarity is a future option, tracked in the backlog as BL-009.

---

## Claim

A discrete, source-quoted fact extracted from a Chunk. Claims are the primary unit of meaning
in the system — every claim must be traceable to a source span.

Example: claim text = "The Varkaar regarded oath-breaking as a capital offense",
source_span = "...oath-breakers were put to death by the Covenant..."

---

## Document

A narrative source text. Stored under `data/lore_texts/`. The starting point of the pipeline.

Example: `SaskanCanon-VarkaarCovenant.pdf`

---

## FTS5 (SQLite Full-Text Search)

SQLite FTS5 is the built-in full-text search extension shipped with SQLite 3.9+. It enables
efficient keyword and phrase search over text columns without scanning every row.

**How it works:**

FTS5 creates a *virtual table* — a special table whose storage and query logic is handled by
the extension rather than SQLite's standard B-tree engine. The virtual table maintains an
inverted index: for each token (word) it records which rows contain it, enabling fast lookups
regardless of table size.

**Content tables:**

Rather than copying data into the virtual table, FTS5 supports a *content table* mode: the
virtual table indexes text from an existing table and stores only the index, not the content.
Queries return rowids that are joined back to the source table to fetch the actual data.

```sql
-- Create a content virtual table backed by the claims table
CREATE VIRTUAL TABLE claims_fts USING fts5(
    claim_text,
    content='claims',
    content_rowid='id'
);

-- Populate the index from existing rows
INSERT INTO claims_fts(claims_fts) VALUES('rebuild');

-- Query: returns rowids of matching claims, ranked by BM25 relevance
SELECT rowid, rank
FROM claims_fts
WHERE claims_fts MATCH 'oath covenant'
ORDER BY rank
LIMIT 5;
```

**BM25 ranking:**

FTS5 exposes a `rank` column that returns the BM25 score for each match. BM25
(Best Match 25) is a standard information retrieval ranking function that weighs term
frequency against document length. Lower (more negative) rank values indicate stronger
matches. Sort `ORDER BY rank` to get the best results first.

In practice: a claim that contains the query term many times in a short text scores
lower (stronger) than one that mentions it once in passing. For example, a claim
whose entire text is about oath law will rank higher for the query `"oath"` than a
long claim that happens to mention it in a subordinate clause.

In this project, `bm25_rank` is stored on each `RetrievalHit` and logged for
inspection, but is not shown to the user — it is used only for ordering results.
A typical strong match in a small lore database will produce values in the range
of roughly -1 to -5; the exact scale depends on corpus size and term distribution.

**MATCH syntax:**

| Pattern | Meaning |
| --- | --- |
| `'oath'` | rows containing the token `oath` |
| `'oath covenant'` | rows containing both tokens (implicit AND) |
| `'oath OR covenant'` | rows containing either token |
| `'"oath breaker"'` | exact phrase match |
| `'oath*'` | prefix match (rows with tokens starting with `oath`) |

**In this project:**

FTS5 is used in R5 to search `claims.claim_text`. A `claims_fts` content virtual table is
created via an Alembic migration. At query time, `retrieval.py` issues a `MATCH` query
against `claims_fts`, joins the result rowids to the `claims` table (to filter
`reviewed=True` and fetch metadata), and returns the top N hits ranked by BM25.

Content tables require a manual `rebuild` after bulk inserts (e.g. after loading a batch of
reviewed staging files). This rebuild is triggered by the loader after each successful load.

See also: [sqlite.org/fts5.html](https://www.sqlite.org/fts5.html)

---

## GGUF

A binary file format for storing quantized language models, used by llama.cpp. A GGUF file
packages model weights and metadata into a single portable file. Quantized weights are stored
at reduced precision (e.g., 4-bit or 8-bit integers) to reduce memory footprint and enable
CPU inference without a GPU.

Example: `qwen2.5-3b-instruct-q4_k_m.gguf`

---

## Llama 3

An open-weight language model family released by Meta, available in 1B, 3B, 8B, and larger
sizes. GGUF-format versions suitable for local llama.cpp inference are available via
Hugging Face.

---

## LLM (Large Language Model)

A type of AI model trained on large amounts of text. Given a text input (a *prompt*), it
generates a text response. LLMs do not look up facts — they predict plausible output based
on patterns learned during training. This makes them useful for tasks like extracting
structured data from prose, but it also means their output can contain errors.

In this project, an LLM reads lore text chunks and identifies claims, entities, and
relationships. All output is treated as untrusted until a human reviews it.

---

## M2 Mac vs. Dell Linux Laptop (Local Inference)

Apple Silicon M2 uses a unified memory architecture in which the CPU and GPU share the same
high-bandwidth memory pool. llama.cpp uses the Metal GPU backend on M2, accelerating
inference significantly — even for 3B models.

An older Intel/AMD Dell laptop running Ubuntu runs llama.cpp CPU-only, with no GPU
offloading. This is substantially slower for the same model and quantization level.

For this project, the M2 Mac is the preferred local inference machine.

---

## MagicMock

[`unittest.mock.MagicMock`](https://docs.python.org/3/library/unittest.mock.html) is a
Python standard library class for creating test doubles. A `MagicMock` is an object that
accepts any attribute access or method call and records what was called, with what arguments,
and how many times. It returns another `MagicMock` by default, so code that calls methods
on it does not crash.

**Key patterns:**

```python
from unittest.mock import MagicMock, patch

# Replace a function entirely for a test block
with patch("saskan_lore.analyzer.extractor.complete", return_value='{"claims": []}'):
    result = extract_chunk(chunk, document)

# Replace a module in sys.modules so it is never imported for real
mock_module = MagicMock()
mock_module.SomeClass.return_value = MagicMock()
sys.modules["some_package"] = mock_module
```

In this project: `llama_cpp` is replaced in `sys.modules` via `MagicMock` in the R3 test
conftest so that `inference.py` can be imported without a real GGUF model file on disk.
Individual tests then patch `saskan_lore.analyzer.extractor.complete` to return controlled
fixture strings.

**`return_value` vs `side_effect`:**

| | Meaning |
| --- | --- |
| `mock.return_value = x` | Every call to `mock()` returns `x` |
| `mock.side_effect = [a, b]` | First call returns `a`, second returns `b` |
| `mock.side_effect = Exception` | Calling `mock()` raises the exception |

---

## Mako Templates

[Mako](https://www.makotemplates.org/) is a Python template engine. Alembic uses a single
Mako template — `alembic/script.py.mako` — to generate new migration script files.

When you run `alembic revision -m "some message"`, Alembic reads `script.py.mako` and
substitutes placeholders like `${up_revision}`, `${message}`, and `${create_date}` to
produce a new `.py` file in `alembic/versions/`. You never run or edit the `.mako` file
directly after initial setup — it just sits there, silently generating migration files.

The syntax is similar to Python f-strings but uses `${}` for substitution. For this
project, the default template requires no modifications.

---

## monkeypatch (pytest)

[`monkeypatch`](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) is a built-in
pytest fixture that temporarily overrides attributes, environment variables, dictionary
entries, or items in `sys.path` for the duration of a single test. All changes are
automatically undone when the test finishes — no manual teardown required.

**Key methods:**

```python
def test_something(monkeypatch, tmp_path):
    # Set an environment variable for this test only
    monkeypatch.setenv("REVIEWED_DIR", str(tmp_path / "reviewed"))

    # Override an attribute on a module or object
    monkeypatch.setattr("saskan_lore.analyzer.extractor._VALID_SCOPE", "other")

    # Override a dictionary entry
    monkeypatch.setitem(os.environ, "DATABASE_URL", "sqlite:///:memory:")
```

**`monkeypatch` vs `patch`:**

Both override things temporarily, but they serve slightly different roles:

| | `monkeypatch` | `unittest.mock.patch` |
| --- | --- | --- |
| Scope | Single test function | Block (`with`) or decorator |
| Best for | Env vars, simple attribute swaps | Replacing callables with `MagicMock` |
| Auto-reset | Yes (pytest teardown) | Yes (context exit) |

In this project: `monkeypatch.setenv("REVIEWED_DIR", ...)` is used in R3 tests to point
the extractor at a `tmp_path` staging directory instead of the real `var/reviewed/` path.

---

## pdfminer.six

[pdfminer.six](https://pdfminersix.readthedocs.io) is a pure-Python PDF text extraction
library (the Python 3 fork of the original `pdfminer`). Uses layout analysis to extract
text in reading order.

**Key pattern:**

```python
from pdfminer.high_level import extract_text

text = extract_text("data/lore_texts/SaskanCanon-VarkaarCovenant.pdf")
```

In this project: used in `ingest.py` (R2) to extract plain text from lore PDFs before
passing to `chunk_text()`. Chosen over `pypdf` for more granular layout control.

---

## Poetry (Virtual Environment)

[Poetry](https://python-poetry.org/) manages dependencies and the virtual environment for
this project. All commands assume Python 3.12.

**Activate the environment:**

```bash
source scripts/poetry_activate.sh
```

Run this from the repo root. The script wraps `poetry env activate` so you do not need to
copy-paste the `eval` form each time. Use `deactivate` to exit.

**Load environment variables:**

```bash
source scripts/setenv.sh          # loads env.local (default)
source scripts/setenv.sh local    # same, explicit
source scripts/setenv.sh test     # loads env.test
source scripts/setenv.sh prod     # loads env.prod
```

Environment files live at `saskan_lore/infra/config/env.<name>`. Only `env.example` is
committed; `env.local`, `env.test`, and `env.prod` are gitignored.

**Common commands** (run outside an activated environment):

```bash
poetry install                  # install deps and create venv
poetry add <package>            # add a dependency
poetry run <command>            # run a command without activating
poetry lock && poetry install   # resync lock file and venv
poetry env list                 # list known environments
poetry env remove python        # remove the current env (then reinstall)
poetry show                     # list installed dependencies
```

Applications should commit `poetry.lock`. See `docs/guides/workflows.md` for a quick
reference.

---

## Qwen

An open-weight language model family from Alibaba (Qwen 2.5). The 3B instruct variant is
well-suited for structured extraction tasks at small scale. GGUF versions are available for
local inference via llama.cpp.

---

## RAG (Retrieval-Augmented Generation)

A pattern for grounding LLM answers in retrieved source material rather than model memory.

Steps:

1. Search chunks/claims for relevant passages.
2. Insert retrieved passages into the model prompt.
3. Model answers using only the supplied material.

Example: User asks "What did the Covenant believe about oath-breaking?" → system retrieves
top 3 matching chunks → model answers from those chunks.

Used here because lore is custom, truth and traceability matter, and no training is planned.

---

## SQLAlchemy and SQLite

**SQLite** is a file-based relational database. The entire database is a single `.db` file
on disk. There is no server process — the application reads and writes the file directly.
It supports full SQL, foreign keys (with a pragma), and transactions. Ideal for local,
single-user tools where simplicity and inspectability matter more than concurrency.
See: [sqlite.org](https://www.sqlite.org/docs.html)

**SQLAlchemy** is a Python SQL toolkit and ORM. It has two layers:

- **Core** — SQL expression language; construct and execute queries directly.
- **ORM** — map Python classes to database tables; work with objects instead of raw SQL.

This project uses the ORM (declarative style). Each table is a Python class that inherits
from a shared `Base`. SQLAlchemy handles DDL (table creation), DML (insert/update/query),
and connection management.
See: [docs.sqlalchemy.org](https://docs.sqlalchemy.org/en/20/)

**Declarative model pattern:**

```python
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy import create_engine

class Base(DeclarativeBase):
    pass

class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"
    id          = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    text        = Column(Text, nullable=False)
```

**Session usage:**

```python
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    chunk = session.get(Chunk, chunk_id)
    session.add(Chunk(document_id=1, text="..."))
    session.commit()
```

**SQLite-specific: enable foreign key enforcement.**

SQLite does not enforce foreign keys by default. Add this event listener in
`infra/db/db.py`:

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
```

**Best practices:**

- One `Base` shared across all models; keep all models in one file at this project scale.
- Never call `Base.metadata.create_all()` in production code — use Alembic migrations.
- Use an in-memory database (`sqlite:///:memory:`) in pytest fixtures for fast, isolated tests.
- Always enable the FK pragma (see above) — SQLite silently allows orphaned records otherwise.
- Use `Session` as a context manager so connections are always closed on exit.

---

## Testable (Claim)

A claim is testable if a specific question can be written against it with a verifiable answer.

| | Example |
| --- | --- |
| Not testable | "The Covenant was important." |
| Testable | "The Covenant of Varkaar governed oath law in the northern provinces during the Ashen Era." |

---

## Type Annotations

`from __future__ import annotations` makes Python type hints lazy — stored as strings at
runtime rather than evaluated immediately. Prevents circular import errors and is the
default behavior in Python 3.11+.

Include at the top of any module that uses type hints.

---

## Typer

[Typer](https://typer.tiangolo.com) is a Python library for building CLI applications,
built on top of Click. Arguments and options are declared as typed function parameters;
help text and validation are generated automatically from the annotations.

**Key pattern:**

```python
import typer

app = typer.Typer()

@app.command()
def ingest(
    path: str = typer.Option(..., help="Path to source PDF"),
    title: str = typer.Option(..., help="Document title"),
    scope: str = typer.Option("varkaar", help="Lore scope"),
):
    ...
```

The entry point in `pyproject.toml`:

```toml
[tool.poetry.scripts]
saskan-lore = "saskan_lore.loader.ingest:app"
```

In this project: used to expose the `ingest` command in R2.
