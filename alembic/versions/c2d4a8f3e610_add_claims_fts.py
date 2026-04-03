# -*- coding: utf-8 -*-
"""add claims_fts FTS5 virtual table

Revision ID: c2d4a8f3e610
Revises: 791013d72aa0
Create Date: 2026-04-03

Creates a SQLite FTS5 content virtual table backed by the claims table.
The virtual table indexes claims.claim_text for full-text search without
duplicating data. The index is populated on creation and must be rebuilt
manually after bulk inserts (see load_reviewed.load_file()).

FTS5 virtual tables are not ORM models and are not detected by Alembic
autogenerate — this migration is written by hand.

See: docs/design/r5_retrieval/design.md, docs/guides/reference.md (FTS5 entry).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d4a8f3e610"
down_revision: Union[str, None] = "791013d72aa0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE VIRTUAL TABLE claims_fts
        USING fts5(
            claim_text,
            content='claims',
            content_rowid='id'
        )
        """)
    # Populate the index from any existing claims rows.
    # On a fresh database this is a no-op; on an existing database with
    # reviewed claims already loaded it will index them immediately.
    op.execute("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS claims_fts")
