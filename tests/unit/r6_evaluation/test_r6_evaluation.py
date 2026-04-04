# tests/unit/r6_evaluation/test_r6_evaluation.py
"""
R6 evaluation unit tests.

Covers: load_eval_questions.py — load_eval_questions(), schema validation.
        evaluate.py            — run_evaluation(), grade_result(),
                                 eval_summary(), export_results().
See docs/design/r6_evaluation/test_cases.md for the full test-case
register (TC-R6-01 through TC-R6-14).

All tests use the db_session fixture from tests/conftest.py (in-memory
SQLite, StaticPool, FK pragma ON, fresh per test).

llama_cpp is mocked at collection time via conftest.py. answer() is patched
directly in tests that call run_evaluation() so model calls never occur.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from saskan_lore.analyzer.evaluate import (
    eval_summary,
    export_results,
    grade_result,
    run_evaluation,
)
from saskan_lore.data.models import Chunk, Claim, Document, EvalQuestion, EvalResult
from saskan_lore.data.schema.data_schema import AnswerResult
from saskan_lore.loader.load_eval_questions import load_eval_questions

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_VALID_QUESTIONS = [
    {
        "question_id": "q_001",
        "question_text": "What is the Covenant of Varkaar?",
        "expected_answer": "A governing body.",
        "scope": "varkaar",
    },
    {
        "question_id": "q_002",
        "question_text": "How does the Covenant function?",
        "expected_answer": "Through negotiated agreements.",
        "scope": "varkaar",
    },
]

_MOCK_ANSWERABLE = AnswerResult(answerable=True, answer="A governing body.", evidence=[1])
_MOCK_UNANSWERABLE = AnswerResult(answerable=False, answer=None, evidence=[])


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def questions_file(tmp_path: Path) -> Path:
    """Write _VALID_QUESTIONS to a temporary JSON file."""
    p = tmp_path / "test_questions.json"
    p.write_text(json.dumps(_VALID_QUESTIONS), encoding="utf-8")
    return p


@pytest.fixture
def seeded_questions(db_session):
    """Insert two EvalQuestion rows directly and return them."""
    q1 = EvalQuestion(
        question_id="q_001",
        question_text="What is the Covenant of Varkaar?",
        expected_answer="A governing body.",
        scope="varkaar",
    )
    q2 = EvalQuestion(
        question_id="q_002",
        question_text="How does the Covenant function?",
        expected_answer="Through negotiated agreements.",
        scope="varkaar",
    )
    db_session.add_all([q1, q2])
    db_session.commit()
    return db_session


@pytest.fixture
def seeded_with_claims(seeded_questions):
    """Extend seeded_questions with a Document, Chunk, and approved Claim."""
    session = seeded_questions
    doc = Document(
        title="Varkaar Canon",
        source_path="/fake/varkaar.pdf",
        scope="varkaar",
        content_hash="a" * 64,
    )
    session.add(doc)
    session.flush()
    chunk = Chunk(document_id=doc.id, sequence=0, text="Covenant passage.")
    session.add(chunk)
    session.flush()
    claim = Claim(
        chunk_id=chunk.id,
        document_id=doc.id,
        claim_text="The Covenant governs the Varkaar region.",
        source_span="The Covenant governs",
        truth_status="fact",
        status="approved",
    )
    session.add(claim)
    session.commit()
    return session


# ---------------------------------------------------------------------------
# TC-R6-01  load_eval_questions: loads questions from valid JSON file
# ---------------------------------------------------------------------------


def test_load_eval_questions_loads_from_file(db_session, questions_file):
    """load_eval_questions() inserts one EvalQuestion per entry in the file."""
    summary = load_eval_questions(db_session, questions_file)

    assert summary["loaded"] == 2
    assert summary["skipped"] == 0
    assert db_session.query(EvalQuestion).count() == 2


# ---------------------------------------------------------------------------
# TC-R6-02  load_eval_questions: idempotent — duplicate load skips existing
# ---------------------------------------------------------------------------


def test_load_eval_questions_idempotent(db_session, questions_file):
    """Loading the same file twice inserts each question only once."""
    load_eval_questions(db_session, questions_file)
    summary = load_eval_questions(db_session, questions_file)

    assert summary["loaded"] == 0
    assert summary["skipped"] == 2
    assert db_session.query(EvalQuestion).count() == 2


# ---------------------------------------------------------------------------
# TC-R6-03  load_eval_questions: question_id used as idempotence key
# ---------------------------------------------------------------------------


def test_load_eval_questions_keyed_on_question_id(db_session, questions_file):
    """question_id is the idempotence key; same ID from two files is skipped."""
    load_eval_questions(db_session, questions_file)
    count_before = db_session.query(EvalQuestion).count()

    # Second load with same content — nothing new
    load_eval_questions(db_session, questions_file)
    assert db_session.query(EvalQuestion).count() == count_before


# ---------------------------------------------------------------------------
# TC-R6-04  load_eval_questions: rejects malformed JSON (schema validation)
# ---------------------------------------------------------------------------


def test_load_eval_questions_rejects_invalid_schema(db_session, tmp_path):
    """load_eval_questions() raises ValueError when the file fails validation."""
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps([{"question_id": "q_001", "question_text": "Missing fields."}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema validation"):
        load_eval_questions(db_session, bad)


# ---------------------------------------------------------------------------
# TC-R6-05  run_evaluation: creates one EvalResult per question
# ---------------------------------------------------------------------------


def test_run_evaluation_creates_one_result_per_question(seeded_with_claims):
    """run_evaluation() inserts exactly one EvalResult per active question."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    assert len(records) == 2
    assert session.query(EvalResult).count() == 2


