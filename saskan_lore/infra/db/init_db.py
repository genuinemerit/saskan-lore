# saskan_lore/infra/db/init_db.py
"""
One-time database initialization script.

Runs `alembic upgrade head` to create or migrate the database to the
latest schema. Safe to call on an already-initialized database — Alembic
is a no-op if the schema is already current.

Usage:
    poetry run python -m saskan_lore.infra.db.init_db

    Or from code:
        from saskan_lore.infra.db.init_db import init_db
        init_db()
"""

from __future__ import annotations

from alembic import command
from alembic.config import Config


def init_db(alembic_cfg_path: str = "alembic.ini") -> None:
    """
    Apply all pending Alembic migrations.

    Args:
        alembic_cfg_path: path to alembic.ini, relative to the working
                          directory. Default assumes the project root.
    """
    cfg = Config(alembic_cfg_path)
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    init_db()
