# tests/unit/r5_retrieval/test_r5_retrieval.py
"""
R5 retrieval and answering unit tests.

Covers: retrieval.py — tokenize(), retrieve(), format_context().
        answering.py  — answer().
See docs/design/r5_retrieval/test_cases.md for the full test-case
register (TC-R5-01 through TC-R5-11).

All tests use the db_session fixture from tests/conftest.py (in-memory
SQLite, StaticPool, FK pragma ON, fresh per test).

The claims_fts FTS5 virtual table is created by the shared db_session fixture
in tests/conftest.py (mirrors alembic/versions/c2d4a8f3e610_add_claims_fts.py).
llama_cpp is mocked at collection time via tests/unit/r5_retrieval/conftest.py
so that answering.py can be imported without a real GGUF model on disk.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from unittest.mock import patch

from saskan_lore.analyzer.answering import answer
from saskan_lore.analyzer.retrieval import format_context, retrieve, tokenize
from saskan_lore.data.models import Chunk, Claim, Document
from saskan_lore.data.schema.data_schema import AnswerResult, RetrievalHit

# ---------------------------------------------------------------------------
# Fixture: session with FTS5 virtual table and seeded data
# ---------------------------------------------------------------------------


@pytest.fixture
def fts_session(db_session):
    """Extend db_session with the claims_fts virtual table and seed data.

    Creates the FTS5 content virtual table via raw SQL (mirrors the Alembic
    migration), inserts a Document, Chunk, and two Claims — one approved,
    one rejected — then rebuilds the FTS5 index.
    """
    # Seed: document → chunk → two claims
    doc = Document(
        title="Varkaar Canon",
        source_path="/fake/varkaar.pdf",
        scope="varkaar",
        content_hash="a" * 64,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = Chunk(document_id=doc.id, sequence=3, text="Oath law passage.")
    db_session.add(chunk)
    db_session.flush()

    approved = Claim(
        chunk_id=chunk.id,
        document_id=doc.id,
        claim_text="The Covenant of Varkaar prescribed death for oath-breaking.",
        source_span="oath-breakers were put to death under Covenant law",
        truth_status="fact",
        status="approved",
    )
    rejected = Claim(
        chunk_id=chunk.id,
        document_id=doc.id,
        claim_text="Varkaar oath ceremonies involved elaborate feasts.",
        source_span="feasts were held to celebrate the oath",
        truth_status="rumor",
        status="rejected",
    )
    db_session.add_all([approved, rejected])
    db_session.flush()

    # Populate the FTS5 index from the claims table
    db_session.execute(text("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')"))
    db_session.commit()

    yield db_session


# ---------------------------------------------------------------------------
# TC-R5-01  tokenize: splits on whitespace and punctuation
# ---------------------------------------------------------------------------


def test_tokenize_splits_query():
    """tokenize() returns lowercase alphanumeric tokens, ignoring punctuation."""
    result = tokenize("Oath-breaking, Covenant?")
    assert result == ["oath", "breaking", "covenant"]


# ---------------------------------------------------------------------------
# TC-R5-02  tokenize: empty and punctuation-only queries yield no tokens
# ---------------------------------------------------------------------------


def test_tokenize_empty_and_punctuation():
    """tokenize() returns an empty list for blank or punctuation-only input."""
    assert tokenize("") == []
    assert tokenize("???  ---") == []


# ---------------------------------------------------------------------------
# TC-R5-03  retrieve: matching query returns approved claim
# ---------------------------------------------------------------------------


def test_retrieve_returns_approved_claim(fts_session):
    """retrieve() returns a RetrievalHit for a query matching an approved claim."""
    hits = retrieve("oath covenant", fts_session)

    assert len(hits) == 1
    hit = hits[0]
    assert isinstance(hit, RetrievalHit)
    assert "Covenant" in hit.claim_text
    assert hit.truth_status == "fact"
    assert hit.document_title == "Varkaar Canon"
    assert hit.chunk_sequence == 3


# ---------------------------------------------------------------------------
# TC-R5-04  retrieve: rejected claims are excluded
# ---------------------------------------------------------------------------


def test_retrieve_excludes_rejected_claims(fts_session):
    """retrieve() does not return claims with status='rejected'."""
    # "feasts" is only in the rejected claim
    hits = retrieve("feasts ceremonies", fts_session)
    assert hits == []


# ---------------------------------------------------------------------------
# TC-R5-05  retrieve: query with no matching tokens returns empty list
# ---------------------------------------------------------------------------


def test_retrieve_no_tokens_returns_empty(fts_session):
    """retrieve() returns an empty list when the query tokenizes to nothing."""
    hits = retrieve("???", fts_session)
    assert hits == []


# ---------------------------------------------------------------------------
# TC-R5-06  retrieve: query with tokens that match nothing returns empty list
# ---------------------------------------------------------------------------


def test_retrieve_no_match_returns_empty(fts_session):
    """retrieve() returns an empty list when no approved claims match."""
    hits = retrieve("dragons magic enchantment", fts_session)
    assert hits == []


# ---------------------------------------------------------------------------
# TC-R5-07  retrieve: top_n limits the number of results
# ---------------------------------------------------------------------------


def test_retrieve_top_n_respected(fts_session):
    """retrieve() returns at most top_n results."""
    # Add a second approved claim that also matches "covenant"
    doc_id = fts_session.query(Document).first().id
    chunk_id = fts_session.query(Chunk).first().id
    extra = Claim(
        chunk_id=chunk_id,
        document_id=doc_id,
        claim_text="The Covenant governed all oath disputes in the northern provinces.",
        source_span="Covenant governed oath disputes",
        truth_status="fact",
        status="approved",
    )
    fts_session.add(extra)
    fts_session.flush()
    fts_session.execute(text("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')"))
    fts_session.commit()

    hits = retrieve("covenant", fts_session, top_n=1)
    assert len(hits) == 1


# ---------------------------------------------------------------------------
# TC-R5-08  format_context: produces numbered entries with expected fields
# ---------------------------------------------------------------------------


def test_format_context_structure(fts_session):
    """format_context() returns a numbered string with claim, source, and ref."""
    hits = retrieve("oath covenant", fts_session)
    assert hits  # guard: need at least one hit

    context = format_context(hits)

    assert "[1]" in context
    assert "fact" in context
    assert "Varkaar Canon" in context
    assert "chunk 3" in context
    assert hits[0].source_span in context
    assert hits[0].claim_text in context


# ---------------------------------------------------------------------------
# TC-R5-09  answer: no retrieval hits → answerable=False, model not called
# ---------------------------------------------------------------------------


def test_answer_no_hits_returns_not_answerable(fts_session):
    """answer() returns answerable=False and does not call the model when no claims match."""
    with patch("saskan_lore.analyzer.answering.complete") as mock_complete:
        result = answer("dragons magic enchantment", fts_session)

    assert isinstance(result, AnswerResult)
    assert result.answerable is False
    assert result.answer is None
    assert result.evidence == []
    mock_complete.assert_not_called()


# ---------------------------------------------------------------------------
# TC-R5-10  answer: hits present → model called, evidence list matches hits
# ---------------------------------------------------------------------------


def test_answer_with_hits_calls_model_and_returns_evidence(fts_session):
    """answer() calls the model when claims match and returns the correct evidence list."""
    model_response = "The Covenant of Varkaar prescribed death for oath-breaking."

    with patch("saskan_lore.analyzer.answering.complete", return_value=model_response):
        result = answer("oath covenant", fts_session)

    assert isinstance(result, AnswerResult)
    assert result.answerable is True
    assert result.answer == model_response
    assert len(result.evidence) == 1
    hits = retrieve("oath covenant", fts_session)
    assert result.evidence == [h.claim_id for h in hits]


# ---------------------------------------------------------------------------
# TC-R5-11  answer: cannot-answer model response is preserved as-is
# ---------------------------------------------------------------------------


def test_answer_cannot_answer_signal_preserved(fts_session):
    """A 'cannot answer' model response is returned as the answer, not treated as an error."""
    cannot_answer = "I cannot answer from the available evidence."

    with patch("saskan_lore.analyzer.answering.complete", return_value=cannot_answer):
        result = answer("oath covenant", fts_session)

    assert result.answerable is True
    assert result.answer == cannot_answer
    assert result.evidence  # evidence was still supplied to the model


# ---------------------------------------------------------------------------
# TC-R5-12  format_context: empty hits list returns empty string
# ---------------------------------------------------------------------------


def test_format_context_empty_hits():
    """format_context() returns an empty string when given no hits."""
    assert format_context([]) == ""


# ---------------------------------------------------------------------------
# TC-R5-13  format_context: multiple hits are numbered and separated
# ---------------------------------------------------------------------------


def test_format_context_multiple_hits(fts_session):
    """format_context() numbers each hit and separates entries with a blank line."""
    # Add a second approved claim so we can retrieve two hits
    doc_id = fts_session.query(Document).first().id
    chunk_id = fts_session.query(Chunk).first().id
    extra = Claim(
        chunk_id=chunk_id,
        document_id=doc_id,
        claim_text="Covenant arbiters enforced the oath before witnesses.",
        source_span="arbiters enforced the oath",
        truth_status="fact",
        status="approved",
    )
    fts_session.add(extra)
    fts_session.flush()
    fts_session.execute(text("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')"))
    fts_session.commit()

    hits = retrieve("covenant oath", fts_session, top_n=2)
    assert len(hits) == 2

    context = format_context(hits)
    assert "[1]" in context
    assert "[2]" in context
    # Entries are separated by a blank line (double newline)
    assert "\n\n" in context


# ---------------------------------------------------------------------------
# TC-R5-14  retrieve: inactive approved claims are excluded
# ---------------------------------------------------------------------------


def test_retrieve_excludes_inactive_claims(fts_session):
    """retrieve() does not return claims where is_active=False."""
    # Mark the approved claim as inactive
    claim = fts_session.query(Claim).filter_by(status="approved").first()
    claim.is_active = False
    fts_session.flush()
    fts_session.execute(text("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')"))
    fts_session.commit()

    hits = retrieve("oath covenant", fts_session)
    assert hits == []
