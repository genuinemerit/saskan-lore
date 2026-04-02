# tests/unit/r2_ingestion/test_r2_ingestion.py
"""
R2 ingestion unit tests.

Covers: register_document (register_lore_text.py) and load_chunks (load_chunks.py).
See docs/design/r2_ingestion/test_cases.md for the full test-case
register (TC-R2-01 through TC-R2-10).

All tests use the db_session fixture from tests/conftest.py:
  - in-memory SQLite, StaticPool, FK pragma ON, fresh per test.
"""

from __future__ import annotations

import pytest

from saskan_lore.analyzer.chunker import chunk_text
from saskan_lore.data.models import Chunk, Document
from saskan_lore.loader.load_chunks import load_chunks
from saskan_lore.loader.register_lore_text import register_document

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

# Four sentences → two chunks of two sentences each (chunk_text defaults:
# max_sentences=2).  Enough to exercise sequence ordering and partial recovery.
SAMPLE_TEXT = (
    "The Covenant of Varkaar was established in the third era. "
    "Its laws governed oath-breaking across the northern provinces. "
    "The first Keeper of Oaths was Maren the Steadfast. "
    "She held office for forty years without a single ruling overturned."
)

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lore_file(tmp_path):
    """Write a small fake source file; return its path as a string."""
    p = tmp_path / "test_lore.pdf"
    p.write_bytes(b"fake pdf content for hashing")
    return str(p)


@pytest.fixture
def lore_file_copy(tmp_path):
    """Second file with identical byte content but a different path."""
    p = tmp_path / "test_lore_copy.pdf"
    p.write_bytes(b"fake pdf content for hashing")
    return str(p)


# ---------------------------------------------------------------------------
# TC-R2-01  register_document: new document inserted correctly
# ---------------------------------------------------------------------------


def test_register_document_inserts(db_session, lore_file):
    """register_document creates a Document with correct field values."""
    doc = register_document(
        session=db_session,
        title="Test Lore",
        source_path=lore_file,
        scope="varkaar",
    )
    assert doc.id is not None
    assert doc.title == "Test Lore"
    assert doc.source_path == lore_file
    assert doc.scope == "varkaar"
    assert len(doc.content_hash) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# TC-R2-02  register_document: idempotence by source_path
# ---------------------------------------------------------------------------


def test_register_document_idempotent_by_path(db_session, lore_file):
    """Calling register_document twice with the same path returns the same record."""
    doc1 = register_document(db_session, "Test Lore", lore_file)
    doc2 = register_document(db_session, "Test Lore", lore_file)
    assert doc1.id == doc2.id
    count = db_session.query(Document).filter_by(source_path=lore_file).count()
    assert count == 1


# ---------------------------------------------------------------------------
# TC-R2-03  register_document: idempotence by content_hash
# ---------------------------------------------------------------------------


def test_register_document_idempotent_by_hash(db_session, lore_file, lore_file_copy):
    """A renamed copy of a registered file returns the existing record."""
    doc1 = register_document(db_session, "Test Lore", lore_file)
    doc2 = register_document(db_session, "Test Lore Copy", lore_file_copy)
    assert doc1.id == doc2.id


# ---------------------------------------------------------------------------
# TC-R2-04  register_document: invalid scope raises ValueError
# ---------------------------------------------------------------------------


def test_register_document_invalid_scope(db_session, lore_file):
    """register_document raises ValueError for a scope not in the allowed set."""
    with pytest.raises(ValueError, match="not allowed"):
        register_document(db_session, "Test Lore", lore_file, scope="gondor")


# ---------------------------------------------------------------------------
# TC-R2-05  register_document: missing file raises FileNotFoundError
# ---------------------------------------------------------------------------


def test_register_document_missing_file(db_session):
    """register_document raises FileNotFoundError if source_path does not exist."""
    with pytest.raises(FileNotFoundError):
        register_document(db_session, "Ghost Lore", "/no/such/file.pdf")


# ---------------------------------------------------------------------------
# TC-R2-06  load_chunks: sequence values are correct
# ---------------------------------------------------------------------------


def test_load_chunks_sequence(db_session, lore_file):
    """Chunks are stored with monotonically increasing sequence starting at 0."""
    doc = register_document(db_session, "Seq Test", lore_file)
    load_chunks(db_session, doc, SAMPLE_TEXT)
    chunks = db_session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.sequence).all()
    assert [c.sequence for c in chunks] == list(range(len(chunks)))


# ---------------------------------------------------------------------------
# TC-R2-07  load_chunks: text stored verbatim
# ---------------------------------------------------------------------------


def test_load_chunks_text_verbatim(db_session, lore_file):
    """Stored chunk texts match chunk_text() output exactly."""
    doc = register_document(db_session, "Text Test", lore_file)
    load_chunks(db_session, doc, SAMPLE_TEXT)
    stored = db_session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.sequence).all()
    assert [c.text for c in stored] == chunk_text(SAMPLE_TEXT)


# ---------------------------------------------------------------------------
# TC-R2-08  load_chunks: idempotence on fully-chunked document
# ---------------------------------------------------------------------------


def test_load_chunks_idempotent(db_session, lore_file):
    """Second call on a fully-chunked document returns 0 and adds no chunks."""
    doc = register_document(db_session, "Idempotent Test", lore_file)
    n1 = load_chunks(db_session, doc, SAMPLE_TEXT)
    count_after_first = db_session.query(Chunk).filter_by(document_id=doc.id).count()

    n2 = load_chunks(db_session, doc, SAMPLE_TEXT)
    count_after_second = db_session.query(Chunk).filter_by(document_id=doc.id).count()

    assert n1 > 0
    assert n2 == 0
    assert count_after_first == count_after_second


# ---------------------------------------------------------------------------
# TC-R2-09  load_chunks: partial-failure recovery
# ---------------------------------------------------------------------------


def test_load_chunks_partial_recovery(db_session, lore_file):
    """A partial chunk set is deleted and replaced with the complete set on re-run."""
    doc = register_document(db_session, "Recovery Test", lore_file)
    expected_count = len(chunk_text(SAMPLE_TEXT))

    # Simulate a partial write: insert only one chunk directly.
    db_session.add(Chunk(document_id=doc.id, sequence=0, text="partial only"))
    db_session.commit()

    partial_count = db_session.query(Chunk).filter_by(document_id=doc.id).count()
    assert partial_count < expected_count

    n = load_chunks(db_session, doc, SAMPLE_TEXT)

    assert n == expected_count
    assert db_session.query(Chunk).filter_by(document_id=doc.id).count() == expected_count


# ---------------------------------------------------------------------------
# TC-R2-10  load_chunks: return value equals chunks stored
# ---------------------------------------------------------------------------


def test_load_chunks_return_value(db_session, lore_file):
    """load_chunks return value equals the number of chunks stored."""
    doc = register_document(db_session, "Return Value Test", lore_file)
    n = load_chunks(db_session, doc, SAMPLE_TEXT)
    assert n == len(chunk_text(SAMPLE_TEXT))
    assert db_session.query(Chunk).filter_by(document_id=doc.id).count() == n
