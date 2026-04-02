# -*- coding: utf-8 -*-
"""
load_entities.py

Inserts Entity and EntityAlias records from a reviewed staging file.

Public functions:

    load_entities(session, staging_data) -> dict[str, int]
        Insert Entity records from the staging lists (places, characters,
        factions, key_events). Returns a canonical_name -> entity_id mapping
        for use by downstream loaders (load_reviewed, load_relationships).
        Idempotent: existing entities are looked up by canonical_name, not
        duplicated.

    load_entity_aliases(session, aliases) -> int
        Insert EntityAlias records for a list of (entity_id, alias) pairs.
        Idempotent: existing (entity_id, alias) pairs are skipped.
        Note: the current staging format does not produce alias data. This
        function is a no-op when called with an empty list, and is reserved
        for future use when alias data is available.

Both functions use session.flush() rather than commit. The caller (load_reviewed.py)
owns the transaction boundary.

See: R4 design doc, FR-003, ADR-005.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from saskan_lore.data.models import Entity, EntityAlias

log = logging.getLogger(__name__)

# Staging list field -> entity_type value, in processing order.
_ENTITY_LISTS: list[tuple[str, str]] = [
    ("places", "place"),
    ("characters", "person"),
    ("factions", "faction"),
    ("key_events", "event"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_entities(session: Session, staging_data: dict) -> dict[str, int]:
    """Insert entities from a staging record and return a name->id mapping.

    Processes places, characters, factions, and key_events in order.
    For each name:
      - Empty strings are skipped with a warning.
      - Duplicate names within the same staging file (same name appearing
        in multiple lists) are skipped after the first occurrence.
      - Names already present in the DB are looked up and included in the
        returned mapping without re-inserting.
      - New entities are inserted and flushed to obtain their IDs.

    Args:
        session:      Active SQLAlchemy session.
        staging_data: Parsed staging JSON dict.

    Returns:
        Dict mapping canonical_name -> entity_id for all entities in this
        staging file.
    """
    name_to_id: dict[str, int] = {}
    inserted = 0
    skipped = 0

    for field, entity_type in _ENTITY_LISTS:
        for raw in staging_data.get(field, []):
            name = raw.strip() if isinstance(raw, str) else ""

            if not name:
                log.warning("load_entities: empty name in %r — skipped.", field)
                skipped += 1
                continue

            if name in name_to_id:
                log.warning(
                    "load_entities: %r already seen in this file — skipped.",
                    name,
                )
                skipped += 1
                continue

            existing = session.query(Entity).filter_by(canonical_name=name).first()
            if existing is not None:
                name_to_id[name] = existing.id
                continue

            entity = Entity(canonical_name=name, entity_type=entity_type)
            session.add(entity)
            session.flush()
            name_to_id[name] = entity.id
            inserted += 1

    log.info("load_entities: %d inserted, %d skipped.", inserted, skipped)
    return name_to_id


def load_entity_aliases(session: Session, aliases: list[tuple[int, str]]) -> int:
    """Insert EntityAlias records for a list of (entity_id, alias) pairs.

    Idempotent: existing (entity_id, alias) pairs are skipped without error.

    Note: the current staging format does not produce alias data. This
    function is a no-op when called with an empty list.

    Args:
        session: Active SQLAlchemy session.
        aliases: List of (entity_id, alias_string) tuples.

    Returns:
        Number of alias records inserted.
    """
    inserted = 0

    for entity_id, alias_str in aliases:
        name = alias_str.strip() if isinstance(alias_str, str) else ""

        if not name:
            log.warning(
                "load_entity_aliases: empty alias for entity_id=%d — skipped.",
                entity_id,
            )
            continue

        existing = session.query(EntityAlias).filter_by(entity_id=entity_id, alias=name).first()
        if existing is not None:
            continue

        session.add(EntityAlias(entity_id=entity_id, alias=name))
        session.flush()
        inserted += 1

    log.info("load_entity_aliases: %d inserted.", inserted)
    return inserted
