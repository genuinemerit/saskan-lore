# saskan_lore/infra/db/dba.py
"""
Database administration utilities.

Provides lightweight reporting and inspection functions intended to
complement a full DB IDE (e.g. DBeaver) rather than replace it.
All functions are safe read-only operations unless noted.

Public API:
    summary()               -- print full status report (version, size, counts, schema)
    alembic_version()       -- current migration revision string
    db_size()               -- SQLite file size on disk
    row_counts()            -- active row count per table
    inactive_counts()       -- soft-deleted (is_active=False) row count per table
    check_schema()          -- verify expected tables are present; return warnings
    table_info(table_name)  -- column names, types, nullability, and indexes
    show_rows(table, limit) -- print a sample of rows from any table
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import inspect, text
from tabulate import tabulate

from saskan_lore.infra.db.db import get_engine, get_session

# Tables expected in the current schema (matches models.py).
_EXPECTED_TABLES = {
    "documents",
    "chunks",
    "entities",
    "entity_aliases",
    "claims",
    "claim_entities",
    "relationships",
    "eval_questions",
    "eval_results",
}

# Tables that carry is_active (all nine application tables; excludes alembic_version).
_ACTIVE_TABLES = _EXPECTED_TABLES


def alembic_version() -> str:
    """Return the current Alembic migration revision, or 'none' if unset."""
    with get_session() as session:
        row = session.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else "none"


def db_size() -> str:
    """
    Return the size of the SQLite database file as a human-readable string.
    Returns 'n/a' if the database is in-memory or the file cannot be found.
    """
    url = os.getenv("DATABASE_URL", "")
    path_str = url.replace("sqlite:///", "")
    if not path_str or path_str == ":memory:":
        return "n/a (in-memory)"
    p = Path(path_str).resolve()
    if not p.exists():
        return f"n/a (file not found: {p})"
    size = p.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def row_counts() -> dict[str, int]:
    """Return the count of active (is_active=True) rows per application table."""
    counts: dict[str, int] = {}
    with get_session() as session:
        for table in sorted(_ACTIVE_TABLES):
            result = session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE is_active = 1")  # noqa: S608
            ).scalar()
            counts[table] = result or 0
    return counts


def inactive_counts() -> dict[str, int]:
    """Return the count of soft-deleted (is_active=False) rows per application table."""
    counts: dict[str, int] = {}
    with get_session() as session:
        for table in sorted(_ACTIVE_TABLES):
            result = session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE is_active = 0")  # noqa: S608
            ).scalar()
            counts[table] = result or 0
    return counts


def check_schema() -> list[str]:
    """
    Verify that all expected tables are present in the database.

    Returns a list of warning strings. An empty list means the schema is clean.
    Unexpected extra tables (e.g. temporary work tables) are flagged but not
    treated as errors.
    """
    inspector = inspect(get_engine())
    present = set(inspector.get_table_names()) - {"alembic_version"}
    messages: list[str] = []

    missing = _EXPECTED_TABLES - present
    if missing:
        messages.append(f"MISSING tables: {', '.join(sorted(missing))}")

    extra = present - _EXPECTED_TABLES
    if extra:
        messages.append(f"Unexpected tables (not in models.py): {', '.join(sorted(extra))}")

    return messages


def table_info(table_name: str) -> dict:
    """
    Return schema information for a single table.

    Returns a dict with keys:
        columns  -- list of {name, type, nullable, default}
        indexes  -- list of {name, columns, unique}
    """
    inspector = inspect(get_engine())
    columns = [
        {
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col["nullable"],
            "default": col.get("default"),
        }
        for col in inspector.get_columns(table_name)
    ]
    indexes = [
        {
            "name": idx["name"],
            "columns": idx["column_names"],
            "unique": idx["unique"],
        }
        for idx in inspector.get_indexes(table_name)
    ]
    return {"columns": columns, "indexes": indexes}


def show_rows(table_name: str, limit: int = 10) -> None:
    """
    Print up to `limit` rows from `table_name`, formatted as a table.

    Rows are ordered by id (descending) so the most recent inserts appear first.
    """
    with get_session() as session:
        rows = session.execute(
            text(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT :n"),  # noqa: S608
            {"n": limit},
        ).fetchall()
        if not rows:
            print(f"[{table_name}] — no rows found.")
            return
        keys = session.execute(text(f"SELECT * FROM {table_name} LIMIT 0")).keys()  # noqa: S608
        print(f"\n[{table_name}] — {len(rows)} row(s) shown (limit {limit})")
        print(tabulate(rows, headers=list(keys), tablefmt="simple"))


def summary() -> None:
    """
    Print a full status report: migration version, DB size, row counts,
    inactive counts, and schema validation.
    """
    print("=" * 60)
    print("saskan_lore database summary")
    print("=" * 60)
    print(f"  Migration revision : {alembic_version()}")
    print(f"  DB file size       : {db_size()}")

    warnings = check_schema()
    schema_status = "OK" if not warnings else f"{len(warnings)} warning(s)"
    print(f"  Schema             : {schema_status}")
    for w in warnings:
        print(f"    ! {w}")

    active = row_counts()
    inactive = inactive_counts()
    rows = [
        (table, active[table], inactive[table], active[table] + inactive[table])
        for table in sorted(_ACTIVE_TABLES)
    ]
    print()
    print(tabulate(rows, headers=["table", "active", "inactive", "total"], tablefmt="simple"))
    print()
