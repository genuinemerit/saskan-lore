"""add porter stemmer to claims_fts tokenizer

Revision ID: 0e99af659a1b
Revises: e7f3a2c91d40
Create Date: 2026-06-27 20:08:53.166725

The original claims_fts tokenizer (unicode61, the FTS5 default) does no
stemming, so retrieve()'s implicit AND across query tokens fails whenever
a query word and the indexed claim text differ only by inflection (e.g.
question "function" vs claim "functions", question "accept" vs claim
"accepts"). Confirmed on the R6 macOS acceptance run: q_002 and q_003 had
zero retrieval hits despite an exact-match approved claim existing for
each, purely due to this tokenization mismatch (BL-029... see backlog).

FTS5's tokenizer cannot be altered on an existing virtual table, so this
drops and recreates claims_fts with 'porter unicode61' (Porter stemming
wrapped around the same base tokenizer), then rebuilds the index from the
claims content table.

See: docs/design/r5_retrieval/design.md, docs/guides/reference.md (FTS5 entry).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e99af659a1b"
down_revision: Union[str, None] = "e7f3a2c91d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS claims_fts")
    op.execute("""
        CREATE VIRTUAL TABLE claims_fts
        USING fts5(
            claim_text,
            content='claims',
            content_rowid='id',
            tokenize='porter unicode61'
        )
        """)
    op.execute("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS claims_fts")
    op.execute("""
        CREATE VIRTUAL TABLE claims_fts
        USING fts5(
            claim_text,
            content='claims',
            content_rowid='id'
        )
        """)
    op.execute("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')")
