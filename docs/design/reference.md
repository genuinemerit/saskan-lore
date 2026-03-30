# Glossary

Terms, acronyms, and concepts used in this project.

---

## 3B Class Model

A language model with approximately 3 billion parameters. Small enough to run on consumer hardware without a dedicated GPU, large enough for structured extraction tasks such as claim identification and metadata labeling.

---

## ADR (Architecture Decision Record)

A short, dated document capturing a design decision, its context, options considered, and consequences. One ADR per decision, stored in `docs/architecture/decisions/`.

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

- Always generate migrations via `--autogenerate`, then review the output before applying.
- Never edit a migration that has already been applied to a shared or production database.
- Commit `alembic/versions/` to version control — the migration history is part of the project.
- Use `alembic upgrade head` in `init_db.py`; never call `create_all()` in production code.

In this project: `saskan_lore/infra/db/init_db.py` runs `alembic upgrade head` to initialize
or update the database. See also: `r1_database/design.md`.

---

## Chunk

A retrievable slice of a Document, stored in the database. Typically one to two sentences. Chunks are the unit of retrieval.

Example: "The Covenant of Varkaar governed oath law in the northern provinces during the Ashen Era."

---

## Claim

A discrete, source-quoted fact extracted from a Chunk. Claims are the primary unit of meaning in the system — every claim must be traceable to a source span.

Example: claim text = "The Varkaar regarded oath-breaking as a capital offense", source_span = "...oath-breakers were put to death by the Covenant..."

---

## Document

A narrative source text. Stored under `data/lore_texts/`. The starting point of the pipeline.

Example: `SaskanCanon-VarkaarCovenant.pdf`

---

## GGUF

A binary file format for storing quantized language models, used by llama.cpp. A GGUF file packages model weights and metadata into a single portable file. Quantized weights are stored at reduced precision (e.g., 4-bit or 8-bit integers) to reduce memory footprint and enable CPU inference without a GPU.

Example: `qwen2.5-3b-instruct-q4_k_m.gguf`

---

## LLM (Large Language Model)

A type of AI model trained on large amounts of text. Given a text input (a *prompt*), it
generates a text response. LLMs do not look up facts — they predict plausible output based
on patterns learned during training. This makes them useful for tasks like extracting
structured data from prose, but it also means their output can contain errors.

In this project, an LLM reads lore text chunks and identifies claims, entities, and
relationships. All output is treated as untrusted until a human reviews it.

---

## Llama 3

An open-weight language model family released by Meta, available in 1B, 3B, 8B, and larger sizes. GGUF-format versions suitable for local llama.cpp inference are available via Hugging Face.

---

## Mako Templates

[Mako](https://www.makotemplates.org/) is a Python template engine. Alembic uses a single
Mako template — `alembic/script.py.mako` — to generate new migration script files.

When you run `alembic revision -m "some message"`, Alembic reads `script.py.mako` and
substitutes placeholders like `${up_revision}`, `${message}`, and `${create_date}` to
produce a new `.py` file in `alembic/versions/`. You never run or edit the `.mako` file
directly after initial setup — it just sits there, silently generating migration files.

The syntax is similar to Python f-strings but uses `${}` for substitution. For this project,
the default template requires no modifications.

---

## M2 Mac vs. Dell Linux Laptop (Local Inference)

Apple Silicon M2 uses a unified memory architecture in which the CPU and GPU share the same high-bandwidth memory pool. llama.cpp uses the Metal GPU backend on M2, accelerating inference significantly — even for 3B models.

An older Intel/AMD Dell laptop running Ubuntu runs llama.cpp CPU-only, with no GPU offloading. This is substantially slower for the same model and quantization level.

For this project, the M2 Mac is the preferred local inference machine.

---

## Qwen

An open-weight language model family from Alibaba (Qwen 2.5). The 3B instruct variant is well-suited for structured extraction tasks at small scale. GGUF versions are available for local inference via llama.cpp.

---

## RAG (Retrieval-Augmented Generation)

A pattern for grounding LLM answers in retrieved source material rather than model memory.

Steps:

1. Search chunks/claims for relevant passages.
2. Insert retrieved passages into the model prompt.
3. Model answers using only the supplied material.

Example: User asks "What did the Covenant believe about oath-breaking?" → system retrieves top 3 matching chunks → model answers from those chunks.

Used here because lore is custom, truth and traceability matter, and no training is planned.

---

## SQLAlchemy and SQLite

**SQLite** is a file-based relational database. The entire database is a single `.db` file on
disk. There is no server process — the application reads and writes the file directly. It
supports full SQL, foreign keys (with a pragma), and transactions. Ideal for local, single-user
tools where simplicity and inspectability matter more than concurrency.
See: [sqlite.org](https://www.sqlite.org/docs.html)

**SQLAlchemy** is a Python SQL toolkit and ORM. It has two layers:

- **Core** — SQL expression language; construct and execute queries directly.
- **ORM** — map Python classes to database tables; work with objects instead of raw SQL.

This project uses the ORM (declarative style). Each table is a Python class that inherits from
a shared `Base`. SQLAlchemy handles DDL (table creation), DML (insert/update/query), and
connection management.
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
SQLite does not enforce foreign keys by default. Add this event listener in `infra/db/db.py`:

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
- Never call `Base.metadata.create_all()` in production code — use Alembic migrations instead.
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

## Poetry (Virtual Environment)

[Poetry](https://python-poetry.org/) manages dependencies and the virtual environment for this
project. All commands assume Python 3.12.

**Activate the environment:**

```bash
source saskan_lore/tools/poetry_activate
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
poetry install                           # install deps and create venv
poetry add <package>                     # add a dependency
poetry run <command>                     # run a command without activating
poetry lock && poetry install              # resync lock file and venv
poetry env list                          # list known environments
poetry env remove python                 # remove the current env (then reinstall)
```

Applications should commit `poetry.lock`. See `docs/design/workflows.md` for a quick reference.

---

## Type Annotations (`from __future__ import annotations`)

A future import that makes Python type hints lazy — stored as strings at runtime rather than evaluated immediately. Prevents circular import errors and is the default behavior in Python 3.11+.

Include at the top of any module that uses type hints.
