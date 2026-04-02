# tests/unit/r1_database/test_r1_db.py
"""
R1 database layer unit tests.

Covers: schema structure, column defaults, nullability, unique constraints,
and FK enforcement.  See docs/design/r1_database/test_cases.md
for the full test-case register (TC-R1-01 through TC-R1-10).

All tests use the db_session fixture from tests/conftest.py:
  - in-memory SQLite, StaticPool, FK pragma ON, fresh per test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from saskan_lore.data.models import (
    Chunk,
    Claim,
    ClaimEntity,
    Document,
    Entity,
    EntityAlias,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HASH_A = "a" * 64  # valid SHA-256 placeholder


def _doc(session, *, title="Doc", path="/lore/doc.pdf", scope="varkaar", hash_=_HASH_A):
    """Insert and flush a minimal Document; return the persisted instance."""
    doc = Document(title=title, source_path=path, scope=scope, content_hash=hash_)
    session.add(doc)
    session.flush()
    return doc


def _chunk(session, doc, *, sequence=1, text="some lore text"):
    """Insert and flush a Chunk linked to doc; return the instance."""
    chunk = Chunk(document_id=doc.id, sequence=sequence, text=text)
    session.add(chunk)
    session.flush()
    return chunk


def _claim(session, doc, chunk, *, text="A claim.", span="source span"):
    """Insert and flush a Claim linked to doc and chunk; return the instance."""
    claim = Claim(
        chunk_id=chunk.id,
        document_id=doc.id,
        claim_text=text,
        source_span=span,
        truth_status="fact",
    )
    session.add(claim)
    session.flush()
    return claim


def _entity(session, *, name="Varkaar", kind="faction"):
    """Insert and flush an Entity; return the instance."""
    ent = Entity(canonical_name=name, entity_type=kind)
    session.add(ent)
    session.flush()
    return ent


# ---------------------------------------------------------------------------
# TC-R1-01  All 9 tables present
# ---------------------------------------------------------------------------


def test_all_tables_present(db_session):
    """Schema contains exactly the expected 9 tables after create_all."""
    inspector = sa_inspect(db_session.bind)
    tables = set(inspector.get_table_names())
    expected = {
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
    assert tables == expected


# ---------------------------------------------------------------------------
# TC-R1-02  Claim.status defaults to 'pending'
# ---------------------------------------------------------------------------


def test_claim_status_default(db_session):
    """A new Claim with no explicit status has status == 'pending'."""
    doc = _doc(db_session)
    chunk = _chunk(db_session, doc)
    claim = _claim(db_session, doc, chunk)
    assert claim.status == "pending"


# ---------------------------------------------------------------------------
# TC-R1-03  TimestampMixin is_active defaults to True
# ---------------------------------------------------------------------------


def test_timestamp_mixin_is_active_default(db_session):
    """is_active is True immediately after inserting a Document."""
    doc = _doc(db_session)
    assert doc.is_active is True


# ---------------------------------------------------------------------------
# TC-R1-04  Document.region is nullable
# ---------------------------------------------------------------------------


def test_document_region_nullable(db_session):
    """Document inserts cleanly with region=None (nullable column)."""
    doc = Document(
        title="No Region Doc",
        source_path="/lore/no_region.pdf",
        scope="varkaar",
        content_hash="b" * 64,
        region=None,
    )
    db_session.add(doc)
    db_session.flush()
    assert doc.id is not None
    assert doc.region is None


# ---------------------------------------------------------------------------
# TC-R1-05  Chunk FK orphan raises IntegrityError
# ---------------------------------------------------------------------------


def test_chunk_fk_orphan_raises(db_session):
    """Inserting a Chunk with a nonexistent document_id raises IntegrityError."""
    orphan = Chunk(document_id=99999, sequence=1, text="orphan chunk")
    db_session.add(orphan)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# TC-R1-06  Claim FK orphan raises IntegrityError
# ---------------------------------------------------------------------------


def test_claim_fk_orphan_raises(db_session):
    """Inserting a Claim with a nonexistent chunk_id raises IntegrityError."""
    doc = _doc(db_session)
    orphan = Claim(
        chunk_id=99999,
        document_id=doc.id,
        claim_text="orphan",
        source_span="span",
        truth_status="fact",
    )
    db_session.add(orphan)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# TC-R1-07  Entity.canonical_name unique constraint
# ---------------------------------------------------------------------------


def test_entity_canonical_name_unique(db_session):
    """Two Entities with the same canonical_name raise IntegrityError."""
    _entity(db_session, name="House Varkaar")
    db_session.add(Entity(canonical_name="House Varkaar", entity_type="faction"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# TC-R1-08  EntityAlias (entity_id, alias) unique constraint
# ---------------------------------------------------------------------------


def test_entity_alias_unique_constraint(db_session):
    """Duplicate (entity_id, alias) pair on EntityAlias raises IntegrityError."""
    ent = _entity(db_session)
    db_session.add(EntityAlias(entity_id=ent.id, alias="The Covenant"))
    db_session.flush()
    db_session.add(EntityAlias(entity_id=ent.id, alias="The Covenant"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# TC-R1-09  ClaimEntity FK orphan raises IntegrityError
# ---------------------------------------------------------------------------


def test_claim_entity_fk_orphan_raises(db_session):
    """ClaimEntity with a nonexistent claim_id raises IntegrityError."""
    ent = _entity(db_session)
    orphan = ClaimEntity(claim_id=99999, entity_id=ent.id, role="subject")
    db_session.add(orphan)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# TC-R1-10  Full insert chain
# ---------------------------------------------------------------------------


def test_full_insert_chain(db_session):
    """
    Document → Chunk → Claim → Entity → ClaimEntity all insert without error.
    Verifies that the FK dependency order is correct and all IDs are assigned.
    """
    doc = _doc(db_session, title="Varkaar Chronicle", path="/lore/varkaar.pdf")
    chunk = _chunk(db_session, doc, text="The Covenant was formed in the third era.")
    claim = _claim(
        db_session,
        doc,
        chunk,
        text="The Covenant was formed in the third era.",
        span="The Covenant was formed in the third era.",
    )
    ent = _entity(db_session, name="The Covenant", kind="faction")
    ce = ClaimEntity(claim_id=claim.id, entity_id=ent.id, role="subject")
    db_session.add(ce)
    db_session.flush()

    assert doc.id is not None
    assert chunk.document_id == doc.id
    assert claim.chunk_id == chunk.id
    assert claim.document_id == doc.id
    assert ce.claim_id == claim.id
    assert ce.entity_id == ent.id
