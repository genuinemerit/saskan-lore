# -*- coding: utf-8 -*-
"""
database_schema.py

Canonical schema definitions for the saskan_lore database, plus staging
dataclasses for LLM extraction output.

Each class is a frozen dataclass. DB table classes serve as the authoritative
field-level reference for the SQLAlchemy models built in Release 1. Staging
classes represent the intermediate JSON format written to reviewed/ before
DB load. All classes are importable and linter-clean but are not ORM models.

DB table inventory:
    DocumentRecord      -- registered lore source documents
    ChunkRecord         -- sentence chunks linked to documents
    EntityRecord        -- named entities (persons, places, factions, events, etc.)
    EntityAliasRecord   -- alternate names for entities
    ClaimRecord         -- extracted, source-quoted factual claims
    ClaimEntityRecord   -- junction: claims <-> entities
    RelationshipRecord  -- typed, directed entity relationships
    EvalQuestionRecord  -- evaluation questions with expected answers
    EvalResultRecord    -- per-run evaluation results

Staging (LLM extraction output, not DB tables):
    ExtractionClaimRecord  -- a single claim within an extraction result
    ExtractionRecord       -- full LLM extraction output for one chunk

See: ADR-002 (SQLite + SQLAlchemy), ADR-003 (claims as first-class),
     ADR-004 (truth-status), ADR-005 (relationships), FR-001 through FR-008.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DocumentRecord:
    """
    A registered lore source document. Entry point for the ingestion pipeline.

    See: FR-001, Workflow Stage 1.
    """

    id: int
    title: str
    source_path: str  # path under data/lore_texts/
    scope: str  # lore domain, e.g. "varkaar"
    content_hash: str  # SHA-256 of source text; used for idempotence
    region: str | None = field(default=None)
    ingested_at: datetime | None = field(default=None)
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class ChunkRecord:
    """
    A retrievable text slice from a DocumentRecord.

    Chunk text is stored verbatim except for approved normalization.
    Sequence is 0-indexed within the parent document.

    summary:     LLM-generated summary of this chunk's content (extraction output)
    era:         era label for the events/content described in this chunk
    canon_level: reliability/canonicity of the source; e.g. "canonical", "apocryphal", "disputed"

    See: FR-002, Workflow Stage 2.
    """

    id: int
    document_id: int  # FK -> DocumentRecord.id
    sequence: int  # position within document, 0-indexed
    text: str  # verbatim chunk content
    summary: str | None = field(default=None)
    era: str | None = field(default=None)
    canon_level: str | None = field(default=None)
    char_start: int | None = field(default=None)  # character offset in source
    char_end: int | None = field(default=None)  # character offset in source
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class EntityRecord:
    """
    A named entity in the lore: person, place, faction, artifact, era, or other.

    Canonical names are normalized at ingestion (e.g. title case).
    Entity IDs are stable once assigned and must never be reused.

    See: FR-003, ADR-005.
    """

    id: int
    canonical_name: str
    entity_type: str  # person | place | faction | artifact | era | event | other
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class EntityAliasRecord:
    """
    An alternate name for an EntityRecord.

    One entity may have many aliases; each alias is a separate record.

    See: FR-003.
    """

    id: int
    entity_id: int  # FK -> EntityRecord.id
    alias: str
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class ClaimRecord:
    """
    A discrete, source-quoted factual claim extracted from a ChunkRecord.

    Claims are the primary unit of retrieval and evaluation. Only claims
    with status='approved' are eligible for retrieval.

    truth_status values: fact | belief | interpretation | rumor
    status values:       pending | approved | rejected

    Records are never deleted. Rejected claims remain in the DB with
    status='rejected' to preserve the review audit trail.

    See: FR-004, ADR-003, ADR-004, NFR-003, NFR-004.
    """

    id: int
    chunk_id: int  # FK -> ChunkRecord.id
    document_id: int  # FK -> DocumentRecord.id (denormalized for query convenience)
    claim_text: str  # the extracted statement in clean prose
    source_span: str  # verbatim quote from source supporting this claim
    truth_status: str  # fact | belief | interpretation | rumor
    status: str  # pending | approved | rejected
    confidence: str | None = field(default=None)  # extraction confidence: high | medium | low
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class ClaimEntityRecord:
    """
    Junction table linking claims to the entities they mention.

    role captures the entity's semantic function in the claim,
    e.g. "subject", "object", "location", "faction".

    See: FR-004.
    """

    id: int
    claim_id: int  # FK -> ClaimRecord.id
    entity_id: int  # FK -> EntityRecord.id
    role: str | None = field(default=None)
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class RelationshipRecord:
    """
    A typed, directed relationship between two entities.

    Bidirectional relationships are stored as two separate records.
    Both entities must exist before a relationship can be created.

    relationship_type uses a controlled vocabulary; see FR-005.

    See: FR-005, ADR-005.
    """

    id: int
    source_entity_id: int  # FK -> EntityRecord.id
    target_entity_id: int  # FK -> EntityRecord.id
    relationship_type: str  # e.g. "governs", "allied_with", "opposed_to", "member_of"
    claim_id: int | None = field(default=None)  # FK -> ClaimRecord.id (supporting evidence)
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class EvalQuestionRecord:
    """
    An evaluation question with its expected answer.

    Pre-pilot target: 10 questions covering the Covenant of Varkaar domain.

    See: FR-008, ADR-006.
    """

    id: int
    question_text: str
    expected_answer: str
    scope: str  # lore domain, e.g. "varkaar"
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class EvalResultRecord:
    """
    The result of running one evaluation question through the pipeline.

    pass_fail and failure_type are set by human review after the automated run.

    failure_type values: wrong_fact | hallucination | incomplete | style

    See: FR-008.
    """

    id: int
    question_id: int  # FK -> EvalQuestionRecord.id
    model_answer: str
    retrieved_evidence: str  # JSON-encoded list of ClaimRecord IDs used as context
    pass_fail: str | None = field(default=None)  # pass | fail; set by reviewer
    # wrong_fact | hallucination | incomplete | style
    failure_type: str | None = field(default=None)
    notes: str | None = field(default=None)
    run_at: datetime | None = field(default=None)
    is_active: bool = field(default=True)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)


# ---------------------------------------------------------------------------
# Staging structures -- LLM extraction output (not DB tables)
# Written to reviewed/ as JSON; loaded into DB after human review in R4.
# See: Workflow Stage 3.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionClaimRecord:
    """
    A single claim within an ExtractionRecord.

    Maps to ClaimRecord on DB load; field names are aligned for that purpose.

    statement   -> ClaimRecord.claim_text
    confidence  -> ClaimRecord.confidence
    source_span -> ClaimRecord.source_span
    """

    statement: str  # the extracted claim; maps to ClaimRecord.claim_text
    source_span: str  # verbatim quote from source
    truth_status: str  # fact | belief | interpretation | rumor
    confidence: str | None = field(default=None)  # high | medium | low


@dataclass(frozen=True)
class ExtractionRecord:
    """
    Full LLM extraction output for one chunk. Written to reviewed/ as JSON.

    Not a DB table — this is the staging format consumed by the human review
    and load steps (R4).

    List fields (places, characters, factions, key_events) contain entity
    names that are resolved to EntityRecord entries during DB load.

    canon_level: source reliability; e.g. "canonical", "apocryphal", "disputed"
    era:         era label for the content described in this chunk
    region:      geographic region(s) covered
    """

    chunk_id: str  # string reference, e.g. "chunk_0042"
    document_id: str  # string reference, e.g. "doc_001"
    title: str
    summary: str
    era: str
    canon_level: str
    truth_status: str  # overall truth-status of the source passage
    region: list[str]  # geographic regions mentioned
    places: list[str]  # place entity names (-> EntityRecord, type="place")
    characters: list[str]  # character entity names (-> EntityRecord, type="person")
    factions: list[str]  # faction entity names (-> EntityRecord, type="faction")
    key_events: list[str]  # event entity names (-> EntityRecord, type="event")
    claims: list[ExtractionClaimRecord]
