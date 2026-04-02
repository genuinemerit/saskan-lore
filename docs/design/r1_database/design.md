# Release 1: Database Layer

Status: **Complete**

## Objective

Define and create the SQLite database using SQLAlchemy declarative models as the authoritative
schema source. Set up Alembic for migrations. Provide a session factory and DB initialization
script. No data is loaded in this release — this is infrastructure only.

---

## Deliverables

- `saskan_lore/data/models.py` — all SQLAlchemy declarative models
- `saskan_lore/infra/db/db.py` — engine, session factory, FK pragma hook
- `saskan_lore/infra/db/init_db.py` — one-time DB initialization script (runs `upgrade head`)
- `alembic/` directory — Alembic config and initial migration
- `alembic.ini` — Alembic config pointing at the project DB path

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
from sqlalchemy import Boolean, Column, DateTime, func

class TimestampMixin:
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

All tables inherit `is_active`. Set `is_active=False` to deprecate any record without deleting it.

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
    status       = Column(String(20), default="pending", nullable=False)  # pending|approved|rejected
    confidence   = Column(String(10), nullable=True)   # high|medium|low
```

Claims are never deleted. `status='rejected'` is the deprecation marker.

### Entity model — key fields

```python
class Entity(TimestampMixin, Base):
    __tablename__ = "entities"
    id             = Column(Integer, primary_key=True)
    canonical_name = Column(String(200), nullable=False)
    entity_type    = Column(String(50), nullable=False)  # person|place|faction|artifact|era|event|other
```

### ClaimEntity model — key fields

```python
class ClaimEntity(TimestampMixin, Base):
    __tablename__ = "claim_entities"
    id        = Column(Integer, primary_key=True)
    claim_id  = Column(Integer, ForeignKey("claims.id"), nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    role      = Column(String(50), nullable=True)  # subject|object|location|faction|etc.
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

### infra/db/db.py — SQLite FK enforcement

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

Store the DB path in `DATABASE_URL` (env var). Read it in `infra/db/db.py` and in
`alembic/env.py`. Do not hardcode it in multiple places.

---

## Testability Considerations

- Use an in-memory SQLite database (`sqlite:///:memory:`) in tests — fast and isolated.
- Write a pytest fixture that creates all tables, yields a session, and tears down after each test.
- Test that inserting a `Claim` without a matching `chunk_id` raises an `IntegrityError`.
- Test that `status` defaults to `'pending'` on a new claim.
- Test that the FK pragma is active: inserting an orphaned child record should fail.

---

## Progress

### Implementation

- [x] `saskan_lore/data/models.py` — full column definitions for all nine tables, TimestampMixin, indexes, unique constraints
- [x] `saskan_lore/infra/db/db.py` — engine factory, session context manager, SQLite FK pragma hook
- [x] `saskan_lore/infra/db/init_db.py` — DB initialization via `alembic upgrade head`
- [x] `alembic.ini` — Alembic config at project root; `sqlalchemy.url` read from `DATABASE_URL`
- [x] `alembic/env.py` — reads `DATABASE_URL`, imports `Base`, supports offline and online modes
- [x] `alembic/script.py.mako` — Mako template for migration script generation
- [x] `alembic/versions/b6b114a51559_initial_schema.py` — initial migration (autogenerated)
- [x] `alembic/versions/791013d72aa0_add_foreign_keys.py` — FK migration (hand-edited to add constraint names required by batch mode)
- [x] `var/saskan_lore.db` created and updated by `alembic upgrade head`

### Alembic Commands

- [x] `alembic revision --autogenerate -m "initial schema"` — all 9 tables and all indexes detected
- [x] `alembic upgrade head` — migration applied; all 9 tables created
- [x] `alembic current` — confirms revision `b6b114a51559 (head)`
- [x] `alembic upgrade head` re-run on initialized DB — confirmed no-op (no output, clean exit)
- [x] `alembic revision --autogenerate -m "add foreign keys"` — all 10 FK constraints detected
- [x] `alembic upgrade head` — FK migration applied; revision `791013d72aa0 (head)`

### Testing

- [x] pytest fixture: in-memory SQLite DB (StaticPool), FK pragma ON, yields session, tears down — `tests/conftest.py`
- [x] `status` defaults to `'pending'` on a new Claim
- [x] FK pragma active: orphaned child inserts raise `IntegrityError` (TC-R1-05, TC-R1-06, TC-R1-09)
- [x] Schema matches FR-001 through FR-005 and FR-008 field definitions (TC-R1-01, TC-R1-10)
- [x] Unique constraints enforced: `Entity.canonical_name`, `(entity_id, alias)` (TC-R1-07, TC-R1-08)
- [x] `is_active` defaults to `True` (TimestampMixin); nullable columns accept `None` (TC-R1-03, TC-R1-04)

- [x] `saskan_lore/infra/db/dba.py` — DB admin utilities: `summary()`, `alembic_version()`, `db_size()`, `row_counts()`, `inactive_counts()`, `check_schema()`, `table_info()`, `show_rows()`

### Notes

- `poetry run alembic` does not resolve the venv binary correctly in this environment.
  Use the full venv path: `/home/dave/.cache/pypoetry/virtualenvs/saskan-lore-EY9omgOA-py3.12/bin/alembic`
  or activate the venv directly before running alembic commands.
- Foreign key constraints are intentionally absent in this pass; to be added in a second round.

---

## Acceptance Criteria

- `poetry run alembic upgrade head` completes without error and creates all nine tables.
- Schema matches the field definitions in FR-001 through FR-005 and FR-008.
- All foreign key constraints are enforced at runtime (SQLite FK pragma enabled).
- `status` defaults to `'pending'` on all new claim records.
- Re-running `alembic upgrade head` on an already-initialized DB is safe (no-op).
