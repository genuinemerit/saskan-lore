# tests/integration/test_r6_integration.py
"""
R6 integration test — full pipeline, mocked inference only.

Exercises the complete data-layer pipeline from document registration to
evaluation grading using real file I/O, real DB operations, and real ORM
queries. Only inference.complete() and answer() are mocked — the model is
never called and no GGUF file is required.

Part A: ingest → extract → approve → load
    - Register a synthetic document and load chunks.
    - Call extract_chunk() with mocked inference; verify staging files written.
    - Programmatically approve all claims in staging files.
    - Load each staging file via load_file(); verify DB state and FTS5 index.

Part B: load questions → evaluate → grade → summary → export
    - Load synthetic eval questions into DB.
    - Run run_evaluation() with mocked answer(); verify EvalResult records.
    - Grade results; verify eval_summary() counts.
    - Export results; verify JSON output.

Uses the shared db_session fixture (in-memory SQLite, FTS5 virtual table).
Uses tmp_path for staging files and export output.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from saskan_lore.analyzer.evaluate import (
    eval_summary,
    export_results,
    grade_result,
    run_evaluation,
)
from saskan_lore.analyzer.extractor import extract_chunk
from saskan_lore.data.models import Chunk, Claim, Document, EvalResult
from saskan_lore.data.schema.data_schema import AnswerResult
from saskan_lore.loader.load_chunks import load_chunks
from saskan_lore.loader.load_eval_questions import load_eval_questions
from saskan_lore.loader.load_reviewed import load_file
from saskan_lore.loader.register_lore_text import register_document

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_FIXTURE_TEXT = Path(__file__).parent.parent / "fixtures" / "synthetic_lore.txt"

# ---------------------------------------------------------------------------
# Synthetic eval questions (2 questions, valid against testing_schema.json)
# ---------------------------------------------------------------------------

_EVAL_QUESTIONS = [
    {
        "question_id": "q_001",
        "question_text": "What was the Synthetic Covenant?",
        "expected_answer": "A governing body.",
        "scope": "varkaar",
    },
    {
        "question_id": "q_002",
        "question_text": "Who was Elder Marn?",
        "expected_answer": "The first presiding officer.",
        "scope": "varkaar",
    },
]

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_inference_complete(prompt: str, **kwargs) -> str:
    """Return a valid extraction JSON string with IDs parsed from the prompt.

    The extractor embeds chunk_id and document_id in the prompt user section
    (format: 'chunk_id: chunk_NNNN' / 'document_id: doc_NNN'). This mock
    reads them back so the staging file contains the correct references for
    load_file() to resolve against the DB.
    """
    chunk_id = re.search(r"chunk_id:\s*(chunk_\d+)", prompt)
    doc_id = re.search(r"document_id:\s*(doc_\d+)", prompt)
    chunk_id_str = chunk_id.group(1) if chunk_id else "chunk_0001"
    doc_id_str = doc_id.group(1) if doc_id else "doc_001"

    return json.dumps(
        {
            "chunk_id": chunk_id_str,
            "document_id": doc_id_str,
            "title": "Synthetic Lore Test",
            "summary": "A test passage about the Synthetic Covenant.",
            "era": "",
            "canon_level": "canonical",
            "truth_status": "fact",
            "region": ["Synthetic Region"],
            "places": ["Synthetic Keep"],
            "characters": ["Elder Marn"],
            "factions": ["Synthetic Covenant"],
            "key_events": [],
            "claims": [
                {
                    "claim_text": "The Synthetic Covenant governed the test region.",
                    "source_span": "The Synthetic Covenant was a governing body",
                    "truth_status": "fact",
                    "confidence": "high",
                    "review_status": "pending",
                }
            ],
        }
    )


def _approve_all_claims(staging_path: Path) -> None:
    """Set review_status='approved' on every claim in a staging file."""
    data = json.loads(staging_path.read_text(encoding="utf-8"))
    for claim in data.get("claims", []):
        claim["review_status"] = "approved"
    staging_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Part A — Ingest, extract, approve, load
# ---------------------------------------------------------------------------


class TestPartA:
    """Pipeline from document registration through DB load."""

    def test_a1_register_and_chunk(self, db_session, tmp_path):
        """Registering a document and loading chunks populates the DB."""
        text = _FIXTURE_TEXT.read_text(encoding="utf-8")
        src = tmp_path / "synthetic_lore.txt"
        src.write_text(text, encoding="utf-8")

        doc = register_document(db_session, "Synthetic Lore", str(src))
        n = load_chunks(db_session, doc, text)

        assert db_session.query(Document).count() == 1
        assert n > 0
        assert db_session.query(Chunk).count() == n

    def test_a2_extract_writes_staging_files(self, db_session, tmp_path):
        """extract_chunk() with mocked inference writes one staging file per chunk."""
        text = _FIXTURE_TEXT.read_text(encoding="utf-8")
        src = tmp_path / "synthetic_lore.txt"
        src.write_text(text, encoding="utf-8")
        staging_dir = tmp_path / "reviewed"

        doc = register_document(db_session, "Synthetic Lore", str(src))
        load_chunks(db_session, doc, text)
        chunks = db_session.query(Chunk).filter_by(document_id=doc.id).all()

        with (
            patch(
                "saskan_lore.analyzer.extractor.complete",
                side_effect=_mock_inference_complete,
            ),
            patch.dict(os.environ, {"REVIEWED_DIR": str(staging_dir)}),
        ):
            paths = [extract_chunk(c, doc) for c in chunks]

        written = [p for p in paths if p is not None and "_error" not in p.name]
        assert len(written) == len(chunks)
        assert all(p.exists() for p in written)

    def test_a3_load_approved_claims_into_db(self, db_session, tmp_path):
        """After approving staging files, load_file() inserts claims into the DB."""
        text = _FIXTURE_TEXT.read_text(encoding="utf-8")
        src = tmp_path / "synthetic_lore.txt"
        src.write_text(text, encoding="utf-8")
        staging_dir = tmp_path / "reviewed"

        doc = register_document(db_session, "Synthetic Lore", str(src))
        load_chunks(db_session, doc, text)
        chunks = db_session.query(Chunk).filter_by(document_id=doc.id).all()

        with (
            patch(
                "saskan_lore.analyzer.extractor.complete",
                side_effect=_mock_inference_complete,
            ),
            patch.dict(os.environ, {"REVIEWED_DIR": str(staging_dir)}),
        ):
            paths = [extract_chunk(c, doc) for c in chunks]

        staging_files = [p for p in paths if p is not None and "_error" not in p.name]
        for p in staging_files:
            _approve_all_claims(p)
            load_file(db_session, p)

        approved = db_session.query(Claim).filter_by(status="approved").count()
        assert approved > 0

    def test_a4_fts5_index_populated_after_load(self, db_session, tmp_path):
        """After loading, FTS5 index contains the approved claims."""
        from sqlalchemy import text as sql_text

        fixture_text = _FIXTURE_TEXT.read_text(encoding="utf-8")
        src = tmp_path / "synthetic_lore.txt"
        src.write_text(fixture_text, encoding="utf-8")
        staging_dir = tmp_path / "reviewed"

        doc = register_document(db_session, "Synthetic Lore", str(src))
        load_chunks(db_session, doc, fixture_text)
        chunks = db_session.query(Chunk).filter_by(document_id=doc.id).all()

        with (
            patch(
                "saskan_lore.analyzer.extractor.complete",
                side_effect=_mock_inference_complete,
            ),
            patch.dict(os.environ, {"REVIEWED_DIR": str(staging_dir)}),
        ):
            paths = [extract_chunk(c, doc) for c in chunks]

        for p in (p for p in paths if p and "_error" not in p.name):
            _approve_all_claims(p)
            load_file(db_session, p)

        rows = db_session.execute(
            sql_text("SELECT claim_text FROM claims_fts WHERE claims_fts MATCH 'Covenant'")
        ).fetchall()
        assert len(rows) > 0


# ---------------------------------------------------------------------------
# Part B — Questions, evaluate, grade, summary, export
# ---------------------------------------------------------------------------


class TestPartB:
    """Pipeline from eval question load through export."""

    @pytest.fixture
    def loaded_pipeline(self, db_session, tmp_path):
        """Run Part A setup and return (session, eval_questions_file)."""
        text = _FIXTURE_TEXT.read_text(encoding="utf-8")
        src = tmp_path / "synthetic_lore.txt"
        src.write_text(text, encoding="utf-8")
        staging_dir = tmp_path / "reviewed"

        doc = register_document(db_session, "Synthetic Lore", str(src))
        load_chunks(db_session, doc, text)
        chunks = db_session.query(Chunk).filter_by(document_id=doc.id).all()

        with (
            patch(
                "saskan_lore.analyzer.extractor.complete",
                side_effect=_mock_inference_complete,
            ),
            patch.dict(os.environ, {"REVIEWED_DIR": str(staging_dir)}),
        ):
            paths = [extract_chunk(c, doc) for c in chunks]

        for p in (p for p in paths if p and "_error" not in p.name):
            _approve_all_claims(p)
            load_file(db_session, p)

        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps(_EVAL_QUESTIONS), encoding="utf-8")

        return db_session, q_file

    def test_b1_load_eval_questions(self, loaded_pipeline):
        """load_eval_questions() inserts all questions and is idempotent."""
        session, q_file = loaded_pipeline

        summary = load_eval_questions(session, q_file)
        assert summary["loaded"] == 2
        assert summary["skipped"] == 0

        # Idempotent
        summary2 = load_eval_questions(session, q_file)
        assert summary2["loaded"] == 0
        assert summary2["skipped"] == 2

    def test_b2_run_evaluation_creates_results(self, loaded_pipeline):
        """run_evaluation() creates one EvalResult per question with pass_fail=None."""
        session, q_file = loaded_pipeline
        load_eval_questions(session, q_file)

        mock_result = AnswerResult(
            answerable=True,
            answer="A governing body of the test region.",
            evidence=[1],
        )
        with patch("saskan_lore.analyzer.evaluate.answer", return_value=mock_result):
            records = run_evaluation(session)

        assert len(records) == 2
        assert session.query(EvalResult).count() == 2
        assert all(r.pass_fail is None for r in records)
        assert all(json.loads(r.retrieved_evidence) == [1] for r in records)

    def test_b3_grade_and_summary(self, loaded_pipeline):
        """grade_result() and eval_summary() reflect correct counts."""
        session, q_file = loaded_pipeline
        load_eval_questions(session, q_file)

        mock_result = AnswerResult(answerable=True, answer="A body.", evidence=[])
        with patch("saskan_lore.analyzer.evaluate.answer", return_value=mock_result):
            records = run_evaluation(session)

        grade_result(session, records[0].id, "pass")
        grade_result(session, records[1].id, "fail", failure_type="incomplete", notes="Too brief.")

        summary = eval_summary(session)
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["ungraded"] == 0
        assert summary["failures"] == {"incomplete": 1}

    def test_b4_export_produces_valid_json(self, loaded_pipeline, tmp_path):
        """export_results() writes a JSON file with all results joined to questions."""
        session, q_file = loaded_pipeline
        load_eval_questions(session, q_file)

        mock_result = AnswerResult(answerable=True, answer="A body.", evidence=[])
        with patch("saskan_lore.analyzer.evaluate.answer", return_value=mock_result):
            records = run_evaluation(session)

        grade_result(session, records[0].id, "pass")
        grade_result(session, records[1].id, "fail", failure_type="wrong_fact")

        dest = tmp_path / "export.json"
        export_results(session, dest)

        data = json.loads(dest.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert {r["question_id"] for r in data} == {"q_001", "q_002"}
        assert any(r["pass_fail"] == "pass" for r in data)
        assert any(r["failure_type"] == "wrong_fact" for r in data)
