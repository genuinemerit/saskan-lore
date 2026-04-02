# -*- coding: utf-8 -*-
"""
load_relationships.py

Inserts Relationship records from reviewed staging data into the database.

Public function:

    load_relationships(session, relationships, entity_map) -> int
        Insert typed, directed relationships between entities. Returns the
        number of records inserted.
        Idempotent: existing (source_entity_id, target_entity_id,
        relationship_type) triples are skipped.

Note: the current staging format (ExtractionRecord) does not include a
relationships list. This function is a no-op when called with an empty list
and is ready for use once relationship data is added to the staging format.
That extension belongs to a future extraction design iteration.

Each relationship dict is expected to have:
    source          -- canonical name of the source entity
    target          -- canonical name of the target entity
    relationship_type -- non-empty string, e.g. "governs", "allied_with"
    claim_id        -- (optional) int FK to a loaded Claim record

Entity names are resolved to IDs via the entity_map produced by
load_entities(). Relationships referencing unknown entities are skipped
and logged, not raised as fatal errors.

load_relationships() uses session.flush() rather than commit. The caller
(load_reviewed.py) owns the transaction boundary.

See: R4 design doc, FR-005, ADR-005.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from saskan_lore.data.models import Relationship

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_relationships(
    session: Session,
    relationships: list[dict],
    entity_map: dict[str, int],
) -> int:
    """Insert typed, directed relationships between entities.

    Resolves source and target entity names to IDs using entity_map. Skips
    any relationship where either entity is not present in entity_map or the
    DB, where relationship_type is empty, or where the triple already exists.

    Idempotence key: (source_entity_id, target_entity_id, relationship_type).

    Args:
        session:       Active SQLAlchemy session.
        relationships: List of relationship dicts, each with keys:
                       source, target, relationship_type, and optionally
                       claim_id.
        entity_map:    canonical_name -> entity_id mapping from load_entities().

    Returns:
        Number of Relationship records inserted.
    """
    if not relationships:
        log.info("load_relationships: no relationship data in staging — skipped.")
        return 0

    inserted = 0
    skipped = 0

    for rel in relationships:
        source_name = (rel.get("source") or "").strip()
        target_name = (rel.get("target") or "").strip()
        rel_type = (rel.get("relationship_type") or "").strip()

        if not rel_type:
            log.warning("load_relationships: missing relationship_type — skipped.")
            skipped += 1
            continue

        source_id = entity_map.get(source_name)
        if source_id is None:
            log.warning(
                "load_relationships: source entity %r not found — skipped.",
                source_name,
            )
            skipped += 1
            continue

        target_id = entity_map.get(target_name)
        if target_id is None:
            log.warning(
                "load_relationships: target entity %r not found — skipped.",
                target_name,
            )
            skipped += 1
            continue

        existing = (
            session.query(Relationship)
            .filter_by(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=rel_type,
            )
            .first()
        )
        if existing is not None:
            continue

        claim_id = rel.get("claim_id") or None
        session.add(
            Relationship(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=rel_type,
                claim_id=claim_id,
            )
        )
        session.flush()
        inserted += 1

    log.info("load_relationships: %d inserted, %d skipped.", inserted, skipped)
    return inserted
