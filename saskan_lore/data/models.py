# saskan_lore/data/models.py
"""
SQLAlchemy ORM models for saskan_lore.

Defines Base, TimestampMixin, and all nine DB table model classes.

For field-level reference see: saskan_lore/data/schema/database_schema.py
For schema design notes see:   docs/design/pull_requests/r1_database/design.md
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """
    Audit columns inherited by all models.

    is_active:  False = record is deprecated; never deleted
    created_at: set once on insert
    updated_at: updated automatically on every change
    """

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class Document(TimestampMixin, Base):
    """Registered lore source document. Entry point for the ingestion pipeline."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    source_path = Column(String(500), nullable=False, unique=True)
    scope = Column(String(50), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, unique=True)  # SHA-256
    region = Column(String(100), nullable=True)
    ingested_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------


class Chunk(TimestampMixin, Base):
    """Retrievable text slice from a Document."""

    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    era = Column(String(100), nullable=True)
    canon_level = Column(String(50), nullable=True)   # canonical|apocryphal|disputed
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class Entity(TimestampMixin, Base):
    """Named entity in the lore: person, place, faction, artifact, era, event, or other."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String(200), nullable=False, unique=True)
    entity_type = Column(String(50), nullable=False, index=True)
    # person | place | faction | artifact | era | event | other


# ---------------------------------------------------------------------------
# EntityAlias
# ---------------------------------------------------------------------------


class EntityAlias(TimestampMixin, Base):
    """Alternate name for an Entity. One entity may have many aliases."""

    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint("entity_id", "alias", name="uq_entity_alias"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    alias = Column(String(200), nullable=False)


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------


class Claim(TimestampMixin, Base):
    """
    Discrete, source-quoted factual claim extracted from a Chunk.

    truth_status: fact | belief | interpretation | rumor
    status:       pending | approved | rejected  (never deleted)
    confidence:   high | medium | low
    """

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    source_span = Column(Text, nullable=False)
    truth_status = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    confidence = Column(String(10), nullable=True)


# ---------------------------------------------------------------------------
# ClaimEntity  (junction: claims <-> entities)
# ---------------------------------------------------------------------------


class ClaimEntity(TimestampMixin, Base):
    """Junction table linking Claims to the Entities they mention."""

    __tablename__ = "claim_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    role = Column(String(50), nullable=True)
    # subject | object | location | faction | etc.


# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------


class Relationship(TimestampMixin, Base):
    """
    Typed, directed relationship between two Entities.

    Bidirectional relationships are stored as two separate records.
    claim_id optionally links the relationship to supporting evidence.
    """

    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    target_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)
    # governs | allied_with | opposed_to | member_of | etc.
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)


# ---------------------------------------------------------------------------
# EvalQuestion
# ---------------------------------------------------------------------------


class EvalQuestion(TimestampMixin, Base):
    """Evaluation question with its expected answer."""

    __tablename__ = "eval_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    scope = Column(String(50), nullable=False, index=True)


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------


class EvalResult(TimestampMixin, Base):
    """
    Result of running one EvalQuestion through the pipeline.

    pass_fail and failure_type are set by human review after the automated run.
    retrieved_evidence stores a JSON-encoded list of Claim IDs used as context.

    failure_type: wrong_fact | hallucination | incomplete | style
    """

    __tablename__ = "eval_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("eval_questions.id"), nullable=False, index=True)
    model_answer = Column(Text, nullable=False)
    retrieved_evidence = Column(Text, nullable=True)   # JSON list of claim IDs
    pass_fail = Column(String(10), nullable=True)       # pass | fail
    failure_type = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    run_at = Column(DateTime, nullable=True)
