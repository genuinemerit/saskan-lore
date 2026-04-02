# tests/unit/r3_extraction/test_r3_extraction.py
"""
R3 extraction unit tests.

Covers: extract_chunk (extractor.py) and staging utilities (staging.py).
See docs/design/r3_extraction/test_cases.md for the full
test-case register (TC-R3-01 through TC-R3-10).

llama_cpp is mocked at the conftest level; complete() is patched per-test.
All tests use the db_session fixture from tests/conftest.py.
REVIEWED_DIR is set to a tmp_path subdirectory via monkeypatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from saskan_lore.analyzer.extractor import extract_chunk
from saskan_lore.analyzer.staging import (
    list_errors,
    list_staging,
    load_for_document,
    validate_staging,
)
from saskan_lore.data.models import Chunk, Document

# ---------------------------------------------------------------------------
# Fixture response strings
# ---------------------------------------------------------------------------

# Valid model response — no 'reviewed' field (extractor injects it).
_GOOD_RESPONSE = json.dumps(
    {
        "chunk_id": "chunk_0001",
        "document_id": "doc_001",
        "title": "Oath Law in the Northern Provinces",
        "summary": "The Covenant of Varkaar governed oath law in the northern provinces.",
        "era": "Third Era",
        "canon_level": "canonical",
        "truth_status": "fact",
        "region": ["Northern Provinces"],
        "places": [],
        "characters": [],
        "factions": ["Covenant of Varkaar"],
        "key_events": [],
        "claims": [
            {
                "claim_text": (
                    "The Covenant of Varkaar governed oath law in the northern provinces."
                ),
                "source_span": "The Covenant of Varkaar was established in the third era.",
                "truth_status": "fact",
                "confidence": "high",
            }
        ],
    }
)

# Model response where a claim incorrectly includes reviewed=True.
_REVIEWED_TRUE_RESPONSE = json.dumps(
    {
        "chunk_id": "chunk_0001",
        "document_id": "doc_001",
        "title": "Test",
        "summary": "Test summary.",
        "era": "",
        "canon_level": "canonical",
        "truth_status": "fact",
        "region": [],
        "places": [],
        "characters": [],
        "factions": [],
        "key_events": [],
        "claims": [
            {
                "claim_text": "A claim.",
                "source_span": "A verbatim quote.",
                "truth_status": "fact",
                "confidence": "high",
                "reviewed": True,
            }
        ],
    }
)

_BAD_JSON = "this is not json {"

_MISSING_FIELDS_RESPONSE = json.dumps(
    {
        "summary": "Missing chunk_id, document_id, and claims.",
    }
)

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def reviewed_dir(tmp_path: Path) -> Path:
    """Temporary staging directory."""
    d = tmp_path / "reviewed"
    d.mkdir()
    return d


@pytest.fixture
def varkaar_doc(db_session) -> Document:
    """In-scope Document with scope='varkaar'."""
    doc = Document(
        title="Varkaar Canon", source_path="/fake/doc.pdf", scope="varkaar", content_hash="a" * 64
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
        text="The Covenant of Varkaar was established in the third era.",
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk


@pytest.fixture
def out_of_scope_doc(db_session) -> Document:
    """Document with scope outside the allowed set."""
    doc = Document(
        title="Other Region", source_path="/fake/other.pdf", scope="gondor", content_hash="b" * 64
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture
def out_of_scope_chunk(db_session, out_of_scope_doc) -> Chunk:
    """Chunk linked to the out-of-scope document."""
    chunk = Chunk(document_id=out_of_scope_doc.id, sequence=0, text="Some other region text.")
    db_session.add(chunk)
    db_session.commit()
    return chunk


# ---------------------------------------------------------------------------
# TC-R3-01  extract_chunk: well-formed response produces staging file
# ---------------------------------------------------------------------------


def test_extract_chunk_success(monkeypatch, varkaar_chunk, varkaar_doc, reviewed_dir):
    """Well-formed model response produces a staging file with correct fields."""
    monkeypatch.setenv("REVIEWED_DIR", str(reviewed_dir))
    with patch("saskan_lore.analyzer.extractor.complete", return_value=_GOOD_RESPONSE):
        out = extract_chunk(varkaar_chunk, varkaar_doc)

    assert out is not None
    assert out.exists()
    assert "_error" not in out.name
    data = json.loads(out.read_text())
    assert data["chunk_id"] == f"chunk_{varkaar_chunk.id:04d}"
    assert "claims" in data
    assert len(data["claims"]) == 1


# ---------------------------------------------------------------------------
# TC-R3-02  extract_chunk: reviewed=False enforced at write time
# ---------------------------------------------------------------------------


def test_extract_chunk_reviewed_always_false(monkeypatch, varkaar_chunk, varkaar_doc, reviewed_dir):
    """reviewed=False is injected even when the model response includes reviewed=True."""
    monkeypatch.setenv("REVIEWED_DIR", str(reviewed_dir))
    with patch("saskan_lore.analyzer.extractor.complete", return_value=_REVIEWED_TRUE_RESPONSE):
        out = extract_chunk(varkaar_chunk, varkaar_doc)

    assert out is not None
    data = json.loads(out.read_text())
    for claim in data["claims"]:
        assert claim["reviewed"] is False


# ---------------------------------------------------------------------------
# TC-R3-03  extract_chunk: invalid JSON → error file, no exception
# ---------------------------------------------------------------------------


def test_extract_chunk_invalid_json(monkeypatch, varkaar_chunk, varkaar_doc, reviewed_dir):
    """Non-JSON model response produces an error file; no exception is raised."""
    monkeypatch.setenv("REVIEWED_DIR", str(reviewed_dir))
    with patch("saskan_lore.analyzer.extractor.complete", return_value=_BAD_JSON):
        out = extract_chunk(varkaar_chunk, varkaar_doc)

    assert out is not None
    assert "_error" in out.name
    error_data = json.loads(out.read_text())
    assert error_data["error"] is True
    assert error_data["chunk_id"] == f"chunk_{varkaar_chunk.id:04d}"


# ---------------------------------------------------------------------------
# TC-R3-04  extract_chunk: missing required fields → error file, no exception
# ---------------------------------------------------------------------------


def test_extract_chunk_missing_fields(monkeypatch, varkaar_chunk, varkaar_doc, reviewed_dir):
    """Valid JSON missing required fields produces an error file; no exception raised."""
    monkeypatch.setenv("REVIEWED_DIR", str(reviewed_dir))
    with patch(
        "saskan_lore.analyzer.extractor.complete",
        return_value=_MISSING_FIELDS_RESPONSE,
    ):
        out = extract_chunk(varkaar_chunk, varkaar_doc)

    assert out is not None
    assert "_error" in out.name
    error_data = json.loads(out.read_text())
    assert error_data["error"] is True


# ---------------------------------------------------------------------------
# TC-R3-05  extract_chunk: out-of-scope document → None, no file written
# ---------------------------------------------------------------------------


def test_extract_chunk_out_of_scope(
    monkeypatch, out_of_scope_chunk, out_of_scope_doc, reviewed_dir
):
    """Chunk from a non-varkaar document returns None and writes no file."""
    monkeypatch.setenv("REVIEWED_DIR", str(reviewed_dir))
    with patch("saskan_lore.analyzer.extractor.complete", return_value=_GOOD_RESPONSE):
        out = extract_chunk(out_of_scope_chunk, out_of_scope_doc)

    assert out is None
    assert list(reviewed_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# TC-R3-06  list_staging: returns success files only
# ---------------------------------------------------------------------------


def test_list_staging_excludes_errors(reviewed_dir):
    """list_staging() returns only *_extraction.json files, not error files."""
    (reviewed_dir / "chunk_0001_extraction.json").write_text("{}")
    (reviewed_dir / "chunk_0002_extraction.json").write_text("{}")
    (reviewed_dir / "chunk_0003_extraction_error.json").write_text("{}")

    results = list_staging(reviewed_dir)
    names = [p.name for p in results]

    assert len(results) == 2
    assert "chunk_0001_extraction.json" in names
    assert "chunk_0002_extraction.json" in names
    assert "chunk_0003_extraction_error.json" not in names


# ---------------------------------------------------------------------------
# TC-R3-07  list_errors: returns error files only
# ---------------------------------------------------------------------------


def test_list_errors_only(reviewed_dir):
    """list_errors() returns only *_extraction_error.json files."""
    (reviewed_dir / "chunk_0001_extraction.json").write_text("{}")
    (reviewed_dir / "chunk_0002_extraction_error.json").write_text("{}")

    results = list_errors(reviewed_dir)
    names = [p.name for p in results]

    assert len(results) == 1
    assert "chunk_0002_extraction_error.json" in names
    assert "chunk_0001_extraction.json" not in names


# ---------------------------------------------------------------------------
# TC-R3-08  validate_staging: valid record returns no errors
# ---------------------------------------------------------------------------


def test_validate_staging_valid():
    """validate_staging() returns an empty list for a well-formed staging record."""
    record = json.loads(_GOOD_RESPONSE)
    record["claims"][0]["reviewed"] = False

    errors = validate_staging(record)
    assert errors == []


# ---------------------------------------------------------------------------
# TC-R3-09  validate_staging: invalid record returns error strings
# ---------------------------------------------------------------------------


def test_validate_staging_invalid():
    """validate_staging() returns errors for a record missing required claim fields."""
    record = {
        "chunk_id": "chunk_0001",
        "document_id": "doc_001",
        "title": "Test",
        "summary": "Test.",
        "era": "",
        "canon_level": "canonical",
        "truth_status": "fact",
        "region": [],
        "places": [],
        "characters": [],
        "factions": [],
        "key_events": [],
        "claims": [
            {
                "claim_text": "A claim.",
                # source_span missing — violates NFR-003 and schema minLength:1
                "truth_status": "fact",
                "reviewed": False,
            }
        ],
    }
    errors = validate_staging(record)
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# TC-R3-10  load_for_document: returns valid records for matching document_id
# ---------------------------------------------------------------------------


def test_load_for_document(reviewed_dir):
    """load_for_document() returns only valid records matching the document_id."""
    good_record = json.loads(_GOOD_RESPONSE)
    good_record["claims"][0]["reviewed"] = False

    # Matching valid record
    (reviewed_dir / "chunk_0001_extraction.json").write_text(json.dumps(good_record))
    # Different document — should be excluded
    other = dict(good_record)
    other["document_id"] = "doc_002"
    (reviewed_dir / "chunk_0002_extraction.json").write_text(json.dumps(other))
    # Invalid JSON — should be skipped without error
    (reviewed_dir / "chunk_0003_extraction.json").write_text("not json")

    results = load_for_document(reviewed_dir, "doc_001")

    assert len(results) == 1
    assert results[0]["document_id"] == "doc_001"
