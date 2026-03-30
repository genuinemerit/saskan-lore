# saskan_lore/infra/db/db.py
"""
Database engine, session factory, and SQLite FK pragma hook.

Public API:
    get_engine()         -- returns the shared SQLAlchemy Engine
    get_session()        -- context manager yielding a Session

The engine is created once from DATABASE_URL (env var) and reused.
The FK pragma hook fires on every new SQLite connection to enforce
foreign key constraints (SQLite disables them by default).

For Postgres: change DATABASE_URL to a postgresql+psycopg:// URL.
No code changes needed — the FK pragma is SQLite-only and is skipped
automatically for other dialects.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine as _create_engine

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the shared engine, creating it on first call."""
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise EnvironmentError(
                "DATABASE_URL is not set. "
                "Source env.local before running."
            )
        _engine = _create_engine(url, echo=False)
    return _engine


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_conn: object, _: object) -> None:
    """Enable FK enforcement for SQLite connections."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


def reset_engine() -> None:
    """
    Reset the global engine singleton.

    Call this in test fixtures before switching to an in-memory database:

        from saskan_lore.infra.db.db import reset_engine
        import os

        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        reset_engine()   # next call to get_engine() creates a fresh in-memory engine
    """
    global _engine
    _engine = None


def _session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine())


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Yield a database session, committing on success and rolling back on error.

    Usage:
        from saskan_lore.infra.db.db import get_session

        with get_session() as session:
            session.add(some_object)
    """
    session: Session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
