# tests/conftest.py
"""
Shared pytest fixtures for saskan-lore tests.

db_session: in-memory SQLite session with FK enforcement, fresh per test.
"""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from saskan_lore.data.models import Base


@pytest.fixture
def db_session():
    """
    Yield an in-memory SQLite session with full schema and FK pragma enabled.

    StaticPool ensures all ORM operations share the same single connection, so
    tables created by create_all() are visible to every subsequent query in the
    same test.  Dropped and disposed after each test for clean isolation.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn: object, _: object) -> None:
        if isinstance(dbapi_conn, sqlite3.Connection):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
