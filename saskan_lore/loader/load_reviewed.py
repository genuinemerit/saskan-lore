# -*- coding: utf-8 -*-
"""
load_reviewed.py

Orchestrates the full load sequence for a reviewed staging file.

Public functions:

    load_file(session, path) -> dict
        Load all approved and rejected records from a staging file into the
        database in dependency order. Commits the transaction on success.
        Returns a summary dict.

    print_load_summary(summary)
        Print a formatted load summary to stdout.

Load order (mirrors FK dependency chain):
    1. load_entities()        — no FK dependencies
    2. load_entity_aliases()  — depends on entities (no-op; staging has no alias data)
    3. _load_claims()         — depends on chunks, documents
    4. _load_claim_entities() — depends on claims, entities
    5. load_relationships()   — depends on entities (no-op; staging has no relationship data)

Validation is skip-and-log: records failing validation are counted and reported
in the summary, not raised as fatal errors.

Note: validate_staging() (R3 extractor output check) is not used here. Post-review
staging files may have reviewed=true, status, and reject_reason fields that would
fail that schema. The loader validates fields directly in code. See R4 design doc.

See: R4 design doc, FR-003, FR-004, FR-005, NFR-003, NFR-004.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from sqlalchemy.orm import Session

from saskan_lore.data.models import Chunk, Claim, ClaimEntity
from saskan_lore.loader.load_entities import load_entities, load_entity_aliases
from saskan_lore.loader.load_relationships import load_relationships

log = logging.getLogger(__name__)

_VALID_TRUTH_STATUSES = frozenset({"fact", "belief", "interpretation", "rumor"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_int_id(value: str) -> int | None:
    """Parse a staging reference string to an integer ID.

    Handles formats like 'chunk_0042' -> 42 and 'doc_001' -> 1.
    Returns None if parsing fails.
    """
    try:
        return int(value.split("_")[-1])
    except (ValueError, AttributeError, IndexError):
        return None


def _validate_claim(claim: dict) -> list[str]:
    """Return a list of validation error strings for a claim dict.

    An empty list means the claim is valid for DB insertion.
    """
    errors = []
    if not str(claim.get("claim_text") or "").strip():
        errors.append("missing claim_text")
    if not str(claim.get("source_span") or "").strip():
        errors.append("missing source_span")
    if claim.get("truth_status") not in _VALID_TRUTH_STATUSES:
        errors.append(f"invalid truth_status {claim.get('truth_status')!r}")
    return errors


def _load_claims(
    session: Session,
    claims: list[dict],
    chunk_id: int,
    document_id: int,
) -> tuple[list[tuple[int, str]], int, int]:
    """Insert Claim records from a list of staging claim dicts.

    Processes approved (reviewed=true) and rejected (status='rejected') claims.
    Unreviewed claims (neither flag set) are skipped with a warning.

    Idempotence key: (chunk_id, claim_text).

    Args:
        session:     Active SQLAlchemy session.
        claims:      List of claim dicts from the staging file.
        chunk_id:    Integer chunk FK.
        document_id: Integer document FK.

    Returns:
        Tuple of (approved_pairs, skipped_count, rejected_count) where
        approved_pairs is a list of (claim_id, claim_text) for use by
        _load_claim_entities().
    """
    approved: list[tuple[int, str]] = []
    skipped = 0
    rejected = 0

    for claim in claims:
        is_approved = claim.get("reviewed") is True
        is_rejected = claim.get("status") == "rejected"

        if not is_approved and not is_rejected:
            log.warning(
                "load_claims: claim not yet reviewed — skipped. " "text: %.60r",
                claim.get("claim_text", ""),
            )
            skipped += 1
            continue

        errors = _validate_claim(claim)
        if errors:
            log.warning(
                "load_claims: validation failed (%s) — skipped.",
                ", ".join(errors),
            )
            skipped += 1
            continue

        claim_text = claim["claim_text"].strip()

        existing = session.query(Claim).filter_by(chunk_id=chunk_id, claim_text=claim_text).first()
        if existing is not None:
            log.warning("load_claims: duplicate claim — skipped.")
            skipped += 1
            continue

        status = "approved" if is_approved else "rejected"
        record = Claim(
            chunk_id=chunk_id,
            document_id=document_id,
            claim_text=claim_text,
            source_span=claim["source_span"].strip(),
            truth_status=claim["truth_status"],
            status=status,
            confidence=claim.get("confidence") or None,
        )
        session.add(record)
        session.flush()

        if is_approved:
            approved.append((record.id, claim_text))
            if claim.get("reject_reason"):
                log.info(
                    "load_claims: approved claim had reject_reason set — ignored.",
                )
        else:
            rejected += 1
            reason = claim.get("reject_reason", "")
            log.info(
                "load_claims: rejected claim inserted (id=%d). reason: %s",
                record.id,
                reason or "none provided",
            )

    return approved, skipped, rejected


def _load_claim_entities(
    session: Session,
    approved_claims: list[tuple[int, str]],
    entity_map: dict[str, int],
) -> int:
    """Create ClaimEntity links for entities that appear in approved claim text.

    Uses case-insensitive substring matching to detect entity mentions.
    Role is not set (NULL) as the staging format does not provide role data.
    Idempotent: existing (claim_id, entity_id) pairs are skipped.

    Args:
        session:         Active SQLAlchemy session.
        approved_claims: List of (claim_id, claim_text) from _load_claims().
        entity_map:      canonical_name -> entity_id from load_entities().

    Returns:
        Number of ClaimEntity records inserted.
    """
    linked = 0

    for claim_id, claim_text in approved_claims:
        text_lower = claim_text.lower()
        for name, entity_id in entity_map.items():
            if name.lower() not in text_lower:
                continue
            existing = (
                session.query(ClaimEntity).filter_by(claim_id=claim_id, entity_id=entity_id).first()
            )
            if existing is not None:
                continue
            session.add(ClaimEntity(claim_id=claim_id, entity_id=entity_id))
            session.flush()
            linked += 1

    log.info("_load_claim_entities: %d link(s) created.", linked)
    return linked


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_file(session: Session, path: Path) -> dict:
    """Load all approved and rejected records from a staging file.

    Runs the full load sequence in FK dependency order, commits on success,
    and returns a summary dict.

    Raises:
        ValueError:        If chunk_id or document_id cannot be parsed, or if
                           the referenced chunk does not exist in the DB.
        FileNotFoundError: If path does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    chunk_id = _parse_int_id(data.get("chunk_id", ""))
    document_id = _parse_int_id(data.get("document_id", ""))

    if chunk_id is None:
        raise ValueError(f"Cannot parse chunk_id from {data.get('chunk_id')!r}")
    if document_id is None:
        raise ValueError(f"Cannot parse document_id from {data.get('document_id')!r}")

    if session.get(Chunk, chunk_id) is None:
        raise ValueError(f"Chunk id={chunk_id} not found in database.")

    # 1. Entities
    entity_map = load_entities(session, data)

    # 2. Aliases — no-op for current staging format
    load_entity_aliases(session, [])

    # 3. Claims
    approved_claims, skipped, rejected = _load_claims(
        session, data.get("claims", []), chunk_id, document_id
    )

    # 4. Claim-entity links
    linked = _load_claim_entities(session, approved_claims, entity_map)

    # 5. Relationships — no-op for current staging format
    load_relationships(session, [], entity_map)

    session.commit()

    return {
        "entities_loaded": len(entity_map),
        "claims_loaded": len(approved_claims),
        "claims_skipped": skipped,
        "claims_rejected": rejected,
        "claim_entity_links": linked,
    }


def print_load_summary(summary: dict) -> None:
    """Print a formatted load summary to stdout."""
    typer.echo("")
    typer.echo("── Load summary " + "─" * 40)
    typer.echo(f"  Entities loaded      : {summary['entities_loaded']}")
    typer.echo(f"  Claims loaded        : {summary['claims_loaded']}")
    typer.echo(f"  Claims skipped       : {summary['claims_skipped']}")
    typer.echo(f"  Claims rejected      : {summary['claims_rejected']}")
    typer.echo(f"  Claim-entity links   : {summary['claim_entity_links']}")
    typer.echo("")
