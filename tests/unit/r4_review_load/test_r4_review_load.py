# tests/unit/r4_review_load/test_r4_review_load.py
"""
R4 review and load unit tests.

Covers: review_staging.py, load_entities.py, load_relationships.py,
and load_reviewed.py.
See docs/design/r4_review_load/test_cases.md for the full test-case
register (TC-R4-01 through TC-R4-10).

All tests use the db_session fixture from tests/conftest.py:
  - in-memory SQLite, StaticPool, FK pragma ON, fresh per test.
Staging files are written to tmp_path — no reads from var/reviewed/.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from saskan_lore.data.models import Chunk, Claim, Document, Entity
from saskan_lore.loader.load_entities import load_entities
from saskan_lore.loader.load_relationships import load_relationships
from saskan_lore.loader.load_reviewed import load_file
from saskan_lore.loader.review_staging import review_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_staging(chunk_id: int, doc_id: int, claims: list[dict]) -> dict:
    """Build a minimal staging dict for a given chunk and document."""
    return {
        "chunk_id": f"chunk_{chunk_id:04d}",
        "document_id": f"doc_{doc_id:03d}",
        "title": "Oath Law in the Northern Provinces",
        "summary": "The Covenant of Varkaar governed oath law.",
        "era": "Third Era",
        "canon_level": "canonical",
        "truth_status": "fact",
        "region": ["Northern Provinces"],
        "places": ["Northern Provinces"],
        "characters": ["High Arbiter"],
        "factions": ["Covenant of Varkaar"],
        "key_events": [],
        "claims": claims,
    }


_APPROVED_CLAIM = {
    "claim_text": "The Covenant of Varkaar governed oath law.",
    "source_span": "The Covenant governed the northern provinces.",
    "truth_status": "fact",
    "confidence": "high",
    "review_status": "approved",
}

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def varkaar_doc(db_session) -> Document:
    """Registered Document with scope='varkaar'."""
    doc = Document(
        title="Varkaar Canon",
        source_path="/fake/varkaar.pdf",
        scope="varkaar",
        content_hash="a" * 64,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture
def varkaar_chunk(db_session, varkaar_doc) -> Chunk:
    """Chunk linked to the varkaar document."""
    chunk = Chunk(
        document_id=varkaar_doc.id,
        sequence=0,
        text="The Covenant governed the northern provinces.",
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk


@pytest.fixture
def staging_path(tmp_path, varkaar_chunk, varkaar_doc) -> Path:
    """Staging file with one approved claim."""
    data = _make_staging(varkaar_chunk.id, varkaar_doc.id, [dict(_APPROVED_CLAIM)])
    p = tmp_path / f"chunk_{varkaar_chunk.id:04d}_extraction.json"
    p.write_text(json.dumps(data, indent=2))
    return p


# ---------------------------------------------------------------------------
# TC-R4-01  load_entities: inserts from staging lists with correct types
# ---------------------------------------------------------------------------


def test_load_entities_inserts_from_staging(db_session, varkaar_chunk, varkaar_doc):
    """Entities from places, characters, and factions are inserted correctly."""
    staging = _make_staging(varkaar_chunk.id, varkaar_doc.id, [])

    name_to_id = load_entities(db_session, staging)

    assert "Northern Provinces" in name_to_id
    assert "High Arbiter" in name_to_id
    assert "Covenant of Varkaar" in name_to_id

    np_entity = db_session.get(Entity, name_to_id["Northern Provinces"])
    assert np_entity.entity_type == "place"

    ha_entity = db_session.get(Entity, name_to_id["High Arbiter"])
    assert ha_entity.entity_type == "person"

    cov_entity = db_session.get(Entity, name_to_id["Covenant of Varkaar"])
    assert cov_entity.entity_type == "faction"


# ---------------------------------------------------------------------------
# TC-R4-02  load_entities: idempotent — no duplicates on second call
# ---------------------------------------------------------------------------


def test_load_entities_idempotent(db_session, varkaar_chunk, varkaar_doc):
    """Calling load_entities() twice produces no duplicate Entity records."""
    staging = _make_staging(varkaar_chunk.id, varkaar_doc.id, [])

    map1 = load_entities(db_session, staging)
    map2 = load_entities(db_session, staging)

    assert map1 == map2
    count = db_session.query(Entity).filter_by(canonical_name="Covenant of Varkaar").count()
    assert count == 1


# ---------------------------------------------------------------------------
# TC-R4-03  load_file: approved claim inserted with status='approved'
# ---------------------------------------------------------------------------


def test_load_file_approved_claim_inserted(db_session, staging_path):
    """A claim with review_status='approved' is inserted with status='approved'."""
    summary = load_file(db_session, staging_path)

    assert summary["claims_loaded"] == 1
    claim = db_session.query(Claim).first()
    assert claim is not None
    assert claim.status == "approved"
    assert claim.claim_text == _APPROVED_CLAIM["claim_text"]


# ---------------------------------------------------------------------------
# TC-R4-04  load_file: unreviewed claim is skipped
# ---------------------------------------------------------------------------


def test_load_file_unreviewed_claim_skipped(db_session, tmp_path, varkaar_chunk, varkaar_doc):
    """A claim with review_status='pending' is not inserted."""
    pending = {**_APPROVED_CLAIM, "review_status": "pending"}

    data = _make_staging(varkaar_chunk.id, varkaar_doc.id, [pending])
    p = tmp_path / "chunk_unreviewed.json"
    p.write_text(json.dumps(data))

    summary = load_file(db_session, p)

    assert summary["claims_loaded"] == 0
    assert summary["claims_skipped"] == 1
    assert db_session.query(Claim).count() == 0


# ---------------------------------------------------------------------------
# TC-R4-05  load_file: rejected claim inserted with status='rejected'
# ---------------------------------------------------------------------------


def test_load_file_rejected_claim_inserted(db_session, tmp_path, varkaar_chunk, varkaar_doc):
    """A claim with status='rejected' is inserted with status='rejected'."""
    rejected = {
        "claim_text": "An invented detail.",
        "source_span": "The Covenant governed the northern provinces.",
        "truth_status": "fact",
        "review_status": "rejected",
        "reject_reason": "hallucinated",
    }
    data = _make_staging(varkaar_chunk.id, varkaar_doc.id, [rejected])
    p = tmp_path / "chunk_rejected.json"
    p.write_text(json.dumps(data))

    summary = load_file(db_session, p)

    assert summary["claims_rejected"] == 1
    assert summary["claims_loaded"] == 0
    claim = db_session.query(Claim).first()
    assert claim is not None
    assert claim.status == "rejected"


# ---------------------------------------------------------------------------
# TC-R4-06  load_file: claim missing source_span is skipped
# ---------------------------------------------------------------------------


def test_load_file_invalid_claim_skipped(db_session, tmp_path, varkaar_chunk, varkaar_doc):
    """A claim missing source_span fails validation and is not inserted."""
    invalid = {
        "claim_text": "The Covenant governed oath law.",
        "source_span": "",
        "truth_status": "fact",
        "review_status": "approved",
    }
    data = _make_staging(varkaar_chunk.id, varkaar_doc.id, [invalid])
    p = tmp_path / "chunk_invalid.json"
    p.write_text(json.dumps(data))

    summary = load_file(db_session, p)

    assert summary["claims_skipped"] == 1
    assert summary["claims_loaded"] == 0
    assert db_session.query(Claim).count() == 0


# ---------------------------------------------------------------------------
# TC-R4-07  load_file: idempotent — no duplicates on second load
# ---------------------------------------------------------------------------


def test_load_file_idempotent(db_session, staging_path):
    """Loading the same staging file twice produces no duplicate records."""
    load_file(db_session, staging_path)
    load_file(db_session, staging_path)

    assert db_session.query(Claim).count() == 1
    assert (db_session.query(Entity).filter_by(canonical_name="Covenant of Varkaar").count()) == 1


# ---------------------------------------------------------------------------
# TC-R4-08  load_file: missing chunk raises ValueError
# ---------------------------------------------------------------------------


def test_load_file_missing_chunk_raises(db_session, tmp_path):
    """load_file() raises ValueError when chunk_id has no matching DB record."""
    data = _make_staging(chunk_id=9999, doc_id=1, claims=[dict(_APPROVED_CLAIM)])
    p = tmp_path / "chunk_9999_extraction.json"
    p.write_text(json.dumps(data))

    with pytest.raises(ValueError, match="not found"):
        load_file(db_session, p)


# ---------------------------------------------------------------------------
# TC-R4-09  load_relationships: unknown entity is skipped, no error raised
# ---------------------------------------------------------------------------


def test_load_relationships_unknown_entity_skipped(db_session):
    """load_relationships() skips a relationship when source is not in entity_map."""
    relationships = [
        {
            "source": "Unknown Faction",
            "target": "Covenant of Varkaar",
            "relationship_type": "opposed_to",
        }
    ]
    result = load_relationships(db_session, relationships, entity_map={})

    assert result == 0


# ---------------------------------------------------------------------------
# TC-R4-10  review_file: approve action writes review_status='approved' to JSON
# ---------------------------------------------------------------------------


def test_review_file_approve_writes_review_status_approved(tmp_path):
    """Approve action sets review_status='approved' on the claim and writes back to disk."""
    claim = {
        "claim_text": "The Covenant governed oath law.",
        "source_span": "The Covenant governed the northern provinces.",
        "truth_status": "fact",
        "review_status": "pending",
    }
    data = {
        "chunk_id": "chunk_0001",
        "document_id": "doc_001",
        "claims": [claim],
    }
    p = tmp_path / "chunk_0001_extraction.json"
    p.write_text(json.dumps(data))

    with patch("typer.prompt", return_value="a"), patch("typer.echo"):
        counts = review_file(p)

    assert counts["approved"] == 1
    written = json.loads(p.read_text())
    assert written["claims"][0]["review_status"] == "approved"