# ---------------------------------------------------------------------------
# TC-R6-06  run_evaluation: pass_fail is None after automated run
# ---------------------------------------------------------------------------


def test_run_evaluation_pass_fail_is_none(seeded_with_claims):
    """EvalResult.pass_fail is None immediately after run_evaluation()."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    for r in records:
        assert r.pass_fail is None
        assert r.failure_type is None


# ---------------------------------------------------------------------------
# TC-R6-07  run_evaluation: retrieved_evidence is a valid JSON string
# ---------------------------------------------------------------------------


def test_run_evaluation_evidence_is_json(seeded_with_claims):
    """retrieved_evidence is a JSON-encoded list, even when empty."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    for r in records:
        parsed = json.loads(r.retrieved_evidence)
        assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# TC-R6-08  run_evaluation: returns empty list when no questions present
# ---------------------------------------------------------------------------


def test_run_evaluation_no_questions_returns_empty(db_session):
    """run_evaluation() returns [] when no active varkaar questions exist."""
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(db_session)

    assert records == []
    assert db_session.query(EvalResult).count() == 0


# ---------------------------------------------------------------------------
# TC-R6-09  grade_result: sets pass, failure_type, and notes correctly
# ---------------------------------------------------------------------------


def test_grade_result_sets_fields(seeded_with_claims):
    """grade_result() writes pass_fail, failure_type, and notes to the record."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    result = grade_result(
        session,
        result_id=records[0].id,
        pass_fail="fail",
        failure_type="hallucination",
        notes="Invented a council name.",
    )

    assert result.pass_fail == "fail"
    assert result.failure_type == "hallucination"
    assert result.notes == "Invented a council name."


# ---------------------------------------------------------------------------
# TC-R6-10  grade_result: raises ValueError for invalid pass_fail value
# ---------------------------------------------------------------------------


def test_grade_result_rejects_invalid_verdict(seeded_with_claims):
    """grade_result() raises ValueError when pass_fail is not 'pass' or 'fail'."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    with pytest.raises(ValueError, match="pass_fail"):
        grade_result(session, result_id=records[0].id, pass_fail="maybe")


# ---------------------------------------------------------------------------
# TC-R6-11  grade_result: raises ValueError for unrecognised failure_type
# ---------------------------------------------------------------------------


def test_grade_result_rejects_invalid_failure_type(seeded_with_claims):
    """grade_result() raises ValueError for an unrecognised failure_type."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    with pytest.raises(ValueError, match="failure_type"):
        grade_result(
            session,
            result_id=records[0].id,
            pass_fail="fail",
            failure_type="wrong_vibes",
        )


# ---------------------------------------------------------------------------
# TC-R6-12  grade_result: raises ValueError for unknown result_id
# ---------------------------------------------------------------------------


def test_grade_result_unknown_id_raises(db_session):
    """grade_result() raises ValueError when result_id does not exist."""
    with pytest.raises(ValueError, match="not found"):
        grade_result(db_session, result_id=9999, pass_fail="pass")


# ---------------------------------------------------------------------------
# TC-R6-13  eval_summary: correct counts after grading
# ---------------------------------------------------------------------------


def test_eval_summary_correct_counts(seeded_with_claims):
    """eval_summary() returns accurate pass/fail/ungraded counts."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    grade_result(session, result_id=records[0].id, pass_fail="pass")
    grade_result(
        session,
        result_id=records[1].id,
        pass_fail="fail",
        failure_type="incomplete",
    )

    summary = eval_summary(session)

    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["ungraded"] == 0
    assert summary["failures"] == {"incomplete": 1}


# ---------------------------------------------------------------------------
# TC-R6-14  eval_summary: ungraded results excluded from pass/fail counts
# ---------------------------------------------------------------------------


def test_eval_summary_ungraded_excluded(seeded_with_claims):
    """Ungraded results (pass_fail=None) count toward ungraded, not pass/fail."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    # Grade only the first result
    grade_result(session, result_id=records[0].id, pass_fail="pass")

    summary = eval_summary(session)

    assert summary["passed"] == 1
    assert summary["failed"] == 0
    assert summary["ungraded"] == 1


# ---------------------------------------------------------------------------
# TC-R6-15  export_results: writes valid JSON file with expected structure
# ---------------------------------------------------------------------------


def test_export_results_writes_json(seeded_with_claims, tmp_path):
    """export_results() writes a JSON file with one entry per EvalResult."""
    session = seeded_with_claims
    with patch("saskan_lore.analyzer.answering.answer", return_value=_MOCK_ANSWERABLE):
        records = run_evaluation(session)

    grade_result(session, result_id=records[0].id, pass_fail="pass")

    dest = tmp_path / "export.json"
    written = export_results(session, dest)

    assert written == dest
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["question_id"] == "q_001"
    assert data[0]["pass_fail"] == "pass"
    assert isinstance(data[0]["retrieved_evidence"], list)
