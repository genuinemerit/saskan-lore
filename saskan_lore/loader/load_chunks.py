# saskan_lore/loader/load_chunks.py
"""
Split a registered lore text into chunks and persist them.

All chunks for a document are always stored in a single call — full document,
sequence starting at 0. The idempotence guard compares the stored count against
the expected total, so a partial set left by a failed run is replaced cleanly
on the next call.

Public API: load_chunks(session, document, text)
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from saskan_lore.analyzer.chunker import chunk_text
from saskan_lore.data.models import Chunk, Document


def load_chunks(session: Session, document: Document, text: str) -> int:
    """
    Chunk a lore text and persist the results for the given document.

    Computes the full chunk list from text, then compares the stored count
    against the expected total:

    - If stored count equals expected: no-op (already complete).
    - Otherwise: delete any existing chunks for the document and insert the
      full set. This handles both first-time ingestion and recovery from a
      partial failure.

    Args:
        session:  Active SQLAlchemy session.
        document: Registered Document record (must have a valid id).
        text:     Full plain text of the source document.

    Returns:
        Number of chunks stored (0 if the document was already fully chunked).
    """
    chunks = chunk_text(text)
    expected = len(chunks)

    existing = session.query(Chunk).filter_by(document_id=document.id).count()
    if existing == expected:
        return 0

    session.query(Chunk).filter_by(document_id=document.id).delete()
    for i, chunk_text_val in enumerate(chunks):
        session.add(
            Chunk(
                document_id=document.id,
                sequence=i,
                text=chunk_text_val,
            )
        )
    session.commit()
    return expected
