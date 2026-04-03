# -*- coding: utf-8 -*-
"""
evaluate.py

Run evaluation questions through the retrieval and answering pipeline,
record results, and produce summary reports.

Public functions:

    run_evaluation(session) -> list[EvalResult]
        Run all active Varkaar EvalQuestions through answer(). Write one
        EvalResult record per question with pass_fail=None (requires human
        grading via `saskan-lore grade`). Returns the inserted records.

    grade_result(session, result_id, pass_fail, failure_type=None, notes=None)
        Set pass_fail and optional failure_type/notes on one EvalResult.

    eval_summary(session) -> dict
        Return pass/fail counts and failure type breakdown for all graded
        Varkaar results. Ungraded results (pass_fail=None) are excluded.

    print_eval_summary(summary)
        Print a formatted summary report to stdout.

    export_results(session, output_path) -> Path
        Export all EvalResult records (joined to EvalQuestion) to JSON.
        Returns the path written.

See: FR-008, ADR-006, R6 design doc.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import typer
from sqlalchemy.orm import Session

from saskan_lore.analyzer.answering import answer
from saskan_lore.data.models import EvalQuestion, EvalResult

log = logging.getLogger(__name__)

_VALID_FAILURE_TYPES = frozenset({"wrong_fact", "hallucination", "incomplete", "style"})
_SCOPE = "varkaar"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_evaluation(session: Session) -> list[EvalResult]:
    """Run all active Varkaar EvalQuestions through the pipeline.

    Creates one EvalResult per question. pass_fail is None on all records —
    set it with grade_result() after reviewing the answers.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        List of inserted EvalResult ORM objects.
    """
    questions = (
        session.query(EvalQuestion)
        .filter_by(scope=_SCOPE, is_active=True)
        .order_by(EvalQuestion.question_id)
        .all()
    )

    if not questions:
        log.warning("run_evaluation: no active %s questions found.", _SCOPE)
        return []

    records: list[EvalResult] = []
    run_at = datetime.now(tz=timezone.utc)

    for q in questions:
        result = answer(q.question_text, session)
        evidence_json = json.dumps(result.evidence)

        record = EvalResult(
            question_id=q.id,
            model_answer=result.answer or "",
            retrieved_evidence=evidence_json,
            pass_fail=None,
            failure_type=None,
            notes=None,
            run_at=run_at,
        )
        session.add(record)
        session.flush()
        records.append(record)
        log.info(
            "run_evaluation: q=%s result_id=%d answerable=%s evidence=%d",
            q.question_id,
            record.id,
            result.answerable,
            len(result.evidence),
        )

    session.commit()
    return records


def grade_result(
    session: Session,
    result_id: int,
    pass_fail: str,
    failure_type: str | None = None,
    notes: str | None = None,
) -> EvalResult:
    """Set pass_fail (and optionally failure_type/notes) on one EvalResult.

    Args:
        session:      Active SQLAlchemy session.
        result_id:    Primary key of the EvalResult to grade.
        pass_fail:    "pass" or "fail".
        failure_type: Required when pass_fail="fail". One of: wrong_fact,
                      hallucination, incomplete, style.
        notes:        Optional free-text note for failure analysis.

    Returns:
        The updated EvalResult record.

    Raises:
        ValueError: If result_id not found, pass_fail is invalid, or
                    failure_type is provided with an unrecognised value.
    """
    record = session.get(EvalResult, result_id)
    if record is None:
        raise ValueError(f"EvalResult id={result_id} not found.")

    if pass_fail not in {"pass", "fail"}:
        raise ValueError(f"pass_fail must be 'pass' or 'fail', got {pass_fail!r}.")

    if failure_type is not None and failure_type not in _VALID_FAILURE_TYPES:
        raise ValueError(
            f"Invalid failure_type {failure_type!r}. "
            f"Valid values: {sorted(_VALID_FAILURE_TYPES)}"
        )

    record.pass_fail = pass_fail
    record.failure_type = failure_type
    record.notes = notes
    session.commit()
    return record


def eval_summary(session: Session) -> dict:
    """Return pass/fail counts and failure breakdown for graded Varkaar results.

    Only results with pass_fail set (not None) are included. Results linked
    to inactive questions are excluded.

    Returns:
        Dict with keys: total, passed, failed, ungraded,
        failures (dict of failure_type -> count).
    """
    questions = session.query(EvalQuestion).filter_by(scope=_SCOPE, is_active=True).all()
    question_ids = {q.id for q in questions}

    all_results = session.query(EvalResult).filter(EvalResult.question_id.in_(question_ids)).all()

    passed = 0
    failed = 0
    ungraded = 0
    failures: dict[str, int] = {}

    for r in all_results:
        if r.pass_fail is None:
            ungraded += 1
        elif r.pass_fail == "pass":
            passed += 1
        else:
            failed += 1
            key = r.failure_type or "unclassified"
            failures[key] = failures.get(key, 0) + 1

    return {
        "total": len(all_results),
        "passed": passed,
        "failed": failed,
        "ungraded": ungraded,
        "failures": failures,
    }


def print_eval_summary(summary: dict) -> None:
    """Print a formatted evaluation summary report to stdout."""
    total = summary["total"]
    passed = summary["passed"]
    failed = summary["failed"]
    ungraded = summary["ungraded"]
    graded = passed + failed
    pass_pct = round(100 * passed / graded) if graded else 0

    typer.echo("")
    typer.echo("── Evaluation summary — Varkaar domain " + "─" * 17)
    typer.echo(f"  Total questions : {total}")
    typer.echo(f"  Graded          : {graded}")
    typer.echo(f"  Ungraded        : {ungraded}")
    typer.echo(f"  Pass            : {passed}  ({pass_pct}%)")
    typer.echo(f"  Fail            : {failed}")

    if summary["failures"]:
        typer.echo("")
        typer.echo("  Failures by type:")
        for ftype, count in sorted(summary["failures"].items()):
            typer.echo(f"    {ftype:<16}: {count}")

    typer.echo("")


def export_results(session: Session, output_path: Path) -> Path:
    """Export all EvalResult records joined to EvalQuestion to JSON.

    Args:
        session:     Active SQLAlchemy session.
        output_path: Destination file path.

    Returns:
        The path written.
    """
    questions = {q.id: q for q in session.query(EvalQuestion).all()}
    results = session.query(EvalResult).order_by(EvalResult.id).all()

    rows = []
    for r in results:
        q = questions.get(r.question_id)
        rows.append(
            {
                "result_id": r.id,
                "question_id": q.question_id if q else None,
                "question_text": q.question_text if q else None,
                "expected_answer": q.expected_answer if q else None,
                "scope": q.scope if q else None,
                "model_answer": r.model_answer,
                "retrieved_evidence": json.loads(r.retrieved_evidence or "[]"),
                "pass_fail": r.pass_fail,
                "failure_type": r.failure_type,
                "notes": r.notes,
                "run_at": r.run_at.isoformat() if r.run_at else None,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("export_results: wrote %d records to %s", len(rows), output_path)
    return output_path
