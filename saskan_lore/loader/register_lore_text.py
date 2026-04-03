# saskan_lore/loader/register_lore_text.py
"""
Register source lore texts in the database.

Records the existence and metadata of a source PDF without loading its content.
Content hashing ensures that duplicate files (even if renamed) are not registered twice.

Public API: register_document(session, title, source_path, scope)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from saskan_lore.data.models import Document

_VALID_SCOPES = {"varkaar"}


def register_document(
    session: Session,
    title: str,
    source_path: str,
    scope: str = "varkaar",
) -> Document:
    """
    Register a source lore text in the database.

    Checks for an existing record by source_path or content_hash before inserting.
    If either matches, returns the existing record without creating a duplicate.

    Args:
        session:     Active SQLAlchemy session.
        title:       Human-readable document title.
        source_path: Path to the source PDF (relative or absolute).
        scope:       Lore scope. Only "varkaar" is accepted in the pilot.

    Returns:
        The existing or newly inserted Document record.

    Raises:
        ValueError:        If scope is not in the allowed set.
        FileNotFoundError: If source_path does not exist on disk.
    """
    if scope not in _VALID_SCOPES:
        raise ValueError(
            f"Scope {scope!r} is not allowed. " f"Valid scopes: {sorted(_VALID_SCOPES)}"
        )

    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    doc = (
        session.query(Document)
        .filter((Document.source_path == source_path) | (Document.content_hash == content_hash))
        .first()
    )
    if doc:
        return doc

    doc = Document(
        title=title,
        source_path=source_path,
        content_hash=content_hash,
        scope=scope,
    )
    session.add(doc)
    session.commit()
    return doc
