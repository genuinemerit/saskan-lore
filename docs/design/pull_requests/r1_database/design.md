# Release 1: Database Layer

Status: **Ready to build**

## Objective

Define and create the SQLite database using SQLAlchemy declarative models as the authoritative
schema source. Set up Alembic for migrations. Provide a session factory and DB initialization
script. No data is loaded in this release — this is infrastructure only.

---

## Deliverables

- `saskan_lore/data/models.py` — all SQLAlchemy declarative models
- `saskan_lore/loader/db.py` — engine, session factory, FK pragma hook
- `alembic/` directory — Alembic config and initial migration
- `alembic.ini` — Alembic config pointing at the project DB path
- `saskan_lore/loader/init_db.py` — one-time DB initialization script (runs `upgrade head`)

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| ADR-002 | SQLite + SQLAlchemy ORM; Alembic for migrations |
| ADR-003 | Claims table with source span; claims are first-class |
| ADR-004 | `truth_status` column on claims |
| ADR-005 | `relationships` table present from the start |
| FR-001 | `documents` table |
| FR-002 | `chunks` table linked to documents |
| FR-003 | `entities` and `entity_aliases` tables |
| FR-004 | `claims` table with `reviewed` flag |
| FR-005 | `relationships` table |
| FR-008 | `eval_questions` and `eval_results` tables |
| NFR-001 | Local SQLite only; no external DB dependency |
| NFR-003 | Schema enforces FK links between claims, chunks, documents |
| NFR-004 | `reviewed` boolean on claims; defaults to `False` |

---

## Schema Overview

Nine tables. Dependency order (for inserts):

```txt
documents
  └── chunks (→ documents)
        └── claims (→ chunks, documents)
              └── claim_entities (→ claims, entities)
entities
  └── entity_aliases (→ entities)
  └── relationships (→ entities × 2)
eval_questions
  └── eval_results (→ eval_questions)
```

---

## Design Notes

### models.py structure

Use a single `Base = declarative_base()` shared across all models. Each model class maps
to one table. Keep models in one file for this project scale.

Shared pattern for all tables:

```python
from sqlalchemy import Column, Integer, DateTime, func

class TimestampMixin:
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
```

### Claim model — key fields

```python
class Claim(TimestampMixin, Base):
    __tablename__ = "claims"
    id           = Column(Integer, primary_key=True)
    chunk_id     = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    document_id  = Column(Integer, ForeignKey("documents.id"), nullable=False)
    claim_text   = Column(Text, nullable=False)
    source_span  = Column(Text, nullable=False)
    truth_status = Column(String(20), nullable=False)  # fact|belief|interpretation|rumor
    reviewed     = Column(Boolean, default=False, nullable=False)
    status       = Column(String(20), default="pending")  # pending|approved|rejected
```

### Relationship model — key fields

```python
class Relationship(TimestampMixin, Base):
    __tablename__ = "relationships"
    id                 = Column(Integer, primary_key=True)
    source_entity_id   = Column(Integer, ForeignKey("entities.id"), nullable=False)
    target_entity_id   = Column(Integer, ForeignKey("entities.id"), nullable=False)
    relationship_type  = Column(String(50), nullable=False)
    claim_id           = Column(Integer, ForeignKey("claims.id"), nullable=True)
```

### db.py — SQLite FK enforcement

SQLite does not enforce foreign keys by default. Enable with a connection event:

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
```

### Alembic

- Run `alembic init alembic` from the project root.
- In `alembic/env.py`, import `Base` from `saskan_lore.data.models` and set
  `target_metadata = Base.metadata`.
- Generate the initial migration: `alembic revision --autogenerate -m "initial schema"`.
- Apply: `alembic upgrade head`.

Do not use `Base.metadata.create_all()` in production code — always go through Alembic
so that the migration history is maintained.

### DB path

Store the DB path in a single config location (e.g., `saskan_lore/config.py` or an env var).
Do not hardcode it in multiple places.

---

## Testability Considerations

- Use an in-memory SQLite database (`sqlite:///:memory:`) in tests — fast and isolated.
- Write a pytest fixture that creates all tables, yields a session, and tears down after each test.
- Test that inserting a `Claim` without a matching `chunk_id` raises an `IntegrityError`.
- Test that `reviewed` defaults to `False` on a new claim.
- Test that the FK pragma is active: inserting an orphaned child record should fail.

---

## Acceptance Criteria

- `poetry run alembic upgrade head` completes without error and creates all nine tables.
- Schema matches the field definitions in FR-001 through FR-005 and FR-008.
- All foreign key constraints are enforced at runtime (SQLite FK pragma enabled).
- `reviewed` defaults to `False` on all new claim records.
- Re-running `alembic upgrade head` on an already-initialized DB is safe (no-op).
